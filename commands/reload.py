config = {
    "access": "owner",
    "help": ".reload [modules] (--blacklist) || .reload commands || Reloads specified modules",
    "reversible": False
}

def command(guid, manager, irc, channel, user, modules, blacklist = False):
    yield manager.master.loadModules(modules.split(" "), blacklist)
    irc.msg(channel, u"Modules reloaded")
