from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".assign [position] [victim] [show name] || .assign timer Foogimahn Accel World || Assigns the victim to the position for the show",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    position = self.getPosition(msg[0])
    if position is None:
        self.msg(channel, "%s is not a valid position. Try %s, or %s." % (msg[0], ", ".join(self.factory.config.positions[:-1]), self.factory.config.positions[-1]))
        return
    victim = msg[1]
    show = self.factory.resolve(" ".join(msg[2:]), channel)
    if show is None:
        return
    data = {"id":show["id"],"method":"position","position":position,"value":victim}
    data = yield self.factory.load("show","update", data=data)
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    self.msg(channel, "%s for %s is assigned to %s" % (position, show["series"], victim))
