config = {
    "access": "admin",
    "help": ".topicclear || .topicclear || Clears all text from the end of the topic",
    "reversible": False
}

def command(self, user, channel, msg):
    self.factory.config.topic = self.factory.config.topic[:3]
    self.factory.update_topic()
