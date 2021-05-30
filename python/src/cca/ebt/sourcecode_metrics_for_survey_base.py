#!/usr/bin/env python3

'''
  Source code metrics

  Copyright 2013-2018 RIKEN
  Copyright 2018-2020 Chiba Institute of Technology

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
'''

__author__ = 'Masatomo Hashimoto <m.hashimoto@stair.center>'

import sys
import pprint
import logging

from cca.ccautil.sparql import get_localname
from cca.ccautil import sparql
from cca.ccautil.ns import FB_NS, NS_TBL
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT

logger = logging.getLogger()

LINES_OF_CODE        = 'lines_of_code'
MAX_LOOP_DEPTH       = 'max_loop_depth'
MAX_FUSIBLE_LOOPS    = 'max_fusible_loops'
MAX_MERGEABLE_ARRAYS = 'max_mergeable_arrays'
MAX_ARRAY_RANK       = 'max_array_rank'
MAX_LOOP_LEVEL       = 'max_loop_level'

N_BRANCHES   = 'branches'
N_STMTS      = 'stmts'
N_FP_OPS     = 'fp_ops'
N_OPS        = 'ops'
N_CALLS      = 'calls'

N_A_REFS     = ['array_refs0','array_refs1','array_refs2']
N_IND_A_REFS = ['indirect_array_refs0','indirect_array_refs1','indirect_array_refs2']
N_DBL_A_REFS = ['dbl_array_refs0','dbl_array_refs1','dbl_array_refs2']

BF = ['bf0','bf1','bf2']

abbrv_tbl = {
    LINES_OF_CODE        : 'LOC',
    MAX_LOOP_DEPTH       : 'LpD',
    MAX_FUSIBLE_LOOPS    : 'FLp',
    MAX_MERGEABLE_ARRAYS : 'MA',
    MAX_ARRAY_RANK       : 'ARk',
    MAX_LOOP_LEVEL       : 'LLv',

    N_BRANCHES   : 'Br',
    N_STMTS      : 'St',
    N_FP_OPS     : 'FOp',
    N_OPS        : 'Op',
    N_CALLS      : 'Ca',

    N_A_REFS[0]     : 'AR0',
    N_IND_A_REFS[0] : 'IAR0',
    N_DBL_A_REFS[0] : 'DAR0',

    N_A_REFS[1]     : 'AR1',
    N_IND_A_REFS[1] : 'IAR1',
    N_DBL_A_REFS[1] : 'DAR1',

    N_A_REFS[2]     : 'AR2',
    N_IND_A_REFS[2] : 'IAR2',
    N_DBL_A_REFS[2] : 'DAR2',

    BF[0] : 'BF0',
    BF[1] : 'BF1',
    BF[2] : 'BF2',
}

###


def ent_to_str(uri_str):
    return uri_str.replace(NS_TBL['ent_ns'], '')



Q_PROJ_LIST = '''
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?g
WHERE {
GRAPH ?g {
  ?src a src:SourceTree .
}
}
''' % NS_TBL


GITREV_PREFIX = NS_TBL['gitrev_ns']

def get_lver(uri):
    v = get_localname(uri)
    if uri.startswith(GITREV_PREFIX):
        v = v[0:7]
    return v


def get_proj_list(method='odbc'):
    driver = sparql.get_driver(method)

    proj_list = []

    for qvs, row in driver.query(Q_PROJ_LIST):
        g = row['g']
        proj_list.append(get_localname(g))

    return proj_list


def ftbl_list_to_orange(ftbl_list, outfile, META_KEYS):
    
    if not ftbl_list:
        return

    import Orange

    ks = ftbl_list[0].keys()
    ks.remove('meta')

    items = list(ks)

    features = [Orange.feature.Continuous(k) for k in items]
    domain = Orange.data.Domain(features, False)

    def add_meta(m):
        domain.add_meta(Orange.feature.Descriptor.new_meta_id(), Orange.feature.String(m))

    keys = META_KEYS

    for k in keys:
        add_meta(k)

    data = Orange.data.Table(domain)
    
    for ftbl in ftbl_list:
        vs = [ftbl[item] for item in items]
        inst = Orange.data.Instance(domain, vs)
        m = ftbl['meta']
        for k in keys:
            inst[k] = m[k]

        data.append(inst)
    
    try:
        data.save(outfile)
    except Exception as e:
        logger.error(str(e))



class Ent:
    def __init__(self, ent, is_loop=False):
        self.ent = ent
        self.is_loop = is_loop

    def __hash__(self):
        return self.ent.__hash__()

    def __eq__(self, other):
        return self.ent == other.ent and self.is_loop == other.is_loop
        


