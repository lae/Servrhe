from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
import datetime

config = {
    "access": "public",
    "help": ".blame [show name] || .blame Accel World || Reports who is to blame for a show not being released",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    dt = datetime.datetime
    show = self.factory.resolve(" ".join(msg), channel)
    if show is None:
        return
    data = yield self.factory.load("show",show["id"],"substatus")
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    data = data["results"]
    if data["position"] in ["encoder","translator"]:
        data["updated"] = show["airtime"] + 30*60 # Airtime + 30min, adjusts for completion of airing
    updated = dt.utcnow() - dt.utcfromtimestamp(data["updated"])
    when = dt2ts(updated)
    if data["position"] == "completed" and data["value"] == "completed":
        self.msg(channel, "%s is completed as of %s ago." % (show["series"], when))
    elif data["position"] == "DROPPED" and data["value"] == "DROPPED":
        self.msg(channel, "%s has been dropped at episode %s as of %s ago." % (show["series"], data["episode"], when))
    else:
        self.msg(channel, "Episode %s of %s is at the %s, %s, as of %s ago." % (data["episode"], show["series"], data["position"], data["value"], when))
