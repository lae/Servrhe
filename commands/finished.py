from twisted.internet.defer import inlineCallbacks

config = {
    "access": "admin",
    "help": ".finished [show name] || .finished Accel World || Marks a show as released",
    "reversible": True,
    "reverse_help": ".unfinished [show name] || .unfinished Accel World || Reverts the show to last week and marks as not released"
}

@inlineCallbacks
def command(self, user, channel, msg, reverse = False):
    show = self.factory.resolve(" ".join(msg), channel)
    if show is None:
        return
    method = "restart_last_episode" if reverse else "next_episode"
    data = {"id":show["id"],"method":method}
    data = yield self.factory.load("show","update", data=data)
    if "status" in data and not data["status"]:
        self.msg(channel, data["message"])
        return
    self.msg(channel, "{} is {}".format(show["series"], "reverted to last week" if reverse else "marked as completed for the week"))
    self.factory.update_topic()
