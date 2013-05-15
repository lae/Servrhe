# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.task import LoopingCall
import inspect, os, pkgutil, shutil, uuid

dependencies = ["config", "alias", "irc"]

class CommandException(Exception):
    pass

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("commands")
        self.admins = {}
        self.commands = {}
        self.exception = CommandException
        self.loadCommands()
        self._admin_cache = LoopingCall(self.cache_admins)
        self._admin_cache.start(60)

    def stop(self):
        if self._admin_cache is not None and self._admin_cache.running:
            self._admin_cache.stop()
            self._admin_cache = None

    @inlineCallbacks
    def getPermissions(self, user):
        irc = self.master.modules["irc"]
        alias = yield self.master.modules["alias"].resolve(user)
        permissions = ["public"]
        if "#commie-staff" in irc.channels and user in irc.channels["#commie-staff"]:
            permissions.append("staff")
            rank = irc.channels["#commie-staff"][user]
            if rank >= irc.ranks.ADMIN:
                permissions.append("admin")
            for perm, users in self.admins.items():
                if alias in users:
                    permissions.append(perm)
        returnValue(permissions)

    def getGUID(self):
        guid = uuid.uuid4().hex
        while os.path.exists(guid):
            guid = uuid.uuid4().hex
        os.mkdir(guid)
        return guid

    @inlineCallbacks
    def cache_admins(self):
        self.admins = yield self.config.get("admins", {})

    @inlineCallbacks
    def loadCommands(self):
        commands = {}
        path = yield self.config.get("path","commands_2")
        for loader, name, ispkg in pkgutil.iter_modules([path]):
            if ispkg:
                continue
            try:
                command = getattr(__import__(path, fromlist=[name.encode("utf8")]), name)
                reload(command)
                command.config["name"] = name
                command.config["command"] = inlineCallbacks(command.command) if inspect.isgeneratorfunction(command.command) else command.command
                args, _, _, kwargs = inspect.getargspec(command.command)

                if args[:5] != ["guid", "manager", "irc", "channel", "user"]:
                    continue

                if kwargs:
                    boundary = -1 * len(kwargs)
                    command.config["args"] = args[5:boundary]
                    command.config["kwargs"] = args[boundary:]
                else:
                    command.config["args"] = args[5:]
                    command.config["kwargs"] = []

                if "disabled" in command.config and command.config["disabled"]:
                    continue

                commands[name] = command.config
            except:
                self.err("Failed to load {}.{}", path, name)
        self.commands = commands

    @inlineCallbacks
    def irc_message(self, channel, user, message):
        perms = yield self.getPermissions(user)
        irc = self.master.modules["irc"]

        # Only bother with commands
        if not message.startswith(".") and not (message.startswith("@") and "superadmin" in perms):
            return

        # Parse the message into args and kwargs, respecting quoted substrings
        command_char = message[0]
        parts = message[1:].split(" ")
        filtered = []
        kwargs = {}
        while parts:
            arg = parts.pop(0)
            if arg.startswith("--"):
                name, _, value = arg[2:].partition("=")
                name = name.replace("-","_")
                if value:
                    if value.startswith('"'):
                        vparts = [value[1:]]
                        while parts:
                            arg = parts.pop(0)
                            if arg[-1] == '"':
                                vparts.append(arg[:-1])
                                break
                            else:
                                vparts.append(arg)
                        value = " ".join(vparts)
                else:
                    value = True
                kwargs[name] = value
            else:
                filtered.append(arg)
        message = " ".join(filtered).strip()
        args = []
        while message:
            if message.startswith('"'):
                arg, _, message = message.partition('" ')
                if not message and arg[-1] == '"':
                    arg = arg[:-1]
                args.append(arg)
            else:
                arg, _, message = message.partition(" ")
                args.append(arg)

        # Add in admin_mode after parsing, so that users can't override it
        kwargs["admin_mode"] = command_char == "@"

        # Extract command name, checking if it is a reversed command
        command = args.pop(0)
        if command.startswith("un"):
            command = command[2:]
            kwargs["reverse"] = True
        else:
            kwargs["reverse"] = False

        # Exchange command name for command dictionary
        if command not in self.commands:
            return
        command = self.commands[command]

        # Check access before we print help text. It avoids confusion
        if command["access"] not in perms:
            return

        # Ensure that if they tried a reverse command, that it is actually reversible
        if kwargs["reverse"] and "reverse" not in command["kwargs"]:
            return

        # Filter kwargs
        filtered = {}
        for arg in command["kwargs"]:
            if arg in kwargs:
                filtered[arg] = kwargs[arg]
        kwargs = filtered

        # Fix up args
        arglen = len(command["args"])
        if arglen > len(args):
            irc.msg(channel, command["reverse_help"] if "reverse" in kwargs and kwargs["reverse"] else command["help"])
            return

        if arglen:
            args = args[:arglen-1] + [" ".join(args[arglen-1:])]
        else:
            # As a special case, if there are no args, map args to kwargs
            args = dict(zip(command["kwargs"], args))
            args.update(kwargs)
            kwargs = args
            args = []

        # Get a working directory & identifier
        guid = self.getGUID()

        # Run the command
        self.log("Running command: {} {} {} {} {!r} {!r}", command["name"], guid, channel, user, args, kwargs)
        self.dispatch("start", command["name"], guid, channel, user, args, kwargs)
        try:
            yield maybeDeferred(command["command"], guid, self, irc, channel, user, *args, **kwargs)
        except CommandException as e:
            irc.msg(channel, unicode(e))
        except:
            self.err("{} on behalf of {} failed unexpectedly.", command["name"], user)
            irc.msg(channel, u"Fugiman: {} on behalf of {} failed unexpectedly.".format(command["name"], user))
        self.dispatch("finish", guid)

        # Clean up
        shutil.rmtree(guid)
