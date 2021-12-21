#!/usr/bin/env python3


'''
  A script for outlining Fortran programs

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

import os
import json
from sympy import Symbol
from io import StringIO
from tokenize import generate_tokens, NAME
from keyword import iskeyword
import logging

from .common import NS_TBL
from .outline_for_survey_fortran import Outline as OutlineFortran
from .outline_for_survey_base import (tbl_get_dict, tbl_get_list, get_lver,
                                      ensure_dir, get_proj_list)
from .outline_for_survey_base import SourceFiles

from cca.factutil.entity import SourceCodeEntity
from cca.ccautil.siteconf import GIT_REPO_BASE, PROJECTS_DIR
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT

###

logger = logging.getLogger()

Q_LCTL_OF_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?init ?term ?stride
WHERE {
GRAPH <%%(proj)s> {

  ?constr a f:ContainerUnit ;
          f:loopControl ?lctl ;
          f:inProgramUnit ?pu .

  ?lctl a f:LoopControl ;
        f:initial ?init ;
        f:terminal ?term .

  OPTIONAL {
    ?lctl f:stride ?stride .
  }

  ?pu a f:ProgramUnit ;
      src:inFile/src:location ?loc ;
      ver:version ?ver .

}
}
''' % NS_TBL


Q_FOP_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr %(var)s
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?op) AS %(var)s) ?ver ?loc
    WHERE {

      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      ?op a f:IntrinsicOperator ;
          #src:treeDigest ?h ;
          a %(cat)s;
          f:inContainerUnit ?constr .

      ?opr a f:Expr ;
           src:parent+ ?op .

      FILTER (EXISTS {
        ?opr a f:RealLiteralConstant
      } || EXISTS {
        ?opr a f:FunctionReference ;
             f:name ?fname .
        FILTER (?fname IN ("real", "dble"))
      } || EXISTS {
        ?opr f:declarator ?dtor .
        ?dtor a f:Declarator ;
              f:declarationTypeSpec [a f:FloatingPointType] .
      } || EXISTS {
        ?opr f:typeSpec ?tspec .
        FILTER (?tspec IN ("Real", "DoublePrecision", "DoubleComplex", "Complex"))
      })

    } GROUP BY ?constr ?ver ?loc
  }

}
}
'''

fquery_tbl = {
    'nfadd': Q_FOP_IN_CONSTR_F % dict(NS_TBL, var='?nfadd', cat='f:Add'),
    'nfsub': Q_FOP_IN_CONSTR_F % dict(NS_TBL, var='?nfsub', cat='f:Subt'),
    'nfmul': Q_FOP_IN_CONSTR_F % dict(NS_TBL, var='?nfmul', cat='f:Mult'),
    'nfdiv': Q_FOP_IN_CONSTR_F % dict(NS_TBL, var='?nfdiv', cat='f:Div'),
}


Q_ZOP_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr %(var)s
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?op) AS %(var)s) ?ver ?loc
    WHERE {

      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      ?op a f:IntrinsicOperator ;
          #src:treeDigest ?h ;
          a %(cat)s ;
          f:inContainerUnit ?constr .

      FILTER NOT EXISTS {
        ?opr a f:Expr ;
             src:parent+ ?op ;
             f:declarator ?dtor .
        ?dtor a f:Declarator ;
              f:declarationTypeSpec [a f:FloatingPointType] .
      }
      FILTER NOT EXISTS {
        ?opr a f:RealLiteralConstant ;
             src:parent+ ?op .
      }
      FILTER NOT EXISTS {
        ?opr a f:FunctionReference ;
             src:parent+ ?op ;
             f:name ?fname .
        FILTER (?fname IN ("real", "dble"))
      }
      FILTER NOT EXISTS {
        ?opr a f:Expr ;
             src:parent+ ?op ;
             f:typeSpec ?tspec .
        FILTER (?tspec IN ("Real", "DoublePrecision", "DoubleComplex", "Complex"))
      }

    } GROUP BY ?constr ?ver ?loc
  }

}
}
'''

