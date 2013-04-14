from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".next [show name] || .next Accel World || Reports airing ETA for a show",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    show = " ".join(msg)
    if not show:
        data = yield self.factory.load("airing","next")
    else:
        show = self.factory.resolve(show, channel)
        if show is None:
            return
        data = yield self.factory.load("airing","next",show["id"])
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    data = data["results"]
    if data["episode"] == "finished":
        self.msg(channel, "The last episode of %s (%s) finished airing %s ago." % (data["series"], data["series_jp"], data["when"]))
    else:
        self.msg(channel, "Episode %s of %s (%s) will air in %s." % (data["episode"], data["series"], data["series_jp"], data["when"]))