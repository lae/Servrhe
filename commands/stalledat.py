from datetime import datetime as dt

config = {
    "access": "public",
    "help": ".stalledat [person] || .stalledat foogiman || Reports which shows a user is stalling"
}

def command(guid, manager, irc, channel, user, victim):
    victim = yield manager.master.modules["alias"].resolve(victim)
    shows = []
    for show in manager.master.modules["showtimes"].shows.values():
        blame = yield manager.master.modules["showtimes"].substatus(show)
        staller = yield manager.master.modules["alias"].resolve(blame.name)
        if staller == victim:
            shows.append(show)
    if not shows:
        raise manager.exception(u"{} is not stalling anything right now.".format(victim))

    parts = []
    for show in shows:
        updated = dt.utcnow() - dt.utcfromtimestamp(show.updated)
        when = manager.master.modules["utils"].dt2ts(updated)
        parts.append(u"{} ({} ago)".format(show.name.english, when))
    irc.msg(channel, u"{} is stalling: {}".format(victim, u", ".join(parts)))
