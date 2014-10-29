#!/bin/env python2

import sys
sys.path.insert(0, 'lib')

import requests as R
from bs4 import BeautifulSoup as BS
import re

URL_REGEX = re.compile(r'(?:https?://)?[0-9a-z-]+\.bandcamp\.com(?:/(?:album|track)/[0-9a-z-]+)?(?:#[0-9a-z-]*)?')

def valid_url(url):
    return re.match(URL_REGEX, url)

def extract_urls(text):
    return re.findall(URL_REGEX, text)

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



if __name__ == '__main__':
    unittest.main()
