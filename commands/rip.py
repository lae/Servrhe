from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessValue
from twisted.protocols.ftp import FTPClient
from twisted.web.client import Agent
from lib.utils import Downloader, getPath
import urllib, os, uuid, shutil

config = {
    "access": "admin",
    "help": ".rip [file name] || .rip [HorribleSubs] Natsuyuki Rendezvous - 11 [720p].mkv || Downloads the file and rips the subs",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    name = " ".join(msg)
    url = "http://host.horriblesubs.info/hsddl/{}".format(urllib.quote(name))

    if name[:-4] != ".mkv":
        self.msg(channel, "Can only rip MKVs")
        return

    response = yield Agent(reactor).request("GET", url, None, None)
    if response.code != 200:
        self.msg(channel, "{} returned non-successful HTTP code".format(url))
        return

    guid = uuid.uuid4().hex
    while os.path.exists(guid):
        guid = uuid.uuid4().hex
    os.mkdir(guid)

    d = Deferred()
    dl = Downloader("{}/{}".format(guid, name), d)
    response.deliverBody(dl)
    yield d
    dl.done()
    self.notice(user, "{} downloaded".format(name))

    dest = name[:-3] + "ass"
    exitCode = yield getProcessValue(getPath("mkvextract"), args=["tracks","{}/{}".format(guid, name),"3:{}/{}".format(guid, dest)], env=os.environ)
    if exitCode == 0:
        self.notice(user, "{} extracted".format(dest))
        ftp = yield ClientCreator(reactor, FTPClient, self.factory.config.ftp_user, self.factory.config.ftp_pass).connectTCP(self.factory.config.ftp_host, self.factory.config.ftp_port)
        store, finish = ftp.storeFile("./{}/{}".format(self.factory.config.ftp_encode_dir, dest))
        sender = yield store
        with open("{}/{}".format(guid, dest), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish
        self.notice(user, "{} uploaded".format(dest))
    else:
        self.msg(channel, "Failed to extract subs for {}".format(name))

    shutil.rmtree(guid, True)
