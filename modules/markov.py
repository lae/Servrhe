# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.task import LoopingCall
from collections import deque
from txmongo._pymongo.son import SON
import datetime, json, inspect, random, re, txmongo

dependencies = ["config", "alias"]

def aggregate(self, pipeline):
    if not isinstance(pipeline, (dict, list, tuple)):
        raise TypeError("pipeline must be a dict, list or tuple")

    if isinstance(pipeline, dict):
        pipeline = [pipeline]

    command = SON([("aggregate", self._collection_name)])
    command.update({"pipeline": pipeline})

    return self._database["$cmd"].find_one(command)

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("markov")
        self.db = master.db.markov
        self.db.aggregate = lambda p: aggregate(self.db, p)
        self.ranking = {}
        self.rankingLoop = LoopingCall(self.loadRanking)
        self.rankingLoop.start(60)

    def stop(self):
        if self.rankingLoop is not None and self.rankingLoop.running:
            self.rankingLoop.stop()
            self.rankingLoop = None

    @inlineCallbacks
    def loadRanking(self):
        result = yield self.db.aggregate([{"$group": {"_id": "$name", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}])
        self.ranking = {}
        for rank, data in enumerate(result["result"]):
            self.ranking[data["_id"].lower()] = {
                "rank": rank+1,
                "name": data["_id"],
                "lines": data["count"]
            }
    
    @inlineCallbacks
    def learn(self, name, phrase, channel):
        name = yield self.master.modules["alias"].resolve(name)

        now = datetime.datetime.utcnow()

        words = phrase.split(" ")
        c1 = [None] + words[:-1]
        c2 = words[:]
        c3 = words[1:] + [None]
        chain = zip(c1, c2, c3)

        documents = []

        for w1, w2, w3 in chain:
            documents.append({
                "name": name,
                "word1": w1,
                "word2": w2,
                "word3": w3,
                "added": now,
                "source": channel,
                "random": random.random()
            })

        yield self.db.insert(documents, safe=True)

    @inlineCallbacks
    def ramble(self, name=None, seed=None):
        if name:
            name = yield self.master.modules["alias"].resolve(name)
            if name not in self.ranking:
                returnValue("")

        message = deque()

        if seed:
            before, _, after = yield self.find(name, word2=seed)
            before = None if before is False else before
            after = None if after is False else after
            if before is not None or after is not None:
                message.append(before)
                message.append(seed)
                message.append(after)
                while message[0] is not None and len(message) < 80:
                    word, _, _ = yield self.find(name, word2=message[0], word3=message[1])
                    if word is False:
                        word, _, _ = yield self.find(name, word2=message[0])
                        word = None if word is False else word
                    message.appendleft(word)
            else:
                words = yield self.find(name, word1=None)
                message.extend(words)
        else:
            words = yield self.find(name, word1=None)
            message.extend(words)

        while message[-1] is not None and len(message) < 80:
            _, _, word = yield self.find(name, word1=message[-2], word2=message[-1])
            if word is False:
                _, _, word = yield self.find(name, word2=message[-1])
                word = None if word is False else word
            message.append(word)

        message = list(message)
        response = u" ".join(message[1:-1])
        if len(response) > 320:
            response = response[:320] + u"..."
        returnValue(response)

    @inlineCallbacks
    def find(self, name, **query):
        rand = random.random()
        query["random"] = {"$gte": rand}
        if name:
            query["name"] = name
        result = yield self.db.find(query, fields=["word1","word2","word3"], limit=1, filter=txmongo.filter.sort(txmongo.filter.ASCENDING("random")))
        if not result:
            query["random"] = {"$lte": rand}
            result = yield self.db.find(query, fields=["word1","word2","word3"], limit=1, filter=txmongo.filter.sort(txmongo.filter.DESCENDING("random")))
        if not result:
            returnValue((False, False, False))
        returnValue((result[0]["word1"], result[0]["word2"], result[0]["word3"]))

    @inlineCallbacks
    def irc_message(self, channel, user, message):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("filter_"):
                result = yield maybeDeferred(method, message, user, channel)
                if not result:
                    return
        self.learn(user, message, channel)

    def filter_commands(self, message, user, channel):
        return not (message.startswith(".") or message.startswith("@") or message.startswith("!"))

    def filter_links(self, message, user, channel):
        return "http" not in message and "ftp" not in message

    @inlineCallbacks
    def filter_banwords(self, message, user, channel):
        banwords = yield self.config.get("banwords")
        for word in banwords:
            if word in message:
                returnValue(False)
        returnValue(True)

    @inlineCallbacks
    def filter_banusers(self, message, user, channel):
        banusers = yield self.config.get("banusers")
        returnValue(user not in banusers)

    def filter_quotes(self, message, user, channel):
        match1 = re.match("\[Quote\] #\d+ added by .* ago.", message)
        match2 = re.match("\[Quote\] \d+ matches found: #[\d,]+", message)
        return not (user == "Quotes" and (match1 or match2))
