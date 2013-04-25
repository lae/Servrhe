config = {
    "access": "owner",
    "help": ".say [channel] [message] || .say #commie-subs derp derp derp || Say something",
    "reversible": False
}

def command(self, user, channel, msg):
    if len(msg) < 2:
        self.msg(channel, "Need a target and a message")
        return
    target, message = msg[0], " ".join(msg[1:])
    self.msg(target, message)