class MetricsBase(object):
    def __init__(self, proj_id, method='odbc',
                 pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):

        self._proj_id = proj_id
        self._graph_uri = FB_NS + proj_id
        self._sparql = sparql.get_driver(method, pw=pw, port=port)

        self._tree = None

        self._result_tbl = {} # item name -> (ver * loc * lnum) -> value

        self._metadata_tbl = {} # (ver * loc * lnum) -> {'sub','digest'}

        self._ipp_tbl = {} # uri -> uri (inter-procedural parent tbl)

        self._ent_tbl = {} # uri -> is_loop

        self._loop_digest_tbl = {} # (ver * loc * sub * loop) -> digest set

        self._max_loop_level_tbl = {} # uri -> lv

    def get_loop_digest(self, key):
        digest = None
        ds = self._loop_digest_tbl.get(key, None)
        if ds:
            digest = ':'.join(sorted(list(ds)))
        return digest

    def set_loop_digest(self, key, d):
        try:
            s = self._loop_digest_tbl[key]
        except KeyError:
            s = set()
            self._loop_digest_tbl[key] = s
        s.add(d)

    def get_metadata(self, key):
        return self._metadata_tbl[key]

    def get_tree(self):
        return self._tree

    def set_tree(self, tree):
        self._tree = tree


    def get_item_tbl(self, name):
        return self._result_tbl[name]

    def get_value(self, name, key):
        v = 0

        try:
            v = self._result_tbl[name][key]
        except KeyError:
            pass

        return v

    def search(self, _key): # VER:PATH:LNUM

        key = tuple(_key.split(':'))

        logger.info('key=(%s,%s,%s)' % key)

        ftbl_list = []

        try:
            ftbl = self.find_ftbl(key)
            ftbl_list.append(ftbl)
        except KeyError:
            pass

        return ftbl_list

    def dump(self):
        pp = pprint.PrettyPrinter(indent=2)
        pp.pprint(self._result_tbl)


    def find_ftbl(self, key):
        raise KeyError
        

    def get_ftbl_list(self):
        keys = set()

        for (item, tbl) in self._result_tbl.items():
            for k in tbl.keys():
                keys.add(k)

        ftbl_list = []

        for key in keys:
            ftbl = self.find_ftbl(key)
            ftbl_list.append(ftbl)

        return ftbl_list


    def key_to_string(self, key):
        return '<KEY>'

    def set_metrics(self, name, _key, value, add=False):
        pass

    def ipp_add(self, ent, parent, is_loop=False):
        try:
            s = self._ipp_tbl[ent]
        except KeyError:
            s = set()
            self._ipp_tbl[ent] = s

        self._ent_tbl[parent] = is_loop
        s.add(parent)


    def finalize_ipp(self):
        pass

    def build_tree(self, f=None):
        return {}


    def iter_tree(self, tree, root, f):
        children_tbl = tree['children']
        for child in children_tbl.get(root, []):
            if root != child:
                self.iter_tree(tree, child, f)
        f(root)

    def calc_loop_metrics(self):
        logger.info('calculating loop metrics...')

        try:
            tree = self.build_tree()
            children_tbl = tree['children']
            parent_tbl   = tree['parent']
            top_loops    = tree['roots']

            #

            def get_max_depth(depth, key):
                children = filter(lambda c: c != key, children_tbl.get(key, []))
                l = [depth]+[get_max_depth(depth+1, k) for k in children]
                return max(l)

            for key in top_loops:

                max_loop_depth = get_max_depth(1, key)

                fusible_tbl = {}

                def find_fusible_loops(key):
                    for (_, _, _, _, vn) in children_tbl.get(key, []):
                        try:
                            fusible_tbl[(key, vn)] += 1
                        except KeyError:
                            fusible_tbl[(key, vn)] = 1

                self.iter_tree(tree, key, find_fusible_loops)

                max_fusible_loops = 0
                if fusible_tbl:
                    max_fusible_loops = max(fusible_tbl.values())

                logger.debug('key=%s' % (self.key_to_string(key)))
                logger.debug('max_loop_depth=%d max_fusible_loops=%d' % (max_loop_depth,
                                                                       max_fusible_loops,
                                                                   ))

                self.set_metrics(MAX_LOOP_DEPTH, key, max_loop_depth)
                self.set_metrics(MAX_FUSIBLE_LOOPS, key, max_fusible_loops)

        except KeyError:
            pass

        logger.info('done.')


    def get_key(self, row):
        key = ('', '', '', '', '')
        return key

    def get_loop_of_key(self, key):
        (lver, loc, sub, loop, vname) = key
        return loop


    def calc_max_loop_level(self):
        logger.info('calculating loop level...')
        tree = self.get_tree()
        for key in tree['roots']:
            loop = self.get_loop_of_key(key)
            lv = self.get_max_loop_level(loop)
            self.set_metrics(MAX_LOOP_LEVEL, key, lv)

    def get_max_loop_level(self, ent):
        lv = self._get_max_loop_level([], ent)
        return lv
            
    def _get_max_loop_level(self, traversed, ent):
        max_lv = 0
        try:
            max_lv = self._max_loop_level_tbl[ent]
        except KeyError:
            n = len(traversed)
            lvs = []
            indent = '  '*n
            logger.debug('%s* %s ->' % (indent, ent_to_str(ent)))
            for p in self._ipp_tbl.get(ent, []):
                lv = 0
                is_loop = self._ent_tbl[p]

                if p not in traversed and p != ent:
                    if is_loop:
                        lv += 1
                    lv += self._get_max_loop_level([ent]+traversed, p)

                logger.debug('%s  %s (%s) %d' % (indent, ent_to_str(p), is_loop, lv))

                lvs.append(lv)

            if lvs:
                max_lv = max(lvs)
            
            self._max_loop_level_tbl[ent] = max_lv

            logger.debug('%s%d' % (indent, max_lv))

        return max_lv




if __name__ == '__main__':
    pass
