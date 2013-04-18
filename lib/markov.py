from twisted.internet.defer import inlineCallbacks, returnValue
from lib.utils import normalize
import json, random

class Markov(object):
    def __init__(self, db, aliases, order=3):
        self.db = db
        self.aliases = aliases
        self.order = order
        self.users = {}
        self.loadUsers()

    @inlineCallbacks
    def loadUsers(self):
        result = yield self.db.runQuery("SELECT DISTINCT name FROM parts")
        for line in result:
            self.users[line[0]] = True
    
    @inlineCallbacks
    def learn(self, name, phrase):
        name = self.aliases.resolve(name)
        if name not in self.users:
            self.users[name] = True

        order = -1 * (self.order - 1)
        phrase = phrase.split(" ")

        for i in range(len(phrase) + 1):
            seed = normalize(" ".join(phrase[:i][order:]))
            small = normalize(phrase[i-1] if i > 0 else "")
            answer = normalize(phrase[i] if i < len(phrase) else "")

            yield self.db.runQuery("INSERT INTO parts(name, seed, answer) VALUES(%s, %s, %s)", (name, seed, answer))

            if small != seed:
                yield self.db.runQuery("INSERT INTO parts(name, seed, answer) VALUES(%s, %s, %s)", (name, small, answer))

    @inlineCallbacks
    def ramble(self, name):
        name = self.aliases.resolve(name)
        if name not in self.users:
            returnValue("")

        chunk = yield self.fetch(name, "")
        message = []
        while chunk and len(" ".join(message)) < 400:
            message.append(chunk)
            chunk = yield self.fetch(name, chunk)
        returnValue(" ".join(message))

    @inlineCallbacks
    def fetch(self, name, seed):
        result = yield self.db.runQuery("SELECT answer FROM parts WHERE name = %s AND seed = %s ORDER BY RAND() LIMIT 1", (name, seed))
        if not result:
            returnValue("")
        returnValue(result[0][0])
