config = {
    "access": "admin",
    "help": ".join [channel] [channel] ... || .join #commie-subs || Makes the bot join channels",
    "reversible": True,
    "reverse_help": ".unjoin [channel] [channel] ... || .unjoin #commie-subs || Makes the bot leave channels"
}

def command(self, user, channel, msg, reverse = False):
    for c in msg:
        if not reverse:
            self.join(c)
            self.factory.config.channels.append(c)
        else:
            self.leave(c)
            self.factory.config.channels.remove(c)
