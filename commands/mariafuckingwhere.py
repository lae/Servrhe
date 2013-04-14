import datetime

config = {
    "access": "public",
    "help": ".mariafuckingwhere || .mariafuckingwhere || Tells you where Maria fucking is",
    "reversible": False
}

def command(self, user, channel, msg):
    dt = datetime.date
    times = {"8":dt(2013,1,6),"9":dt(2013,5,2),"10":dt(2013,8,31),"11":dt(2014,1,5),"12":dt(2014,5,18),"13":dt(2014,10,11)}
    show = self.factory.resolve("Maria", channel)
    if show is None:
        return
    ep = int(show["current_ep"]) + 1
    if ep > 12:
        self.msg(channel, "Maria fucking here! http://www.nyaa.eu/?page=view&tid=418999")
    else:
        when = times[str(ep)] - dt.today()
        self.msg(channel, "%s %d will be released in %d days" % (show["series"], ep, when.days))