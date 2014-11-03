import webapp2
import logging
import model
import board
import cgi
import bandcamp
import jinja2
import os
import random
from google.appengine.ext import ndb

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

    push = []
    f = gzip.open(db)
    thrs = pickle.load(f)
    for key in thrs:
        jt = thrs[key]
        if jt is None:
            import pdb; pdb.set_trace()
        t = board.Thread(json=jt)
        if t.is_band_thread():
            push.append(t.to_prop())

    ndb.put_multi(push)

def get_db_thread(id):
    return board.Thread(prop=model.ThreadProp.thread(id))

def get_db_threads():
    return [board.Thread(prop=p) for p in model.ThreadProp.all_threads()]

def get_db_open_threads():
    thrs = model.ThreadProp.open_threads()
    return [board.Thread(prop=p) for p in thrs]

def get_db_popular_bands(thrs=None):
    if thrs is None:
        thrs = get_db_threads()
    bands = {}
    for t in thrs:
        for p in t.posts:
            if p.is_band():
                nrefs = len(t.ref_to_post(p.id()))
                urls = bandcamp.extract_urls(board.textify(p.com()))
                slugs = set([bandcamp.BandcampUrl(u).band_slug() for u in urls]) # set to remove dups
                for s in slugs:
                    bands[s] = bands.get(s, 0) + nrefs

    return [(bandcamp.BandcampUrl(slug=s), bands[s]) for s in sorted(bands.keys(), key=lambda x: bands[x], reverse=True)]

def get_db_random_band():
    thrs = get_db_threads()
    bands = get_db_popular_bands(thrs)
    return random.choice(bands)

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

class MainPage(webapp2.RequestHandler):
    def get(self):
        tpl = JINJA_ENV.get_template('base.html')
        self.response.write(tpl.render({}))

class UpdatePage(webapp2.RequestHandler):
    def get(self):
        update_thread_db()
        self.redirect('/')

class PopulatePage(webapp2.RequestHandler):
    def get(self):
        populate_from_archive('mu_db.pkl.gz')
        self.redirect('/')

class PopularPage(webapp2.RequestHandler):
    def get(self):
        bands = get_db_popular_bands()
        tpl = JINJA_ENV.get_template('popular.html')
        self.response.write(tpl.render({'bands': bands}))

class OpenPage(webapp2.RequestHandler):
    def get(self):
        openthrs = get_db_open_threads()
        tpl = JINJA_ENV.get_template('open.html')
        self.response.write(tpl.render({'threads': openthrs}))

class ArchivePage(webapp2.RequestHandler):
    def get(self, **kwargs):
        thrs = get_db_threads()
        tpl = JINJA_ENV.get_template('thread-list.html')
        self.response.write(tpl.render({'threads': thrs}))

class ThreadPage(webapp2.RequestHandler):
    def get(self, **kwargs):
        thr = get_db_thread(int(kwargs['id']))
        tpl = JINJA_ENV.get_template('thread.html')
        self.response.write(tpl.render({'t': thr}))

class RandomBandPage(webapp2.RequestHandler):
    def get(self):
        try:
            b = get_db_random_band()[0]
            self.redirect(b.canonical())
        except IndexError:
            self.redirect('/')

app = webapp2.WSGIApplication([
    webapp2.Route('/',        handler=OpenPage),
    webapp2.Route('/open',    handler=OpenPage),
    webapp2.Route('/popular', handler=PopularPage),
    webapp2.Route('/archive', handler=ArchivePage),
    webapp2.Route('/archive/<page:\d+>', handler=ArchivePage),
    webapp2.Route('/thread/<id:\d+>',    handler=ThreadPage),
    webapp2.Route('/random', handler=RandomBandPage),

    webapp2.Route('/update',   handler=UpdatePage),
    webapp2.Route('/populate', handler=PopulatePage),
], debug=True)
