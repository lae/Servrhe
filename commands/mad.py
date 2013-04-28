config = {
    "access": "superadmin",
    "help": ".mad || .mad || Makes the bot mad on the behalf of glorious leader",
    "reversible": True,
    "reverse_help": ".unmad || .unmad || Relaxes the bot"
}

def command(self, user, channel, msg, reverse = False):
    if user.lower() != "fugiman":
        return self.msg(channel, "Denied")
    self.factory.config.mad = not reverse
    self.msg(channel, "The bot is now {}".format("calm" if reverse else "mad"))
