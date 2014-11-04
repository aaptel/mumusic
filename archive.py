#!/usr/bin/env python

import cPickle as pickle
import argparse
import logging
import logging.handlers
import sys
import errno
import time
import os
import json
import gzip
import requests
import re

LOG = logging.getLogger('archive')

DEFAULT_DB  = 'mu_db.pkl.gz'
CATALOG_URL = 'http://a.4cdn.org/mu/catalog.json'
THREAD_URL  = 'http://a.4cdn.org/mu/thread/%d.json'
DOWNLOAD_DELAY = .6
LOG_DIR = 'logs'
NB_DL = 0

THREAD_RX = map(lambda x: re.compile(x, flags=re.IGNORECASE), [
    'bandcamp', 'soundcloud', 'youtube', 'jamendo', 'alonetone', 'altsounds', '8tracks',
    'vibedeck', 'topspin', 'noisetrade', 'myspace',
])


def init_log(level=logging.INFO, email=False, file=False):
    LOG.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", datefmt="%Y-%m-%d %H:%M")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    LOG.addHandler(console)

    try:
        os.makedirs(LOG_DIR)
    except OSError as e:
        if e.errno != errno.EEXIST:
            LOG.error("can't create log dir '%s': %s", LOG_DIR, e.strerror)


    if email and os.path.isfile("/usr/sbin/sendmail"):
        h = MailHandler('mu-archive@diobla.info', ['aurelien.aptel@gmail.com'], 'mu-archive log report', 100)
        h.setLevel(logging.WARNING)
        h.setFormatter(fmt)
        LOG.addHandler(h)
    if file:
        h = logging.FileHandler(os.path.join(LOG_DIR, "log"))
        h.setLevel(logging.INFO)
        h.setFormatter(fmt)
        LOG.addHandler(h)

# logging handler that sends emails using sendmail
class MailHandler(logging.handlers.BufferingHandler):
    def __init__(self, fromaddr, toaddrs, subject, capacity=10):
        logging.handlers.BufferingHandler.__init__(self, capacity)
        self.fromaddr = fromaddr
        self.toaddrs = toaddrs
        self.subject = subject

    def flush(self):
        if len(self.buffer) > 0:
            p = os.popen("/usr/sbin/sendmail -t", "w")
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (self.fromaddr, string.join(self.toaddrs, ","), self.subject)
            for record in self.buffer:
                s = self.format(record)
                #print s
                msg += s + "\r\n"
            p.write(msg)
            r = p.close()
            self.buffer = []


def load(db):
    LOG.debug('loading db %s', db)

    start = time.time()
    try:
        f = gzip.open(db)
        r = pickle.load(f)
    except IOError:
        r = {}

    LOG.info('db %s loaded in %.03fs', db, time.time()-start)
    return r

def save(thrs, db):
    LOG.debug('saving db %s', db)

    start = time.time()
    f = gzip.open(db, 'w+')
    pickle.dump(thrs, f)
    LOG.info('db %s saved in %.03fs', db, time.time()-start)

def get(url):
    global NB_DL
    NB_DL += 1
    LOG.debug('fetch url %s', url)

    r = requests.get(url)

    time.sleep(DOWNLOAD_DELAY)
    return r

def get_file_name():
    n = int((time.time() + 0.5) * 1000)
    while os.path.exists(os.path.join(LOG_DIR, str(n))):
        n += 1
    return os.path.join(LOG_DIR, str(n))

def dump_object(o):
    fn = get_file_name()
    f = open(fn, 'w+')
    pickle.dump(o, f)
    return fn

def get_thread(no):
    LOG.debug('fetch thread %d', no)

    r = get(THREAD_URL % no)
    if r.status_code == 404:
        LOG.info('thread %d is dead (404)', no)
        return None
    if r.status_code == 200:
        return r
    else:
        LOG.error('fetch thread %d: status_code = %d, response dump in %s', no, r.status_code, dump_object(r.text))
        return None


def clean(html):
    return re.sub(r'''<wbr>''', '', html)

def keep_thread_p(t):
    if len(t['posts']) > 10:
        for p in t['posts']:
            txt = clean(p.get('sub', '') + ' ' + p.get('com', ''))
            for rx in THREAD_RX:
                if re.search(rx, txt):
                    return True
    return False

def update(db):
    start = time.time()
    thrs = load(db)

    r = get(CATALOG_URL)
    if r.status_code != 200:
        LOG.error('fetch catalog: status_code = %d, response dump in %s', r.status_code, dump_object(r.text))
        raise Exception("fetch catalog failed")

    cata = r.json()
    nb_thr = 0

    # start by the last threads to limit 404s
    for page in reversed(cata):
        for t in reversed(page['threads']):
            n = t['no']
            r = get_thread(n)
            if r is not None:
                t = r.json()
                if keep_thread_p(t):
                    thrs[n] = t
                    nb_thr += 1

    save(thrs, db)
    LOG.info('update done in %.03fs (%d fetch, +%d threads)', time.time()-start, NB_DL, nb_thr)

def purge(db):
    start = time.time()
    thrs = load(db)
    new = {}
    for k in thrs:
        if keep_thread_p(thrs[k]):
            new[k] = thrs[k]
    save(new, db)
    LOG.info('purge done in %.03fs (-%d threads)', time.time()-start, len(thrs)-len(new))

def dump_json(db, thr=None, pretty=None):
    thrs = load(db)
    opts = {}

    if pretty:
        opts['sort_keys'] = True
        opts['indent'] = 4
        opts['separators'] = (',', ': ')

    if thr:
        json.dump(thrs.get(thr, {}), sys.stdout, **opts)
    else:
        json.dump(thrs, sys.stdout, **opts)

def merge(db, files):
    start = time.time()
    thrs = load(db)
    nb = len(thrs)
    for f in files:
        ts = load(f)
        for k in ts:
            if k not in thrs or len(ts[k]['posts']) > len(thrs[k]):
                thrs[k] = ts[k]
    save(thrs, db)
    LOG.info('merge done in %.03fs (+%d threads)', time.time()-start, len(thrs)-nb)

def main():
    parser = argparse.ArgumentParser(description='Archive /mu/ threads')
    parser.add_argument('-m', '--merge', help='merge db with another one', nargs='+')
    parser.add_argument('-f', '--file', help='use file as pickle db', default=DEFAULT_DB)
    parser.add_argument('-j', '--json', help='dump on stdout as json', action='store_true')
    parser.add_argument('-p', '--pretty', help='pretty print json output', action='store_true')
    parser.add_argument('-P', '--purge', help='purge db (re-apply thread predicate)', action='store_true')
    parser.add_argument('-t', '--thread', help='dump single thread', type=int)
    parser.add_argument('-v', '--verbose', help='verbose, show debug messages', action='store_true')
    parser.add_argument('-l', '--log', help='log output type', action='append', default=[], choices=['file', 'email'])
    args = parser.parse_args()

    init_log(level=(logging.DEBUG if args.verbose else logging.INFO),
             file=('file' in args.log),
             email=('email' in args.log))

    if args.json:
        dump_json(args.file, thr=args.thread, pretty=args.pretty)
    elif args.purge:
        purge(args.file)
    elif args.merge:
        merge(args.file, args.merge)
    else:
        update(args.file)

if __name__ == '__main__':
    try:
        main()
    except:
        LOG.exception('archive exception')
