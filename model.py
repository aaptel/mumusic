#!/bin/env python2

from google.appengine.ext import ndb

THREAD_KEY_NAME = 'threads'

def thread_key():
    return ndb.Key('ThreadProp', THREAD_KEY_NAME)

class PostProp(ndb.Model):
    json = ndb.JsonProperty()

class ThreadProp(ndb.Model):
    id = ndb.IntegerProperty()
    open = ndb.BooleanProperty()
    date = ndb.DateTimeProperty()
    posts = ndb.StructuredProperty(PostProp, repeated=True)

    @classmethod
    def open_threads(cls):
        q = cls.query(ancestor=thread_key()).filter(cls.open == True).order(-cls.date)
        return q.fetch()

    @classmethod
    def all_threads(cls):
        q = cls.query(ancestor=thread_key()).order(-cls.date)
        return q.fetch()
