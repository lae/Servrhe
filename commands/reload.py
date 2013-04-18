config = {
    "access": "owner",
    "help": ".reload || .reload || Reloads all commands",
    "reversible": False
}

def command(self, user, channel, msg):
    self.factory.pluginmanager.load()
    self.msg(channel, "Plugins reloaded")
