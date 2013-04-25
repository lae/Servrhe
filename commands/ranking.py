config = {
    "access": "public",
    "help": ".ranking [name] || .ranking duwang || Gives the markov rank of a user, or the top 5 if not user specified",
    "reversible": False
}

def command(self, user, channel, msg):
    if not msg:
        ranks = sorted(self.factory.markov.ranking.values(), key=lambda x: x["rank"])[:5]
        self.msg(channel, ", ".join(["#{:d}: {} ({:,d} words)".format(d["rank"], d["name"], d["lines"]) for d in ranks]))
        return

    name = self.factory.alias.resolve(msg[0])
    if name not in self.factory.markov.ranking:
        self.msg(channel, "{} is not ranked as we have no record of them ever speaking.".format(name))
        return

    data = self.factory.markov.ranking[name]
    self.msg(channel, "{} is rank #{:d} with {:,d} words".format(data["name"], data["rank"], data["lines"]))
