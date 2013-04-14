config = {
    "access": "public",
    "help": ".commands || .commands || Lists available commands",
    "reversible": False
}

def command(self, user, channel, msg):
    permissions = ["public"]
    if user.lower() in self.admins and self.admins[user]:
        permissions.append("admin")

    r = []
    for command in self.factory.pluginmanager.plugins.values():
        if command["access"] in permissions:
            r.append(command["name"])
            if command["reversible"]:
                r.append("un{}".format(command["name"]))
    r.sort()
    self.msg(channel, "Available commands: {}".format(" ".join(r)))