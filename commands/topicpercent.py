config = {
    "access": "admin",
    "help": ".topicpercent [percentage] || .topicpercent 100.00 || Sets the Mahoyo progress percentage",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        return self.msg(channel, "No percentage given")
    try:
        self.factory.config.topic[2] = float(msg[0])
        self.factory.update_topic()
    except ValueError:
        self.msg(channel, "Invalid percentage (must be a float)")
