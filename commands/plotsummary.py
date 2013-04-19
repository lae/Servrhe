from twisted.internet.defer import inlineCallbacks
from lib.utils import fetchPage
import base64, urllib, re, HTMLParser

config = {
    "access": "admin",
    "help": ".plotsummary [show name] || .plotsummary eotena || Gives a summary of the show, taken from MAL",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    show = self.factory.resolve(" ".join(msg), channel)
    if not show:
        return
    creds = "{}:{}".format(self.factory.config.mal_user, self.factory.config.mal_pass)
    auth = "Basic {}".format(base64.b64encode(creds))
    data = yield fetchPage("http://myanimelist.net/api/anime/search.xml?q={}".format(urllib.quote_plus(show["series"])), headers={"Authorization": [auth]})
    if not data:
        self.msg(channel, "Couldn't find a summary for {}".format(show["series"]))
        return
    data = data.replace("\r","").replace("\n","")
    title, plot = re.search("<title>(.*?)</title>", data), re.search("<synopsis>(.*?)</synopsis>", data)
    if not title or not plot:
        self.msg(channel, "Couldn't parse response for {}".format(show["series"]))
        return
    h = HTMLParser.HTMLParser()
    title = h.unescape(title.group(1))
    plot = h.unescape(plot.group(1)).replace("<br />", " ")
    print u"\n{}\n{}\n".format(title, plot)
    self.msg(channel, u"{}: {}".format(title, plot))
