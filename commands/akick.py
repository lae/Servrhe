config = {
    "access": "owner",
    "help": ".akick [faggot] || .akick torchlight || Makes them go and stay go",
    "reverse_help": ".unakick [faggot] || .unakick torchlight || Lets them back in",
}

def command(guid, manager, irc, channel, user, faggot, reverse = False):
    akick = manager.master.modules["akick"]
    method = "remove" if reverse else "add"
    getattr(akick, method)(channel, faggot)
