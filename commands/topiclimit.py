config = {
    "access": "admin",
    "help": ".topiclimit [limit] || .topiclimit 20 || Sets the max number of shows to display in the topic",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        return self.msg(channel, "No limit given")
    try:
        self.factory.config.topic[1] = int(msg[0])
        self.factory.update_topic()
    except ValueError:
        self.msg(channel, "Invalid limit (must be an int)")
