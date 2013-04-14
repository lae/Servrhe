from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".whodoes [position] [show name] || .whodoes timer Accel World || Reports who does a job for a show",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    position = msg[0]
    if position not in self.factory.config.positions:
        self.msg(channel, "%s is not a valid position. Try %s, or %s." % (msg[0], ", ".join(self.factory.config.positions[:-1]), self.factory.config.positions[-1]))
        return
    show = self.factory.resolve(" ".join(msg[1:]), channel)
    if show is None:
        return
    data = yield self.factory.load("show",show["id"],position)
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    data = data["results"]
    self.msg(channel, "%s is the %s for %s" % (data["name"], data["position"], show["series"]))