from lib.utils import normalize
import json, random

class Markov(object):
    def __init__(self, db, order=3):
        self.db = db
        self.order = order
        self.load()

    def save(self):
        try:
            with open(self.db, "w") as f:
                f.write(json.dumps(self.cache))
        except:
            print "Failed to save markov database ({})".format(self.db)

    def load(self):
        try:
            with open(self.db, "r") as f:
                self.cache = json.loads(f.read())
        except:
            self.cache = {"": {}}

    def learn(self, phrase):
        order = -1 * (self.order - 1)
        for i in range(len(phrase) + 1):
            seed = normalize(" ".join(phrase[:i][order:]))
            small = normalize(phrase[i-1] if i > 0 else "")
            answer = normalize(phrase[i] if i < len(phrase) else "")

            if seed not in self.cache:
                self.cache[seed] = {}
            if answer not in self.cache[seed]:
                self.cache[seed][answer] = 0
            self.cache[seed][answer] += 1

            if small != seed:
                if small not in self.cache:
                    self.cache[small] = {}
                if answer not in self.cache[small]:
                    self.cache[small][answer] = 0
                self.cache[small][answer] += 1

    def ramble(self):
        chunk = self.fetch("")
        message = []
        while chunk:
            message.append(chunk)
            chunk = self.fetch(chunk)
        return " ".join(message)

    def fetch(self, seed):
        if seed not in self.cache:
            return ""
        possibilities = self.cache[seed].items()
        maximum = sum([x[1] for x in possibilities]) - 1
        choice = random.randint(0, maximum)
        for answer, probability in possibilities:
            choice -= probability
            if choice < 0:
                return answer
        return ""
