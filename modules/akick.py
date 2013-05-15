# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks

dependencies = ["config", "irc"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("akick")

    def stop(self):
        pass

    @inlineCallbacks
    def irc_join(self, channel, user):
        irc = self.master.modules["irc"]
        akicks = yield self.config.get("users", {})

        if channel in akicks and user in akicks[channel]:
            irc.kickban(channel, user, u"pls go an stay go")

    @inlineCallbacks
    def add(self, channel, user):
        irc = self.master.modules["irc"]
        akicks = yield self.config.get("users", {})

        if channel not in akicks:
            akicks[channel] = []

        akicks[channel].append(user)

        yield self.config.set("users", akicks)

        if channel in irc.channels and user in irc.channels[channel]:
            irc.kickban(channel, user, u"pls go an stay go")

    @inlineCallbacks
    def remove(self, channel, user):
        akicks = yield self.config.get("users", {})

        if channel not in akicks:
            return

        akicks[channel].remove(user)

        if not akicks[channel]:
            del akicks[channel]

        yield self.config.set("users", akicks)
