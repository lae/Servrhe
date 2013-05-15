# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import CookieAgent, FileBodyProducer
from twisted.web.http_headers import Headers
from StringIO import StringIO
import cookielib, urllib

dependencies = ["config", "commands", "utils"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("tt")

    def stop(self):
        pass

    @inlineCallbacks
    def upload(self, link):
        exception = self.master.modules["commands"].exception
        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        ttagent = CookieAgent(self.master.agent, cookielib.CookieJar())

        if user is None or passwd is None:
            raise exception(u"No TT username or password in config")

        response = yield ttagent.request("POST","http://tokyotosho.info/login.php",
            Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
            FileBodyProducer(StringIO(urllib.urlencode({"username": user,"password": passwd,"submit": "Submit"}))))

        body = yield self.master.modules["utils"].returnBody(response)
        if "Logged in." not in body:
            raise exception(u"Couldn't login to TT.")

        response = yield ttagent.request("POST","http://tokyotosho.info/new.php",
            Headers({'Content-Type': ['application/x-www-form-urlencoded']}),
            FileBodyProducer(StringIO(urllib.urlencode({
                "type": "1",
                "url": link,
                "comment": "#commie-subs@irc.rizon.net",
                "website": "http://www.commiesubs.com/",
                "send": "Submit New Torrent"
            }))))

        body = yield self.master.modules["utils"].returnBody(response)
        if "Torrent Submitted" not in body:
            raise exception(u"Couldn't upload torrent to TT.")
