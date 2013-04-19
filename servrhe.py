#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Actual bot stuff
from twisted.enterprise import adbapi
from twisted.internet import reactor, protocol, task, defer
from twisted.words.protocols import irc
from lib.config import Config
from lib.pluginmanager import PluginManager
from lib.alias import Aliases
from lib.markov import Markov
from lib.utils import log, fetchPage, normalize
import urllib, json, datetime

class Servrhe(irc.IRCClient):
    nickname = "ServrheV3"
    versionName = "Servrhe (Custom Bot)"
    versionNum = "1.0"
    versionEnv = "Twisted-Python"
    sourceURL = "https://github.com/Fugiman/Servrhe"
    lineRate = 0.400 # 400ms between messages. Because JDP tried to flood-kick the bot.
    admins = {}
    
    # Bot maintenance
    def signedOn(self):
        print("Connected!")
        self.msg("NickServ","IDENTIFY %s" % self.factory.config.password)
        self.factory.resetDelay()
        self.factory.protocols.append(self)
        for c in self.factory.config.channels:
            self.join(str(c))
    
    def connectionLost(self, reason=None):
        print("Disconnected!")
        self.factory.protocols.remove(self)

    def getPermissions(self, user):
        permissions = ["public"]
        if user.lower() in self.admins and self.admins[user.lower()]:
            permissions.append("admin")
            if user.lower() == "fugiman":
                permissions.append("owner")
        return permissions

    def getPosition(self, given):
        base = given.replace("ing","").replace("or","").replace("er","")
        for perm in ("or","er"):
            if base+perm in self.factory.config.positions:
                return base+perm
        return None

    def isAdmin(self, alias):
        for name in self.admins.keys():
            if alias == self.factory.alias.resolve(name):
                return True
        return False

    def privmsg(self, hostmask, channel, msg):
        user = hostmask.split("!", 1)[0]
        channel = channel if channel != self.nickname else user
        if not msg.startswith("."): # not a trigger command
            alias = self.factory.alias.resolve(user)
            self.factory.markov.learn(alias, msg)
            return # do nothing
        command, sep, rest = msg.lstrip(".").partition(" ")
        command, msg, reverse = command.lower(), filter(lambda x: x, rest.split(" ")), False
        if command not in self.factory.pluginmanager.plugins and command[:2] == "un" and command[2:] in self.factory.pluginmanager.plugins:
            command = command[2:]
            reverse = True
            if not self.factory.pluginmanager.plugins[command]["reversible"]:
                return
        permissions = self.getPermissions(user)
        if command in self.factory.pluginmanager.plugins and self.factory.pluginmanager.plugins[command]["access"] in permissions:
            log(user, channel, command, msg, reverse)
            if not self.factory.pluginmanager.plugins[command]["reversible"]:
                self.factory.pluginmanager.plugins[command]["command"](self, user, channel, msg)
            else:
                self.factory.pluginmanager.plugins[command]["command"](self, user, channel, msg, reverse)
        else:
            alias = self.factory.alias.resolve(command)
            if alias in self.factory.markov.users and "markov" in self.factory.pluginmanager.plugins:
                msg = [alias] + msg
                self.factory.pluginmanager.plugins["markov"]["command"](self, user, channel, msg)

    def msg(self, channel, message):
        irc.IRCClient.msg(self, channel, normalize(message))

    def notice(self, user, message):
        irc.IRCClient.notice(self, user, normalize(message))

    def userJoined(self, user, channel):
        if channel.lower() == "#commie-staff":
            self.admins[user.lower()] = False

    def userLeft(self, user, channel):
        if channel.lower() == "#commie-staff":
            del self.admins[user.lower()]

    def userQuit(self, user, msg):
        if user.lower() in self.admins:
            del self.admins[user.lower()]

    def userKicked(self, user, channel, kicker, msg):
        if channel.lower() == "#commie-staff":
            del self.admins[user.lower()]

    def userRenamed(self, old, new):
        if old.lower() in self.admins:
            self.admins[new.lower()] = self.admins[old.lower()]
            del self.admins[old.lower()]
            self.factory.alias.add(old, new)

    def irc_RPL_NAMREPLY(self, prefix, params):
        _, _, channel, users = params
        users = users.split(" ")
        if channel.lower() == "#commie-staff":
            for user in users:
                rank, name = user[0], user[1:]
                if rank not in "~&@%+":
                    rank, name = "", user
                if rank == "&":
                    self.admins[name.lower()] = True
                else:
                    self.admins[name.lower()] = False

    def modeChanged(self, user, channel, set, modes, args):
        if channel.lower() == "#commie-staff":
            # "aqohv"
            for mode, name in zip(modes, args):
                if mode == "a":
                    self.admins[name.lower()] = set
    
