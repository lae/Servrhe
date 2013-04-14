from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessValue
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from twisted.web.client import Agent, CookieAgent, FileBodyProducer
from twisted.web.http_headers import Headers
from twisted.web.xmlrpc import Proxy
from StringIO import StringIO
from lib.multipart import MultiPartProducer
from lib.torrent import makeTorrent
from lib.utils import Downloader, cache, getPath, returnBody
import uuid, os, fnmatch, shutil, binascii, cookielib, re, urllib

config = {
    "access": "admin",
    "help": ".release [filter] [show name] || .release premux Accel World || Release the show where the FTP file contains the filter",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if len(msg) < 2:
        self.msg(channel, "Need a filter and a showname")
        return
    name_filter = msg[0]
    show = self.factory.resolve(" ".join(msg[1:]), channel)
    if show is None:
        return
    if not show["folder"]:
        self.msg(channel, "No FTP folder given for {}".format(show["series"]))
        return
    if not show["xdcc_folder"]:
        self.msg(channel, "No XDCC folder given for {}".format(show["series"]))
        return
    episode = show["current_ep"] + 1
    guid = uuid.uuid4().hex
    while os.path.exists(guid):
        guid = uuid.uuid4().hex
    os.mkdir(guid)
    self.msg(channel, "Fugiman: {} has initiated a release for {} {:d}. UUID is {}. Thought you ought to know.".format(user, show["series"], episode, guid))

    # Step 1: Search FTP for complete episode, or premux + xdelta
    ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
    ftp.changeDirectory("/{}/{:02d}/".format(show["folder"], episode))
    filelist = FTPFileListProtocol()
    yield ftp.list(".", filelist)
    files = [x["filename"] for x in filelist.files if x["filetype"] != "d"]
    complete = fnmatch.filter(files, "[[]Commie[]]*{}*.mkv".format(name_filter))
    xdelta = fnmatch.filter(files, "*{}*.xdelta".format(name_filter))
    premux = fnmatch.filter(files, "*{}*.mkv".format(name_filter))

    if complete:
        # Step 1a: Download completed file
        if len(complete) > 1:
            self.msg(channel, "Too many completed files match the filter: {}".format(", ".join(complete)))
            return
        else:
            complete = complete[0]
        self.notice(user, "Found complete file: {}".format(complete))
        complete_len = [x["size"] for x in filelist.files if x["filename"] == complete][0]
        complete_downloader = Downloader("{}/{}".format(guid, complete))
        yield ftp.retrieveFile(complete, complete_downloader)
        if complete_downloader.done() != complete_len:
            self.msg(channel, "Aborted releasing {}: Download of complete file had incorrect size.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return

    elif xdelta and premux:
        # Step 1b: Download premux + xdelta, merge into completed file
        if len(premux) > 1:
            self.msg(channel, "Too many premux files match the filter: {}".format(", ".join(premux)))
            return
        else:
            premux = premux[0]
        if len(xdelta) > 1:
            self.msg(channel, "Too many xdelta files match the filter: {}".format(", ".join(xdelta)))
            return
        else:
            xdelta = xdelta[0]
        self.notice(user, "Found xdelta and premux: {} and {}".format(xdelta, premux))

        if not os.path.isfile("{}/{}".format(self.factory.config.premux_dir, premux)):
            premux_len = [x["size"] for x in filelist.files if x["filename"] == premux][0]
            success = yield cache(self, user, ftp, premux, premux_len)
            if not success:
                self.msg(channel, "Aborted releasing {}: Download of premux file had incorrect size.".format(show["series"]))
                yield ftp.quit()
                ftp.fail(None)
                return
        shutil.copyfile("{}/{}".format(self.factory.config.premux_dir, premux), "{}/{}".format(guid, premux))
        xdelta_len = [x["size"] for x in filelist.files if x["filename"] == xdelta][0]
        xdelta_downloader = Downloader("{}/{}".format(guid, xdelta))
        yield ftp.retrieveFile(xdelta, xdelta_downloader)
        if xdelta_downloader.done() != xdelta_len:
            self.msg(channel, "Aborted releasing {}: Download of xdelta file had incorrect size.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return
        code = yield getProcessValue(getPath("xdelta3"), args=["-f","-d","{}/{}".format(guid, xdelta)], env=os.environ)
        if code != 0:
            self.msg(channel, "Aborted releasing {}: Couldn't merge premux and xdelta.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return
        self.notice(user, "Merged premux and xdelta")
        complete = fnmatch.filter(os.listdir(guid), "[[]Commie[]]*.mkv")
        if not complete:
            self.msg(channel, "No completed file found")
            return
        elif len(complete) > 1:
            self.msg(channel, "Too many completed files found after merging: {}".format(", ".join(complete)))
            return
        else:
            complete = complete[0]
        if not complete:
            self.msg(channel, "Aborted releasing {}: Couldn't find completed file after merging.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return
    else:
        self.msg(channel, "Aborted releasing {}: Couldn't find completed episode.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    yield ftp.quit()
    ftp.fail(None)
    # Step 1c: Verify CRC
    crc = complete[-13:-5] # Extract CRC from filename
    try:
        with open("{}/{}".format(guid, complete), "rb") as f:
            calc = "{:08X}".format(binascii.crc32(f.read()) & 0xFFFFFFFF)
    except:
        self.msg(channel, "Aborted releasing {}: Couldn't open completed file for CRC verification.".format(show["series"]))
        return
    if crc != calc:
        self.msg(channel, "Aborted releasing {}: CRC failed verification. Filename = '{}', Calculated = '{}'.".format(show["series"], crc, calc))
        return

    # Step 2: Create torrent
    try:
        torrent = makeTorrent(complete, guid)
    except Exception, e:
        self.msg(channel, "Aborted releasing {}: Couldn't create torrent.".format(show["series"]))
        return
    self.notice(user, "Created torrent")

    # Step 3: Upload episode to XDCC server
    try:
        ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.xdcc_user, self.factory.config.xdcc_pass).connectTCP(self.factory.config.xdcc_host, self.factory.config.xdcc_port)
        store, finish = ftp.storeFile("./{}/{}/{}".format(self.factory.config.xdcc_folder, show["xdcc_folder"], complete))
        sender = yield store
        with open("{}/{}".format(guid, complete), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish
    except:
        self.msg(channel, "Aborted releasing {}: Couldn't upload completed episode to XDCC server.".format(show["series"]))
        return
    self.notice(user, "Uploaded to XDCC")

    # Step 4: Upload episode to seedbox
    try:
        ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.seed_user, self.factory.config.seed_pass).connectTCP(self.factory.config.seed_host, self.factory.config.seed_port)
        store, finish = ftp.storeFile("./{}/{}".format(self.factory.config.seed_file_folder, complete))
        sender = yield store
        with open("{}/{}".format(guid, complete), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish
    except:
        self.msg(channel, "Aborted releasing {}: Couldn't upload completed episode to seedbox.".format(show["series"]))
        return
    self.notice(user, "Uploaded to seedbox")

    # Step 5: Upload torrent to Nyaa
    nyaagent = CookieAgent(Agent(reactor), cookielib.CookieJar())
    response = yield nyaagent.request("POST","http://www.nyaa.eu/?page=login",
        Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
        FileBodyProducer(StringIO(urllib.urlencode({"loginusername": self.factory.config.nyaa_user,"loginpassword": self.factory.config.nyaa_pass}))))
    body = yield returnBody(response)
    if "Login successful" not in body:
        self.msg(channel, "Aborted releasing {}: Couldn't login to Nyaa.".format(show["series"]))
        return
    response = yield nyaagent.request("POST","http://www.nyaa.eu/?page=upload",
        Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
        MultiPartProducer({"torrent": "{}/{}".format(guid, torrent)},{
            "name": complete,
            "catid": "1_37",
            "info": "#commie-subs@irc.rizon.net",
            "description": "Visit us at [url]http://commiesubs.com[/url] for the latest updates and news.\nFollow at [url]https://twitter.com/RHExcelion[/url].",
            "remake": 0,
            "anonymous": 0,
            "hidden": 1,
            "rules": 1,
            "submit": "Upload"
        }))
    if response.code != 200:
        nyaa_codes = {
            418: "I'm a teapot (You're doing it wrong)",
            460: "Missing Announce URL",
            461: "Already Exists",
            462: "Invalid File",
            463: "Missing Data",
            520: "Configuration Broken"
        }
        self.msg(channel, "Aborted releasing {}: Couldn't upload torrent to Nyaa. Error #{:d}: {}".format(show["series"], response.code, nyaa_codes[response.code]))
        return
    self.notice(user, "Uploaded to Nyaa")

    # Step 6: Get torrent link from Nyaa
    body = yield returnBody(response)
    match = re.search("http://www.nyaa.eu/\?page=view&#38;tid=[0-9]+", body)
    if not match:
        self.msg(channel, "Aborted releasing {}: Couldn't find torrent link in Nyaa's response.".format(show["series"]))
        return
    info_link = match.group(0).replace("&#38;","&")
    download_link = info_link.replace("view","download")
    self.notice(user, "Got Nyaa torrent link")

    # Step 7: Upload torrent link to TT
    ttagent = CookieAgent(Agent(reactor), cookielib.CookieJar())
    response = yield ttagent.request("POST","http://tokyotosho.info/login.php",
        Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
        FileBodyProducer(StringIO(urllib.urlencode({"username": self.factory.config.tt_user,"password": self.factory.config.tt_pass,"submit": "Submit"}))))
    body = yield returnBody(response)
    if "Logged in." not in body:
        self.msg(channel, "Couldn't login to TT. Continuing to release {} regardless.".format(show["series"]))
    else:
        response = yield ttagent.request("POST","http://tokyotosho.info/new.php",
            Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
            FileBodyProducer(StringIO(urllib.urlencode({
                "type": 1,
                "url": download_link,
                "comment": "#commie-subs@irc.rizon.net",
                "website": "http://www.commiesubs.com/",
            }))))
        body = yield returnBody(response)
        if "Torrent Submitted" not in body:
            self.msg(channel, "Couldn't upload torrent to TT. Continuing to release {} regardless.".format(show["series"]))
        else:
            self.notice(user, "Uploaded to TT")

    # Step 8: Create blog post
    blog = Proxy("http://commiesubs.com/xmlrpc.php")
    try:
        yield blog.callRemote("wp.newPost",
            0, # Blog ID
            self.factory.config.blog_user, # Username
            self.factory.config.blog_pass, # Password
            { # Content
                "post_type": "post",
                "post_status": "published",
                "post_title": show["series"] + " " + episode,
                "post_content": "<a href=\"{}\">Torrent</a>".format(info_link),
                "terms_names": {"category": ["The Bread Lines", show["blog_link"].split("/")[-2].replace("-"," ")]}
            }
        )
        self.notice(user, "Created blog post")
    except:
        self.msg(channel, "Couldn't create blog post. Continuing to release {} regardless.".format(show["series"]))

    # Step 9: Start seeding torrent
    try:
        ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.seed_user, self.factory.config.seed_pass).connectTCP(self.factory.config.seed_host, self.factory.config.seed_port)
        store, finish = ftp.storeFile("./{}/{}".format(self.factory.config.seed_torrent_folder, torrent))
        sender = yield store
        with open("{}/{}".format(guid, torrent), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish
        self.notice(user, "Seeding started")
    except:
        self.msg(channel, "Couldn't start seeding the torrent. Continuing to release {} regardless.".format(show["series"]))
    self.msg(channel, "%s is released." % show["series"])

    # Step 10: Mark show finished on showtimes
    data = yield self.factory.load("show","update", data={"id":show["id"],"method":"next_episode"})
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    self.msg(channel, "%s is marked as completed for the week" % show["series"])

    # Step 11: Update the topic
    self.factory.update_topic()

    # Step 12: Clean up
    shutil.rmtree(guid, True)
