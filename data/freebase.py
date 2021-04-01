#!/usr/bin/env python3
'''Load freebase topic JSON for each feature.

This includes goodies like descriptions, population and area.
'''

import os
import json
import sys
import urllib.request, urllib.error, urllib.parse

from data import mqlkey

PREDICATE_PREFIXES = ['/location/statistical_region', '/common/topic']

MONKEY_PATCHES = {
    'Myanmar': 'Burma',
    'Vatican City State': 'Vatican City'
}

def _path(filename):
    return os.path.join(os.path.dirname(__file__), filename)

TOPIC_OVERRIDES = json.load(open(_path('topic-overrides.json')))

class Freebase(object):
    '''Freebase Topic API wrapper. Maps wikipedia title --> topic JSON.'''
    service_url = 'https://www.googleapis.com/freebase/v1/topic'
    cache_dir = '/var/tmp/freebase'

    def __init__(self, api_key=None, use_cache=True):
        if not api_key:
            api_key = open(os.path.join(os.path.dirname(__file__), '.freebase_api_key')).read()
        self._key = api_key
        self._use_cache = use_cache

    def _cache_file(self, title):
        title = title.replace(' ', '_').replace('/', '_')
        return os.path.join(self.cache_dir, '%s.json' % title)

    def _get_from_cache(self, title):
        if not self._use_cache: return None
        p = self._cache_file(title)
        if os.path.exists(p):
            try:
                d = json.load(open(p))
            except ValueError:
                sys.stderr.write('Unable to decode json for %s, %s\n' % (title, p))
                raise

            if 'error' in d:
                return None
            sys.stderr.write('Loaded %s from cache.\n' % title)
            return d
        else:
            return None

    def _construct_url(self, title):
        params = [
            ('key', self._key),
            ('limit', 1000)  # get population at lots of dates!
        ] + [('filter', x) for x in PREDICATE_PREFIXES]

        if title in MONKEY_PATCHES:
            title = MONKEY_PATCHES[title]

        if title in TOPIC_OVERRIDES:
            topic_id = TOPIC_OVERRIDES[title]
        else:
            title_key = quotekey(title)
            topic_id = '/wikipedia/en_title/%s' % title_key
        url = self.service_url + topic_id + '?' + urllib.parse.urlencode(params)
        return url

    def get_topic_json(self, title):
        '''title is a Wikipedia title for the topic.'''
        d = self._get_from_cache(title)
        if d: return d

        url = self._construct_url(title)
        sys.stderr.write('Fetching %s\n' % url)
        data = urllib.request.urlopen(url, None, 10.0).read()
        #if self._use_cache:
        open(self._cache_file(title), 'w').write(data)
        return json.loads(data)


WIKI_URL_PREFIX = 'http://en.wikipedia.org/wiki/'
def wiki_url_to_title(uurl):
    if isinstance(uurl, str):
        url = uurl
    else:
        raise ValueError('wiki_url_to_title() expects utf-8 string or unicode')

    if WIKI_URL_PREFIX not in url:
        sys.stderr.write('ERROR Invalid wiki URL: %s\n' % url)
        return None

    title = url.replace(WIKI_URL_PREFIX, '')
    title = urllib.parse.unquote(title)
    title = title.replace('_', ' ')
    return title


def get_aliases(topic):
    try:
        aliases = topic['property']['/common/topic/alias']['values']
    except KeyError:
        return []

    return [v['text'] for v in aliases]


def quotekey(title):
    return mqlkey.quotekey(title.replace(' ', '_'))


if __name__ == '__main__':
    freebase = Freebase()
    freebase_nocache = Freebase(use_cache=False)

    gj = json.load(open("comparea/static/data/comparea.geo.json"))
    for feature in gj['features']:
        props = feature['properties']
        url = props['wikipedia_url']
        title = wiki_url_to_title(url)
        if not title:
            continue

        try:
            d = freebase.get_topic_json(title)
            if 'property' not in d or len(d['property']) == 0:
                d = freebase_nocache.get_topic_json(title)
        except IOError:
            sys.stderr.write('ERROR unable to fetch %s\n' % title)
