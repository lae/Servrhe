from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".markov [name] || .markov foogi || Ramble as [name] would, utilizing markov chains",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if not msg:
        self.msg(channel, "Need a name")
        return
    name, permissions = self.factory.alias.resolve(msg[0]), self.getPermissions(user)
    if "owner" not in permissions or name != "list":
        if name not in self.factory.markov.users:
            self.msg(channel, "No data on {}".format(msg[0]))
            return
        message = yield self.factory.markov.ramble(name)
        self.msg(channel, message)
        return
    self.msg(channel, ", ".join(self.factory.markov.users.keys()))