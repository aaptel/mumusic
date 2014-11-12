#!/bin/env python2

from google.appengine.ext import ndb
import datetime

def thread_key(tid):
    return ndb.Key(ThreadProp, str(tid))

class PostProp(ndb.Model):
    json = ndb.PickleProperty()

class ThreadProp(ndb.Model):
    tid = ndb.IntegerProperty()
    open = ndb.BooleanProperty()
    cdate = ndb.DateTimeProperty() # creation
    mdate = ndb.DateTimeProperty() # last update
    posts = ndb.StructuredProperty(PostProp, repeated=True)

    @classmethod
    def open_threads(cls):
        q = cls.query().filter(cls.open == True).order(-cls.mdate)
        return q.fetch()

    @classmethod
    def all_threads(cls):
        q = cls.query().order(-cls.mdate)
        return q.fetch()

    @classmethod
    def thread(cls, tid):
        return cls.get_by_id(str(tid))

class DbUpdateProp(ndb.Model):
    date = ndb.DateTimeProperty()

    @classmethod
    def update(cls):
        DbUpdateProp(id='update', date=datetime.datetime.now()).put()

    @classmethod
    def last(cls):
        t = cls.get_by_id('update')
        if t:
            return t.date
        else:
            return datetime.datetime.fromtimestamp(0)

class BandProp(ndb.Model):
    name = ndb.StringProperty()
    nbpost = ndb.IntegerProperty()
    nbcom = ndb.IntegerProperty()
    com_per_post = ndb.FloatProperty()

    @classmethod
    def all_bands(cls):
        return cls.query().fetch()

    @classmethod
    def popular(cls, n=None):
        q = cls.query().filter(cls.nbcom >= 10)
        r = None
        if n is None:
            r = q.fetch()
        else:
            r = q.fetch(n)
        return sorted(r, key=lambda x: -x.com_per_post)
