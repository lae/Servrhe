import pkgutil

class PluginManager(object):
    def __init__(self, path):
        self.path = path
        self.load()

    def load(self):
        self.plugins = {}
        for loader, name, ispkg in pkgutil.iter_modules([self.path]):
            if ispkg:
                continue
            try:
                plugin = getattr(__import__(self.path, fromlist=[name]), name)
                reload(plugin)
                plugin.config["name"] = name
                plugin.config["command"] = plugin.command
                if "disabled" in plugin.config and plugin.config["disabled"]:
                    continue
                self.plugins[name] = plugin.config
            except:
                print "WARNING: Failed to import {}.{}!".format(self.path, name)
