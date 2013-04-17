from lib.utils import dt2ts
import datetime

config = {
    "access": "public",
    "help": ".airing || .airing || Lists the shows airing in the next 24 hours",
    "reversible": False
}

def command(self, user, channel, msg):
    dt = datetime.datetime
    now = dt.utcnow()
    shows = []
    ret = []
    for show in self.factory.shows.itervalues():
        if show["current_ep"] == show["total_eps"]:
            continue
        diff = dt.utcfromtimestamp(show["airtime"]) - now
        if diff.days == 0 or show["id"] == 17:
            shows.append((diff,show["series"],show["channel"]))
    shows.sort(key=lambda s: s[0])
    if not shows:
        self.msg(channel, "No shows airing in the next 24 hours")
    for s in shows:
        self.msg(channel, "%s airs in %s on %s" % (s[1], dt2ts(s[0]), s[2]))
