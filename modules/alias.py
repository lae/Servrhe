# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue

dependencies = []

class Module(object):
    def __init__(self, master):
        self.master = master
        self.db = master.db.alias

    def stop(self):
        pass

    @inlineCallbacks
    def resolve(self, name):
        name = name.lower()
        result = yield self.db.find({"slaves": name})
        returnValue(result[0]["master"] if result else name)

    @inlineCallbacks
    def learn(self, master, slave):
        master, slave = master.lower(), slave.lower()
        mrecord = yield self.db.find({"slaves": master})
        srecord = yield self.db.find({"slaves": slave})
        mrecord = mrecord[0] if mrecord else None
        srecord = srecord[0] if srecord else None
        if mrecord and srecord:
            slaves = mrecord["slaves"] + srecord["slaves"]
            mrecord["slaves"] = self._unique(slaves)
            mrecord["alts"].append(srecord["master"])
            yield self.db.save(mrecord, safe=True)
            yield self.db.remove(srecord, safe=True)
        elif mrecord:
            mrecord["slaves"].append(slave)
            yield self.db.save(mrecord, safe=True)
        elif srecord:
            srecord["slaves"].append(master)
            yield self.db.save(srecord, safe=True)
        else:
            record = {"master": master, "slaves": [master, slave], "alts": []}
            yield self.db.save(record, safe=True)

    def _unique(self, l):
        s, r = {}, []
        for i in l:
            if i in s: continue
            s[i] = True
            r.append(i)
        return r

    def irc_rename(self, old, new):
        self.learn(old, new)
