#!/usr/bin/env python3

'''
  Source code metrics for C programs

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
import logging

from .sourcecode_metrics_for_survey_base import get_lver, get_proj_list, ftbl_list_to_orange, MetricsBase
from .metrics_queries_cpp import QUERY_TBL

from cca.ccautil import sparql
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT
from cca.factutil.entity import SourceCodeEntity

logger = logging.getLogger()

FOP_TBL = { # number of FP operations (for SPARC64 VIIIfx)
    'nint'  : 2,
    'jnint' : 2,
    'cos'   : 29,
    'dcos'  : 31,
    'exp'   : 19,
    'dexp'  : 23,
    'log'   : 19,
    'alog'  : 19,
    'dlog'  : 23,
    'mod'   : 8,
    'amod'  : 8,
    'dmod'  : 8,
    'sign'  : 2,
    'dsign' : 2,
    'sin'   : 29,
    'dsin'  : 31,
    'sqrt'  : 11,
    'dsqrt' : 21,
    'tan'   : 58,
    'dtan'  : 64,
}
FOP_TBL_DBL_EXTRA = {
    'cos'  : 2,
    'exp'  : 4,
    'log'  : 4,
    'sin'  : 2,
    'sqrt' : 10,
    'tan'  : 6,
}
FOP_TBL_VA = {
    'max'   : lambda n: n-1,
    'amax1' : lambda n: n-1,
    'dmax1' : lambda n: n-1,
    'min'   : lambda n: n-1,
    'amin1' : lambda n: n-1,
    'dmin1' : lambda n: n-1,
}

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

META_KEYS = ['proj', 'ver', 'path', 'sub', 'lnum', 'digest']

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

def count_aas(aas):
    c = 0
    for aa in aas:
        if aa.startswith(','):
            c += 2
        else:
            c += 1
    return c

def get_nfops(name, nargs, double=False):
    nfop = 1
    try:
        nfop = FOP_TBL_VA[name](nargs)
    except KeyError:
        nfop = FOP_TBL.get(name, 1)
        if double:
            nfop += FOP_TBL_DBL_EXTRA.get(name, 0)
    prec = 's'
    if double:
        prec = 'd'
    logger.debug('%s{%s}(%d) --> %d' % (name, prec, nargs, nfop))
    return nfop


def make_feature_tbl():
    v = { 'meta' : {'proj' : '',
                    'ver'  : '', 
                    'path' : '',
                    'sub'  : '',
                    'lnum' : '',
                },
          
          BF[0]                : 0.0,
          BF[1]                : 0.0,
          BF[2]                : 0.0,

          N_FP_OPS             : 0,
          N_OPS                : 0,

          N_A_REFS[0]          : 0,
          N_IND_A_REFS[0]      : 0,
          N_DBL_A_REFS[0]      : 0,
          N_A_REFS[1]          : 0,
          N_IND_A_REFS[1]      : 0,
          N_DBL_A_REFS[1]      : 0,
          N_A_REFS[2]          : 0,
          N_IND_A_REFS[2]      : 0,
          N_DBL_A_REFS[2]      : 0,

          N_BRANCHES           : 0,
          N_STMTS              : 0,
          N_CALLS              : 0,

          LINES_OF_CODE        : 0,

          MAX_LOOP_LEVEL       : 0,
          MAX_ARRAY_RANK       : 0,
          MAX_LOOP_DEPTH       : 0,
          MAX_FUSIBLE_LOOPS    : 0,
          MAX_MERGEABLE_ARRAYS : 0,
      }
    return v


def ftbl_to_string(ftbl):
    meta_str = '%(proj)s:%(ver)s:%(path)s:%(sub)s:%(lnum)s' % ftbl['meta']
    cpy = ftbl.copy()
    cpy['meta'] = meta_str

    ks = ftbl.keys()
    ks.remove('meta')
    
    fmt = '%(meta)s ('

    fmt += ','.join(['%s:%%(%s)s' % (abbrv_tbl[k], k) for k in ks])

    fmt += ')'

    s = fmt % cpy

    return s



class Metrics(MetricsBase):
    def __init__(self, proj_id, method='odbc',
                 pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):

        MetricsBase.__init__(self, proj_id, method, pw, port)


    def find_ftbl(self, key):
        md = self.get_metadata(key)
        fn = md['fn']
        digest = md['digest']

        (ver, path, lnum) = key

        ftbl = make_feature_tbl()

        ftbl['meta'] = {
            'proj'   : self._proj_id,
            'ver'    : ver,
            'path'   : path,
            'fn'     : fn,
            'lnum'   : str(lnum),
            'digest' : digest,
        }

        fop = self.get_value(N_FP_OPS, key)

        if fop > 0:
            for lv in range(3):
                if BF[lv] in ftbl:
                    aa  = self.get_value(N_A_REFS[lv], key)
                    daa = self.get_value(N_DBL_A_REFS[lv], key)
                    saa = aa - daa
                    bf = float(saa * 4 + daa * 8) / float(fop)
                    print('!!! {} -> fop={} aa[{}]={} daa[{}]={} bf[{}]={}'.format(key, fop, lv, aa, lv, daa, lv, bf))
                    ftbl[BF[lv]] = bf
            
        for item in ftbl.keys():
            try:
                ftbl[item] = self._result_tbl[item][key]
            except KeyError:
                pass

        return ftbl
        

    def key_to_string(self, key):
        (ver, loc, fn, loop, vname) = key
        e = SourceCodeEntity(uri=loop)
        lnum = e.get_range().get_start_line()
        s = '%s:%s:%s:%s' % (ver, loc, fn, lnum)
        return s


    def set_metrics(self, name, _key, value, add=False):
        #print('!!! set_metrics: name={} key={} value={} add={}'.format(name, _key, value, add))

        (ver, loc, fn, loop, vname) = _key

        ent = SourceCodeEntity(uri=loop)
        lnum = ent.get_range().get_start_line()

        key = (ver, loc, str(lnum))
        key_str = '%s:%s:%s' % key

        logger.debug('%s(%s): %s -> %s' % (self.key_to_string(_key), key_str, name, value))

        loop_d = self.get_loop_digest(_key)

        self._metadata_tbl[key] = {'fn':fn,'digest':loop_d}

        try:
            tbl = self._result_tbl[name]
        except KeyError:
            tbl = {}
            self._result_tbl[name] = tbl

        if add:
            v = tbl.get(key, 0)
            tbl[key] = v + value
        else:
            tbl[key] = value


    def finalize_ipp(self):
        logger.info('finalizing call graph...')

        query = QUERY_TBL['fd_fd'] % { 'proj' : self._graph_uri }

        for qvs, row in self._sparql.query(query):
            callee = row['callee']
            fd     = row['fd']
            self.ipp_add(callee, fd)

        query = QUERY_TBL['loop_fd'] % { 'proj' : self._graph_uri }

        for qvs, row in self._sparql.query(query):
            callee = row['callee']
            loop   = row['loop']
            self.ipp_add(callee, loop, is_loop=True)


    def build_tree(self, f=None):
        query = QUERY_TBL['loop_loop'] % { 'proj' : self._graph_uri }

        children_tbl = {}
        parent_tbl = {}

        for qvs, row in self._sparql.query(query):
            ver   = row['ver']
            loc   = row['loc']
            fn    = row.get('fn', '')
            loop  = row['loop']
            loop_d = row['loop_d']
            vname = ''

            child_loop = row.get('child_loop', None)
            child_loop_d = row.get('child_loop_d', '')
            child_vname = ''

            lver = get_lver(ver)

            key = (lver, loc, fn, loop, vname)
            self.set_loop_digest(key, loop_d)

            if f:
                f(key, row)

            try:
                child_loops = children_tbl[key]
            except KeyError:
                child_loops = []
                children_tbl[key] = child_loops

            if child_loop:
                child_key = (lver, loc, fn, child_loop, child_vname)
                self.set_loop_digest(child_key, child_loop_d)

                if child_key not in child_loops:
                    child_loops.append(child_key)
                    parent_tbl[child_key] = key
                    self.ipp_add(child_loop, loop, is_loop=True)

        roots = []
        for k in children_tbl.keys():
            if k not in parent_tbl:
                roots.append(k)
                r = SourceCodeEntity(uri=self.get_loop_of_key(k)).get_range()
                lines = r.get_end_line() - r.get_start_line() + 1
                self.set_metrics(LINES_OF_CODE, k, lines)

        logger.info('%d top loops found' % len(roots))
                
        tree = {'children':children_tbl,'parent':parent_tbl,'roots':roots}

        self.set_tree(tree)

        return tree


    def get_key(self, row):
        ver    = row['ver']
        loc    = row['loc']
        fn     = row.get('fn', '')
        loop   = row['loop']
        vname  = ''

        lver = get_lver(ver)
        key = (lver, loc, fn, loop, vname)
        return key


    def calc_array_metrics(self):
        logger.info('calculating array metrics...')

        try:
            query = QUERY_TBL['arrays'] % { 'proj' : self._graph_uri }

            tbl = {}

            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)

                array = row['dtor']
                tyc   = row['tyc']
                rank  = int(row['rank'])
                try:
                    arrays = tbl[key]
                except KeyError:
                    arrays = []
                    tbl[key] = arrays

                arrays.append((array, (tyc, rank)))


            def get(key):
                arrays = tbl.get(key, [])
                max_rank = 0
                t = {}
                for (a, spec) in arrays:
                    (tyc, rank) = spec
                    if rank > max_rank:
                        max_rank = rank
                    try:
                        t[spec] += 1
                    except KeyError:
                        t[spec] = 1

                max_mergeable_arrays = 0
                for spec in t.keys():
                    if t[spec] > max_mergeable_arrays:
                        max_mergeable_arrays = t[spec]

                return {'max_rank':max_rank, 'max_mergeable_arrays':max_mergeable_arrays}


            tree = self.get_tree()

            for key in tree['roots']:

                data = {'max_rank':0, 'max_mergeable_arrays':0}

                def f(k):
                    d = get(k)
                    if d['max_rank'] > data['max_rank']:
                        data['max_rank'] = d['max_rank']
                    if d['max_mergeable_arrays'] > data['max_mergeable_arrays']:
                        data['max_mergeable_arrays'] = d['max_mergeable_arrays']

                self.iter_tree(tree, key, f)

                logger.debug('key=%s' % (self.key_to_string(key)))
                logger.debug('max_mergeable_arrays=%(max_mergeable_arrays)d max_rank=%(max_rank)d' % data)

                self.set_metrics(MAX_MERGEABLE_ARRAYS, key, data['max_mergeable_arrays'])
                self.set_metrics(MAX_ARRAY_RANK, key, data['max_rank'])

        except KeyError:
            pass

        logger.info('done.')


    def calc_in_loop_metrics(self):
        logger.info('calculating other in_loop metrics...')

        try:
            query = QUERY_TBL['in_loop'] % { 'proj' : self._graph_uri }

            def make_data():
                return { 'nbr'  : 0,
                         'nes'  : 0,
                         'nop'  : 0,
                         'nc'   : 0,
                     }

            tbl = {}

            for qvs, row in self._sparql.query(query):

                key = self.get_key(row)

                data = make_data()
                data['nbr']  = int(row['nbr'] or '0')
                data['nes']  = int(row['nes'] or '0')
                data['nop']  = int(row['nop'] or '0')
                data['nc']   = int(row['nc'] or '0')

                tbl[key] = data

                fd = row['fd']
                if fd:
                    self.ipp_add(row['loop'], fd)

            tree = self.get_tree()

            for key in tree['roots']:

                data = make_data()

                def f(k):
                    d = tbl.get(k, None)
                    if d:
                        data['nbr']   += d['nbr']
                        data['nes']   += d['nes']
                        data['nop']   += d['nop']
                        data['nc']    += d['nc']

                self.iter_tree(tree, key, f)

                self.set_metrics(N_BRANCHES,   key, data['nbr'])
                self.set_metrics(N_STMTS,      key, data['nes'])
                self.set_metrics(N_OPS,        key, data['nop'])
                self.set_metrics(N_CALLS,      key, data['nc'])

        except KeyError:
            raise

        logger.info('done.')
    # end of calc_in_loop_metrics


    def calc_aref_in_loop_metrics(self, lv): # level: 0, 1, 2
        logger.info('calculating other aref_in_loop metrics (lv=%d)...' % lv)

        try:
            if lv == 0:
                qtbl = QUERY_TBL['aref0_in_loop']
            elif lv == 1 or lv == 2:
                qtbl = QUERY_TBL['aref12_in_loop']
            else:
                logger.warning('illegal level: %d' % lv)
                return

            tbl = {}

            kinds = ['aa','iaa','daa']

            def make_data():
                d = {}
                for k in kinds:
                    d[k] = set()
                return d

            for kind in kinds:

                query = qtbl[kind] % {'proj':self._graph_uri,'level':lv}

                for qvs, row in self._sparql.query(query):

                    key = self.get_key(row)

                    sig = row.get('sig')

                    if sig:
                        try:
                            data = tbl[key]
                        except KeyError:
                            data = make_data()
                            tbl[key] = data

                        data[kind].add(sig)


            tree = self.get_tree()

            for key in tree['roots']:

                data = make_data()

                def f(k):
                    d = tbl.get(k, None)
                    if d:
                        for kind in kinds:
                            data[kind] |= d.get(kind, set())

                self.iter_tree(tree, key, f)

                self.set_metrics(N_A_REFS[lv],     key, count_aas(data['aa']))
                self.set_metrics(N_IND_A_REFS[lv], key, count_aas(data['iaa']))
                self.set_metrics(N_DBL_A_REFS[lv], key, count_aas(data['daa']))

        except KeyError:
            raise

        logger.info('done.')
    # end of calc_aref_in_loop_metrics


    def calc_fop_in_loop_metrics(self):
        logger.info('calculating fop metrics...')

        try:
            query = QUERY_TBL['fop_in_loop'] % { 'proj' : self._graph_uri }

            def make_data():
                return { 
                         'nfop' : 0,
                     }

            tbl = {}

            for qvs, row in self._sparql.query(query):

                key = self.get_key(row)

                data = make_data()
                data['nfop'] = int(row['nfop'] or '0')

                tbl[key] = data

                fd = row['fd']
                if fd:
                    self.ipp_add(row['loop'], fd)

            tree = self.get_tree()

            for key in tree['roots']:

                data = make_data()

                def f(k):
                    d = tbl.get(k, None)
                    if d:
                        data['nfop'] += d['nfop']

                self.iter_tree(tree, key, f)

                self.set_metrics(N_FP_OPS, key, data['nfop'])

        except KeyError:
            raise

        logger.info('done.')
    # end of calc_fop_in_loop_metrics


    def calc_ffr_in_loop_metrics(self):
        logger.info('calculating ffr metrics...')

        try:
            query = QUERY_TBL['ffr_in_loop'] % { 'proj' : self._graph_uri }

            tbl = {} # key -> hash -> fname * nargs * is_dbl

            for qvs, row in self._sparql.query(query):

                key = self.get_key(row)

                try:
                    fref_tbl = tbl[key] # hash -> fname * nargs * is_dbl
                except KeyError:
                    fref_tbl = {}
                    tbl[key] = fref_tbl

                h     = row['h']
                fname = row['fname']
                nargs = row['nargs']

                fref_tbl[h] = (fname, nargs, False)

                fd = row['fd']
                if fd:
                    self.ipp_add(row['loop'], fd)

            #

            query = QUERY_TBL['dfr_in_loop'] % { 'proj' : self._graph_uri }
            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)
                fref_tbl = tbl.get(key, None)
                if fref_tbl:
                    h     = row['h']
                    fname = row['fname']
                    try:
                        (fn, na, b) = fref_tbl[h]
                        if fn == fname:
                            fref_tbl[h] = (fn, na, True)
                        else:
                            logger.warning('function name mismatch (%s != %s)' % (fname, fn))
                    except KeyError:
                        logger.warning('reference of %s not found (hash=%s)' % (fname, h))

            #

            tree = self.get_tree()

            def make_data():
                return { 
                         'nfop' : 0,
                     }

            for key in tree['roots']:

                data = make_data()

                def f(k):
                    fref_tbl = tbl.get(k, None)
                    if fref_tbl:
                        for (h, (fn, na, dbl)) in fref_tbl.items():
                            data['nfop'] += get_nfops(fn, na, double=dbl)

                self.iter_tree(tree, key, f)

                self.set_metrics(N_FP_OPS, key, data['nfop'], add=True)

        except KeyError:
            raise

        logger.info('done.')
    # end of calc_ffr_in_loop_metrics


    def filter_results(self):
        logger.info('filtering results...')

        to_be_removed = set()

        for item in (MAX_ARRAY_RANK, N_FP_OPS, N_A_REFS[0]):
            for (k, v) in self._result_tbl.get(item, {}).items():
                if v == 0:
                    to_be_removed.add(k)

        for (item, tbl) in self._result_tbl.items():
            for k in to_be_removed:
                del tbl[k]
        

    def calc(self):
        logger.info('calculating for "%s"...' % self._proj_id)
        self.calc_loop_metrics()
        self.calc_array_metrics()
        self.calc_fop_in_loop_metrics()
        self.calc_ffr_in_loop_metrics()

        for lv in range(3):
            self.calc_aref_in_loop_metrics(lv)

        self.calc_in_loop_metrics()
        self.finalize_ipp()
        self.calc_max_loop_level()
        self.filter_results()

        #self.dump()


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='get source code metrics')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='enable debug printing')

    parser.add_argument('-k', '--key', dest='key', default=None,
                        metavar='KEY', type=str, help='show metrics for KEY=VER:PATH:LNUM')

    parser.add_argument('-o', '--outfile', dest='outfile', default=None,
                        metavar='FILE', type=str, help='dump feature vector into FILE')

    parser.add_argument('-m', '--method', dest='method', default='odbc',
                        metavar='METHOD', type=str, help='execute query via METHOD (odbc|http)')

    parser.add_argument('proj_list', nargs='*', default=[], 
                        metavar='PROJ', type=str, help='project id (default: all projects)')

    args = parser.parse_args()

    proj_list = []

    if args.key:
        l = args.key.split(':')
        if len(l) != 3:
            print('invalid key: %s' % args.key)
            exit(1)
        else:
            try:
                int(l[2])
            except:
                print('invalid key: %s' % args.key)
                exit(1)
                

    if args.proj_list:
        proj_list = args.proj_list
    else:
        proj_list = get_proj_list()


    ftbl_list = []

    for proj_id in proj_list:
        m = Metrics(proj_id, method=args.method)
        m.calc()

        if args.key:
            ftbl_list += m.search(args.key)
        else:
            ftbl_list += m.get_ftbl_list()

    if ftbl_list:
        if args.outfile:
            ftbl_list_to_orange(ftbl_list, args.outfile, META_KEYS)
        else:
            for ftbl in sorted(ftbl_list,
                               key=lambda x: (x['meta']['ver'],
                                              x['meta']['fn'],
                                              x['meta']['lnum'])):
                print('%s' % ftbl_to_string(ftbl))

    else:
        print('not found')
