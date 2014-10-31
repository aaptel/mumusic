import webapp2
import logging
import model
import board
import cgi
import bandcamp
import jinja2
import os

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)+'/template'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def index(e, list):
    try:
        return list.index(e)
    except ValueError:
        return -1

def get_db_open_threads():
    thrs = model.ThreadProp.open_threads()
    return [board.Thread(prop=p) for p in thrs]

def get_db_popular_bands():
    thrs = [board.Thread(prop=p) for p in model.ThreadProp.all_threads()]
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


def update_thread_db():
    openthrs = get_db_open_threads()
    openthr_ids = [thr.id() for thr in openthrs]

    catathrs = board.get_catalog_threads()
    catathr_ids = [thr.id() for thr in catathrs]
    #from pdb import set_trace;set_trace()

    # 1. update or add threads from the catalog
    for thr in catathrs:
        print "T ", thr.id(), "(catalog)"
        i = index(thr.id(), openthr_ids)
        if i >= 0:
            if thr.newer_than(openthrs[i]):
                # fetch full thread and update entry in db
                print "fetch & update"
                openthrs[i].update()
                openthrs[i].to_prop().put()
        else:
            # fetch full thread and create entry in db
            print "fetch & create"
            thr.update() # fetch full thread
            thr.to_prop().put()

    # 2. close any open thread not in the catalog anymore
    for thr in openthrs:
        thr.update()
        thr.to_prop().put()

class MainPage(webapp2.RequestHandler):
    def get(self):
        tpl = JINJA_ENV.get_template('base.html')
        self.response.write(tpl.render({}))

class UpdatePage(webapp2.RequestHandler):
    def get(self):
        r = self.response
        r.headers['Content-Type'] = 'text/plain'
        r.write("updating...\n")
        update_thread_db()
        r.write("done!\n")

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

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/update', UpdatePage),
    ('/open', OpenPage),
    ('/popular', PopularPage)
], debug=True)
