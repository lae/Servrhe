#!/usr/bin/env python
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
import datetime

config = {
    "access": "admin",
    "help": ".funi [subcommand] ... || .funi help || Everything Funimation (use .funi help for more)",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if not msg:
        self.msg(channel, config["help"])
        return

    subcommands = ("rip", "autorip", "list", "info", "config", "reload", "login")
    command = msg[0].lower()

    if command not in subcommands:
        self.msg(channel, "Available subcommands are: {}. Use .funi [subcommand] for their use".format(", ".join(subcommands)))
        return

    if command == "rip":
        if len(msg) < 4:
            self.msg(channel, ".funi rip [quality] [episode] [series] || Quality is 360, 480 or 720, Series uses Funi's naming")
            return

        quality, episode, series = msg[1], msg[2], " ".join(msg[3:])
        success, series = self.factory.funi.resolve(series)

        if quality not in ("360", "480", "720"):
            self.msg(channel, "Invalid quality, must be 360, 480 or 720")
            return

        try:
            episode = int(episode)
        except:
            self.msg(channel, "Invalid episode number, must be an integer")
            return

        if not success:
            self.msg(channel, series)
            return

        key = "{:02d}".format(episode)
        if key not in self.factory.funi.data["shows"][series]:
            self.msg(channel, "No data for that episode, try again when Funi has added it")
            return

        success = yield self.factory.funi.rip(series, episode, quality, lambda x: self.notice(user, x))
        self.msg(channel, "Ripping of {} {:02d} [{}p] was {}".format(series, episode, quality, "successful" if success else "unsuccessful"))

    elif command == "autorip":
        if len(msg) < 3:
            self.msg(channel, ".funi autorip [quality] [series] || Quality is 360, 480 or 720, Series uses Funi's naming")
            return

        quality, series = msg[1], " ".join(msg[2:])
        success, series = self.factory.funi.resolve(series)

        if quality not in ("360", "480", "720"):
            self.msg(channel, "Invalid quality, must be 360, 480 or 720")
            return

        if not success:
            self.msg(channel, series)
            return

        self.factory.funi.data["auto_downloads"][series] = {
            "quality": quality,
            "downloaded": self.factory.funi.data["shows"][series].keys()
        }

        self.msg(channel, "Set {} to autorip at {}p. You won't really know if it works though. ┐(￣ー￣)┌".format(series, quality))

    elif command == "list":
        if len(msg) < 2:
            self.msg(channel, ".funi list series || .funi list episodes [series] || .funi list autodownloads || Either lists known series, or known episodes for a series. Series uses Funi's naming")
            return

        subcommand = msg[1].lower()

        if subcommand == "series":
            self.msg(channel, ", ".join(sorted(self.factory.funi.data["shows"].keys())))

        elif subcommand == "episodes":
            if len(msg) < 3:
                self.msg(channel, ".funi list episodes [series] || You forgot the series name, try again.")
                return

            series = " ".join(msg[2:])
            success, series = self.factory.funi.resolve(series)

            if not success:
                self.msg(channel, series)
                return

            self.msg(channel, ", ".join(sorted(self.factory.funi.data["shows"][series].keys())))

        elif subcommand == "autodownloads":
            data = self.factory.funi.data["auto_downloads"]
            self.msg(channel, ", ".join(["{} at {}p".format(k,data[k]["quality"]) for k in sorted(data.keys())]))

        else:
            self.msg(channel, ".funi list series || .funi list episodes [series] || .funi list autodownloads || Those are your only three options, stop trying to be a special snowflake.")

    elif command == "info":
        if len(msg) < 3:
            self.msg(channel, ".funi info [episode] [series] || Gives you data on an episode. Series uses Funi's naming")
            return

        episode, series = msg[1], " ".join(msg[2:])
        success, series = self.factory.funi.resolve(series)

        try:
            episode = int(episode)
        except:
            self.msg(channel, "Invalid episode number, must be an integer")
            return

        if not success:
            self.msg(channel, series)
            return

        key = "{:02d}".format(episode)
        if key not in self.factory.funi.data["shows"][series]:
            self.msg(channel, "No data for that episode, try again when Funi has added it")
            return

        data = self.factory.funi.data["shows"][series][key]

        now = datetime.datetime.utcnow()
        airtime = datetime.datetime.utcfromtimestamp(data["airtime"])
        if now > airtime:
            airing = "aired {} ago".format(dt2ts(now - airtime))
        else:
            airing = "airs in {}".format(dt2ts(airtime - now))

        self.msg(channel, "{} {:02d}, \"{}\", {} with a duration of {}. Funi ID = {}, Video ID = {}.".format(series, episode, data["title"], airing, data["duration"], data["funi_id"], data["vid_id"]))

    elif command == "config":
        if len(msg) < 2:
            self.msg(channel, ".funi config save || .funi config load || Saves or loads the config file")
            return

        subcommand = msg[1].lower()

        if subcommand == "load":
            self.factory.funi.load()
            self.msg(channel, "Funi config loaded")

        elif subcommand == "save":
            self.factory.funi.save()
            self.msg(channel, "Funi config saved")

        else:
            self.msg(channel, ".funi config save || .funi config load || Is it really that hard?")

    elif command == "reload":
        force = len(msg) > 1 and msg[1].lower() == "force"
        self.notice(user, "Starting caching with forced overwriting {}".format("on" if force else "off"))
        yield self.factory.funi.cache(0, force)
        self.msg(channel, "Funimation data reloaded")

    elif command == "login":
        yield self.factory.funi.login()
        if self.factory.funi.logged_in:
            self.msg(channel, "Login to Funimation successful")
        else:
            self.msg(channel, "Login to Funimation failed, but will automatically retry until it works.")

    else:
        self.msg(channel, "ERROR 634: How the fuck did this happen?")
