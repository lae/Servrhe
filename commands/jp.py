config = {
    "access": "public",
    "help": ".jp [show name] || .jp Accel World || Prints the Japanese title of the show"
}

def command(guid, manager, irc, channel, user, show):
    show = manager.master.modules["showtimes"].resolve(show)
    if show.name.japanese:
        irc.msg(channel, u"{} -> {}".format(show.name.english, show.name.japanese))
    else:
        irc.msg(channel, u"{} does not have a Japanese title stored in showtimes.".format(show.name.english))
