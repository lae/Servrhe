# -*- coding: utf-8 -*-

from twisted.internet import reactor

dependencies = []

class Module(object):
    def __init__(self, master):
        self.master = master
        self.profile = {}
        self.running = {}

    def stop(self):
        pass

    def commands_start(self, name, guid, *args):
        self.running[guid] = {"name": "command_{}".format(name), "start": reactor.seconds()}

    def commands_finish(self, guid):
        if guid not in self.running:
            return
        data = self.running[guid]
        name, start = data["name"], data["start"]
        del self.running[guid]
        if name not in self.profile:
            self.profile[name] = {"time": 0, "calls": 0}
        self.profile[name]["calls"] += 1
        self.profile[name]["time"] += reactor.seconds() - start
        self.dispatch("update", name, self.profile[name]["time"], self.profile[name]["calls"])
