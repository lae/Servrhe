import datetime

config = {
    "access": "admin",
    "help": ".notify [# of weeks|forever|clear] [show name|*] || .notify forever * || Adds you to the notify list for a show."
}

def command(guid, manager, irc, channel, user, duration, name):
    if name != "*":
        show = manager.master.modules["showtimes"].resolve(name)
        id = show.id
    else:
        id = "*"
    if duration == "forever":
        duration = -1
    elif duration == "clear":
        duration = 0
    else:
        try:
            duration = int(duration)
        except:
            raise manager.exception(u"Failed to convert duration to an integer")
    yield manager.master.modules["showtimes"].notify(id, user, duration)
