# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

dependencies = []

class Shard(object):
    def __init__(self, master, name):
        self.master = master
        self.name = name

    def get(self, key, default=None):
        return self.master.modules["config"].get("{}_{}".format(self.name, key), default)

    def set(self, key, value):
        return self.master.modules["config"].set("{}_{}".format(self.name, key), value)

class Module(object):
    def __init__(self, master):
        self.master = master
        self.db = master.db.config

    def stop(self):
        pass

    @inlineCallbacks
    def get(self, key, default=None):
        result = yield self.db.find_one({"_id": key})
        returnValue(result["value"] if result else default)

    @inlineCallbacks
    def set(self, key, value):
        try:
            result = yield self.db.save({"_id": key, "value": value}, safe=True)
        except:
            self.log.err("Failed to save {} = {!r}".format(key, value))
            returnValue(False)
        else:
            returnValue(True)

    def interface(self, name):
        return Shard(self.master, name)
