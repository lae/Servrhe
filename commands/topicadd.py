config = {
    "access": "admin",
    "help": ".topicadd [contents] || .topicadd Some Faggotry Here || Adds some text to the end of the topic",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        return self.msg(channel, "No message given")
    self.factory.config.topic.append(" ".join(msg))
    self.factory.update_topic()
