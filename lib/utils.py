from twisted.internet import reactor, protocol, defer
from twisted.web.client import Agent, FileBodyProducer
from twisted.web.http_headers import Headers
from StringIO import StringIO
from functools import wraps
import os

def normalize(s):
    if not isinstance(s, basestring):
        try:
            return str(s)
        except UnicodeEncodeError:
            return unicode(s).encode('utf-8','backslashreplace')
    elif isinstance(s, unicode):
        return s.encode('utf-8', 'backslashreplace')
    else:
        if s.decode('utf-8', 'ignore').encode('utf-8', 'ignore') == s: # Ensure s is a valid UTF-8 string
            return s
        else: # Otherwise assume it is Windows 1252
            return s.decode("cp1252", 'replace').encode('utf-8', 'backslashreplace')

def log(*params):
    print " ".join([repr(x) for x in params])

def dt2ts(dt):
    hours = dt.seconds // 3600
    minutes = (dt.seconds // 60) % 60
    seconds = dt.seconds % 60
    when = ""
    if dt.days:
        when = "%d days, %d hours, %d minutes and %d seconds" % (dt.days, hours, minutes, seconds)
    elif hours:
        when = "%d hours, %d minutes and %d seconds" % (hours, minutes, seconds)
    elif minutes:
        when = "%d minutes and %d seconds" % (minutes, seconds)
    else:
        when = "%d seconds" % seconds
    return when

def bytes2human(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

class BodyStringifier(protocol.Protocol):
    def __init__(self, deferred):
        self.deferred = deferred
        self.buffer = ""
    def dataReceived(self, data):
        self.buffer += data
    def connectionLost(self, reason):
        self.deferred.callback(self.buffer)

def returnBody(response):
    if response.code == 204:
        d = defer.succeed("")
    else:
        d = defer.Deferred()
        response.deliverBody(BodyStringifier(d))
    return d

def fetchPage(url, data=None, headers={}):
    method = "POST" if data else "GET"
    body = FileBodyProducer(StringIO(data)) if data else None
    d = Agent(reactor).request(method, url, Headers(headers), body)
    d.addCallback(returnBody)
    return d

def getPath(cmd):
    if os.path.isabs(cmd):
        return cmd
    exts = [""] if "." in cmd else ["",".exe",".bat"]
    paths = filter(lambda x: x, os.environ["PATH"].replace("\\\\","/").split(os.pathsep))
    for p in paths:
        for e in exts:
            r = os.path.join(p, cmd) + e
            if os.path.isfile(r):
                return r
    raise Exception("No valid path found for "+cmd)

class Downloader(protocol.Protocol):
    def __init__(self, name, deferred = None):
        self.file = open(name, "wb")
        self.len = 0
        self.deferred = deferred
    def dataReceived(self, data):
        self.file.write(data)
        self.len += len(data)
    def connectionLost(self, reason):
        if self.deferred:
            self.deferred.callback(self.len)
    def done(self):
        self.file.close()
        return self.len

@defer.inlineCallbacks
def cache(self, user, ftp, premux, premux_len):
    self.notice(user, "Beginning caching of {}".format(premux))
    premux_downloader = Downloader("{}/{}".format(self.factory.config.premux_dir, premux))
    yield ftp.retrieveFile(premux, premux_downloader)

    if premux_downloader.done() != premux_len:
        os.remove("{}/{}".format(self.factory.config.premux_dir, premux))
        defer.returnValue(False)
    else:
        defer.returnValue(True)

def getRheinbow(v):
    v = v % 1536
    r, g, b = 255, v, 0
    if g > 255:
        r -= g - 255
        g = 255
    if r < 0:
        b = -r
        r = 0
    if b > 255:
        g -= b - 255
        b = 255
    if g < 0:
        r = -g
        g = 0
    if r > 255:
        b -= r - 255
        r = 255
    return "{:02X}{:02X}{:02X}".format(r, g, b)

def getRheinbows(n):
    total = 1536
    chunk = total / n
    bows = []
    for i in range(n):
        bows.append(getRheinbow(i * chunk))
    return bows

def rheinbowify(text):
    final = []
    count, skip = 0, 0
    for letter in text:
        if letter == "[":
            skip += 1
        elif letter == "]" and skip > 0:
            skip -= 1
        elif not skip and letter != " ":
            count += 1
    bows = getRheinbows(count)
    count, skip = 0, 0
    for letter in text:
        if letter == "[":
            skip += 1
        elif letter == "]" and skip > 0:
            skip -= 1
        if skip or letter == "]" or letter == " ":
            final.append(letter)
        else:
            final.append('[color="#{}"]{}[/color]'.format(bows[count], letter))
            count += 1
    return "".join(final)
