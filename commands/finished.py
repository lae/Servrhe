config = {
    "access": "admin",
    "help": ".finished [show name] || .finished Accel World || Marks a show as released",
    "reverse_help": ".unfinished [show name] || .unfinished Accel World || Reverts the show to last week and marks as not released"
}

def command(guid, manager, irc, channel, user, show, reverse = False):
    method = "unfinished" if reverse else "finished"
    show = manager.master.modules["showtimes"].resolve(show)

    manager.dispatch("update", guid, "Waiting on showtimes.{}".format(method))
    yield getattr(manager.master.modules["showtimes"], method)(show)
    yield manager.master.modules["showtimes"].updateTopic()

    irc.msg(channel, u"{} marked {}".format(show.name.english, method))
