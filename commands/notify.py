import datetime

config = {
    "access": "admin",
    "help": ".notify [# of weeks|forever|clear] [show name|*] || .notify forever * || Adds you to the notify list for a show.",
    "reversible": False
}

def command(self, user, channel, msg):
    if len(msg) < 2:
        return self.msg(channel, "Duration and name required")
    duration, name = msg[0], " ".join(msg[1:])
    if name != "*":
        show = self.factory.resolve(id, channel)
        if not show:
            return
        id = show["id"]
        name = show["series"]
    else:
        id = "*"
    if duration == "forever":
        duration = -1
    elif duration == "clear":
        duration = 0
    else:
        try:
            duration = int(duration)
        except:
            return self.msg(channel, "Failed to convert duration to an integer")
    if id not in self.factory.config.notifies:
        self.factory.config.notifies[id] = {}
    if duration:
        self.factory.config.notifies[id][user] = duration
        extra = ""
        if id != "*":
            show = self.factory.shows[id]
            dt = datetime.datetime
            now = dt.utcnow()
            diff = dt.utcfromtimestamp(show["airtime"]) - now
            extra = " (airs in {} on {})".format(dt2ts(diff), show["channel"])
        self.msg(channel, "You'll now be notified for {}{}".format(name, extra))
    elif user in self.factory.config.notifies[id]:
        del self.factory.config.notifies[id][user]
        self.msg(channel, "You are now no longer being notified for {}".format(name))
    else:
        self.msg(channel, "You already weren't being notified for {}".format(name))