zquery_tbl = {
    'nzadd': Q_ZOP_IN_CONSTR_F % dict(NS_TBL, var='?nzadd', cat='f:Add'),
    'nzsub': Q_ZOP_IN_CONSTR_F % dict(NS_TBL, var='?nzsub', cat='f:Subt'),
    'nzmul': Q_ZOP_IN_CONSTR_F % dict(NS_TBL, var='?nzmul', cat='f:Mult'),
    'nzdiv': Q_ZOP_IN_CONSTR_F % dict(NS_TBL, var='?nzdiv', cat='f:Div'),
}


Q_FFR_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?fref ?fname ?nargs ?h
WHERE {
GRAPH <%%(proj)s> {
  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr ?fref ?h ?fname (COUNT(DISTINCT ?arg) AS ?nargs)
    WHERE {

      ?fref a f:FunctionReference OPTION (INFERENCE NONE) ;
           src:treeDigest ?h ;
           f:inContainerUnit ?constr ;
           f:name ?fname .

      ?arg src:parent ?fref .

      ?farg a f:Expr ;
            src:parent+ ?fref .

      FILTER (?fname IN ("real", "dble") ||
              EXISTS { ?farg a f:RealLiteralConstant } ||
              EXISTS {
                ?farg f:declarator ?dtor .
                FILTER EXISTS {
                  ?dtor a f:Declarator ;
                        f:declarationTypeSpec [ a f:FloatingPointType ] .
                }
              }
              )

    } GROUP BY ?constr ?fref ?h ?fname
  }
}
}
''' % NS_TBL


Q_DFR_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?fname ?h ?fref
WHERE {
GRAPH <%%(proj)s> {
  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr ?fref ?h ?fname
    WHERE {

      ?fref a f:FunctionReference OPTION (INFERENCE NONE) ;
           src:treeDigest ?h ;
           f:inContainerUnit ?constr ;
           f:name ?fname .

    } GROUP BY ?constr ?fref ?h ?fname
  }

  FILTER (
          EXISTS {
            ?farg a f:RealLiteralConstant ;
                  f:value ?val ;
                  src:parent+ ?fref .
            FILTER (CONTAINS(STR(?val), "d") || CONTAINS(STR(?val), "D"))
          } ||
          EXISTS {
            ?farg a f:Expr ;
                  f:declarator ?dtor ;
                  src:parent+ ?fref .

            ?dtor a f:Declarator ;
                  f:declarationTypeSpec ?tspec .

            ?tspec a ?cat OPTION (INFERENCE NONE) .

            FILTER (?cat = f:DoublePrecision ||
                    (?cat = f:Real &&
                     EXISTS {
                       ?tspec src:children/rdf:first/src:children/rdf:first/f:value 8
                     })
                    )
          }
          )

}
}
''' % NS_TBL

Q_AREFL_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?narefl
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?aa) AS ?narefl)
    WHERE {

      ?pn a f:PartName ;
          src:parent ?aa .

      ?aa a f:ArrayAccess ;
          #src:treeDigest ?h ;
          f:inContainerUnit ?constr .

      ?assign a f:AssignmentStmt ;
              src:children/rdf:first ?aa .

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

    } GROUP BY ?constr
  }

}
}
''' % NS_TBL

Q_AREFR_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?narefr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?aa) AS ?narefr)
    WHERE {

      ?pn a f:PartName ;
          src:parent ?aa .

      ?aa a f:ArrayAccess ;
          #src:treeDigest ?h ;
          f:inContainerUnit ?constr .

      FILTER NOT EXISTS {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?aa .
      }

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

    } GROUP BY ?constr
  }

}
}
''' % NS_TBL

