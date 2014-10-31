#!/bin/env python2

import board
import cPickle as pickle
import argparse
import logging
import logging.handlers
import sys

log = logging.getLogger('archive')
log.setLevel(logging.WARNING)
log.addHandler(logging.StreamHandler(sys.stderr))

DEFAULT_DB = 'mu_band_db.pickle'


def index(e, list):
    try:
        return list.index(e)
    except ValueError:
        return -1

def load(db):
    try:
        f = open(db)
        return pickle.load(f)
    except IOError:
        return []

def save(thrs, db):
    f = open(db, 'w+')
    pickle.dump(thrs, f)

def open_threads(thrs):
    r = []
    for t in thrs:
        if t.is_open():
            r.append(t)
    return r

def update_threads(db):
    thrs = load(db)

    openthrs = open_threads(thrs)
    openthr_ids = [thr.id() for thr in openthrs]

    catathrs = board.get_catalog_threads()
    catathr_ids = [thr.id() for thr in catathrs]

    # 1. update or add threads from the catalog
    for thr in catathrs:
        log.info("T %d (catalog)" % thr.id())
        i = index(thr.id(), openthr_ids)
        if i >= 0:
            if thr.newer_than(openthrs[i]):
                # fetch full thread and update entry in db
                log.info("fetch & update")
                openthrs[i].update()
        else:
            # fetch full thread and create entry in db
            log.info("fetch & create")
            thr.update() # fetch full thread
            thrs.append(thr)

    # 2. close any open thread not in the catalog anymore
    for thr in openthrs:
        if thr.id() not in catathr_ids:
            log.info("close %d & update" % thr.id())
            thr.close()

    save(thrs, db)

def main():
    parser = argparse.ArgumentParser(description='Archive /mu/ bandcamp threads')
    parser.add_argument('-f', '--file', help='use file as pickle db', default=DEFAULT_DB)
    parser.add_argument('-v', '--verbose', help='verbose', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        log.setLevel(logging.INFO)
    update_threads(args.file)

if __name__ == '__main__':
    main()
