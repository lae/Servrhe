config = {
    "access": "admin",
    "help": ".cache [showname] (--previous) || .cache eotena || Caches the premux for a show so that .chapters, .xdelta and .release work faster"
}

def command(guid, manager, irc, channel, user, show, previous = False):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset
    folder = "/{}/{:02d}/".format(show.folder.ftp, episode)
    
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")
    cached = yield manager.master.modules["ftp"].isCached(premux)

    if cached:
        raise manager.exception(u"{} already is cached. Message fugi if you need it re-cached.".format(premux))

    irc.msg(channel, u"Caching {}".format(premux))
    manager.dispatch("update", guid, u"Caching {}".format(premux))
    yield manager.master.modules["ftp"].cache(folder, premux)

    irc.msg(channel, u"{} cached.".format(premux))
