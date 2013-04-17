from lib.markov import Markov

config = {
    "access": "public",
    "help": ".markov [add|remove|save|load|say] [name] || .markov say herkz || Controls markov functions",
    "reversible": False
}

def command(self, user, channel, msg):
    if len(msg) < 2:
        return self.msg(channel, "Need a name and method")
    method, name = msg[:2]
    if method not in ("add", "remove", "save", "load", "say"):
        return self.msg(channel, "Invalid method. Try 'add', 'remove', 'save', 'load' or 'say'.")
    if method != "say" and "admin" not in self.getPermissions(user):
        return # Insufficient permissions
    if method == "add":
        if name.lower() in self.factory.markov:
            return self.msg(channel, "{} is already being tracked.".format(name))
        self.factory.markov[name.lower()] = Markov(name.lower() + ".json")
        self.factory.config.markov.append(name.lower())
        self.msg(channel, "Now tracking {}".format(name))
    elif method == "remove":
        if name.lower() not in self.factory.markov:
            return self.msg(channel, "{} is already not being tracked.".format(name))
        del self.factory.markov[name.lower()]
        self.factory.config.markov.remove(name.lower())
        self.msg(channel, "No longer tracking {}".format(name))
    elif method == "save":
        if name.lower() not in self.factory.markov:
            return self.msg(channel, "{} is not being tracked.".format(name))
        self.factory.markov[name.lower()].save()
        self.msg(channel, "Saved markov cache for {}".format(name))
    elif method == "load":
        if name.lower() not in self.factory.markov:
            return self.msg(channel, "{} is not being tracked.".format(name))
        self.factory.markov[name.lower()].load()
        self.msg(channel, "Loaded markov cache for {}".format(name))
    elif method == "say":
        if name.lower() not in self.factory.markov:
            return self.msg(channel, "{} is not being tracked.".format(name))
        self.msg(channel, self.factory.markov[name.lower()].ramble())
