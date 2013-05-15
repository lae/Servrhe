import fnmatch

config = {
    "access": "public",
    "help": ".man [command] [command] ... || .man man commands || Gives usage and description of commands"
}

def command(guid, manager, irc, channel, user, commands):
    if not commands:
        commands = ["man"]
    else:
        commands = commands.split(" ")

    permissions = yield manager.getPermissions(user)

    available = []
    for command in manager.commands.values():
        if command["access"] not in permissions:
            continue
        available.append(command["name"])
        if "reverse" in command["kwargs"]:
            available.append("un" + command["name"])

    matches = set()
    for command in commands:
        command = command.lower()
        matches.update(set(fnmatch.filter(available, command)))

    if not matches:
        raise manager.exception("Couldn't find any matching commands")
    if len(matches) > 5:
        raise manager.exception("No, fuck you. That's too many.")

    for match in matches:
        reverse = False
        if match[:2] == "un":
            match = match[2:]
            reverse = True
        irc.msg(channel, manager.commands[match]["reverse_help" if reverse else "help"])
