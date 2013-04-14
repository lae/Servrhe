from twisted.internet.defer import inlineCallbacks

config = {
    "access": "admin",
    "help": ".done [position] [show name] || .done timer Accel World || Marks a position for a show as done",
    "reversible": True,
    "reverse_help": ".undone [position] [show name] || .undone timer Accel World || Marks a position for a show as not done"
}

@inlineCallbacks
def command(self, user, channel, msg, reverse = False):
    position = msg[0]
    if position not in self.factory.config.positions:
        self.msg(channel, "%s is not a valid position. Try %s, or %s." % (msg[0], ", ".join(self.factory.config.positions[:-1]), self.factory.config.positions[-1]))
        return
    if position == "qc":
        self.msg(channel, "Can't use .done qc, you must use .finished instead")
        return
    show = self.factory.resolve(" ".join(msg[1:]), channel)
    if show is None:
        return
    data = {"id":show["id"],"method":"position_status","position":position,"value":"0" if reverse else "1"}
    data = yield self.factory.load("show","update", data=data)
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    self.msg(channel, "%s for %s is marked as %s" % (position, show["series"], "not done" if reverse else "done"))
