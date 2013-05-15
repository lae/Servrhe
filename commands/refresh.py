config = {
    "access": "admin",
    "help": ".refresh || .refresh || Refresh show cache"
}

def command(guid, manager, irc, channel, user):
    yield manager.master.modules["showtimes"].refreshShows()
    irc.msg(channel, "Show cache refreshed")
