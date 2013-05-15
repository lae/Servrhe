# -*- coding: utf-8 -*-

from twisted.web.resource import Resource

dependencies = []

class Module(Resource):
    isLeaf = True

    def __init__(self, master):
        Resource.__init__(self)

    def stop(self):
        pass
