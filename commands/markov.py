from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".markov [name] || .markov foogi || Ramble as [name] would, utilizing markov chains",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    permissions = self.getPermissions(user)
    if "owner" not in permissions:
        self.notice(user, "Temporarily disabled due to oENDERo")
        return
    if not msg:
        message = yield self.factory.markov.ramble()
        self.msg(channel, message)
        return
    name = self.factory.alias.resolve(msg[0])
    if "owner" not in permissions or name != "list":
        if name not in self.factory.markov.users:
            self.msg(channel, "No data on {}".format(msg[0]))
            return
        if self.isAdmin(name) and user.lower() not in self.admins:
            self.kick(channel, user, "Do not highlight staff")
        else:
            seed = msg[1] if len(msg) > 1 else ""
            message = yield self.factory.markov.ramble(name, seed)
            self.msg(channel, message)
        return
    self.msg(channel, ", ".join(self.factory.markov.users.keys()))
