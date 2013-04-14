from twisted.internet.defer import inlineCallbacks

config = {
    "access": "admin",
    "help": ".refresh || .refresh || Refresh show cache",
    "reversible": False
}

@inlineCallbacks
def command(self, user, channel, msg):
    yield self.factory.refresh_shows()
    self.msg(channel, "Show cache refreshed")
