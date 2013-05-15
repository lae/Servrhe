config = {
    "access": "admin",
    "help": ".topicset [contents] || .topicset Some Faggotry Here || Sets the text at the end of the topic"
}

def command(guid, manager, irc, channel, user, text):
    yield manager.master.modules["showtimes"].setTopic(text)
    yield manager.master.modules["showtimes"].updateTopic()
