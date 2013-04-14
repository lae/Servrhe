config = {
    "access": "admin",
    "help": ".config [save|load] || .config load || Reloads (or resaves) the config",
    "reversible": False
}

def command(self, user, channel, msg):
    action = msg[0]
    if action not in ("save", "load"):
        return self.msg(channel, "Can only save or load the config")
    getattr(self.factory.config, action)()
    self.msg(channel, "Config {}{}".format(action, "d" if action[-1] == "e" else "ed"))
