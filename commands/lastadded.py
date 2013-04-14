from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
import time, re

config = {
    "access": "admin",
    "help": ".lastadded || .lastadded || Lists the last 5 files added to new encodes",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
    ftp.changeDirectory("/{}/".format(self.factory.config.ftp_encode_dir))
    filelist = FTPFileListProtocol()
    yield ftp.list(".", filelist)
    files = [(x["filename"].decode("utf-8"), time.strptime(x["date"], "%b %d %H:%M")) for x in filelist.files if x["filetype"] != "d" and re.match("\w{3} \d{2} \d{2}:\d{2}", x["date"])]
    s_files = [s[0] for s in sorted(files, key=lambda f: f[1], reverse=True)]
    self.msg(channel, u"The last five files added are: {}".format(", ".join(s_files[:5])))
