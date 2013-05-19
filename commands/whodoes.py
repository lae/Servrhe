config = {
    "access": "public",
    "help": ".whodoes [position] [show name] || .whodoes timer Accel World || Reports who does a job for a show"
}

def command(guid, manager, irc, channel, user, position, show):
    position = yield manager.master.modules["showtimes"].getPosition(position)
    show = manager.master.modules["showtimes"].resolve(show)

    if position == "encoder":
        raise manager.exception(u"Fuck you Wessie")

    name = getattr(show, position).name
    irc.msg(channel, u"{} is the {} for {}".format(name, position, show.name.english))
