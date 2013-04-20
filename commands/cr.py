from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessOutputAndValue
from twisted.protocols.ftp import FTPClient
from twisted.web.client import Agent, CookieAgent, FileBodyProducer
from twisted.web.http_headers import Headers

from lib.crunchy import Decoder, player_revision, qualities, xml_url, swf_url
from lib.flv import FLVFile
from lib.utils import getPath, returnBody

from StringIO import StringIO
from bs4 import BeautifulSoup

import os, uuid, urllib, cookielib, shutil, codecs

config = {
    "access": "admin",
    "help": ".cr [contents] [quality] [episode URL] || .cr both 1080 http://crunchyroll.com/shit-anime-season-two/ep11 || Rips video and/or subs from CR",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if len(msg) < 3:
        self.msg(channel, "Requires contents (subs, video or both), a quality (360, 480, 720 or 1080), and a URL")
        return

    # Step 1: Download the XML meta-data
    content, quality, video_page = msg[0], msg[1], " ".join(msg[2:])
    guid = uuid.uuid4().hex
    while os.path.exists(guid):
        guid = uuid.uuid4().hex
    os.mkdir(guid)

    if content not in ("subs", "video", "both"):
        self.msg(channel, "Invalid content, must be one of: subs, video, both")
    if quality not in qual:
        self.msg(channel, "Invalid quality, must be one of: {}".format(", ".join(qual.keys())))
        return

    stream = {}
    format = qualities[quality]
    vid_id = video_page.split("-")[-1]
    upload_subs = content in ("subs", "both")
    upload_video = content in ("video", "both")

    url = 'https://www.crunchyroll.com/?a=formhandler'
    playlist = xml_url.format(vid_id, format[0], format[1])
    headers = Headers({
        'Content-Type': ['application/x-www-form-urlencoded'],
        'Referer': ['https://www.crunchyroll.com'],
        'User-Agent': ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:17.0) Gecko/17.0 Firefox/17.0']
    })
    login_data = FileBodyProducer(StringIO(urllib.urlencode({
        'formname': 'RpcApiUser_Login',
        'next_url': '',
        'fail_url': '/login',
        'name': self.factory.config.cr_user,
        'password': self.factory.config.cr_pass
    })))
    video_data = FileBodyProducer(StringIO(urllib.urlencode({
        'current_page': video_page
    })))

    self.notice(user, "Logging in to Crunchyroll")
    agent = CookieAgent(Agent(reactor), cookielib.CookieJar())
    response = yield agent.request("POST", url, headers, login_data)
    response = yield agent.request("POST", playlist, headers, video_data)
    xmlSource = yield returnBody(response)

    # Step 2: Parse the XML
    self.notice(user, "Parsing response")
    soup = BeautifulSoup(xmlSource)
    player_url = soup.find('default:chromelessplayerurl').string
    stream_info = soup.find('stream_info')
    showinfo = soup.find('media_metadata')
    vidinfo = soup.find('metadata')
    subtitles = soup.find('subtitles')

    if not stream_info:
        self.msg(channel, "Failed to rip {}".format(video_page))
        return

    if showinfo:
        filename = "{0} - {1:02d} [{2}p] [CR]".format(showinfo.series_title.string, int(showinfo.episode_number.string), vidinfo.height.string)
    else:
        filename = vid_id

    stream['url'] = stream_info.host.string
    stream['token'] = stream_info.token.string
    stream['file'] = stream_info.file.string
    stream['swf_url'] = swf_url+player_revision+"/"+player_url

    # Step 3: Extract the subs
    if upload_subs:
        if not subtitles:
            self.msg(channel, "Couldn't find subtitles for {}".format(video_page))
            return
        self.notice(user, "Extracting subtitles")
        formattedSubs = Decoder(xmlSource).fancy
        with open(os.path.join(guid, filename + ".ass"), 'wb') as subfile:
            subfile.write(codecs.BOM_UTF8)
            subfile.write(formattedSubs.encode('utf-8'))

    # Step 4: Download the FLV and re-mux to MKV
    if upload_video:
        self.notice(user, "Downloading video")
        rtmpargs = ["-e", "-r", stream['url'], "-y", stream['file'], "-W", stream['swf_url'], "-T", stream['token'], "-o", os.path.join(guid, filename + '.flv')]
        mkvmergeargs = ["-o", os.path.join(guid, filename+".mkv"),
            "--forced-track","0:yes","--compression","0:none","--timecodes","0:"+os.path.join(guid, filename+".txt"),"-d","0","-A","-S",os.path.join(guid, filename+".264"),
            "--forced-track","0:yes","-a","0","-D","-S",os.path.join(guid, filename + ".aac")]

        retries = 15
        out, err, code = yield getProcessOutputAndValue(getPath("rtmpdump"), args=rtmpargs, env=os.environ)
        while code == 2 and retries:
            retries -= 1
            self.notice(user, "rtmpdump failed in a resumable way, trying again. ({:d} retries left)".format(retries))
            out, err, code = yield getProcessOutputAndValue(getPath("rtmpdump"), args=rtmpargs, env=os.environ)
        if code != 0:
            self.msg(channel, "Failed to download FLV for {}".format(video_page))
            print "CODE: {:d}\nOUT: {}\nERR: {}\n".format(code, out, err)
            return

        self.notice(user, "Remuxing video")
        try:
            FLVFile(os.path.join(guid, filename + ".flv")).ExtractStreams(True, True, True, True)
        except:
            self.msg(channel, "Failed to extract video and audio streams for {}".format(video_page))
            raise

        out, err, code = yield getProcessOutputAndValue(getPath("mkvmerge"), args=mkvmergeargs, env=os.environ)
        if code == 2:
            self.msg(channel, "Failed to mux MKV for {}".format(video_page))
            print "CODE: {:d}\nOUT: {}\nERR: {}\n".format(code, out, err)
            return

    # Step 5: Upload it
    self.notice(user, "Uploading files")
    ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
    ftp.changeDirectory(self.factory.config.ftp_encode_dir)

    if upload_subs:
        store, finish = ftp.storeFile(filename+".ass")
        sender = yield store
        with open("{}/{}.ass".format(guid, filename), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish

    if upload_video:
        store, finish = ftp.storeFile(filename+".mkv")
        sender = yield store
        with open("{}/{}.mkv".format(guid, filename), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish

    # Step 6: Clean up
    self.msg(channel, "Finished ripping {}".format(video_page))
    yield ftp.quit()
    ftp.fail(None)
    shutil.rmtree(guid, True)