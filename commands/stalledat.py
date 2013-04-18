from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
import datetime

config = {
    "access": "public",
    "help": ".stalledat [person] || .stalledat foogiman || Reports which shows a user is stalling",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if not msg:
        self.msg(channel, "Must provide a victim to check")
        return
    victim = self.factory.alias.resolve(" ".join(msg))
    dt = datetime.datetime
    yield self.factory.refresh_shows()
    shows = []
    for show in self.factory.shows.values():
        blame = ""
        if not show["encoded"]:
            continue
        if not show["tl_status"]:
            blame = show["translator"]
        elif not show["ed_status"]:
            blame = show["editor"]
        elif not show["tm_status"]:
            blame = show["timer"]
        elif not show["ts_status"]:
            blame = show["typesetter"]
        elif not show["qc_status"]:
            blame = show["qc"]

        if self.factory.alias.resolve(blame) == victim:
            shows.append(show)
    if not shows:
        self.msg(channel, "{} is not stalling anything right now.".format(victim))
        return
    parts = []
    for show in shows:
        updated = dt.utcnow() - dt.utcfromtimestamp(show["updated"])
        when = dt2ts(updated)
        parts.append("{} ({} ago)".format(show["series"], when))
    self.msg(channel, "{} is stalling: {}".format(victim, ", ".join(parts)))
