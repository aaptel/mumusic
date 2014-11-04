#!/bin/env python2

import sys
sys.path.insert(0, 'lib')

from collections import defaultdict
import bs4
from bs4 import BeautifulSoup as BS
import requests as R
import re
import datetime
import pickle
import os
import time

# don't import model in running as stand alone script
if os.environ.get('SERVER_SOFTWARE', ''):
    import model


CATALOG_URL = 'http://a.4cdn.org/mu/catalog.json'
THREAD_URL  = 'http://a.4cdn.org/mu/thread/%d.json'
THREAD_SUB_RX = re.compile(r'bandcamp.+(?:topic|thread|general|station)', flags=re.IGNORECASE)

THREAD_FN_RX = re.compile(r'\bbc\b|bandcamp', flags=re.IGNORECASE)
THREAD_MIN_LINK = 3
DOWNLOAD_DELAY = .5

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

    def filename(self, ext=None):
        fn = self.json.get('filename', '')
        if ext:
            fn += self.json.get('ext', '')
        return fn

    def id(self):
        return self.json['no'] # must exist

    def sub(self):
        return self.json.get('sub', '')

    def com(self):
        com = self.json.get('com', '')
        com = re.sub('<br>', '<br/>', com)
        com = re.sub('<wbr>', '', com)
        return urlify_dumb(com)

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
        self.posts = []
        self.rindex = None

        if prop is not None:
            self.posts = [Post(prop=p, thr=self) for p in prop.posts]
            self.json = self.posts[0].json
        elif json is not None:
            if 'posts' in json:
                # thread page
                self.json = json['posts'][0]
                try:
                    self.posts = [Post(json=p, thr=self) for p in json['posts']]
                except KeyError:
                    import pdb; pdb.set_trace()
            else:
                self.json = json


    def to_prop(self):
        if self.prop:
            # update
            # tid won't change
            self.prop.open = self.is_open()
            self.prop.cdate = self.datetime()
            self.prop.mdate = self.last_datetime()
            self.prop.posts = [p.to_prop() for p in self.posts] # may not be very efficient
        else:
            # create new prop
            self.prop = model.ThreadProp(id=str(self.id()),
                                         tid=self.id(),
                                         open=self.is_open(),
                                         cdate=self.datetime(),
                                         mdate=self.last_datetime(),
                                         posts=[p.to_prop() for p in self.posts])
        return self.prop

    def is_open(self):
        return self.json.get('closed', 0) == 0

    def close(self):
        self.json['closed'] = 1

    def update(self):
        r = R.get(THREAD_URL % self.id())
        time.sleep(DOWNLOAD_DELAY)

        if r.status_code == 200:
            data = r.json()
            self.posts = []
            self.json = data['posts'][0]
            for p in data['posts']:
                self.posts.append(Post(json=p, thr=self))
        elif r.status_code == 404:
            self.close()

    def ref_to_post(self, id):
        if not self.rindex:
            self.build_ref_index()
        return self.rindex[id]

    def last_datetime(self):
        if 'last_replies' in self.json and len(self.json['last_replies']) > 0:
            return Post(json=self.json['last_replies'][-1]).datetime()
        else:
            return self.posts[-1].datetime()

    def newer_than(self, thr):
        return self.last_datetime() > thr.last_datetime()

    def is_band_thread(self):
        n = 0
        for p in self.posts:
            if p.is_band():
                n += 1

        if n < THREAD_MIN_LINK:
            return False

        # sharethreads are not band threads
        if re.search(r'share\s*thread', textify(self.sub()), flags=re.IGNORECASE):
            return False

        if re.search(THREAD_SUB_RX, textify(self.sub())):
            return True
        if re.search(THREAD_SUB_RX, textify(self.com())):
            return True

        return False

    def build_ref_index(self):
        d = defaultdict(set)
        self.rindex = defaultdict(list)

        for p in self.posts:
            for r in p.refs():
                d[r].add(p)
        for k in d:
            self.rindex[k] = sorted(d[k])


def get_catalog_threads():
    data = R.get(CATALOG_URL).json()
    time.sleep(DOWNLOAD_DELAY)

    r = []
    for page in data:
        for tjson in page['threads']:
            t = Thread(json=tjson)
            t.update()
            if t.is_band_thread():
                r.append(t)
    return r



def repl_url(m):
    proto = m.group(1)
    link = m.group(0)

    if proto and proto.startswith('http'):
        return '<a class=ext href="%s">%s</a>' % (link, link)
    else:
        return '<a class=ext href="http://%s">%s</a>' % (link, link)

def urlify_dumb(source):
    return re.sub(r'''(?:(https?)://)?[^<>\s;&]{2,}[^\s<>;&\.]\.[^\s<>;&\.][^\s<>;&]{1,}''', repl_url, source)

def urlify(source):
    b = BS(source)
    for e in b.contents:
        if type(e) == bs4.element.NavigableString:
            txt = unicode(e)
            rep = re.sub(r'''(?:(https?)://)?\S{3,}\.\S{2,}''', repl_url, txt)
            e.replace_with(BS(rep))
    return unicode(b)