Q_IAREFL_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?niarefl
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?aa0) AS ?niarefl)
    WHERE {

      ?pn0 a f:PartName ;
           src:parent ?aa0 .

      ?aa0 a f:ArrayAccess ;
           #src:treeDigest ?h0 ;
           f:inContainerUnit ?constr .

      FILTER EXISTS {
        ?assign0 a f:AssignmentStmt ;
                 src:children/rdf:first ?aa0 .

        ?pn0 f:declarator ?dtor0 .

        ?dtor0 a f:Declarator ;
               f:declarationTypeSpec ?tspec0 .

        ?tspec0 a f:NumericType .
      }

      ?x0 src:parent+ ?aa0 .
      FILTER (?x0 != ?aa0)
      FILTER (EXISTS {
        ?x0 a f:ArrayElement .
      } || EXISTS {
        ?x0 a f:ArraySection .
      } || EXISTS {
        ?x0 a f:FunctionReference .
      })

    } GROUP BY ?constr
  }

}
}
''' % NS_TBL

Q_IAREFR_IN_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?constr ?niarefr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?constr
    WHERE {
      ?constr a f:ContainerUnit ;
              f:inProgramUnit ?pu .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?constr
  }

  {
    SELECT DISTINCT ?constr (COUNT(DISTINCT ?aa1) AS ?niarefr)
    WHERE {

      ?pn1 a f:PartName ;
           src:parent ?aa1 .

      ?aa1 a f:ArrayAccess ;
           #src:treeDigest ?h1 ;
           f:inContainerUnit ?constr .

      FILTER NOT EXISTS {
        ?assign1 a f:AssignmentStmt ;
                 src:children/rdf:first ?aa1 .
      }

      FILTER EXISTS {
        ?pn1 f:declarator ?dtor1 .

        ?dtor1 a f:Declarator ;
               f:declarationTypeSpec ?tspec1 .

        ?tspec1 a f:NumericType .
      }

      ?x1 src:parent+ ?aa1 .
      FILTER (?x1 != ?aa1)
      FILTER (EXISTS {
        ?x1 a f:ArrayElement .
      } || EXISTS {
        ?x1 a f:ArraySection .
      } || EXISTS {
        ?x1 a f:FunctionReference .
      })

    } GROUP BY ?constr
  }

}
}
''' % NS_TBL

QUERY_TBL = {'fortran':
             {
                  'fop_in_constr':    fquery_tbl,
                  'zop_in_constr':    zquery_tbl,
                  'ffr_in_constr':    Q_FFR_IN_CONSTR_F,
                  'dfr_in_constr':    Q_DFR_IN_CONSTR_F,
                  'arefl_in_constr':  Q_AREFL_IN_CONSTR_F,
                  'arefr_in_constr':  Q_AREFR_IN_CONSTR_F,
                  'iarefl_in_constr': Q_IAREFL_IN_CONSTR_F,
                  'iarefr_in_constr': Q_IAREFR_IN_CONSTR_F,
                  'lctl_of_loop':     Q_LCTL_OF_LOOP_F,
              }
             }


def iter_tree(node, pre=None, post=None):
    if pre:
        pre(node)

    children = node['children']

    for child in children:
        iter_tree(child, pre=pre, post=post)

    if post:
        post(node)


def metrics_subt(m0, m1):
    def check(k):
        if k in m0:
            if k in m1:
                m0[k] -= m1[k]
                if m0[k] == 0:
                    del m0[k]

    check('nfadd')
    check('nfsub')
    check('nfmul')
    check('nfdiv')
    check('nzadd')
    check('nzsub')
    check('nzmul')
    check('nzdiv')
    check('narefl')
    check('narefr')
    check('niarefl')
    check('niarefr')

    f0 = m0.get('nfref', None)
    if f0:
        f1 = m1.get('nfref', None)
        if f1:
            for (fn, d0) in f0.items():
                if fn in f1:
                    if 'single' in d0:
                        d0['single'] -= f1[fn].get('single', 0)
                        if d0['single'] == 0:
                            del d0['single']

                    if 'double' in d0:
                        d0['double'] -= f1[fn].get('double', 0)
                        if d0['double'] == 0:
                            del d0['double']

            for fn in f0.keys():
                if f0[fn] == {}:
                    del f0[fn]

        if m0['nfref'] == {}:
            del m0['nfref']


def simplify_expr(expr):
    g = generate_tokens(StringIO(expr).readline)
    repl = []
    symbols = set()
    env = {'Symbol': Symbol}
    for (toknum, tokval, _, _, _) in g:
        if toknum == NAME:
            if tokval not in symbols:
                symbols.add(tokval)

                x = tokval
                if iskeyword(tokval) or tokval == 'Symbol':
                    x = tokval+'_'
                    repl.append((tokval, x))

                ln = '%s = Symbol("%s")' % (x, tokval)
                exec(ln, env)

    for (old, new) in repl:
        expr = expr.replace(old, new)

    res = str(eval(expr, env))

    return res


