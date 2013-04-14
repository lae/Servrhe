from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".prev [show name] || .prev Accel World || Reports when a show last aired",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    show = " ".join(msg)
    if not show:
        data = yield self.factory.load("airing","previous")
    else:
        show = self.factory.resolve(show, channel)
        if show is None:
            return
        data = yield self.factory.load("airing","previous",show["id"])
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    data = data["results"]
    if data["episode"] == "unaired":
        self.msg(channel, "The first episode of %s (%s) won't air for another %s." % (data["series"], data["series_jp"], data["when"]))
    else:
        self.msg(channel, "Episode %s of %s (%s) aired %s ago." % (data["episode"], data["series"], data["series_jp"], data["when"]))