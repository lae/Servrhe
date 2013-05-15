config = {
    "access": "admin",
    "help": ".assign [position] [victim] [show name] || .assign timer Foogimahn Accel World || Assigns the victim to the position for the show"
}

def command(guid, manager, irc, channel, user, position, victim, show):
    position = yield manager.master.modules["showtimes"].getPosition(position)
    show = manager.master.modules["showtimes"].resolve(show)
    manager.dispatch("update", guid, "Waiting on showtimes.assign")
    yield manager.master.modules["showtimes"].assign(show, position, victim)
    irc.msg(channel, u"{} for {} is assigned to {}".format(position, show.name.english, victim))