class Exit(Exception):
    pass


class Outline(OutlineFortran):

    def __init__(self,
                 proj_id,
                 commits=['HEAD'],
                 method='odbc',
                 pw=VIRTUOSO_PW,
                 port=VIRTUOSO_PORT,
                 gitrepo=GIT_REPO_BASE,
                 proj_dir=PROJECTS_DIR,
                 ver='unknown',
                 simple_layout=False):

        super().__init__(proj_id,
                         commits=commits,
                         method=method,
                         pw=pw,
                         port=port,
                         gitrepo=gitrepo,
                         proj_dir=proj_dir,
                         ver=ver,
                         simple_layout=simple_layout)

        self._fop_tbl = None  # key -> nfop_tbl
        self._zop_tbl = None  # key -> nzop_tbl
        self._ffr_tbl = None  # key -> hash -> fname * nargs * is_dbl
        self._aref_tbl = None  # key -> naref_tbl
        self._iaref_tbl = None  # key -> niaref_tbl

        self._lctl_tbl = {}  # key -> (init * term * stride) list

    def get_key(self, row):
        ver = row['ver']
        loc = row['loc']
        constr = row['constr']

        lver = get_lver(ver)

        ent = SourceCodeEntity(uri=constr)

        r = ent.get_range()
        start_line = r.get_start_line()
        end_line = r.get_end_line()

        key = (lver, loc, str(start_line), str(end_line))

        return key

    def setup_lctl_tbl(self):
        logger.info('setting up loop control table...')
        for lang in QUERY_TBL.keys():
            try:
                query = QUERY_TBL[lang]['lctl_of_loop'] % {'proj': self._graph_uri}

                for qvs, row in self._sparql.query(query):

                    key = self.get_key(row)

                    init = row['init']
                    term = row['term']
                    stride = row.get('stride', None)

                    li = tbl_get_list(self._lctl_tbl, key)
                    li.append((init, term, stride))

            except KeyError:
                raise
                pass

        logger.info('done.')

    def count_aref_in_constr(self):
        self._aref_tbl = {}
        logger.info('counting arefs...')
        for lang in QUERY_TBL.keys():
            query = QUERY_TBL[lang]['arefl_in_constr'] % {'proj': self._graph_uri}
            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)
                narefl = int(row['narefl'] or '0')
                try:
                    d = self._aref_tbl[key]
                    d['narefl'] = narefl
                except KeyError:
                    self._aref_tbl[key] = {'narefl': narefl}

            query = QUERY_TBL[lang]['arefr_in_constr'] % {'proj': self._graph_uri}
            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)
                narefr = int(row['narefr'] or '0')
                try:
                    self._aref_tbl[key]['narefr'] = narefr
                except KeyError:
                    self._aref_tbl[key] = {'narefr': narefr}

        logger.info('done.')

    def count_iaref_in_constr(self):
        self._iaref_tbl = {}
        logger.info('counting iarefs...')
        for lang in QUERY_TBL.keys():
            query = QUERY_TBL[lang]['iarefl_in_constr'] % {'proj': self._graph_uri}
            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)
                niarefl = int(row['niarefl'] or '0')
                try:
                    d = self._iaref_tbl[key]
                    d['niarefl'] = niarefl
                except KeyError:
                    self._iaref_tbl[key] = {'niarefl': niarefl}

            query = QUERY_TBL[lang]['iarefr_in_constr'] % {'proj': self._graph_uri}
            for qvs, row in self._sparql.query(query):
                key = self.get_key(row)
                niarefr = int(row['niarefr'] or '0')
                try:
                    self._iaref_tbl[key]['niarefr'] = niarefr
                except KeyError:
                    self._iaref_tbl[key] = {'niarefr': niarefr}

        logger.info('done.')

    def count_fop_in_constr(self):
        self._fop_tbl = {}
        logger.info('counting fops...')
        for lang in QUERY_TBL.keys():
            for (v, q) in QUERY_TBL[lang]['fop_in_constr'].items():
                logger.info('%s' % v)
                query = q % {'proj': self._graph_uri}
                for qvs, row in self._sparql.query(query):
                    key = self.get_key(row)
                    n = int(row[v] or '0')
                    try:
                        self._fop_tbl[key][v] = n
                    except KeyError:
                        self._fop_tbl[key] = {v: n}

        logger.info('done.')

    def count_zop_in_constr(self):
        self._zop_tbl = {}
        logger.info('counting zops...')
        for lang in QUERY_TBL.keys():
            for (v, q) in QUERY_TBL[lang]['zop_in_constr'].items():
                logger.info('%s' % v)
                query = q % {'proj': self._graph_uri}
                for qvs, row in self._sparql.query(query):
                    key = self.get_key(row)
                    n = int(row[v] or '0')
                    try:
                        self._zop_tbl[key][v] = n
                    except KeyError:
                        self._zop_tbl[key] = {v: n}

        logger.info('done.')

    def count_ffr_in_constr(self):
        self._ffr_tbl = {}
        logger.info('counting ffrs...')
        for lang in QUERY_TBL.keys():

            query = QUERY_TBL[lang]['ffr_in_constr'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):

                key = self.get_key(row)

                try:
                    fref_tbl = self._ffr_tbl[key]  # hash -> fname * nargs * is_dbl
                except KeyError:
                    fref_tbl = {}
                    self._ffr_tbl[key] = fref_tbl

                # h = row['h']
                fref = row['fref']
                fname = row['fname']
                nargs = row['nargs']

                fref_tbl[fref] = (fname, nargs, False)

            #

            query = QUERY_TBL[lang]['dfr_in_constr'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):

                key = self.get_key(row)

                fref_tbl = self._ffr_tbl.get(key, None)

                if fref_tbl:
                    # h = row['h']
                    fref = row['fref']
                    fname = row['fname']
                    try:
                        (fn, na, b) = fref_tbl[fref]
                        if fn == fname:
                            fref_tbl[fref] = (fn, na, True)
                        else:
                            logger.warning('function name mismatch ({} != {})'.format(fname, fn))
                    except KeyError:
                        logger.warning('reference of {} not found'.format(fname))

        logger.info('done.')

    def get_metrics(self, lang, key):

        if self._fop_tbl is None:
            self.count_fop_in_constr()

        if self._zop_tbl is None:
            self.count_zop_in_constr()

        if self._ffr_tbl is None:
            self.count_ffr_in_constr()

        if self._aref_tbl is None:
            self.count_aref_in_constr()

        if self._iaref_tbl is None:
            self.count_iaref_in_constr()

        nfop_tbl = self._fop_tbl.get(key, {})
        nzop_tbl = self._zop_tbl.get(key, {})

        naref_tbl = self._aref_tbl.get(key, {})
        narefl = naref_tbl.get('narefl', None)
        narefr = naref_tbl.get('narefr', None)

        niaref_tbl = self._iaref_tbl.get(key, {})
        niarefl = niaref_tbl.get('niarefl', None)
        niarefr = niaref_tbl.get('niarefr', None)

        fref_tbl = self._ffr_tbl.get(key, None)

        fref_count_tbl = {}

        if fref_tbl:
            for (fref, (fn, na, dbl)) in fref_tbl.items():
                try:
                    c = fref_count_tbl[fn]
                except KeyError:
                    c = {'single': 0, 'double': 0}
                    fref_count_tbl[fn] = c

                if dbl:
                    c['double'] = c['double'] + 1
                else:
                    c['single'] = c['single'] + 1

        data = {}

        if nfop_tbl:
            for (k, v) in nfop_tbl.items():
                if v:
                    data[k] = v

        if nzop_tbl:
            for (k, v) in nzop_tbl.items():
                if v:
                    data[k] = v

        if fref_count_tbl:
            data['nfref'] = fref_count_tbl

        if narefl:
            data['narefl'] = narefl
        if narefr:
            data['narefr'] = narefr

        if niarefl:
            data['niarefl'] = niarefl
        if niarefr:
            data['niarefr'] = niarefr

        return data

    def get_text(self, line_text_tbl, loc, ent):
        text = None
        try:
            r = ent.get_range()
            sl = r.get_start_line()
            sc = r.get_start_col()
            ec = r.get_end_col()
            line = line_text_tbl[loc][sl]
            text = line[sc:ec+1]
        except Exception as e:
            logger.warning('%s: %s %s' % (loc, type(e), str(e)))
            raise
        return text

    def get_niter_sub(self, line_text_tbl, loc, init_term_stride):
        init, term, stride = init_term_stride
        niter_ln = None
        try:
            init_ent = SourceCodeEntity(uri=init)
            term_ent = SourceCodeEntity(uri=term)

            init_text = self.get_text(line_text_tbl, loc, init_ent)
            term_text = self.get_text(line_text_tbl, loc, term_ent)

            stride_text = None
            if stride:
                stride_ent = SourceCodeEntity(uri=stride)
                stride_text = self.get_text(line_text_tbl, loc, stride_ent)

            if init_text and term_text:
                if stride_text:
                    niter = '((%s)-(%s)+1)/%s' % (term_text, init_text, stride_text)
                else:
                    niter = '(%s)-(%s)+1' % (term_text, init_text)

                if niter:
                    niter = simplify_expr(niter)

                niter_ln = niter, init_ent.get_range().get_start_line()

        except KeyError:
            pass

        return niter_ln

    def get_niter(self, line_text_tbl, key):
        niter = None

        if not self._lctl_tbl:
            self.setup_lctl_tbl()

        (ver, loc, _, _) = key

        li = []
        for t in self._lctl_tbl.get(key, []):
            niter_ln = self.get_niter_sub(line_text_tbl, loc, t)
            if niter_ln:
                li.append(niter_ln)

        li.sort(key=lambda x: x[1])

        niter = ' | '.join([x for (x, _) in li])

        return niter

    def gen_data(self, lang, outdir='.', keep_rev=False, debug_flag=False):

        tree = self.get_tree(callgraph=False,
                             other_calls=False,
                             directives=False,
                             mark=False)

        root_tbl = {}  # ver -> loc -> root (contains loop) list

        def f(lv, k):  # filter out trees that do not contain loops
            if k.cat == 'do-construct':
                raise Exit

        count = 0

        for root in tree['roots']:
            try:
                self.iter_tree(root, f)
            except Exit:
                count += 1
                loc_tbl = tbl_get_dict(root_tbl, root.ver)
                roots = tbl_get_list(loc_tbl, root.loc)

                roots.append(root)

        logger.info('%d root nodes (units that contain loops) found' % count)

        source_files = SourceFiles(self._conf, gitrepo=self._gitrepo,
                                   proj_dir=self._proj_dir)

        for ver in root_tbl.keys():

            if ver not in self._conf.versionURIs:
                continue

            lver = get_lver(ver)

            loc_tbl = root_tbl[ver]

            json_ds = []

            logger.info('generating line text table for "%s"...' % lver)

            line_text_tbl = self.get_line_text_tbl(source_files, ver,
                                                   strip=False)

            debug_tbl = {}  # path -> (start_line * metrics)

            def elaborate(node, d):

                loc = node.loc

                start_line = node.get_start_line()
                end_line = node.get_end_line()

                mkey = (lver, loc, str(start_line), str(end_line))

                try:
                    mdata = self.get_metrics(lang, mkey)
                    if mdata:
                        d['metrics'] = mdata

                        ms = tbl_get_list(debug_tbl, loc)
                        ms.append((start_line, node.get_end_line(), node.cat,
                                   mdata))

                except KeyError:
                    pass

                niter = self.get_niter(line_text_tbl, mkey)
                if niter:
                    d['niter'] = niter

            logger.info('converting trees into JSON for "%s"...' % lver)

            for loc in loc_tbl.keys():

                ds = []

                fid = None

                for root in loc_tbl[loc]:
                    if not fid:
                        fid = self._fid_tbl.get((ver, root.loc), None)

                    ds.append(root.to_dict([root], {}, elaborate=elaborate))

                loc_d = {
                    'loc':      loc,
                    'children': ds,
                    'fid':      fid,
                }

                json_ds.append(loc_d)

            json_ds.sort(key=lambda x: x['loc'])

            if keep_rev and self._conf.ver_tbl:
                lver_ = self._conf.ver_tbl.get(lver, lver)
                lver_dir = os.path.join(outdir, lver_)
            else:
                lver_dir = os.path.join(outdir, lver)

            def cleanup(d):
                m = d.get('metrics', None)
                if m == {}:
                    del d['metrics']

                if m:
                    f = m.get('nfref', None)
                    if f:
                        for (fn, d) in f.items():
                            if 'single' in d:
                                if d['single'] == 0:
                                    del d['single']

                            if 'double' in d:
                                if d['double'] == 0:
                                    del d['double']

                c = d.get('children', None)
                if c == []:
                    del d['children']

            # adjusting metrics
            def adjust(d):
                m = d.get('metrics', None)
                if m:
                    for c in d['children']:
                        cm = c.get('metrics', None)
                        if cm:
                            metrics_subt(m, cm)

            for json_d in json_ds:
                iter_tree(json_d, post=cleanup)
                # iter_tree(json_d, pre=adjust, post=cleanup)

            if debug_flag:
                for json_d in json_ds:
                    loc = json_d['loc']
                    ds = debug_tbl.get(loc, None)
                    if ds:
                        ds.sort(key=lambda x: int(x[0]))
                        print('* %s' % loc)
                        for d in ds:
                            m = d[3]
                            flag0 = m.get('nfadd', None)
                            flag1 = False

                            f = m.get('nfref', None)
                            if f:
                                for (fn, sd) in f.items():
                                    if sd['single'] or sd['double']:
                                        flag1 = True
                                        break
                            if flag0 or flag1:
                                print('%s-%s:%s:%s' % d)
                        print

            if ensure_dir(lver_dir):
                for json_d in json_ds:
                    json_file_name = '%s.json' % json_d['fid']
                    json_path = os.path.join(lver_dir, json_file_name)

                    logger.info('dumping JSON into "%s"...' % json_path)

                    try:
                        with open(json_path, 'w') as jsonf:
                            json.dump(json_d, jsonf)

                    except Exception as e:
                        logger.warning(str(e))
                        continue


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='outline loops and get source code metrics for them',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('--method', dest='method', default='odbc',
                        metavar='METHOD', type=str,
                        help='execute query via METHOD (odbc|http)')

    parser.add_argument('-c', '--commits', dest='commits', default=['HEAD'],
                        nargs='+', metavar='COMMIT', type=str,
                        help='analyze COMMIT')

    parser.add_argument('-g', '--git-repo-base', dest='gitrepo', metavar='DIR',
                        type=str, default=GIT_REPO_BASE,
                        help='location of git repositories')

    parser.add_argument('-p', '--proj-dir', dest='proj_dir', metavar='DIR',
                        type=str, default=PROJECTS_DIR,
                        help='location of projects')

    parser.add_argument('--ver', dest='ver', metavar='VER', type=str,
                        default='unknown', help='version')

    parser.add_argument('--simple-layout', dest='simple_layout',
                        action='store_true',
                        help='assumes simple directory layout')

    parser.add_argument('-k', '--keep-rev', dest='keep_rev',
                        action='store_true', help='keep designated commit ref')

    parser.add_argument('-o', '--outdir', dest='outdir', default='.',
                        metavar='DIR', type=str, help='dump data into DIR')

    parser.add_argument('proj_list', nargs='*', default=[],
                        metavar='PROJ', type=str,
                        help='project id (default: all projects)')

    args = parser.parse_args()

    proj_list = []

    if args.proj_list:
        proj_list = args.proj_list
    else:
        proj_list = get_proj_list()

    for proj in proj_list:
        ol = Outline(proj,
                     commits=args.commits,
                     method=args.method,
                     gitrepo=args.gitrepo,
                     proj_dir=args.proj_dir,
                     ver=args.ver,
                     simple_layout=args.simple_layout)

        for lang in QUERY_TBL.keys():
            ol.gen_data(lang, outdir=args.outdir, keep_rev=args.keep_rev)


if __name__ == '__main__':
    pass
