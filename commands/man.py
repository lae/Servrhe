config = {
    "access": "public",
    "help": ".man [command] [command] ... || .man man commands || Gives usage and description of commands",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        msg = ["man"]

    permissions = ["public"]
    if user in self.admins and self.admins[user]:
        permissions.append("admin")

    for command in msg:
        command, reverse = command.lower(), False
        if command not in self.factory.pluginmanager.plugins and command[:2] == "un" and command[2:] in self.factory.pluginmanager.plugins:
            command = command[2:]
            reverse = True
            if not self.factory.pluginmanager.plugins[command]["reversible"]:
                continue
        if command in self.factory.pluginmanager.plugins and self.factory.pluginmanager.plugins[command]["access"] in permissions:
            self.msg(channel, self.factory.pluginmanager.plugins[command]["reverse_help" if reverse else "help"])
