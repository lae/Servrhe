from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessValue
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from lib.utils import cache, getPath, Downloader
import uuid, os, fnmatch, shutil, binascii

config = {
    "access": "admin",
    "help": ".xdelta [filter] [show name] || .xdelta premux eotena || Creates an xdelta for the premux and ass matching the filter for the show",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if len(msg) < 2:
        self.msg(channel, "Need a filter and show name")
        return
    name_filter, show, fname = msg[0], " ".join(msg[1:]), "test.mkv"

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
    chapters = fnmatch.filter(files, "*{}*.xml".format(name_filter))

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
    if not chapters:
        self.msg(channel, "No chapters found")
        return
    elif len(chapters) > 1:
        self.msg(channel, "Too many chapter files match the filter: {}".format(", ".join(chapters)))
        return
    else:
        chapters = chapters[0]

    # Step 2: Download that shit
    if not os.path.isfile("{}/{}".format(self.factory.config.premux_dir, premux)):
        premux_len = [x["size"] for x in filelist.files if x["filename"] == premux][0]
        success = yield cache(self, user, ftp, premux, premux_len)
        if not success:
            self.msg(channel, "Aborted creating xdelta for {}: Download of premux file had incorrect size.".format(show["series"]))
            yield ftp.quit()
            ftp.fail(None)
            return
    shutil.copyfile("{}/{}".format(self.factory.premux_dir, premux), "{}/{}".format(guid, premux))
    script_len = [x["size"] for x in filelist.files if x["filename"] == script][0]
    script_downloader = Downloader("{}/{}".format(guid, script))
    yield ftp.retrieveFile(script, script_downloader)
    if script_downloader.done() != script_len:
        self.msg(channel, "Aborted creating xdelta for {}: Download of script file had incorrect size.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    chapters_len = [x["size"] for x in filelist.files if x["filename"] == chapters][0]
    chapters_downloader = Downloader("{}/{}".format(guid, chapters))
    yield ftp.retrieveFile(chapters, chapters_downloader)
    if chapters_downloader.done() != chapters_len:
        self.msg(channel, "Aborted creating xdelta for {}: Download of chapter file had incorrect size.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    self.notice(user, "Found premux, script and chapters: {}, {} and {}".format(premux, script, chapters))

    # Step 3: Download fonts
    filelist = FTPFileListProtocol()
    yield ftp.list("fonts", filelist)
    files = [x["filename"] for x in filelist.files if x["filetype"] != "d"]
    fonts = []
    for font in files:
        font_len = [x["size"] for x in filelist.files if x["filename"] == font][0]
        font_downloader = Downloader("{}/{}".format(guid, font))
        yield ftp.retrieveFile("fonts/{}".format(font), font_downloader)
        if font_downloader.done() != font_len:
            self.notice(user, "Failed to download font: {}. Proceeding without it.".format(font))
        else:
            fonts.append(font)
    self.notice(user, "Fonts downloaded. ({})".format(", ".join(fonts)))

    # Step 4: MKVMerge
    arguments = ["-o", "{}/{}".format(guid, fname), "--no-chapters", "--chapters", "{}/{}".format(guid, chapters)]
    for font in fonts:
        arguments.extend(["--attachment-mime-type", "application/x-truetype-font", "--attach-file", "{}/{}".format(guid, font)])
    arguments.extend(["{}/{}".format(guid, premux), "{}/{}".format(guid, script)])
    code = yield getProcessValue(getPath("mkvmerge"), args=arguments, env=os.environ)
    if code != 0:
        self.msg(channel, "Aborted creating xdelta for {}: Couldn't merge premux and script.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    self.notice(user, "Merged premux and script")

    # Step 5: Determine filename
    match = re.search("(v\d+).ass", script)
    version = match.group(1) if match is not None else ""
    try:
        with open("{}/{}".format(guid, fname), "rb") as f:
            crc = "{:08X}".format(binascii.crc32(f.read()) & 0xFFFFFFFF)
    except:
        self.msg(channel, "Aborted creating xdelta for {}: Couldn't open completed file for CRC verification.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    nfname = "[Commie] {} - {:02d}{} [{}].mkv".format(show["series"], episode, version, crc)
    os.rename("{}/{}".format(guid, fname), "{}/{}".format(guid, nfname))
    fname = nfname
    self.notice(user, "Determined final filename to be {}".format(fname))

    # Step 5: Make that xdelta
    xdelta = script.replace(".ass",".xdelta")
    code = yield getProcessValue(getPath("xdelta3"), args=["-f","-e","-s","{}/{}".format(guid, premux),"{}/{}".format(guid, fname),"{}/{}".format(guid, xdelta)], env=os.environ)
    if code != 0:
        self.msg(channel, "Aborted creating xdelta for {}: Couldn't create xdelta.".format(show["series"]))
        yield ftp.quit()
        ftp.fail(None)
        return
    self.notice(user, "Made xdelta")

    # Step 6: Upload that xdelta
    store, finish = ftp.storeFile("{}".format(xdelta))
    sender = yield store
    with open("{}/{}".format(guid, xdelta), "rb") as f:
        sender.transport.write(f.read())
    sender.finish()
    yield finish
    self.msg(channel, "xdelta for {} uploaded".format(show["series"]))

    # Step 7: Clean up
    yield ftp.quit()
    ftp.fail(None)
    shutil.rmtree(guid, True)
