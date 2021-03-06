import webapp2
import logging
import model
import board
import cgi
import bandcamp
import jinja2
import os
import random
import re
from google.appengine.ext import ndb
from collections import defaultdict

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)+'/template'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def index(e, list):
    try:
        return list.index(e)
    except ValueError:
        return -1

def populate_from_archive(db):
    import cPickle as pickle
    import gzip

    catalog = board.get_catalog_threads(full_thread=False, band_filter=False)
    open_ids = defaultdict(lambda: False)
    for t in catalog:
        open_ids[t.id()] = True

    push = []
    f = gzip.open(db)
    thrs = pickle.load(f)
    for key in thrs:
        jt = thrs[key]
        t = board.Thread(json=jt)
        if t.is_band_thread():
            if not open_ids[t.id()]:
                t.close()
            push.append(t.to_prop())

    ndb.put_multi(push)

def get_db_thread(id):
    return board.Thread(prop=model.ThreadProp.thread(id))

def get_db_threads():
    return [board.Thread(prop=p) for p in model.ThreadProp.all_threads()]

def get_db_open_threads():
    thrs = model.ThreadProp.open_threads()
    return [board.Thread(prop=p) for p in thrs]

def get_db_random_band():
    bands = model.BandProp.all_bands()
    while True:
        b = random.choice(bands)
        if not re.search('invalid url', b.name):
            return b

def update_thread_db():
    openthrs = get_db_open_threads()
    openthr_ids = [thr.id() for thr in openthrs]

    catathrs = board.get_catalog_threads()
    catathr_ids = [thr.id() for thr in catathrs]

    done = {}
    push = []

    # 1. update or add threads from the catalog
    for thr in catathrs:
        print "T ", thr.id(), "(catalog)"
        i = index(thr.id(), openthr_ids)
        if i >= 0:
            if thr.newer_than(openthrs[i]):
                # fetch full thread and update entry in db
                print "fetch & update"
                openthrs[i].update()
                push.append(openthrs[i].to_prop())
                done[i] = True
        else:
            # fetch full thread and create entry in db
            print "fetch & create"
            push.append(thr.to_prop())

    # 2. close any open thread not in the catalog anymore
    for (i, thr) in enumerate(openthrs):
        if i not in done:
            thr.update()
            push.append(thr.to_prop())

    ndb.put_multi(push)
    model.DbUpdateProp.update()

def update_band_db(thrs=None):
    if thrs is None:
        # update everything
        thrs = get_db_threads()

    bands = {}

    for t in thrs:
        for p in t.posts:
            if p.is_band():
                nrefs = len(t.ref_to_post(p.id()))
                urls = bandcamp.extract_urls(board.textify(p.com()))
                slugs = set([bandcamp.BandcampUrl(u).band_slug() for u in urls]) # set to remove dups
                for s in slugs:
                    if s not in bands:
                        bands[s] = model.BandProp(id=s, nbcom=0, nbpost=0)
                    bands[s].nbcom += nrefs
                    bands[s].nbpost += 1

    for s, b in bands.iteritems():
        bc = bandcamp.BandcampUrl(slug=s)
        b.name = bc.artist()
        b.com_per_post = float(b.nbcom)/b.nbpost

    ndb.put_multi(bands.values())

class MainPage(webapp2.RequestHandler):
    def get(self):
        tpl = JINJA_ENV.get_template('base.html')
        self.response.write(tpl.render({}))

class UpdatePage(webapp2.RequestHandler):
    def get(self, type):
        if type == 'thread':
            update_thread_db()
        elif type == 'band':
            update_band_db()
        else:
            self.response.write('invalid type')
            return

        self.response.write('ok')

class PopulatePage(webapp2.RequestHandler):
    def get(self):
        populate_from_archive('mu_db.pkl.gz')
        self.redirect('/')

# TODO: when updating threads, fetch all bandprops, and only update
# artist when necessary
class PopularPage(webapp2.RequestHandler):
    def get(self):
        bands = model.BandProp.popular(50)
        tpl = JINJA_ENV.get_template('popular.html')
        self.response.write(tpl.render({
            'dateupdate': model.DbUpdateProp.last(),
            'bands': [
                {
                    'url': bandcamp.BandcampUrl(slug=b.key.id()).canonical(),
                    'name': b.name,
                    'nbpost' : b.nbpost,
                    'nbcom' : b.nbcom,
                    'com_per_post' : b.com_per_post,
                } for b in bands
            ]
        }))

class OpenPage(webapp2.RequestHandler):
    def get(self):
        openthrs = get_db_open_threads()
        tpl = JINJA_ENV.get_template('open.html')
        self.response.write(tpl.render({'dateupdate': model.DbUpdateProp.last(), 'threads': openthrs}))

class ArchivePage(webapp2.RequestHandler):
    def get(self, **kwargs):
        thrs = get_db_threads()
        tpl = JINJA_ENV.get_template('thread-list.html')
        self.response.write(tpl.render({'dateupdate': model.DbUpdateProp.last(), 'threads': thrs}))

class ThreadPage(webapp2.RequestHandler):
    def get(self, **kwargs):
        thr = get_db_thread(int(kwargs['id']))
        tpl = JINJA_ENV.get_template('thread.html')
        self.response.write(tpl.render({'dateupdate': model.DbUpdateProp.last(), 't': thr}))

class RandomBandPage(webapp2.RequestHandler):
    def get(self):
        try:
            prop = get_db_random_band()
            b = bandcamp.BandcampUrl(slug=prop.key.id())
            self.redirect(b.canonical())
        except IndexError:
            self.redirect('/')

class FaqPage(webapp2.RequestHandler):
    def get(self):
        tpl = JINJA_ENV.get_template('faq.html')
        self.response.write(tpl.render({'dateupdate': model.DbUpdateProp.last()}))

app = webapp2.WSGIApplication([
    webapp2.Route('/',        handler=OpenPage),
    webapp2.Route('/open',    handler=OpenPage),
    webapp2.Route('/popular', handler=PopularPage),
    webapp2.Route('/archive', handler=ArchivePage),
    webapp2.Route('/archive/<page:\d+>', handler=ArchivePage),
    webapp2.Route('/thread/<id:\d+>',    handler=ThreadPage),
    webapp2.Route('/random', handler=RandomBandPage),
    webapp2.Route('/faq', handler=FaqPage),

    webapp2.Route('/update/<type>',   handler=UpdatePage),
    webapp2.Route('/populate', handler=PopulatePage),
], debug=True)
