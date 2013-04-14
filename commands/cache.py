from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from lib.utils import cache
import fnmatch

config = {
    "access": "admin",
    "help": ".cache [filter] [showname] || .cache premux eotena || Caches the premux for a show so that .chapters, .xdelta and .release work faster",
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

    ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
    ftp.changeDirectory("/{}/{:02d}/".format(show["folder"], episode))
    filelist = FTPFileListProtocol()
    yield ftp.list(".", filelist)
    files = [x["filename"] for x in filelist.files if x["filetype"] != "d"]
    premux = fnmatch.filter(files, "*{}*.mkv".format(name_filter))

    if not premux:
        self.msg(channel, "No premux found")
        return
    elif len(premux) > 1:
        self.msg(channel, "Too many premux files match the filter: {}".format(", ".join(premux)))
        return
    else:
        premux = premux[0]
    premux_len = [x["size"] for x in filelist.files if x["filename"] == premux][0]

    success = yield cache(self, user, ftp, premux, premux_len)

    if success:
        self.msg(channel, "{} cached.".format(premux))
    else:
        self.msg(channel, "Caching of {} failed.".format(premux))

    yield ftp.quit()
    ftp.fail(None)
