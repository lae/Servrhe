config = {
    "access": "admin",
    "help": ".funiautorip [quality] [series] || Quality is 360, 480, or 720. Series uses CR's naming"
}

def command(guid, manager, irc, channel, user, quality, show):
    if quality not in ("360", "480", "720"):
        raise manager.exception("Invalid quality, must be 360, 480, or 720")

    show = manager.master.modules["funi"].resolve(show)

    yield manager.master.modules["funi"].autodownload(show, quality)
    irc.msg(channel, u"Set {} to autorip at {}p".format(series, quality))
