import json

class Aliases(object):
    def __init__(self, db):
        self.db = db
        self.cache = {}
        self.load()

    def save(self):
        try:
            with open(self.db, "w") as f:
                f.write(json.dumps(self.cache, sort_keys=True, indent=2))
        except:
            print "Failed to save aliases"

    def load(self):
        try:
            with open(self.db, "r") as f:
                self.cache = json.loads(f.read())
        except:
            self.cache = {}

    def add(self, original, alias):
        original, alias = original.lower(), alias.lower()
        if alias in self.cache:
            return
        if self.resolve(original) == alias:
            return
        self.cache[alias] = original

    def resolve(self, name, depth=0):
        name = name.lower()
        if depth > 20:
            return name
        if name in self.cache:
            return self.resolve(self.cache[name], depth+1)
        return name