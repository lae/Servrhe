import fnmatch

config = {
    "access": "public",
    "help": ".man [command] [command] ... || .man man commands || Gives usage and description of commands",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        msg = ["man"]

    permissions = self.getPermissions(user)

    commands = []
    for command in self.factory.pluginmanager.plugins.values():
        if command["access"] not in permissions:
            continue
        commands.append(command["name"])
        if command["reversible"]:
            commands.append("un" + command["name"])

    matches = set()
    for command in msg:
        command = command.lower()
        matches.update(set(fnmatch.filter(commands, command)))

    if not matches:
        return self.msg(channel, "Couldn't find any matching commands")
    if len(matches) > 5:
        return self.msg(channel, "No, fuck you. That's too many.")

    for match in matches:
        reverse = False
        if match[:2] == "un":
            match = match[2:]
            reverse = True
        self.msg(channel, self.factory.pluginmanager.plugins[match]["reverse_help" if reverse else "help"])
