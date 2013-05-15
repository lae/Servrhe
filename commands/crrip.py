config = {
    "access": "admin",
    "help": ".crrip [contents] [quality] [episode] [series] || Contents is subs, video or both. Quality is 360, 480, 720, or 1080. Series uses CR's naming"
}

def command(guid, manager, irc, channel, user, contents, quality, episode, show):
    if contents not in ("subs","video","both"):
        raise manager.exception("Invalid content, must be subs, video or both")

    if quality not in ("360", "480", "720", "1080"):
        raise manager.exception("Invalid quality, must be 360, 480, 720, or 1080")

    try:
        episode = int(episode)
    except:
        raise manager.exception("Invalid episode number, must be an integer")

    show = manager.master.modules["crunchy"].resolve(show)

    key = "{:02d}".format(episode)
    if key not in show.episodes:
        raise manager.exception("No data for that episode, try again when CR has added it")

    data = show.episodes[key]
    subs = contents in ("subs", "both")
    video = contents in ("video", "both")
    yield manager.master.modules["crunchy"].rip(guid, data, quality, video, subs)
    irc.msg(channel, u"Ripping of {} {} [{}p] was successful".format(show.name, key, quality))
