#!/bin/env python2

import sys
sys.path.insert(0, 'lib')

import requests as R
from bs4 import BeautifulSoup as BS
import re
import cgi

URL_REGEX = re.compile(r'(?:https?://)?[0-9a-z-]+\.bandcamp\.com(?:/(?:album|track)/[0-9a-z-]+)?(?:#[0-9a-z-]*)?')
URL_CAPTURE_REGEX = re.compile(r'(?:https?://)?([0-9a-z-]+)\.bandcamp\.com(/(?:album|track)/[0-9a-z-]+)?(?:#[0-9a-z-]*)?')


def valid_url(url):
    return re.match(URL_REGEX, url)

def extract_urls(text):
    return re.findall(URL_REGEX, text)

def repl_url(m):
    t = m.group(0)
    if str.startwith('http', t):
        return '<a href="%s">%s</a>' % (t,t)
    else:
        return '<a href="https://%s">%s</a>' % (t,t)

def urlify(text):
    return re.sub(URL_REGEX, repl_url, text)

class BandcampUrl:
    def __init__(self, url):
        self._url = url
        self._artist = None
        self._bs = None


    def soup(self):
        if self._bs is None:
            r = R.get(self._url)
            self._bs = BS(r.text)
        return self._bs

    def artist(self):
        if self._artist is None:
            # should works on artist, album or track pages
            self._artist = self.soup().select('p#band-name-location span.title')[0].get_text()
        return self._artist

    def canonical(self):
        m = re.match(URL_CAPTURE_REGEX, self._url)
        base = 'https://%s.bandcamp.com' % m.group(1)
        if m.group(2):
            base += m.group(2)
        return base

#
# TESTS
#

import unittest
class BandcampTests(unittest.TestCase):

    def test_valid_url(self):
        self.assertTrue(valid_url('https://backtoakert.bandcamp.com/'))
        self.assertTrue(valid_url('http://backtoakert.bandcamp.com/'))
        self.assertTrue(valid_url('http://backto-akert.bandcamp.com'))
        self.assertTrue(valid_url('https://twistpillar.bandcamp.com/album/unity-plaza-deluxe'))
        self.assertTrue(valid_url('https://twistpillar.bandcamp.com/track/b-ss'))
        self.assertTrue(valid_url('gxrxnimx.bandcamp.com'))

        self.failIf(valid_url('https://bandcamp.com'))

    def test_artist(self):
        a = 'Twistpillar'
        self.assertTrue(BandcampUrl('https://twistpillar.bandcamp.com/album/unity-plaza-deluxe').artist() == a)
        self.assertTrue(BandcampUrl('https://twistpillar.bandcamp.com/track/b-ss').artist() == a)
        self.assertTrue(BandcampUrl('https://twistpillar.bandcamp.com').artist() == a)

    def test_extract(self):
        t = '''https://oddfellowsrest.bandcamp.com/album/odd-fellows-rest
>A mix of way too many electronic genres
>Samples from random historical figures
Someone described it as "nightmare soundtracks", I like that description.
-
- gxrxnimx.bandcamp.com
-'''
        urls = ['https://oddfellowsrest.bandcamp.com/album/odd-fellows-rest', 'gxrxnimx.bandcamp.com']

        self.assertEqual(extract_urls(t), urls)

    def test_canonical(self):
        #
        # EQUAL TESTS
        #

        c = 'https://test.bandcamp.com'
        urls = ['test.bandcamp.com', 'http://test.bandcamp.com', 'http://test.bandcamp.com/', 'test.bandcamp.com/#zob']
        self.assertEqual(BandcampUrl(c).canonical(), c)
        for u in urls:
            self.assertEqual(BandcampUrl(u).canonical(), c)

        c = 'https://test.bandcamp.com/album/zob'
        urls = ['test.bandcamp.com/album/zob#foo', 'http://test.bandcamp.com/album/zob']
        self.assertEqual(BandcampUrl(c).canonical(), c)
        for u in urls:
            self.assertEqual(BandcampUrl(u).canonical(), c)

        #
        # NOT EQUAL
        #

        c = 'https://test.bandcamp.com/album/zob'
        urls = ['test.bandcamp.com', 'http://test.bandcamp.com/track/zob']
        for u in urls:
            self.assertNotEqual(BandcampUrl(u).canonical(), c)

if __name__ == '__main__':
    unittest.main()
