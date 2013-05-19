# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks
from twisted.web.xmlrpc import Proxy

dependencies = ["config", "commands"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("blog")

    def stop(self):
        pass

    @inlineCallbacks
    def createPost(self, show, episode, version, info_link, comment = None):
        end = " END" if episode == show.episode.total else ""
        exception = self.master.modules["commands"].exception
        comment = "<br>{}".format(comment) if comment is not None else ""

        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        if user is None or passwd is None:
            raise exception(u"No blog username or password in config")

        blog = Proxy("http://commiesubs.com/xmlrpc.php")
        blog.queryFactory.noisy = False
        slug = show.blog.split("/")[-2]
        categories = ["The Bread Lines"]
        result = yield blog.callRemote("wp.getTerms", 0, user, passwd, "category")
        for term in result:
            if term["slug"] == slug:
                categories.append(term["name"])

        try:
            yield blog.callRemote("wp.newPost",
                0, # Blog ID
                user, # Username
                passwd, # Password
                { # Content
                    "post_type": "post",
                    "post_status": "publish",
                    "comment_status": "open",
                    "post_title": "{} {:02d}{}{}".format(show.name.english, episode, version, end),
                    "post_content": "<a href=\"{}\">Torrent</a>{}".format(info_link, comment),
                    "terms_names": {"category": categories}
                }
            )
        except:
            raise exception(u"Couldn't publish blog post")
