config = {
    "access": "public",
    "help": ".ranking [name] || .ranking duwang || Gives the markov rank of a user, or the top 5 if not user specified"
}

def command(guid, manager, irc, channel, user, name = None, refresh = False, admin_mode = False):
    if admin_mode:
        say = lambda m: irc.msg(channel, m)
    else:
        say = lambda m: irc.notice(user, m)

    perms = yield manager.getPermissions(user)
    if refresh and "owner" in perms:
        yield manager.master.modules["markov"].loadRanking()
        return

    if name is None:
        ranks = sorted(manager.master.modules["markov"].ranking.values(), key=lambda x: x["rank"])[:5]
        say(", ".join(["#{:d}: {} ({:,d} words)".format(d["rank"], d["name"], d["lines"]) for d in ranks]))
        return

    if name[0] == "#":
        try:
            place = int(name[1:]) - 1
        except:
            say("{} is not a valid integer".format(name[1:]))
            return
        ranks = sorted(manager.master.modules["markov"].ranking.values(), key=lambda x: x["rank"])
        data = ranks[place]
        say("{} is rank #{:d} with {:,d} words".format(data["name"], data["rank"], data["lines"]))
        return

    name = yield manager.master.modules["alias"].resolve(name)
    if name not in manager.master.modules["markov"].ranking:
        say("{} is not ranked as we have no record of them ever speaking.".format(name))
        return

    data = manager.master.modules["markov"].ranking[name]
    say("{} is rank #{:d} with {:,d} words".format(data["name"], data["rank"], data["lines"]))
