# -*- coding: utf-8 -*-

from collections import namedtuple
from bs4 import UnicodeDammit
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.words.protocols.irc import IRCClient

dependencies = ["config"]

def normalize(s):
    try:
        u = UnicodeDammit.detwingle(s).decode("utf8")
    except:
        u = UnicodeDammit(s, ["utf8", "windows-1252"]).unicode_markup
    return u

class Module(IRCClient):
    """
    Handles the IRC interface for the bot.

    PROPERTIES
    ranks - standardizes the ranking of users in channels
    channels - contains all channels the bot is in, as well as the users and their rank

    EVENTS
    connected - Bot connected to server
    disconnected - Bot disconnected from server
    joined - Bot joined a channel
    left - Bot left a channel
    kicked - Bot was kicked from a channel
    sent_message - Bot sent a message
    sent_notice - Bot sent a notice

    join - User joined a channel
    part - User left a channel
    kick - User was kicked from a channel
    message - Either channel or private message
    notice - Any notices sent to the bot
    action - A user used /me
    rename - A user changed their nick
    mode - A user's mode changed

    topic - A channel's topic changed
    motd - The server's MOTD
    """
    connected = False
    lineRate = 0.400
    nick_check = None
    performLogin = 0
    ranks = namedtuple("Rank",["DEFAULT","VOICE","HOP","OP","ADMIN","OWNER"])._make(range(6))
    sourceURL = "https://github.com/Fugiman/Servrhe"
    versionEnv = "Twisted-Python"
    versionName = "Servrhe (Custom Bot)"
    versionNum = "1.0"

    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("irc")

    def stop(self):
        if self.connected:
            self.transport.loseConnection()

    # Connection Handling
    @inlineCallbacks
    def connectionMade(self):
        self.connected = True
        IRCClient.connectionMade(self)
        nick = yield self.config.get("nick", "ServrheV4")
        self.register(nick.encode("utf8"))
        self.dispatch("connected")

    @inlineCallbacks
    def signedOn(self):
        password = yield self.config.get("pass")
        if password:
            self.msg("NickServ","IDENTIFY {}".format(password.encode("utf8")))
        self.factory.resetDelay()
        self.factory.connection = self
        self.nick_check = LoopingCall(self.nickCheck)
        self.nick_check.start(60)
        channels = yield self.config.get("channels", [u"#commie-subs"])
        self.channels = {}
        for c in channels:
            self.join(c)
    
    def connectionLost(self, reason=None):
        self.connected = False
        self.factory.connection = None
        self.channels = {}
        if self.nick_check:
            self.nick_check.stop()
            self.nick_check = None
        self.dispatch("disconnected")

    # Force nick to be that of the config
    @inlineCallbacks
    def nickCheck(self):
        nick = yield self.config.get("nick")
        if nick and nick != self.nickname:
            self.setNick(nick.encode("utf8"))

    # Bubble message handling
    def privmsg(self, hostmask, channel, message):
        user = hostmask.split("!", 1)[0]
        channel = channel if channel != self.nickname else user

        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("message", channel, user, message)

    def noticed(self, hostmask, channel, message):
        user = hostmask.split("!", 1)[0]
        channel = channel if channel != self.nickname else user

        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("notice", channel, user, message)

    def kickedFrom(self, channel, kicker, message):
        kicker = normalize(kicker)
        channel = normalize(channel)
        message = normalize(message)

        if channel not in self.channels:
            return

        del self.channels[channel]
        self.config.set("channels", self.channels.keys())
        self.dispatch("kicked", channel, kicker, message)

    def action(self, user, channel, message):
        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("action", channel, user, message)

    def topicUpdated(self, user, channel, message):
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("topic", channel, message)

    def receivedMOTD(self, motd):
        motd = "".join([l.rstrip() for l in motd])
        motd = normalize(motd)

        self.dispatch("motd", motd)

    # Convience methods
    def msg(self, channel, message):
        IRCClient.msg(self, channel.encode("utf8"), message.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("sent_message", channel, nick, message)

    def notice(self, user, message):
        IRCClient.notice(self, user.encode("utf8"), message.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("sent_notice", user, nick, message)

    def kickban(self, channel, user, reason=None):
        if not reason:
            reason = user
        self.mode(channel.encode("utf8"), True, "b", mask="{}!*@*".format(user.encode("utf8")))
        self.kick(channel.encode("utf8"), user.encode("utf8"), reason.encode("utf8"))

    @inlineCallbacks
    def join(self, channel):
        passwords = yield self.config.get("passwords")
        actual, _, password = channel.partition(" ")

        if password:
            passwords[channel] = password
        elif actual in passwords:
            channel = "{} {}".format(actual, passwords[actual])

        self.channels[actual] = {}
        self.config.set("channels", self.channels.keys())
        self.config.set("passwords", passwords)

        IRCClient.join(self, channel.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("joined", actual, nick)

    def leave(self, channel):
        if channel not in self.channels:
            return
        del self.channels[channel]
        self.config.set("channels", self.channels.keys())
        IRCClient.leave(self, channel.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("left", channel, nick)

    # Channel tracking
    def userJoined(self, user, channel):
        user = normalize(user)
        channel = normalize(channel)
        self.channels[channel][user] = self.ranks.DEFAULT
        self.dispatch("join", channel, user)

    def userLeft(self, user, channel):
        user = normalize(user)
        channel = normalize(channel)
        del self.channels[channel][user]
        self.dispatch("part", channel, user)

    def userQuit(self, user, message):
        user = normalize(user)
        for name, channel in self.channels.items():
            if user in channel:
                del channel[user]
                self.dispatch("part", name, user)

    def userKicked(self, user, channel, kicker, message):
        user = normalize(user)
        channel = normalize(channel)
        kicker = normalize(kicker)
        message = normalize(message)
        del self.channels[channel][user]
        self.dispatch("kick", channel, user, kicker, message)

    def userRenamed(self, old, new):
        old = normalize(old)
        new = normalize(new)
        for channel in self.channels.values():
            if old in channel:
                channel[new] = channel[old]
                del channel[old]
        self.dispatch("rename", old, new)

    def irc_RPL_NAMREPLY(self, prefix, params):
        _, _, channel, users = params
        channel = normalize(channel)
        users = users.split(" ")
        ranks = {
            "~": self.ranks.OWNER,
            "&": self.ranks.ADMIN,
            "@": self.ranks.OP,
            "%": self.ranks.HOP,
            "+": self.ranks.VOICE,
            "": self.ranks.DEFAULT
        }
        for user in users:
            rank, name = user[0], user[1:]
            if rank not in "~&@%+":
                rank, name = "", user
            name = normalize(name)
            self.channels[channel][name] = ranks[rank]
            self.dispatch("mode", channel, name, self.channels[channel][name])

    def modeChanged(self, user, channel, added, modes, args):
        channel = normalize(channel)
        if not channel.startswith("#"):
            return

        ranks = {
            "q": self.ranks.OWNER,
            "a": self.ranks.ADMIN,
            "o": self.ranks.OP,
            "h": self.ranks.HOP,
            "v": self.ranks.VOICE
        }
        for mode, name in zip(modes, args):
            if mode not in ranks:
                continue
            name = normalize(name)
            rank = ranks[mode]
            currank = self.channels[channel][name]
            if added and rank > currank:
                self.channels[channel][name] = rank
            if not added and rank == currank:
                self.channels[channel][name] = self.ranks.DEFAULT
            if self.channels[channel][name] != currank:
                self.dispatch("mode", channel, name, self.channels[channel][name])