class ServrheFactory(protocol.ReconnectingClientFactory):
    # Protocol config
    protocol = Servrhe
    maxDelay = 5 * 60 # 5 minutes
    protocols = []
    shows = {}
    
    def __init__(self):
        self.config = Config("servrhe.json", {
            # Bot config
            "password": "",
            "channels": ["#commie-subs","#commie-staff"],
            "notifies": {},
            "premux_dir": "",
            # Release config
            "rip_host": "",
            "ftp_host": "",
            "ftp_port": 21,
            "ftp_user": "",
            "ftp_pass": "",
            "ftp_encode_dir": "",
            "xdcc_host": "",
            "xdcc_port": 21,
            "xdcc_user": "",
            "xdcc_pass": "",
            "xdcc_folder": "",
            "seed_host": "",
            "seed_port": 21,
            "seed_user": "",
            "seed_pass": "",
            "seed_file_folder": "",
            "seed_torrent_folder": "",
            "nyaa_user": "",
            "nyaa_pass": "",
            "tt_user": "",
            "tt_pass": "",
            "blog_user": "",
            "blog_pass": "",
            "mal_user": "",
            "mal_pass": "",
            # Showtime config
            "key": "",
            "base": "http://commie.milkteafuzz.com/st",
            "positions": ["translator","editor","typesetter","timer","encoding"],
            # Topic config
            "topic": ["☭ Commie Subs ☭",20,20.56],
            # Database
            "db_library": "",
            "db_host": "",
            "db_port": "",
            "db_database": "",
            "db_user": "",
            "db_pass": ""
        })
        self.pluginmanager = PluginManager("commands")
        self.db = adbapi.ConnectionPool(self.config.db_library, host=self.config.db_host, port=self.config.db_port, db=self.config.db_database, user=self.config.db_user, passwd=self.config.db_pass, cp_reconnect=True)
        self.alias = Aliases("alias.json")
        self.markov = Markov(self.db, self.alias)
        reactor.addSystemEventTrigger("before", "shutdown", self.shutdown)
        t = task.LoopingCall(self.refresh_shows)
        t.start(5*60) # 5 minutes
        n = task.LoopingCall(self.check_notifies)
        n.start(30) # Every 30 seconds
    
    def broadcast(self, message):
        if self.protocols:
            self.protocols[0].msg("#commie-staff", message)
    
    def load(self, *params, **kwargs):
        url = "/".join([self.config.base]+[str(x) for x in params])
        url = urllib.quote(url.encode("utf-8","ignore"),"/:")
        headers = {}
        data = ""
        if "data" in kwargs:
            d = kwargs["data"]
            d["key"] = self.config.key
            data = json.dumps(d)
            headers["Content-Type"] = ["application/json"]
        d = fetchPage(url, data, headers)
        d.addCallback(json.loads)
        return d
    
    @defer.inlineCallbacks
    def refresh_shows(self):
        data = yield self.load("shows")
        if "status" in data and not data["status"]:
            self.broadcast(data["message"])
            return
        data = data["results"]
        for show in data:
            self.shows[show["id"]] = show
    
    def resolve(self, show, channel):
        matches = []
        if not show:
            self.protocols[0].msg(channel, "Show name not specified.")
            return None
        for s in self.shows.itervalues():
            if (s["series"].lower() == show.lower() or s["abbr"].lower() == show.lower()):
                return s
            if s["series"].lower().count(show.lower()):
                matches.append(s)
        if len(matches) > 1:
            r = [s["series"] for s in matches]
            if len(r) > 5:
                extra = "and {:d} more.".format(len(r) - 5)
                r = r[:5] + [extra]
            self.protocols[0].msg(channel, "Show name not specific, found: %s" % ", ".join(r))
            return None
        elif not matches:
            self.protocols[0].msg(channel, "Show name not found.")
            return None
        return matches[0]
    
    @defer.inlineCallbacks
    def update_topic(self):
        shows = yield self.load("shows","current_episodes")
        shows = [(s["abbr"], s["current_ep"], s["last_release"]) for s in shows["results"]]
        shows.sort(key=lambda x: x[2], reverse=True)
        shows = ", ".join(["{} {:d}".format(s[0],s[1]) for s in shows[:self.config.topic[1]]])
        topic = " || ".join([self.config.topic[0], shows, "Mahoyo progress: {:0.2f}%".format(self.config.topic[2])] + self.config.topic[3:])
        self.protocols[0].topic("#commie-subs", normalize(topic))

    def check_notifies(self):
        dt = datetime.datetime
        now = dt.utcnow()
        shows = []
        for show in self.shows.itervalues():
            if show["current_ep"] == show["total_eps"]:
                continue
            diff = dt.utcfromtimestamp(show["airtime"]) - now
            if 0 <= diff.total_seconds() < 30:
                shows.append(show["id"])
        for id in shows:
            ping = []
            if id in self.config.notifies:
                ping.extend(self.config.notifies[id].keys())
                for k, v in self.config.notifies[id].items():
                    if v > 0:
                        if v == 1:
                            del self.config.notifies[id][k]
                        else:
                            self.config.notifies[id][k] = v - 1
            if "*" in self.config.notifies:
                ping.extend(self.config.notifies["*"].keys())
                for k, v in self.config.notifies["*"].items():
                    if v > 0:
                        if v == 1:
                            del self.config.notifies["*"][k]
                        else:
                            self.config.notifies["*"][k] = v - 1
            if ping:
                self.broadcast("{}: {} has aired on {}".format(", ".join(ping), self.shows[id]["series"], self.shows[id]["channel"]))


    def shutdown(self):
        self.config.save()
        self.alias.save()
    
if __name__ == "__main__":
    factory = ServrheFactory()
    reactor.connectTCP("irc.rizon.net", 6667, factory)
    reactor.run()
