config = {
    "access": "public",
    "help": ".jp [show name] || .jp Accel World || Prints the Japanese title of the show",
    "reversible": False
}

def command(self, user, channel, msg):
    show = self.factory.resolve(" ".join(msg), channel)
    if show is None:
        return
    if show["series_jp"]:
        self.msg(channel, u"{} -> {}".format(show["series"], show["series_jp"]))
    else:
        self.msg(channel, u"{} does not have a Japanese title stored in showtimes.".format(show["series"]))
