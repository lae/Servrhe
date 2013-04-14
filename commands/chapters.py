from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessOutput
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from lib.chapters import ChapterMaker
from lib.subparser import SubParser, timeToInt
from lib.utils import cache, Downloader, getPath
from xml.etree import ElementTree
import uuid, fnmatch, os, shutil

config = {
    "access": "admin",
    "help": ".chapters [filter] [show name] || .chapters premux eotena || Creates chapters for the premux and ass matching the filter for the show",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if len(msg) < 2:
        self.msg(channel, "Need a filter and show name")
        return
    name_filter, show = msg[0], " ".join(msg[1:])

    show = self.factory.resolve(show, channel)
    if show is None:
        return
    if not show["folder"]:
        self.msg(channel, "No FTP folder given for {}".format(show["series"]))
        return
    episode = show["current_ep"] + 1
    guid = uuid.uuid4().hex
    while os.path.exists(guid):
        guid = uuid.uuid4().hex
    os.mkdir(guid)

    # Step 1: Search FTP for premux + script
    ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
    ftp.changeDirectory("/{}/{:02d}/".format(show["folder"], episode))
    filelist = FTPFileListProtocol()
    yield ftp.list(".", filelist)
    files = [x["filename"] for x in filelist.files if x["filetype"] != "d"]
    premux = fnmatch.filter(files, "*{}*.mkv".format(name_filter))
    script = fnmatch.filter(files, "*{}*.ass".format(name_filter))

    if not premux:
        self.msg(channel, "No premux found")
        return
    elif len(premux) > 1:
        self.msg(channel, "Too many premux files match the filter: {}".format(", ".join(premux)))
        return
    else:
        premux = premux[0]
    if not script:
        self.msg(channel, "No script found")
        return
    elif len(script) > 1:
        self.msg(channel, "Too many script files match the filter: {}".format(", ".join(script)))
        return
    else:
        script = script[0]

    # Step 2: Download that shit
    if not os.path.isfile("{}/{}".format(self.factory.config.premux_dir, premux)):
        premux_len = [x["size"] for x in filelist.files if x["filename"] == premux][0]
        success = yield cache(self, user, ftp, premux, premux_len)
        if not success:
            self.msg(channel, "Aborted creating chapters for {}: Download of premux file had incorrect size.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return
    shutil.copyfile("{}/{}".format(self.factory.config.premux_dir, premux), "{}/{}".format(guid, premux))
    script_len = [x["size"] for x in filelist.files if x["filename"] == script][0]
    script_downloader = Downloader("{}/{}".format(guid, script))
    yield ftp.retrieveFile(script, script_downloader)
    if script_downloader.done() != script_len:
        self.msg(channel, "Aborted creating chapters for {}: Download of script file had incorrect size.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return

    # Step 3: Make the damn chapters
    subs = SubParser("{}/{}".format(guid, script))
    chapters = ChapterMaker()

    try:
        data = getProcessOutput(getPath("mkvextract"), args=["chapters","{}/{}".format(guid, premux)], env=os.environ)
    except:
        self.notice(user, "Failed to load chapters from video file.")
    if data:
        tree = ElementTree.fromstring(data)
        for chapter in tree.iter("ChapterAtom"):
            title = chapter.find("ChapterDisplay").find("ChapterString").text
            time = timeToInt(chapter.find("ChapterTimeStart").text)
            chapters.add({title: time})
    
    new_chapters = {"Intro": 33}
    for keyword in subs.keywords:
        word = keyword["keyword"].lower()
        if word == "op":
            new_chapters["OP"] = keyword["time"]
            new_chapters["Part A"] = keyword["time"] + 90000
        elif word == "ed":
            new_chapters["ED"] = keyword["time"]
        elif word == "part a":
            new_chapters["Part A"] = keyword["time"]
        elif word == "eyecatch" or word == "part b":
            new_chapters["Part B"] = keyword["time"]
        elif word == "preview":
            new_chapters["Preview"] = keyword["time"]
    chapters.add(new_chapters)
    if "OP" in chapters.chapters and chapters.chapters["OP"] <= chapters.chapters["Intro"]:
        del chapters.chapters["Intro"]

    # Step 4: Upload
    store, finish = ftp.storeFile("{}".format(script.replace(".ass", ".xml")))
    sender = yield store
    sender.transport.write(str(chapters))
    sender.finish()
    yield finish
    self.msg(channel, "Chapters for {} uploaded".format(show["series"]))

    # Step 5: Clean up
    yield ftp.quit()
    ftp.fail(None)
    shutil.rmtree(guid, True)
