# -*- coding: utf-8 -*-

from twisted.internet import reactor, protocol, defer
from twisted.web.client import Agent, FileBodyProducer
from twisted.web.http_headers import Headers
from StringIO import StringIO
import os

dependencies = []

numeral_map = zip(
    (1000000, 500000, 100000, 50000, 10000, 5000, 1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1),
    (u'M\u0305', u'D\u0305', u'C\u0305', u'L\u0305', u'X\u0305', u'V\u0305', u'M', u'CM', u'D', u'CD', u'C', u'XC', u'L', u'XL', u'X', u'IX', u'V', u'IV', u'I')
)

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

class BodyStringifier(protocol.Protocol):
    def __init__(self, deferred):
        self.deferred = deferred
        self.buffer = []
    def dataReceived(self, data):
        self.buffer.append(data)
    def connectionLost(self, reason):
        self.deferred.callback("".join(self.buffer))

class Module(object):
    def __init__(self, master):
        self.master = master

    def stop(self):
        pass

    def dt2ts(self, dt):
        hours = dt.seconds // 3600
        minutes = (dt.seconds // 60) % 60
        seconds = dt.seconds % 60

        day = "day" if dt.days == 1 else "days"
        hour = "hour" if hours == 1 else "hours"
        minute = "minute" if minutes == 1 else "minutes"
        second = "second" if seconds == 1 else "seconds"

        if dt.days:
            return "{:d} {}, {:d} {}, {:d} {} and {:d} {}".format(dt.days, day, hours, hour, minutes, minute, seconds, second)
        elif hours:
            return "{:d} {}, {:d} {} and {:d} {}".format(hours, hour, minutes, minute, seconds, second)
        elif minutes:
            return "{:d} {} and {:d} {}".format(minutes, minute, seconds, second)
        else:
            return "{:d} {}".format(seconds, second)

    def bytes2human(self, num):
        for x in ['bytes','KB','MB','GB']:
            if num < 1024.0:
                return "{:3.1f}{}".format(num, x)
            num /= 1024.0
        return "{:3.1f}{}".format(num, 'TB')

    def returnBody(self, response):
        if response.code == 204:
            d = defer.succeed("")
        else:
            d = defer.Deferred()
            response.deliverBody(BodyStringifier(d))
        return d

    def fetchPage(self, url, data=None, headers={}):
        method = "POST" if data else "GET"
        body = FileBodyProducer(StringIO(data)) if data else None
        d = self.master.agent.request(method, url, Headers(headers), body)
        d.addCallback(self.returnBody)
        return d

    def getPath(self, cmd):
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

    def rheinbowify(self, text):
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
        return u"".join(final)

    def intToRoman(self, i):
        if i == 0:
            return u"\u221E"
        result = []
        if i < 0:
            result.append(u"-")
            i *= -1
        if i >= 5000000:
            d = int(i / 5000000) * 5000
            result.append(u"\u01C0")
            result.append(self.intToRoman(d))
            result.append(u"\u01C0")
            i -= d * 1000
        for integer, numeral in numeral_map:
            count = int(i / integer)
            result.append(numeral * count)
            i -= integer * count
        return u''.join(result)

