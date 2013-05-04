from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from bs4 import UnicodeDammit
from txmongo._pymongo.son import SON
import datetime, json, random, txmongo

def aggregate(self, pipeline):
    if not isinstance(pipeline, (dict, list, tuple)):
        raise TypeError("pipeline must be a dict, list or tuple")

    if isinstance(pipeline, dict):
        pipeline = [pipeline]

    command = SON([("aggregate", self._collection_name)])
    command.update({"pipeline": pipeline})

    return self._database["$cmd"].find_one(command)

class Markov(object):
    def __init__(self, db, aliases):
        self.db = db.markov
        self.db.aggregate = lambda p: aggregate(self.db, p)
        self.aliases = aliases
        self.users = {}
        self.ranking = {}
        self.start()

    def start(self):
        if isinstance(self.db._database._connection, txmongo._offline):
            reactor.callLater(3, self.start)
            return
        print ">>> MARKOV: Starting..."
        self.loadUsers()
        LoopingCall(self.loadRanking).start(60)

    @inlineCallbacks
    def loadUsers(self):
        result = yield self.db.distinct("name")
        for name in result:
            self.users[name] = True

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
        name = self.aliases.resolve(name)
        if name not in self.users:
            self.users[name] = True

        if "password" in phrase:
            return
        phrase = phrase.split(" ")
        phrase = filter(lambda x: x and "http" not in x and "ftp:" not in x and x[0] != ".", phrase)
        now = datetime.datetime.utcnow()
        documents = []

        for i in range(len(phrase) + 1):
            seed = UnicodeDammit.detwingle(phrase[i-1] if i > 0 else "")
            answer = UnicodeDammit.detwingle(phrase[i] if i < len(phrase) else "")

            documents.append({
                "name": name,
                "seed": seed,
                "answer": answer,
                "added": now,
                "random": random.random()
            })

        yield self.db.insert(documents, safe=True)

    @inlineCallbacks
    def ramble(self, name=None, seed=""):
        if name:
            name = self.aliases.resolve(name)
            if name not in self.users:
                returnValue("")

        message = []

        if seed:
            seed = UnicodeDammit.detwingle(seed)
            chunk = seed
            while chunk and len(" ".join(message)) < 300:
                message.append(chunk)
                chunk = yield self.prev(name, chunk)
            message.reverse()

        chunk = yield self.next(name, seed)
        while chunk and len(" ".join(message)) < 300:
            message.append(chunk)
            chunk = yield self.next(name, chunk)
            if not chunk and len(" ".join(message)) < 30:
                chunk = yield self.next(name, chunk)

        response = (" ".join(message)).decode("utf8")
        if seed and response == seed.decode("utf8"):
            response = yield self.ramble(name)
        returnValue(response)

    @inlineCallbacks
    def prev(self, name, answer):
        query = {"answer": answer, "random": {"$gte": random.random()}}
        if name:
            query["name"] = name
        result = yield self.db.find(query, fields=["seed"], limit=1, filter=txmongo.filter.sort(txmongo.filter.ASCENDING("random")))
        if not result:
            returnValue("")
        returnValue(result[0]["seed"])

    @inlineCallbacks
    def next(self, name, seed):
        query = {"seed": seed, "random": {"$gte": random.random()}}
        if name:
            query["name"] = name
        result = yield self.db.find(query, fields=["answer"], limit=1, filter=txmongo.filter.sort(txmongo.filter.ASCENDING("random")))
        if not result:
            returnValue("")
        returnValue(result[0]["answer"])
