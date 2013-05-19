# -*- coding: utf-8 -*-
from twisted.internet import reactor, protocol
from twisted.internet.defer import DeferredList, inlineCallbacks, returnValue
from twisted.internet.protocol import ClientCreator
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from datetime import datetime as dt
import fnmatch, os, shutil

dependencies = ["config", "commands"]

def parseDate(date):
    if "  " in date:
        d = dt.strptime(date, "%b %d  %Y")
    else:
        d = dt.strptime(date, "%b %d %H:%M")
    return d

class Downloader(protocol.Protocol):
    def __init__(self, name, deferred = None, limit = None):
        self.file = open(name, "wb")
        self.len = 0
        self.deferred = deferred
        self.limit = limit
        self.connected = True

    def dataReceived(self, data):
        if not self.connected:
            return

        added = len(data)
        if self.limit is not None and self.len + added > self.limit:
            added = self.limit - self.len
            data = data[:added]

        self.len += added
        self.file.write(data)

        if self.limit is not None and self.len >= self.limit:
            self.connected = False
            self.transport.loseConnection()

    def connectionLost(self, reason):
        self.file.close()
        if self.deferred is not None:
            self.deferred.callback(self.len)

class Module(object):
    split = 8
    max = 8

    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("ftp")
        self.connections = 0
        self.caching = []

    def stop(self):
        pass

    @inlineCallbacks
    def acquireConnection(self):
        exception = self.master.modules["commands"].exception

        if self.connections >= self.max:
            raise exception(u"No FTP connections available. Please wait and try again.")

        self.connections += 1

        user = yield self.config.get("ftpuser")
        passwd = yield self.config.get("ftppass")
        host = yield self.config.get("ftphost")
        port = yield self.config.get("ftpport")

        if user is None or passwd is None or host is None or port is None:
            self.connections -= 1
            raise exception(u"No FTP user, pass, host or port in config")

        ftp = yield ClientCreator(reactor, FTPClient, user.encode("utf8"), passwd.encode("utf8")).connectTCP(host, int(port))
        returnValue(ftp)

    @inlineCallbacks
    def releaseConnection(self, ftp):
        yield ftp.quit()
        ftp.fail(None)
        self.connections -= 1

    @inlineCallbacks
    def isCached(self, filename):
        premux_dir = yield self.config.get("premuxdir", "premuxes")
        returnValue(os.path.isfile(os.path.join(premux_dir, filename)))

    @inlineCallbacks
    def get(self, folder, filename, destination):
        exception = self.master.modules["commands"].exception

        ftp = yield self.acquireConnection()

        try:
            yield ftp.changeDirectory(folder.encode("utf8"))

            filelist = FTPFileListProtocol()
            yield ftp.list(".", filelist)
            sizes = [x["size"] for x in filelist.files if x["filename"] == filename]
            if not sizes or len(sizes) > 1:
                raise exception(u"Couldn't find file in FTP")

            length = sizes[0]

            downloader = Downloader(os.path.join(destination, filename))
            yield ftp.retrieveFile(filename.encode("utf8"), downloader)

        finally:
            yield self.releaseConnection(ftp)

        if length != downloader.len:
            os.remove(os.path.join(destination, filename))
            raise exception(u"Downloaded file was not the proper size. Got {:,d} instead of {:,d}".format(downloader.len, length))

    @inlineCallbacks
    def getFromCache(self, folder, filename, destination):
        cached = yield self.isCached(filename)
        if not cached:
            yield self.cache(folder, filename)

        premux_dir = yield self.config.get("premuxdir", "premuxes")
        shutil.copyfile(os.path.join(premux_dir, filename), os.path.join(destination, filename))

    @inlineCallbacks
    def getLatest(self, folder, filter):
        exception = self.master.modules["commands"].exception

        ftp = yield self.acquireConnection()

        try:
            yield ftp.changeDirectory(folder.encode("utf8"))

            filelist = FTPFileListProtocol()
            yield ftp.list(".", filelist)

        finally:
            yield self.releaseConnection(ftp)

        files =  fnmatch.filter([x["filename"] for x in filelist.files if x["filetype"] != "d"], filter)
        if not files:
            raise exception(u"No files in FTP match given {}".format(filter))

        files = [(x["filename"], parseDate(x["date"])) for x in filelist.files if x["filename"] in files]
        files.sort(key=lambda x: x[1], reverse=True)
        returnValue(files[0][0])

    @inlineCallbacks
    def put(self, folder, filename, destination = None):
        exception = self.master.modules["commands"].exception
        if destination is None:
            destination = yield self.config.get("ftpdefaultdir")
        if destination is None:
            raise exception(u"No FTP default directory in config")

        ftp = yield self.acquireConnection()

        try:
            yield ftp.changeDirectory(destination.encode("utf8"))

            store, finish = ftp.storeFile(filename.encode("utf8"))
            sender = yield store
            with open(os.path.join(folder, filename), "rb") as f:
                sender.transport.write(f.read())
            sender.finish()
            yield finish

        finally:
            yield self.releaseConnection(ftp)

    @inlineCallbacks
    def putXDCC(self, folder, filename, destination):
        exception = self.master.modules["commands"].exception

        user = yield self.config.get("xdccuser")
        passwd = yield self.config.get("xdccpass")
        host = yield self.config.get("xdcchost")
        port = yield self.config.get("xdccport")
        root = yield self.config.get("xdccfolder")

        if user is None or passwd is None or host is None or port is None or root is None:
            raise exception(u"No XDCC FTP user, pass, host, port or folder in config")

        ftp = yield ClientCreator(reactor, FTPClient, user.encode("utf8"), passwd.encode("utf8")).connectTCP(host, int(port))
        yield ftp.changeDirectory(root.encode("utf8"))
        yield ftp.changeDirectory(destination.encode("utf8"))

        store, finish = ftp.storeFile(filename.encode("utf8"))
        sender = yield store
        with open(os.path.join(folder, filename), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish

        yield ftp.quit()
        ftp.fail(None)

    @inlineCallbacks
    def putSeedbox(self, folder, filename):
        exception = self.master.modules["commands"].exception
        destination = yield self.config.get("seedmkvfolder")
        if destination is None:
            raise exception(u"No Seedbox MKV folder in config")

        user = yield self.config.get("seeduser")
        passwd = yield self.config.get("seedpass")
        host = yield self.config.get("seedhost")
        port = yield self.config.get("seedport")

        if user is None or passwd is None or host is None or port is None:
            raise exception(u"No Seedbox FTP user, pass, host or port in config")

        ftp = yield ClientCreator(reactor, FTPClient, user.encode("utf8"), passwd.encode("utf8")).connectTCP(host, int(port))
        yield ftp.changeDirectory(destination.encode("utf8"))

        store, finish = ftp.storeFile(filename.encode("utf8"))
        sender = yield store
        with open(os.path.join(folder, filename), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish

        yield ftp.quit()
        ftp.fail(None)

    @inlineCallbacks
    def putTorrent(self, folder, filename):
        exception = self.master.modules["commands"].exception
        destination = yield self.config.get("seedtorrentfolder")
        if destination is None:
            raise exception(u"No Seedbox torrent folder in config")

        user = yield self.config.get("seeduser")
        passwd = yield self.config.get("seedpass")
        host = yield self.config.get("seedhost")
        port = yield self.config.get("seedport")

        if user is None or passwd is None or host is None or port is None:
            raise exception(u"No Seedbox FTP user, pass, host or port in config")

        ftp = yield ClientCreator(reactor, FTPClient, user.encode("utf8"), passwd.encode("utf8")).connectTCP(host, int(port))
        yield ftp.changeDirectory(destination.encode("utf8"))

        store, finish = ftp.storeFile(filename.encode("utf8"))
        sender = yield store
        with open(os.path.join(folder, filename), "rb") as f:
            sender.transport.write(f.read())
        sender.finish()
        yield finish

        yield ftp.quit()
        ftp.fail(None)

    @inlineCallbacks
    def uploadFonts(self, destination):
        exception = self.master.modules["commands"].exception
        fontdir = yield self.config.get("fontdir", "fonts")

        ftp = yield self.acquireConnection()

        try:
            yield ftp.changeDirectory(destination.encode("utf8"))

            filelist = FTPFileListProtocol()
            yield ftp.list(".", filelist)

            if fontdir not in [x["filename"] for x in filelist.files if x["filetype"] == "d"]:
                yield ftp.makeDirectory(fontdir.encode("utf8"))

            for font in os.listdir(fontdir):
                path = os.path.join(fontdir, font)
                store, finish = ftp.storeFile(path.encode("utf8"))
                sender = yield store
                with open(path, "rb") as f:
                    sender.transport.write(f.read())
                sender.finish()
                yield finish

        finally:
            yield self.releaseConnection(ftp)

    @inlineCallbacks
    def downloadFonts(self, folder, destination):
        exception = self.master.modules["commands"].exception
        fontdir = yield self.config.get("fontdir", "fonts")

        ftp = yield self.acquireConnection()

        try:
            yield ftp.changeDirectory(folder.encode("utf8"))

            filelist = FTPFileListProtocol()
            yield ftp.list(fontdir.encode("utf8"), filelist)
            fonts = [x["filename"] for x in filelist.files if x["filetype"] != "d"]

            for font in fonts:
                downloader = Downloader(os.path.join(destination, font))
                yield ftp.retrieveFile(os.path.join(fontdir, font).encode("utf8"), downloader)

        finally:
            yield self.releaseConnection(ftp)

        returnValue(fonts)

    @inlineCallbacks
    def cache(self, folder, filename):
        exception = self.master.modules["commands"].exception
        premux_dir = yield self.config.get("premuxdir", "premuxes")

        if filename in self.caching:
            raise exception(u"Already caching {}".format(filename))

        self.caching.append(filename)

        try:
            connections = []
            for _ in range(max(self.split, 1)):
                try:
                    c = yield self.acquireConnection()
                except:
                    break
                else:
                    yield c.changeDirectory(folder.encode("utf8"))
                    connections.append(c)

            if not connections:
                raise exception(u"No FTP connections available. Please wait and try again.")

            try:
                filelist = FTPFileListProtocol()
                yield connections[0].list(".", filelist)
                filedata = [x for x in filelist.files if x["filename"] == filename][0]

                chunk_len = 1024 * ((filedata["size"] / len(connections)) / 1024) # Round to nearest kilobyte
                remainder = filedata["size"] - (chunk_len * (len(connections) - 1))

                deferreds = []
                for i in range(len(connections)):
                    fname = "{}.{:d}".format(filename, i)
                    size = remainder if i == len(connections) - 1 else chunk_len
                    downloader = Downloader(os.path.join(premux_dir, fname), limit=size)
                    d = connections[i].retrieveFile(os.path.join(folder, filename), downloader, offset=chunk_len*i)
                    d.addErrback(lambda _: None) # Swallow FTP fail errors
                    deferreds.append(d)
                yield DeferredList(deferreds)

            finally:
                for c in connections:
                    yield self.releaseConnection(c)

            # Merge files in a way that won't use too much memory
            wrong_size = False
            with open(os.path.join(premux_dir, filename), "wb") as fout:
                for i in range(len(connections)):
                    size = remainder if i == len(connections) - 1 else chunk_len
                    fname = "{}.{:d}".format(filename, i)

                    wrong_size = wrong_size or os.path.getsize(os.path.join(premux_dir, fname)) != size

                    with open(os.path.join(premux_dir, fname), "rb") as fin:
                        shutil.copyfileobj(fin, fout, 65536)
                    os.remove(os.path.join(premux_dir, fname))

            actual = os.path.getsize(os.path.join(premux_dir, filename))
            if wrong_size or actual != filedata["size"]:
                os.remove(os.path.join(premux_dir, filename))
                raise exception(u"Downloaded file was not the proper size. Got {:,d} instead of {:,d}".format(actual, filedata["size"]))

        finally:
            self.caching.remove(filename)

    @inlineCallbacks
    def uncache(self, filename):
        exception = self.master.modules["commands"].exception
        premux_dir = yield self.config.get("premuxdir", "premuxes")

        os.remove(os.path.join(premux_dir, filename))
