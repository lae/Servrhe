#!/usr/bin/env python
# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
from lib.crunchy import spliceContents
import datetime

config = {
    "access": "admin",
    "help": ".cr [subcommand] ... || .cr help || Everything Crunchyroll (use .cr help for more)",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    if not msg:
        self.msg(channel, config["help"])
        return

    subcommands = ("rip", "autorip", "list", "info", "config", "reload", "login", "delete")
    command = msg[0].lower()

    if command not in subcommands:
        self.msg(channel, "Available subcommands are: {}. Use .cr [subcommand] for their use".format(", ".join(subcommands)))
        return

    if command == "rip":
        if len(msg) < 5:
            self.msg(channel, ".cr rip [contents] [quality] [episode] [series] || Contents is subs, video or both. Quality is 360, 480, 720, or 1080. Series uses CR's naming")
            return

        contents, quality, episode, series = msg[1], msg[2], msg[3], " ".join(msg[4:])
        success, series = self.factory.crunchy.resolve(series)

        if contents not in ("subs","video","both"):
            self.msg(channel, "Invalid content, must be subs, video or both")

        if quality not in ("360", "480", "720", "1080"):
            self.msg(channel, "Invalid quality, must be 360, 480, 720, or 1080")
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
        if key not in self.factory.crunchy.data["shows"][series]:
            self.msg(channel, "No data for that episode, try again when CR has added it")
            return

        show = self.factory.crunchy.data["shows"][series][key]
        subs = contents in ("subs", "both")
        video = contents in ("video", "both")
        success = yield self.factory.crunchy.rip(show, quality, video, subs, lambda x: self.notice(user, x))
        self.msg(channel, "Ripping of {} {:02d} [{}p] was {}".format(series.encode("utf8"), episode, quality, "successful" if success else "unsuccessful"))

    elif command == "autorip":
        if len(msg) < 4:
            self.msg(channel, ".cr autorip [contents] [quality] [series] || Contents is subs, video or both. Quality is 360, 480, 720, or 1080. Series uses CR's naming")
            return

        contents, quality, series = msg[1], msg[2], " ".join(msg[3:])
        success, series = self.factory.crunchy.resolve(series)

        if contents not in ("subs","video","both"):
            self.msg(channel, "Invalid content, must be subs, video or both")

        if quality not in ("360", "480", "720", "1080"):
            self.msg(channel, "Invalid quality, must be 360, 480, 720, or 1080")
            return

        if not success:
            self.msg(channel, series)
            return

        subs = contents in ("subs", "both")
        video = contents in ("video", "both")
        self.factory.crunchy.data["auto_downloads"][series] = {
            "quality": quality,
            "video": video,
            "subs": subs,
            "downloaded": sorted(self.factory.crunchy.data["shows"][series].keys())
        }

        contents = spliceContents(video, subs)
        self.msg(channel, "Set {} to autorip {} at {}p. You won't really know if it works though. ┐(￣ー￣)┌".format(series.encode("utf8"), contents, quality))

    elif command == "list":
        if len(msg) < 2:
            self.msg(channel, ".cr list series || .cr list episodes [series] || .cr list autodownloads || Either lists known series, or known episodes for a series. Series uses CR's naming")
            return

        subcommand = msg[1].lower()

        if subcommand == "series":
            self.msg(channel, ", ".join(sorted(self.factory.crunchy.data["shows"].keys())))

        elif subcommand == "episodes":
            if len(msg) < 3:
                self.msg(channel, ".cr list episodes [series] || You forgot the series name, try again.")
                return

            series = " ".join(msg[2:])
            success, series = self.factory.crunchy.resolve(series)

            if not success:
                self.msg(channel, series)
                return

            self.msg(channel, ", ".join(sorted(self.factory.crunchy.data["shows"][series].keys())))

        elif subcommand == "autodownloads":
            data = self.factory.crunchy.data["auto_downloads"]
            self.msg(channel, ", ".join(["{} for {} at {}p".format(spliceContents(data[k]["video"], data[k]["subs"]), k.encode("utf8"), data[k]["quality"]) for k in sorted(data.keys())]))

        else:
            self.msg(channel, ".cr list series || .cr list episodes [series] || .cr list autodownloads || Those are your only three options, stop trying to be a special snowflake.")

    elif command == "info":
        if len(msg) < 3:
            self.msg(channel, ".cr info [episode] [series] || Gives you data on an episode. Series uses CR's naming")
            return

        episode, series = msg[1], " ".join(msg[2:])
        success, series = self.factory.crunchy.resolve(series)

        try:
            episode = int(episode)
        except:
            self.msg(channel, "Invalid episode number, must be an integer")
            return

        if not success:
            self.msg(channel, series)
            return

        key = "{:02d}".format(episode)
        if key not in self.factory.crunchy.data["shows"][series]:
            self.msg(channel, "No data for that episode, try again when CR has added it")
            return

        data = self.factory.crunchy.data["shows"][series][key]

        now = datetime.datetime.utcnow()
        airtime = datetime.datetime.utcfromtimestamp(data["airtime"])
        if now > airtime:
            airing = "aired {} ago".format(dt2ts(now - airtime))
        else:
            airing = "airs in {}".format(dt2ts(airtime - now))

        self.msg(channel, "{} {:02d}, \"{}\", {} with a duration of {}. CR ID = {}.".format(series.encode("utf8"), episode, data["title"], airing, data["duration"], data["media_id"]))

    elif command == "config":
        if len(msg) < 2:
            self.msg(channel, ".cr config save || .cr config load || Saves or loads the config file")
            return

        subcommand = msg[1].lower()

        if subcommand == "load":
            self.factory.crunchy.load()
            self.msg(channel, "CR config loaded")

        elif subcommand == "save":
            self.factory.crunchy.save()
            self.msg(channel, "CR config saved")

        else:
            self.msg(channel, ".cr config save || .cr config load || Is it really that hard?")

    elif command == "reload":
        self.notice(user, "Starting caching")
        yield self.factory.crunchy.cache()
        self.msg(channel, "Crunchyroll data reloaded")

    elif command == "login":
        yield self.factory.crunchy.login()
        self.msg(channel, "Logged in to Crunchyroll")

    elif command == "delete":
        if not "owner" in self.getPermissions(user):
            self.msg(channel, "Insufficient permissions. Only the owner can use this command")
            return

        if len(msg) < 3:
            self.msg(channel, ".cr delete [episode] [series] || Deletes an episode from the cache, Series uses CR's naming")
            return

        key, series = msg[1], " ".join(msg[2:])
        success, series = self.factory.crunchy.resolve(series)

        try:
            key = "{:02d}".format(int(key))
        except:
            self.notice(user, "Episode was not an integer, assuming it was the exact key.")

        if not success:
            self.msg(channel, series)
            return

        if key not in self.factory.crunchy.data["shows"][series]:
            self.msg(channel, "No data for that episode, try again when CR has added it")
            return

        del self.factory.crunchy.data["shows"][series][key]
        self.msg(channel, "{} #{} deleted from Crunchyroll cache".format(series.encode("utf8"), key))

    else:
        self.msg(channel, "ERROR 634: How the fuck did this happen?")
