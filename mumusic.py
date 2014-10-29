import webapp2
import logging
import model
import board
import cgi
import bandcamp

# class BandPost(ndb.Model):
#     pid = ndb.IntegerProperty()
#     date = ndb.DateTimeProperty(auto_now_add=True)
#     text = ndb.StringProperty()
#     img = ndb.StringProperty()

# class BandComment(ndb.Model):
#     pid = ndb.IntegerProperty()
#     date = ndb.DateTimeProperty(auto_now_add=True)
#     text = ndb.StringProperty()

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
        if thr.id() not in catathr_ids:
            print "close", thr.id(), "& update"
            thr.close()
            thr.to_prop().put()

class MainPage(webapp2.RequestHandler):
    def get(self):
        r = self.response
        r.headers['Content-Type'] = 'text/plain'
        r.write('Zoooooooob')

class UpdatePage(webapp2.RequestHandler):
    def get(self):
        r = self.response
        r.headers['Content-Type'] = 'text/plain'
        r.write("updating...\n")
        update_thread_db()
        r.write("done!\n")

class PopularPage(webapp2.RequestHandler):
    def get(self):
        r = self.response
        r.headers['Content-Type'] = 'text/html'

        bands = get_db_popular_bands()
        for (b, n) in bands:
            r.write('<a href="%s">%s</a> - %d<br/>' % (b.canonical(), b.band_slug(), n))

class OpenPage(webapp2.RequestHandler):
    def get(self):
        r = self.response
        r.headers['Content-Type'] = 'text/html'
        openthrs = get_db_open_threads()

        r.write('''<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Open threads</title>
    </head>
    <body>
        <h1>Open Threads</h1>
        ''')

        for thr in openthrs:
            r.write('<h2><a href="http://boards.4chan.org/mu/thread/%d">"%s"</a></h2>' % (thr.id(), thr.sub()))
            for b in thr.posts:
                if b.is_band():
                    r.write('<div id="p%d" style="background: #cccccc;">%s</div>' % (b.id(), b.com()))
                    for c in thr.ref_to_post(b.id()):
                        r.write('<div id="p%d" style="background: #efefef; margin:1em;margin-left:2em;">%s</div>' % (c.id(), c.com()))
        r.write('''
    </body>
</html>''')


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/update', UpdatePage),
    ('/open', OpenPage),
    ('/popular', PopularPage)
], debug=True)
