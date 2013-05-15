from datetime import datetime as dt

config = {
    "access": "public",
    "help": ".aired || .aired || Lists the shows aired but not encoded"
}

def command(guid, manager, irc, channel, user):
    now = dt.utcnow()
    manager.dispatch("update", guid, u"Waiting on showtimes.aired")
    data = yield manager.master.modules["showtimes"].aired()
    if not data:
        irc.msg(channel, u"No shows awaiting encoding")
    for d in data:
        aired = manager.master.modules["utils"].dt2ts(now - dt.utcfromtimestamp(d.airtime))
        irc.msg(channel, u"{} {:02d} aired {} ago on {}".format(d.name.english, d.episode.current + 1, aired, d.channel))
