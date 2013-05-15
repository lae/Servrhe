config = {
    "access": "admin",
    "help": ".topicpercent [percentage] || .topicpercent 100.00 || Sets the Mahoyo progress percentage"
}

def command(guid, manager, irc, channel, user, percentage):
    try:
        percentage = float(percentage)
    except ValueError:
        raise manager.exception(u"Invalid percentage (must be a float)")
    yield manager.master.modules["showtimes"].setPercentage(percentage)
    yield manager.master.modules["showtimes"].updateTopic()
