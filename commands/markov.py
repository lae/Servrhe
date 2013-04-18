from lib.markov import Markov

config = {
    "access": "public",
    "help": ".markov [name] || .markov foogi || Ramble as [name] would, utilizing markov chains",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        return self.msg(channel, "Need a name")
    name, permissions = self.alias(msg[0]), self.getPermissions(user)
    if "owner" not in permissions or name != "list":
        if name not in self.factory.markov:
            return self.msg(channel, "No data on {}".format(msg[0]))
        return self.msg(channel, self.factory.markov[name].ramble())
    return self.notice(user, ", ".join(self.factory.markov.keys()))