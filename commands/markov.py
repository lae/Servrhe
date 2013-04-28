from twisted.internet.defer import inlineCallbacks
from lib.utils import dt2ts
import datetime

config = {
    "access": "public",
    "help": ".markov [name] || .markov foogi || Ramble as [name] would, utilizing markov chains",
    "reversible": False
}

cooldowns = {}

@inlineCallbacks
def command(self, user, channel, msg):
    permissions = self.getPermissions(user)
    now = datetime.datetime.utcnow()

    if "owner" in permissions:
        cooldown = datetime.timedelta(minutes=0)
    elif "admin" in permissions:
        cooldown = datetime.timedelta(minutes=0)
    elif user.lower() in self.admins: # Just for aers
        cooldown = datetime.timedelta(minutes=0)
    else:
        cooldown = datetime.timedelta(minutes=3)

    if user not in cooldowns:
        cooldowns[user] = {
            "time": now,
            "warnings": 0,
            "kicks": 0
        }
    if cooldowns[user]["time"] > now:
        if cooldowns[user]["warnings"] >= 5 or cooldowns[user]["kicks"] >= 10:
            cooldowns[user]["warnings"] = 0
            cooldowns[user]["kicks"] = 0
            self.kickban(channel, user, "Markov command abuse")
        elif cooldowns[user]["warnings"] >= 3:
            cooldowns[user]["kicks"] += 1
            self.kick(channel, user, "Markov command abuse")
        else:
            cooldowns[user]["warnings"] += 1
            diff = dt2ts(cooldowns[user]["time"] - now)
            self.notice(user, "You just used this command, please wait {} before using it again.".format(diff))
        return

    if not msg:
        cooldowns[user]["time"] = now + cooldown
        cooldowns[user]["warnings"] = 0
        message = yield self.factory.markov.ramble()
        self.msg(channel, message)
        return

    name = self.factory.alias.resolve(msg[0])
    if self.isAdmin(name) and user.lower() not in self.admins:
        cooldown *= 5

    if "owner" not in permissions or name != "list":
        if name not in self.factory.markov.users:
            self.msg(channel, "No data on {}".format(msg[0]))
            return
        else:
            cooldowns[user]["time"] = now + cooldown
            cooldowns[user]["warnings"] = 0
            seed = msg[1] if len(msg) > 1 else ""
            message = yield self.factory.markov.ramble(name, seed)
            self.msg(channel, message)
        return
    self.msg(channel, ", ".join(self.factory.markov.users.keys()))
