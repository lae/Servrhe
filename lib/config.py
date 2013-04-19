from lib.utils import normalize
import json

def clean(o):
    if isinstance(o, dict):
        c = {}
        for k, v in o.items():
            c[clean(k)] = clean(v)
        return c
    elif isinstance(o, list):
        return [clean(v) for v in o]
    elif isinstance(o, basestring):
        return normalize(o)
    else:
        return o

class Config(object):
    location = None
    config = None

    def __init__(self, location, defaults = {}):
        self.location = location
        self.config = defaults
        self.load()

    def load(self):
        try:
            with open(self.location, "r") as f:
                config = json.loads(f.read())
        except IOError:
            config = {}
        except ValueError:
            print("Warning: Couldn't parse config file!")
            config = {}
        self.config.update(clean(config))

    def save(self):
        with open(self.location, "w") as f:
            f.write(json.dumps(self.config, sort_keys=True, indent=2))

    def __getattr__(self, name):
        if name in self.config:
            return self.config[name]
        else:
            raise AttributeError

    def __setattr__(self, name, value):
        if hasattr(self, name):
            super(Config, self).__setattr__(name, value)
        elif name in self.config:
            self.config[name] = value
        else:
            raise AttributeError
