from datetime import datetime as dt

config = {
    "access": "public",
    "help": ".since [show name] || .since snafu || Reports how long it's been since a show aired"
}

def command(guid, manager, irc, channel, user, show):
    now = dt.utcnow()
    show = manager.master.modules["showtimes"].resolve(show)

    series = show.name.english
    ep = "{:02d}".format(show.episode.current + 1)
    diff = now - dt.utcfromtimestamp(show.airtime)
    aired = manager.master.modules["utils"].dt2ts(diff)
    alias = yield manager.master.modules["alias"].resolve(user)
    if show.episode.current == show.episode.total:
        irc.msg(channel, u"{} is complete. You're welcome.".format(series))
    elif diff.total_seconds() < 0 and show.id == 17:
        aired = manager.master.modules["utils"].dt2ts(-1 * diff)
        irc.msg(channel, u"{} {} airs in {}. You are wise to be excited".format(series, ep, aired))
    elif diff.total_seconds() < 0 and alias == "jdp":
        irc.msg(channel, u"{} {} hasn't aired yet, chill the fuck out bitch.".format(series, ep))
    elif diff.total_seconds() < 0:
        irc.msg(channel, u"{} {} hasn't aired yet, settle down.".format(series, ep))
    elif diff.total_seconds() > 48 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago?! What the fuck are you doing? Get that shit done NOW!".format(series, ep, aired))
    elif diff.total_seconds() > 24 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago? That's fucking outrageous, why aren't you done yet?".format(series, ep, aired))
    elif diff.total_seconds() > 12 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago. You should probably stop screwing around with typesetting.".format(series, ep, aired))
    elif diff.total_seconds() > 10 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago. I do hope you're QCing right now.".format(series, ep, aired))
    elif diff.total_seconds() > 8 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago. Perfect time to release.".format(series, ep, aired))
    elif diff.total_seconds() > 6 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago. Doing just fine.".format(series, ep, aired))
    elif diff.total_seconds() > 4 * 60 * 60:
        irc.msg(channel, u"{} {} aired {} ago. If you're still waiting for an encode, I pity you.".format(series, ep, aired))
    else:
        irc.msg(channel, u"{} {} aired {} ago. Nothing to worry about yet.".format(series, ep, aired))
