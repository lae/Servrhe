config = {
    "access": "admin",
    "help": ".funirip [quality] [episode] [series] || Quality is 360, 480, or 720. Series uses CR's naming"
}

def command(guid, manager, irc, channel, user, quality, episode, show):
    if quality not in ("360", "480", "720"):
        raise manager.exception("Invalid quality, must be 360, 480, or 720")

    try:
        episode = int(episode)
    except:
        raise manager.exception("Invalid episode number, must be an integer")

    show = manager.master.modules["funi"].resolve(show)

    key = "{:02d}".format(episode)
    if key not in show.episodes:
        raise manager.exception("No data for that episode, try again when Funi has added it")

    data = show[key]
    yield manager.master.modules["funi"].rip(guid, data, quality)
    irc.msg(channel, u"Ripping of {} {} [{}p] was successful".format(series, key, quality))
