#!/usr/bin/env python3

'''
  A script for outlining Fortran programs

  Copyright 2013-2018 RIKEN
  Copyright 2018-2022 Chiba Institute of Technology

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
import logging

from .sourcecode_metrics_for_survey_fortran import (get_proj_list, get_lver,
                                                    Metrics)

from . import sourcecode_metrics_for_survey_fortran as metrics

from .outline_for_survey_base import (QN_SEP, remove_leading_digits, Exit,
                                      norm_callee_name)

from .outline_for_survey_base import (NodeBase, OutlineBase, tbl_get_list,
                                      tbl_get_set, tbl_get_dict)

from .outlining_queries_fortran import (OMITTED, SUBPROGS, LOOPS, CALLS, GOTOS,
                                        TYPE_TBL, QUERY_TBL, get_root_entities)

from cca.ccautil.cca_config import PROJECTS_DIR
from cca.ccautil.siteconf import GIT_REPO_BASE
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT
from cca.factutil.entity import SourceCodeEntity
from cca.ccautil.common import setup_logger

###

logger = logging.getLogger()

DEBUG = False

METRICS_ROW_HEADER = list(metrics.abbrv_tbl.keys()) \
    + metrics.META_KEYS + ['nid', 'root_file']


class Node(NodeBase):
    SUBPROGS = SUBPROGS
    CALLS = CALLS
    LOOPS = LOOPS
    GOTOS = GOTOS

    def __init__(self, ver, loc, uri, cat='',
                 prog=None, sub=None,
                 callee_name=None, pu_name=None, vpu_name=None,
                 all_sps=False, all_calls=False):

        super().__init__(ver, loc, uri, cat, callee_name,
                         all_sps=all_sps, all_calls=all_calls)

        self.prog = prog
        self.sub = sub

        if pu_name:
            self.pu_names = [pu_name]
        else:
            self.pu_names = []

        self.vpu_name = vpu_name

    def __str__(self):
        pu = self.get_pu()
        sl = self.get_start_line()
        el = self.get_end_line()
        if sl == el:
            r = f'{sl}'
        else:
            r = f'{sl}-{el}'

        s = f'{self.cat}[{r}:{self.sub}:{pu}:{os.path.basename(self.loc)}]'

        return s

    def get_container(self):  # subprog or main
        if not self._container:
            if self.cats & SUBPROGS or 'main-program' in self.cats:
                self._container = self
            else:
                nparents = len(self._parents)
                if nparents == 1:
                    p = list(self._parents)[0]
                    self._container = p.get_container()
                    self._parents_in_container.add(p)
                    self._parents_in_container.update(p.get_parents_in_container())

                elif nparents > 1:
                    if 'pp' not in [TYPE_TBL.get(c, None) for c in self.cats]:
                        pstr = ', '.join([str(p) for p in self._parents])
                        logger.warning(f'multiple parents:\n{self}:\nparents=[{pstr}]')

        return self._container

    def score_of_chain(self, chain):
        if chain:
            if 'main-program' in chain[-1].cats:
                score = 0

                for nd in chain:
                    if nd.cats & CALLS:
                        score += nd.count_parent_loops_in_container()

                logger.debug('{} <- [{}]'.format(score, ';'.join([str(x) for x in chain])))
            else:
                score = -1
        else:
            score = -1

        return score

    def is_main(self):
        return 'main-program' in self.cats

    def get_record(self, children):
        d = {
            'cat':      self.cat,
            'loc':      self.loc,
            'pu':       self.get_pu(),
            'sl':       self.get_start_line(),
            'el':       self.get_end_line(),
            'children': children,
        }
        return d

    def get_pu(self):
        if self.pu_names:
            pu = '|'.join(sorted(self.pu_names))
        else:
            pu = self.prog
        return pu

    def get_vpu(self):
        return self.vpu_name

    def get_type(self):
        ty = None
        for c in self.cats:
            if c.startswith('omp-'):
                ty = 'omp'
                break
            elif c.startswith('acc-'):
                ty = 'acc'
                break
            elif c.startswith('dec-'):
                ty = 'dec'
                break
            elif c.startswith('xlf-'):
                ty = 'xlf'
                break
            elif c.startswith('ocl-'):
                ty = 'ocl'
                break

            ty = TYPE_TBL.get(c, None)
            if ty:
                break
        return ty

    def is_construct(self):
        b = False
        for c in self.cats:
            if c.endswith('-construct'):
                b = True
                break
        return b

    def is_block(self):
        b = False
        for c in self.cats:
            if c.endswith('-block'):
                b = True
                break
        return b

    def get_block_cat(self):
        cat = None
        for c in self.cats:
            if c.endswith('-block'):
                cat = c
                break
        return cat

    def is_constr_head(self, child):
        b = all([self.is_construct(),
                 self.get_start_line() == child.get_start_line(),
                 not child.is_pp(),
                 not child.is_construct(),
                 not child.is_block()])
        return b

    def is_constr_tail(self, child):
        b = all([self.is_construct(),
                 self.get_end_line() == child.get_end_line(),
                 not child.is_construct(),
                 not child.is_block()])
        return b

    def set_extra(self, d):
        vpu = self.get_vpu()
        if vpu:
            d['vpu'] = vpu

    def get_name(self):
        return self.sub

    def check_children(self, children_l):
        if children_l:
            if self.is_constr_head(children_l[0]):
                children_l = children_l[1:]
        if children_l:
            if self.is_constr_tail(children_l[-1]):
                children_l = children_l[:-1]
        return children_l

    def to_dict(self, ancl, ntbl,
                elaborate=None,
                idgen=None,
                collapsed_caller_tbl={},
                expanded_callee_tbl={},
                parent_tbl=None,
                is_marked=None,
                omitted=set()):
        d = super().to_dict(ancl, ntbl,
                            elaborate=elaborate,
                            idgen=idgen,
                            collapsed_caller_tbl=collapsed_caller_tbl,
                            expanded_callee_tbl=expanded_callee_tbl,
                            parent_tbl=parent_tbl,
                            is_marked=is_marked,
                            omitted=omitted)
        if self.sub and self.cats & SUBPROGS:
            d['name'] = self.sub
        return d


def chkpu(key, obj):
    if obj.pu_names and key.pu_names \
       and all([n not in obj.pu_names for n in key.pu_names]):
        obj.pu_names += key.pu_names


class Outline(OutlineBase):
    def __init__(self,
                 proj_id,
                 commits=['HEAD'],
                 method='odbc',
                 pw=VIRTUOSO_PW,
                 port=VIRTUOSO_PORT,
                 gitrepo=GIT_REPO_BASE,
                 proj_dir=PROJECTS_DIR,
                 ver='unknown',
                 simple_layout=False,
                 all_sps=False,
                 all_calls=False,
                 conf=None):

        super().__init__(proj_id, commits, method, pw, port, gitrepo,
                         proj_dir, ver, simple_layout, all_sps, all_calls,
                         SUBPROGS=SUBPROGS, CALLS=CALLS,
                         get_root_entities=get_root_entities,
                         METRICS_ROW_HEADER=METRICS_ROW_HEADER,
                         add_root=True, conf=conf)

        self._qspn_tbl = {}  # (ver * loc * start_line) -> name list

    def get_node(self, key):
        return OutlineBase.get_node(self, key, check=chkpu)

    def setup_aa_tbl(self):  # assumes self._node_tbl
        if not self._aa_tbl:
            logger.info('setting up array reference table...')

            tbl = {}

            query = QUERY_TBL['aa_in_loop'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                loop = row['loop']
                pn = row['pn']

                pu_name = row.get('pu_name', None)
                vpu_name = row.get('vpu_name', None)
                dtor = row.get('dtor', None)

                # lver = get_lver(ver)

                loop_node = self.get_node(Node(ver, loc, loop,
                                               cat='do-construct',
                                               pu_name=pu_name,
                                               vpu_name=vpu_name))

                pns = tbl_get_list(tbl, loop_node.get_mkey())

                pn_ent = SourceCodeEntity(uri=pn)
                r = pn_ent.get_range()
                st = {'line': r.get_start_line(), 'ch': r.get_start_col()}
                ed = {'line': r.get_end_line(), 'ch': r.get_end_col()}
                d = {'start': st, 'end': ed}

                if dtor:
                    dtor_ent = SourceCodeEntity(uri=dtor)
                    dtor_fid = dtor_ent.get_file_id()

                    df = {'line': dtor_ent.get_range().get_start_line()}

                    if dtor_fid != pn_ent.get_file_id():
                        df['fid'] = dtor_fid.get_value()
                        df['path'] = row['dtor_loc']

                    d['def'] = df

                pns.append(d)

                for p in loop_node.get_parents_in_container():
                    if 'do-construct' in p.cats:
                        ppns = tbl_get_list(tbl, p.get_mkey())
                        ppns.append(d)

            self._aa_tbl = tbl

    def setup_qspn_tbl(self):
        if not self._qspn_tbl:
            logger.info('setting up qualified subprogram name table...')

            tbl = {}

            query = QUERY_TBL['constr_qspn'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                constr = row['constr']
                qspn = row['qspn']

                pu_name = row.get('pu_name', None)
                # vpu_name = row.get('vpu_name', None)

                # lver = get_lver(ver)

                constr_node = self.get_node(Node(ver, loc, constr))

                li = [remove_leading_digits(x) for x in qspn.split(QN_SEP)]
                li.reverse()
                if li[0] == pu_name:
                    del li[0]
                li.insert(0, pu_name)

                tbl[constr_node.get_mkey()] = li

            query = QUERY_TBL['isp_qspn'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                isp = row['isp']
                qspn = row['qspn']

                pu_name = row.get('pu_name', None)
                # vpu_name = row.get('vpu_name', None)

                # lver = get_lver(ver)

                isp_node = self.get_node(Node(ver, loc, isp))

                li = [remove_leading_digits(x) for x in qspn.split(QN_SEP)]
                li.reverse()
                if li[0] == pu_name:
                    del li[0]
                li.insert(0, pu_name)

                tbl[isp_node.get_mkey()] = li

            self._qspn_tbl = tbl

    def extract_metrics(self):
        if self._metrics is None:
            logger.info('extracting metrics...')
            self._metrics = Metrics(self._proj_id, self._method,
                                    pw=self._pw, port=self._port)
            self._metrics.calc()
            logger.info('done.')

            try:
                fop_tbl = self._metrics.get_item_tbl(metrics.N_FP_OPS)
                logger.info('fop_tbl has {} items'.format(len(fop_tbl)))
                # for k in fop_tbl.keys():
                #     print(f'!!! {k}')
                aa0_tbl = self._metrics.get_item_tbl(metrics.N_A_REFS[0])
                logger.info('aa0_tbl has {} items'.format(len(aa0_tbl)))

            except KeyError:
                logger.warning('could not find metrics')

    def add_edge(self, parent, child, mark=True):
        if parent is child:
            return

        p = self.get_node(parent)
        c = self.get_node(child)

        if p is c:
            return

        p.add_child(c)
        c.add_parent(p)

        logger.debug(f'add_edge: {p}({len(p.get_children())}) -> {c}({len(c.get_children())})')

        if mark and 'do-construct' in c.cats:
            mkey = c.get_mkey()
            try:
                mtbl = self.get_metrics_tbl(mkey)
                bf0 = mtbl[metrics.BF[0]]
                bf1 = mtbl[metrics.BF[1]]
                bf2 = mtbl[metrics.BF[2]]
                if bf0 or bf1 or bf2:
                    self.mark_node(c)

            except KeyError:
                pass

        elif mark and self._all_sps and c.cats & SUBPROGS and p.cats & CALLS:
            self.mark_node(c)

    def setup_cg(self, mark=True):
        logger.info('searching for call relations...')

        logger.debug('sp_sp')
        query = QUERY_TBL['sp_sp'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            sp = row.get('sp', None)
            sub = row.get('sub', None)

            pu_name = row.get('pu_name', None)
            vpu_name = row.get('vpu_name', None)

            main = row.get('main', None)
            prog = None
            if main:
                prog = row.get('prog', '<main>')

            call = row['call']
            call_cat = row['call_cat']

            call_name = row['call_name']
            callee_name = norm_callee_name(row['callee_name'])

            call_node = Node(ver, loc, call, cat=call_cat,
                             all_calls=self._all_calls,
                             prog=prog, sub=sub,
                             callee_name=call_name,
                             pu_name=pu_name,
                             vpu_name=vpu_name)

            parent_constr = row.get('constr', None)

            if sp:
                sp_node = Node(ver, loc, sp, cat=row['sp_cat'],
                               all_sps=self._all_sps,
                               sub=sub, pu_name=pu_name, vpu_name=vpu_name)
                if not parent_constr:
                    self.add_edge(sp_node, call_node, mark=mark)

            if main:
                main_node = Node(ver, loc, main, cat='main-program', prog=prog)
                if not parent_constr and not sp:
                    self.add_edge(main_node, call_node, mark=mark)

            if call_node.is_relevant():
                self._relevant_nodes.add(call_node)

            callee = row['callee']
            callee_loc = row['callee_loc']
            callee_cat = row['callee_cat']
            callee_pu_name = row.get('callee_pu_name', None)

            callee_node = Node(ver, callee_loc, callee, cat=callee_cat,
                               all_sps=self._all_sps,
                               sub=callee_name, pu_name=callee_pu_name)

            self.add_edge(call_node, callee_node, mark=mark)

            if callee_node.is_relevant():
                self._relevant_nodes.add(callee_node)

        logger.debug('constr_sp')
        query = QUERY_TBL['constr_sp'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            constr = row['constr']
            constr_cat = row['cat']

            pu_name = row.get('pu_name', None)
            vpu_name = row.get('vpu_name', None)

            sp = row.get('sp', None)
            sub = row.get('sub', None)
            main = row.get('main', None)
            prog = None
            if main:
                prog = row.get('prog', '<main>')

            constr_node = Node(ver, loc, constr, cat=constr_cat,
                               prog=prog, sub=sub,
                               pu_name=pu_name, vpu_name=vpu_name)

            call = row['call']
            call_cat = row['call_cat']

            call_name = row['call_name']
            callee_name = norm_callee_name(row['callee_name'])

            call_node = Node(ver, loc, call, cat=call_cat,
                             all_calls=self._all_calls,
                             prog=prog, sub=sub,
                             callee_name=call_name,
                             pu_name=pu_name,
                             vpu_name=vpu_name)

            self.add_edge(constr_node, call_node, mark=mark)

            if call_node.is_relevant():
                self._relevant_nodes.add(call_node)

            callee = row['callee']
            callee_loc = row['callee_loc']
            callee_cat = row['callee_cat']
            callee_pu_name = row.get('callee_pu_name', None)

            callee_node = Node(ver, callee_loc, callee, cat=callee_cat,
                               all_sps=self._all_sps,
                               sub=callee_name, pu_name=callee_pu_name)

            self.add_edge(call_node, callee_node, mark=mark)

            if callee_node.is_relevant():
                self._relevant_nodes.add(callee_node)

        logger.info('check marks...')
        a = set()
        for marked in self._marked_nodes:
            # print(f'!!! marked={marked}')
            ancs = marked.get_ancestors()
            a.update(ancs)

        self._marked_nodes.update(a)

    def construct_tree(self, callgraph=True,
                       other_calls=True, directives=True, gotos=True,
                       mark=True):

        self._relevant_nodes = set()

        logger.debug('constr_constr')

        query = QUERY_TBL['constr_constr'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            sp = row.get('sp', None)
            sub = row.get('sub', None)
            constr = row['constr']
            cat = row.get('cat', None)

            pu_name = row.get('pu_name', None)
            vpu_name = row.get('vpu_name', None)

            main = row.get('main', None)
            prog = None
            if main:
                prog = row.get('prog', '<main>')

            constr_node = Node(ver, loc, constr, cat=cat,
                               prog=prog, sub=sub,
                               pu_name=pu_name, vpu_name=vpu_name)

            if constr_node.is_relevant():
                self._relevant_nodes.add(constr_node)

            parent_constr = row.get('parent_constr', None)

            if parent_constr:
                parent_sub = row.get('parent_sub', None)
                parent_prog = row.get('parent_prog', None)
                parent_pu_name = row.get('parent_pu_name', None)
                parent_vpu_name = row.get('parent_vpu_name', None)
                parent_cat = row.get('parent_cat', None)
                parent_node = Node(ver, loc, parent_constr, cat=parent_cat,
                                   prog=parent_prog, sub=parent_sub,
                                   pu_name=parent_pu_name,
                                   vpu_name=parent_vpu_name)
                self.add_edge(parent_node, constr_node, mark=mark)
                if parent_node.is_relevant():
                    self._relevant_nodes.add(parent_node)

            elif sp:
                sp_node = Node(ver, loc, sp, cat=row['sp_cat'],
                               all_sps=self._all_sps,
                               sub=sub, pu_name=pu_name, vpu_name=vpu_name)
                # sp_flag = False
                self.add_edge(sp_node, constr_node, mark=mark)

            elif main:
                main_node = Node(ver, loc, main, cat='main-program', prog=prog)
                # main_flag = False
                self.add_edge(main_node, constr_node, mark=mark)

        #

        if directives:

            logger.debug('directives')

            query = QUERY_TBL['directives'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                sp = row.get('sp', None)
                sub = row.get('sub', None)
                dtv = row['dtv']
                cat = row.get('cat', None)

                pu_name = row.get('pu_name', None)
                vpu_name = row.get('vpu_name', None)

                main = row.get('main', None)
                prog = None
                if main:
                    prog = row.get('prog', '<main>')

                dtv_node = Node(ver, loc, dtv, cat=cat,
                                prog=prog, sub=sub,
                                pu_name=pu_name, vpu_name=vpu_name)

                self._relevant_nodes.add(dtv_node)

                parent_constr = row.get('constr', None)
                if parent_constr:
                    self.add_edge(Node(ver, loc, parent_constr), dtv_node,
                                  mark=mark)

                if sp:
                    sp_node = Node(ver, loc, sp, cat=row['sp_cat'],
                                   all_sps=self._all_sps,
                                   sub=sub, pu_name=pu_name, vpu_name=vpu_name)
                    if not parent_constr:
                        self.add_edge(sp_node, dtv_node, mark=mark)

                if main:
                    main_node = Node(ver, loc, main, cat='main-program',
                                     prog=prog)
                    if not parent_constr and not sp:
                        self.add_edge(main_node, dtv_node, mark=mark)

        #

        if other_calls:

            logger.debug('other calls')

            query = QUERY_TBL['other_calls'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                sp = row.get('sp', None)
                sub = row.get('sub', None)
                call = row['call']

                callee_name = row['callee_name']

                pu_name = row.get('pu_name', None)
                vpu_name = row.get('vpu_name', None)

                main = row.get('main', None)
                prog = None
                if main:
                    prog = row.get('prog', '<main>')

                cat = 'call-stmt*'

                if callee_name.startswith('mpi_'):
                    cat = 'mpi-call'

                call_node = Node(ver, loc, call, cat=cat,
                                 all_calls=self._all_calls,
                                 prog=prog, sub=sub,
                                 callee_name=callee_name,
                                 pu_name=pu_name,
                                 vpu_name=vpu_name)

                if call_node.is_relevant():
                    self._relevant_nodes.add(call_node)

                parent_constr = row.get('constr', None)
                if parent_constr:
                    self.add_edge(Node(ver, loc, parent_constr), call_node,
                                  mark=mark)

                if sp:
                    sp_node = Node(ver, loc, sp, cat=row['sp_cat'],
                                   all_sps=self._all_sps,
                                   sub=sub, pu_name=pu_name, vpu_name=vpu_name)
                    if not parent_constr:
                        self.add_edge(sp_node, call_node, mark=mark)

                if main:
                    main_node = Node(ver, loc, main, cat='main-program', prog=prog)
                    if not parent_constr and not sp:
                        self.add_edge(main_node, call_node, mark=mark)

        if gotos:
            logger.debug('gotos')

            query = QUERY_TBL['gotos'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                sp = row.get('sp', None)
                sub = row.get('sub', None)
                goto = row['goto']
                cat = row['goto_cat']

                # label = row['label']

                pu_name = row.get('pu_name', None)
                vpu_name = row.get('vpu_name', None)

                main = row.get('main', None)
                prog = None
                if main:
                    prog = row.get('prog', '<main>')

                goto_node = Node(ver, loc, goto, cat=cat, prog=prog, sub=sub,
                                 pu_name=pu_name,
                                 vpu_name=vpu_name)

                if goto_node.is_relevant():
                    self._relevant_nodes.add(goto_node)

                parent_constr = row.get('constr', None)
                if parent_constr:
                    self.add_edge(Node(ver, loc, parent_constr), goto_node,
                                  mark=mark)

                if sp:
                    sp_node = Node(ver, loc, sp, cat=row['sp_cat'],
                                   all_sps=self._all_sps,
                                   sub=sub, pu_name=pu_name, vpu_name=vpu_name)
                    if not parent_constr:
                        self.add_edge(sp_node, goto_node, mark=mark)

                if main:
                    main_node = Node(ver, loc, main, cat='main-program', prog=prog)
                    if not parent_constr and not sp:
                        self.add_edge(main_node, goto_node, mark=mark)

        #

        if callgraph:
            self.setup_cg(mark=mark)

        roots = []

        count = 0

        self._lines_tbl = {}
        self._fid_tbl = {}

        self.setup_aa_tbl()
        self.setup_qspn_tbl()

        for k in self._node_tbl.keys():
            count += 1

            (v, _, _) = k

            node = self._node_tbl[k]

            if node.is_root():
                roots.append(node)

            lntbl = tbl_get_dict(self._lines_tbl, v)
            lines = tbl_get_set(lntbl, node.loc)

            for ln in range(node.get_start_line(), node.get_end_line()+1):
                lines.add(ln)

            if not (v, node.loc) in self._fid_tbl:
                fid = node.get_fid()
                self._fid_tbl[(v, node.loc)] = fid

            mkey = node.get_mkey()  # register lines of definitions
            try:
                for pn in self._aa_tbl[mkey]:
                    df = pn.get('def', None)
                    if df:
                        ln = df.get('line', None)
                        p = df.get('path', None)
                        fid = df.get('fid', None)
                        if ln and p:
                            lntbl = tbl_get_dict(self._lines_tbl, v)
                            lines = tbl_get_set(lntbl, p)
                            lines.add(ln)
                            if fid:
                                if not (v, p) in self._fid_tbl:
                                    self._fid_tbl[(v, p)] = fid

            except KeyError:
                pass

        logger.info(f'{len(roots)} root nodes (out of {count} nodes) found')

        if DEBUG:
            def dump(lv, k):
                print('!!! {}{}({}) {}'.format('  '*lv, k,
                                               len(k.get_children()),
                                               ';'.join([c.cat for c in k.get_children()])))
            for root in roots:
                self.iter_tree(root, dump)

        tree = {'node_tbl': self._node_tbl, 'roots': roots}

        for nd in self._relevant_nodes:
            self.get_node(nd).set_relevant()
            for a in nd.get_ancestors():
                self.get_node(a).set_relevant()

        self.set_tree(tree)

        self._node_tbl = {}

        return tree

    def iter_tree(self, root, f, pre=None, post=None):
        self.__iter_tree(0, root, f, pre=pre, post=post)

    def __iter_tree(self, lv, node, f, pre=None, post=None):
        if pre:
            pre(node)

        if f:
            f(lv, node)

        children = node.get_children()

        for child in children:
            if node != child:
                self.__iter_tree(lv+1, child, f, pre=pre, post=post)

        if post:
            post(node)

    def mkrow(self, lver, loc, nd, lnum, mtbl, nid):
        tbl = mtbl.copy()
        tbl['proj'] = self._proj_id
        tbl['ver'] = lver
        tbl['path'] = loc
        tbl['sub'] = nd.sub
        tbl['lnum'] = lnum
        tbl['digest'] = mtbl['meta']['digest']
        tbl['nid'] = nid
        row = []
        for k in METRICS_ROW_HEADER:
            if k != 'root_file':
                row.append(tbl[k])
        return row

    def check_root(self, root, root_entities):
        if root.cats & root_entities:
            for x in root.get_descendants():
                if 'do-construct' in x.cats:
                    raise Exit

    def set_extra2(self, d, mkey):
        try:
            d['qspn'] = self._qspn_tbl[mkey]
        except KeyError:
            pass


def test(proj):
    # proj = 'MG'

    ol = Outline(proj)

    tree = ol.get_tree()

    root_tbl = {}  # ver -> loc -> root (contains loop)

    def f(lv, k):
        if 'do-construct' in k.cats:
            raise Exit

    count = 0

    for root in tree['roots']:
        try:
            ol.iter_tree(root, f)
        except Exit:
            count += 1

            loc_tbl = tbl_get_dict(root_tbl, root.ver)

            roots = tbl_get_list(loc_tbl, root.loc)

            roots.append(root)

    logger.info(f'{count} top constructs (that contain loops) found')

    def dump(lv, k):
        print('{}{}'.format('  '*lv, k))

    for ver in root_tbl.keys():
        lver = get_lver(ver)

        # if lver != 'base':
        #     continue

        loc_tbl = root_tbl[ver]
        for loc in loc_tbl.keys():
            print(f'*** ver={lver} loc={loc}')
            for root in loc_tbl[loc]:
                ol.iter_tree(root, dump)


def test2(proj):
    ol = Outline(proj)

    tree = ol.get_tree()

    node_tbl = tree['node_tbl']

    sub = None

    for (k, node) in node_tbl.items():
        if node.loc == 'ic/grafic.f90':
            if 'subroutine-external-subprogram' in node.cats:
                sub = node

    if sub:
        print(len(sub.get_children()))
        for c in sub.get_children():
            print('{} {}'.format(c, c != sub))


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='outline loops and get source code metrics for them',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('--method', dest='method', default='odbc',
                        metavar='METHOD', type=str,
                        help='execute query via METHOD (odbc|http)')

    parser.add_argument('-c', '--commits', dest='commits', default=['HEAD'], nargs='+',
                        metavar='COMMIT', type=str, help='analyze COMMIT')

    parser.add_argument('-g', '--git-repo-base', dest='gitrepo', metavar='DIR', type=str,
                        default=GIT_REPO_BASE, help='location of git repositories')

    parser.add_argument('-p', '--proj-dir', dest='proj_dir', metavar='DIR', type=str,
                        default=PROJECTS_DIR, help='location of projects')

    parser.add_argument('--ver', dest='ver', metavar='VER', type=str,
                        default='unknown', help='version')

    parser.add_argument('--simple-layout', dest='simple_layout',
                        action='store_true', help='assumes simple directory layout')

    parser.add_argument('-a', '--all-roots', dest='all_roots', action='store_true',
                        help='allow subprograms to be root nodes in addition to main programs')

    parser.add_argument('-o', '--outdir', dest='outdir', default='.',
                        metavar='DIR', type=str, help='dump data into DIR')

    parser.add_argument('-i', '--index', dest='index', metavar='PATH', type=str,
                        default=None, help='index file')

    parser.add_argument('-s', '--doc-src', dest='docsrc', metavar='DIR', type=str,
                        default=None, help='document source for topic search')

    parser.add_argument('-m', '--model', dest='model', metavar='MODEL', type=str,
                        default='lsi', help='topic model (lda|lsi|rp)')

    parser.add_argument('-t', '--ntopics', dest='ntopics', metavar='N', type=int,
                        default=32, help='number of topics')

    parser.add_argument('proj_list', nargs='*', default=[],
                        metavar='PROJ', type=str,
                        help='project id (default: all projects)')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    setup_logger(logger, log_level)

    proj_list = []

    if args.proj_list:
        proj_list = args.proj_list
    else:
        proj_list = get_proj_list()

    for proj in proj_list:
        # test(proj)
        ol = Outline(proj,
                     commits=args.commits,
                     method=args.method,
                     gitrepo=args.gitrepo,
                     proj_dir=args.proj_dir,
                     ver=args.ver,
                     simple_layout=args.simple_layout,
                     )

        ol.gen_data('fortran', args.outdir, omitted=set(OMITTED), all_roots=args.all_roots)

        if args.index:
            logger.info('generating topic data...')
            ol.gen_topic('fortran', args.outdir,
                         docsrc=args.docsrc,
                         index=args.index,
                         model=args.model,
                         ntopics=args.ntopics)


if __name__ == '__main__':
    pass
