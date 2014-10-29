#!/bin/env python2

import sys
sys.path.insert(0, 'lib')

from bs4 import BeautifulSoup as BS
import requests as R
import re
import datetime
import model
import pickle

CATALOG_URL = 'http://a.4cdn.org/mu/catalog.json'
THREAD_URL  = 'http://a.4cdn.org/mu/thread/%d.json'

def textify(html):
    # div hack to prevent BS UserWarning about html looking like a url
    return BS('<div>'+html+'</div>').get_text()

#
# Post and Thread class to handle 4chan stuff
#

class Post:
    def __init__(self, json=None, prop=None, thr=None):
        self.prop = prop
        self.thr = thr

        if prop is not None:
            self.json = prop.json
        elif json is not None:
            self.json = json

    def to_prop(self):
        if self.prop:
            self.prop.json = self.json
        else:
            self.prop = model.PostProp(json=self.json)
        return self.prop


    def id(self):
        return self.json['no'] # must exist

    def sub(self):
        return self.json.get('sub', '')

    def com(self):
        return self.json.get('com', '')

    def timestamp(self):
        return self.json['time']

    def datetime(self):
        return datetime.datetime.fromtimestamp(self.timestamp())

    def refs(self):
        ids = re.findall(r'''<a href="#p(\d+)''', self.com())
        return [int(id) for id in ids]

    def is_band(self):
        t = textify(self.com())
        r = re.search(r'\.bandcamp\.com', t)
        return r is not None


    def is_comment(self):
        refs = self.refs()
        for p in self.thr.posts:
            if p.id() in refs:
                return True
        return False



class Thread(Post):
    def __init__(self, json=None, prop=None):
        self.prop = prop

        if prop is not None:
            self.posts = [Post(prop=p, thr=self) for p in prop.posts]
            self.json = self.posts[0].json
        elif json is not None:
            self.json = json

    def to_prop(self):
        if self.prop:
            # id won't change
            self.prop.open = self.is_open()
            self.prop.date = self.datetime()
            self.prop.posts = [p.to_prop() for p in self.posts] # may not be very efficient
        else:
            self.prop = model.ThreadProp(parent=model.thread_key(),
                                         id=self.id(),
                                         open=self.is_open(),
                                         date=self.datetime(),
                                         posts=[p.to_prop() for p in self.posts])
        return self.prop

    def is_open(self):
        return self.json.get('closed', 0) == 0

    def close(self):
        self.json['closed'] = 1

    def update(self):
        data = R.get(THREAD_URL % self.id()).json()
        self.posts = []
        self.json = data['posts'][0]
        for p in data['posts']:
            self.posts.append(Post(json=p, thr=self))

    def ref_to_post(self, id):
        r = []
        for p in self.posts:
            if id in p.refs():
                r.append(p)
        return r

    def last_datetime(self):
        if 'last_replies' in self.json and len(self.json['last_replies']) > 0:
            return Post(json=self.json['last_replies'][-1]).datetime()
        else:
            return self.posts[-1].datetime()

    def newer_than(self, thr):
        return self.last_datetime() > thr.last_datetime()

def is_band_thread(thr):
    sub = textify(thr.get('sub', ''))
    com = textify(thr.get('com', ''))
    rx = r'bandcamp.+(?:topic|thread)'
    f = re.IGNORECASE

    if re.search(rx, sub, flags=f) or re.match(rx, com, flags=f):
        return True

    n = 0
    threshold = 3

    if Post(json=thr).is_band():
        n += 1

    for pj in thr.get('last_replies', []):
        p = Post(json=pj)
        if p.is_band():
            n += 1

    if n >= threshold:
        return True

    return False

def get_catalog_threads():
    data = R.get(CATALOG_URL).json()
    r = []
    for page in data:
        for thr in page['threads']:
            if is_band_thread(thr):
                r.append(Thread(json=thr))
    return r
