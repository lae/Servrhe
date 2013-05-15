# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from collections import namedtuple
from datetime import datetime as dt
import json, urllib

dependencies = ["config", "commands", "utils", "irc"]

NameObject = namedtuple("NameObject", ["english", "japanese", "abbreviation"])
EpisodeObject = namedtuple("EpisodeObject", ["current", "total"])
FolderObject = namedtuple("FolderObject", ["ftp", "xdcc"])
PositionObject = namedtuple("PositionObject", ["name", "done"])
ShowObject = namedtuple("ShowObject", ["id", "name", "episode", "folder", "translator", "editor", "timer", "typesetter", "qc", "channel", "airtime", "updated", "released", "blog"])

SubstatusObject = namedtuple("SubstatusObject", ["position", "name", "episode", "updated"])

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("showtimes")
        self.shows = {}
        self.show_loop = LoopingCall(self.refreshShows)
        self.show_loop.start(180)
        self.notify_loop = LoopingCall(self.checkNotifications)
        self.notify_loop.start(30)

    def stop(self):
        if self.show_loop is not None and self.show_loop.running:
            self.show_loop.stop()
            self.show_loop = None
        if self.notify_loop is not None and self.notify_loop.running:
            self.notify_loop.stop()
            self.notify_loop = None

    @inlineCallbacks
    def load(self, *params, **kwargs):
        exception = self.master.modules["commands"].exception
        base = yield self.config.get("endpoint")
        url = "/".join([base.encode("utf-8")] + [unicode(x).encode("utf-8") for x in params])
        url = urllib.quote(url,"/:")
        headers = {}
        data = ""
        if "data" in kwargs:
            d = kwargs["data"]
            d["key"] = yield self.config.get("key")
            data = json.dumps(d)
            headers["Content-Type"] = ["application/json"]
        body = yield self.master.modules["utils"].fetchPage(url, data, headers)
        data = json.loads(body)
        if "status" in data and not data["status"]:
            raise exception(u"Error in showtimes API call: {}".format(data["message"]))
        returnValue(data["results"])

    @inlineCallbacks
    def refreshShows(self):
        data = yield self.load("shows")
        for show in data:
            name = NameObject(show["series"], show["series_jp"], show["abbr"])
            episode = EpisodeObject(show["current_ep"], show["total_eps"])
            folder = FolderObject(show["folder"], show["xdcc_folder"])
            translator = PositionObject(show["translator"], show["tl_status"])
            editor = PositionObject(show["editor"], show["ed_status"])
            timer = PositionObject(show["timer"], show["tm_status"])
            typesetter = PositionObject(show["typesetter"], show["ts_status"])
            qc = PositionObject(show["qc"], show["qc_status"])
            self.shows[show["id"]] = ShowObject(show["id"], name, episode, folder, translator, editor, timer, typesetter, qc, show["channel"], show["airtime"], show["updated"], show["last_release"], show["blog_link"])

    def resolve(self, name):
        exception = self.master.modules["commands"].exception
        matches = []
        if not name:
            raise exception(u"Show name not specified.")
        name = name.lower()
        for s in self.shows.values():
            if s.name.english.lower() == name or s.name.abbreviation.lower() == name:
                return s
            if s.name.english.lower().count(name):
                matches.append(s)
        if len(matches) > 1:
            r = [s.name.english for s in matches]
            if len(r) > 5:
                extra = "and {:d} more.".format(len(r) - 5)
                r = r[:5] + [extra]
            raise exception(u"Show name not specific, found: {}".format(u", ".join(matches)))
        elif not matches:
            raise exception(u"Show name not found.")
        return matches[0]

    @inlineCallbacks
    def getPosition(self, given):
        exception = self.master.modules["commands"].exception
        positions = yield self.config.get("positions")
        base = given.replace("ing","").replace("or","").replace("er","")

        for perm in ("","or","er"):
            if base+perm in positions:
                returnValue(base+perm)

        raise exception(u"Invalid position given. Valid positions are: {}".format(u", ".join(positions)))

    @inlineCallbacks
    def updateTopic(self):
        topic = yield self.config.get("topic", {"percentage": 0, "text": None})
        parts = [u"\u000308,04\u262d Commie Subs \u262d\u000f"]
        releases = []

        for show in self.shows.values():
            if show.episode.current < show.episode.total:
                releases.append((show.name.abbreviation, show.episode.current, show.released))
        releases.sort(key=lambda x: x[2], reverse=True)

        parts.append(u", ".join(["{} {:02d}".format(r[0], r[1]) for r in releases[:8]]))
        parts.append(u"Mahoyo progress: {:0.2f}%".format(topic["percentage"]))

        if topic["text"] is not None:
            parts.append(topic["text"])

        final = u" || ".join(parts)
        self.master.modules["irc"].topic("#commie-subs", final.encode("utf8"))

    @inlineCallbacks
    def setPercentage(self, percentage):
        topic = yield self.config.get("topic", {"percentage": 0, "text": None})
        topic["percentage"] = percentage
        yield self.config.set("topic", topic)

    @inlineCallbacks
    def setTopic(self, text):
        topic = yield self.config.get("topic", {"percentage": 0, "text": None})
        topic["text"] = text
        yield self.config.set("topic", topic)

    @inlineCallbacks
    def aired(self):
        data = yield self.load("shows", "aired")
        shows = [self.shows[d["id"]] for d in data]
        returnValue(shows)

    @inlineCallbacks
    def substatus(self, show):
        data = yield self.load("show", show.id, "substatus")
        updated = show.airtime + 30*60 if data["position"] in ["encoder","translator"] else data["updated"]
        o = SubstatusObject(data["position"], data["value"], data["episode"], updated)
        returnValue(o)

    @inlineCallbacks
    def assign(self, show, position, name):
        data = {
            "id": show.id,
            "method": "position",
            "position": position,
            "value": name
        }
        yield self.load("show", "update", data=data)

    @inlineCallbacks
    def done(self, show, position):
        data = {
            "id": show.id,
            "method": "position_status",
            "position": position,
            "value": "1"
        }
        yield self.load("show", "update", data=data)

    @inlineCallbacks
    def undone(self, show, position):
        data = {
            "id": show.id,
            "method": "position_status",
            "position": position,
            "value": "0"
        }
        yield self.load("show", "update", data=data)


    @inlineCallbacks
    def finished(self, show):
        data = {
            "id": show.id,
            "method": "next_episode"
        }
        yield self.load("show", "update", data=data)

    @inlineCallbacks
    def unfinished(self, show):
        data = {
            "id": show.id,
            "method": "restart_last_episode"
        }
        yield self.load("show", "update", data=data)

    @inlineCallbacks
    def notify(self, id, user, duration):
        exception = self.master.modules["commands"].exception
        notifications = yield self.config.get("notifications", {})

        if id != "*":
            show = self.shows[id]
            name = show.name.english
            now = dt.utcnow()
            diff = dt.utcfromtimestamp(show.airtime) - now
            extra = " (airs in {} on {})".format(self.master.modules["utils"].dt2ts(diff), show.channel)
        else:
            name = "everything"
            extra = ""

        if id not in notifications:
            notifications[id] = {}

        if duration:
            notifications[id][user] = duration
            yield self.config.set("notifications", notifications)
            raise exception(u"You'll now be notified for {}{}".format(name, extra))

        elif user in notifications[id]:
            del notifications[id][user]

            if not notifications[id]:
                del notifications[id]

            yield self.config.set("notifications", notifications)
            raise exception(u"You'll no longer be notified for {}".format(name))

        else:
            if not notifications[id]:
                del notifications[id]

            yield self.config.set("notifications", notifications)
            raise exception(u"You already weren't being notified for {}".format(name))

    @inlineCallbacks
    def checkNotifications(self):
        notifications = yield self.config.get("notifications", {})
        now = dt.utcnow()
        shows = []

        for show in self.shows.values():
            if show.episode.current == show.episode.total:
                continue

            diff = dt.utcfromtimestamp(show.airtime) - now
            if 0 <= diff.total_seconds() < 30:
                shows.append(show.id)

        for id in shows:
            ping = []
            if id in notifications:
                ping.extend(notifications[id].keys())
                for k, v in notifications[id].items():
                    if v > 0:
                        if v == 1:
                            del notifications[id][k]
                        else:
                            notifications[id][k] = v - 1
            if "*" in notifications:
                ping.extend(notifications["*"].keys())
                for k, v in notifications["*"].items():
                    if v > 0:
                        if v == 1:
                            del notifications["*"][k]
                        else:
                            notifications["*"][k] = v - 1
            if ping:
                show = self.shows[id]
                self.master.modules["irc"].msg("#commie-staff", "{}: Episode {:d} of {} has aired on {}".format(", ".join(ping), show.episode.current + 1, show.name.english, show.channel))

        yield self.config.set("notifications", notifications)
