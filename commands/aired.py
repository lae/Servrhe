from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
import datetime

config = {
    "access": "public",
    "help": ".aired || .aired || Lists the shows aired but not encoded",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    dt = datetime.datetime
    now = dt.utcnow()
    data = yield self.factory.load("shows","aired")
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    data = data["results"]
    if not data:
        self.msg(channel, "No shows awaiting encoding")
    for d in data:
        ep = str(d["current_ep"]+1)
        aired = dt2ts(now - dt.utcfromtimestamp(d["airtime"]))
        self.msg(channel, "{} {} aired {} ago on {}".format(d["series"], ep, aired, d["channel"]))
