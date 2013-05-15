config = {
    "access": "owner",
    "help": ".join [channel] [channel] ... || .join #commie-subs || Makes the bot join channels",
    "reverse_help": ".unjoin [channel] [channel] ... || .unjoin #commie-subs || Makes the bot leave channels"
}

def command(guid, manager, irc, channel, user, channels, reverse = False, preserve = False):
    channels = channels if preserve else channels.split(" ")
    for c in channels:
        if not reverse:
            irc.join(c)
        else:
            irc.leave(c)
