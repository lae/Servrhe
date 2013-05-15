from datetime import datetime as dt

config = {
    "access": "public",
    "help": ".blame [show name] || .blame Accel World || Reports who is to blame for a show not being released"
}

def command(guid, manager, irc, channel, user, show):
    alias = yield manager.master.modules["alias"].resolve(user)
    show = manager.master.modules["showtimes"].resolve(show)
    manager.dispatch("update", guid, "Waiting on showtimes.substatus")
    data = yield manager.master.modules["showtimes"].substatus(show)

    #updated = show.airtime + 30*60 if data.position in ["encoder","translator"] else data.updated
    updated = dt.utcnow() - dt.utcfromtimestamp(data.updated)
    when = manager.master.modules["utils"].dt2ts(updated)
    worker = yield manager.master.modules["alias"].resolve(data.name)

    if data.position == "completed" and data.name == "completed":
        irc.msg(channel, u"{} is completed as of {} ago.".format(show.name.english, when))
    elif data.position == "DROPPED" and data.value == "DROPPED":
        irc.msg(channel, u"{} has been dropped at episode {:02d} as of {} ago.".format(show.name.english, data.episode, when))
    elif alias == worker:
        irc.msg(channel, u"Why are YOU asking? You know you've delayed episode {:02d} of {} for {}. Get on it!".format(data.episode, show.name.english, when))
    else:
        irc.msg(channel, u"Episode {:02d} of {} is at the {}, {}, as of {} ago.".format(data.episode, show.name.english, data.position, data.name, when))
