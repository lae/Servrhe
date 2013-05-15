# -*- coding: utf-8 -*-

### Copy-Pasted from https://github.com/russss/Herd/blob/master/BitTornado/bencode.py
from types import IntType, LongType, StringType, ListType, TupleType, DictType
import time, hashlib, os
try:
    from types import BooleanType
except ImportError:
    BooleanType = None
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = None


dependencies = []


bencached_marker = []
class Bencached:
    def __init__(self, s):
        self.marker = bencached_marker
        self.bencoded = s
BencachedType = type(Bencached('')) # insufficient, but good as a filter

bencode_func = {
    BencachedType: lambda x: [x.bencoded],
    IntType: lambda x: ['i',str(x),'e'],
    LongType: lambda x: ['i',str(x),'e'],
    StringType: lambda x: [str(len(x)),':',x],
    ListType: lambda x: ['l'] + sum([bencode_func[type(v)](v) for v in x],[]) + ['e'],
    TupleType: lambda x: ['l'] + sum([bencode_func[type(v)](v) for v in x],[]) + ['e'],
    DictType: lambda x: ['d'] + sum([[str(len(k)),':',k]+bencode_func[type(v)](v) for k,v in sorted(x.items())],[]) + ['e']
}
if BooleanType:
    bencode_func[BooleanType] = lambda x: ['i',str(int(x)),'e'],
if UnicodeType:
    bencode_func[UnicodeType] = lambda x: bencode_func[StringType](x.encode('utf-8'))
    
def bencode(x):
    r = []
    r.extend(bencode_func[type(x)](x))
    return ''.join(r)


class Module(object):
    def __init__(self, master):
        self.master = master

    def stop(self):
        pass

    def makeTorrent(self, folder, filename):
        data = {
            "announce": "http://open.nyaatorrents.info:6544/announce",
            "announce-list": [["http://open.nyaatorrents.info:6544/announce"],["udp://tracker.openbittorrent.com:80/announce"]],
            "info": {},
            "creation date": long(time.time()),
            "comment": "#commie-subs@irc.rizon.net",
            "created by": "Servrhe",
            "encoding": "UTF-8"
        }
        data["info"]["name"] = filename
        data["info"]["length"] = size = os.path.getsize(os.path.join(folder, filename))
        # 1MB pieces if file > 512MB, else 512KB pieces
        data["info"]["piece length"] = piece_length = 2**20 if size > 512*1024*1024 else 2**19
        pieces = []
        with open(os.path.join(folder, filename), "rb") as f:
            p = 0L
            while p < size:
                chunk = f.read(min(piece_length, size - p))
                pieces.append(hashlib.sha1(chunk).digest())
                p += piece_length
        data["info"]["pieces"] = "".join(pieces)
        torrentname = filename + ".torrent"
        with open(os.path.join(folder, torrentname), "wb") as f:
            f.write(bencode(data))
        return torrentname
