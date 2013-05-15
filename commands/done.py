config = {
    "access": "admin",
    "help": ".done [position] [show name] || .done timer Accel World || Marks a position for a show as done",
    "reverse_help": ".undone [position] [show name] || .undone timer Accel World || Marks a position for a show as not done"
}

def command(guid, manager, irc, channel, user, position, show, reverse = False):
    method = "undone" if reverse else "done"
    position = yield manager.master.modules["showtimes"].getPosition(position)
    show = manager.master.modules["showtimes"].resolve(show)

    if position == "qc":
        manager.exception("Can't use .done qc, you must use .finished instead")

    manager.dispatch("update", guid, "Waiting on showtimes.{}".format(method))
    yield getattr(manager.master.modules["showtimes"], method)(show, position)

    irc.msg(channel, u"{} for {} is marked as {}".format(position, show.name.english, method))
