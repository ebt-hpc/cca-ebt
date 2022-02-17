#!/usr/bin/env python3

'''
  A script for outlining C/C++ programs

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

import logging

from .sourcecode_metrics_for_survey_cpp import get_proj_list, get_lver, Metrics
from . import sourcecode_metrics_for_survey_cpp as metrics
from .outline_for_survey_base import (NodeBase, OutlineBase, Exit,
                                      norm_callee_name)
from .outline_for_survey_base import (demangle, tbl_get_list, tbl_get_set,
                                      tbl_get_dict)
from .outlining_queries_cpp import (OMITTED, SUBPROGS, LOOPS, CALLS, TYPE_TBL,
                                    QUERY_TBL, get_root_entities)

from cca.ccautil.cca_config import PROJECTS_DIR
from cca.ccautil.siteconf import GIT_REPO_BASE
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT
from cca.factutil.entity import SourceCodeEntity

###

logger = logging.getLogger()

METRICS_ROW_HEADER = list(metrics.abbrv_tbl.keys()) \
    + metrics.META_KEYS + ['nid', 'root_file']


class Node(NodeBase):
    SUBPROGS = SUBPROGS
    CALLS = CALLS
    LOOPS = LOOPS
    GOTOS = set()

    def __init__(self, ver, loc, uri, cat='',
                 fn=None,
                 callee_name=None,
                 all_sps=False, all_calls=False):

        super().__init__(ver, loc, uri, cat, callee_name, all_sps, all_calls)

        self.fn = fn

    def get_name(self):
        return self.fn

    def get_container(self):  # func or main
        if not self._container:
            if self.cats & SUBPROGS:
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
                        logger.warning('multiple parents:\n%s:\nparents=[%s]' % (self, pstr))

        return self._container

    def score_of_chain(self, chain):
        if chain:
            if demangle(chain[-1].fn) == 'main':
                score = 0

                for nd in chain:
                    if nd.cats & CALLS:
                        score += nd.count_parent_loops_in_container()

                logger.debug('%d <- [%s]' % (score, ';'.join([str(x) for x in chain])))
            else:
                score = -1
        else:
            score = -1

        return score

    def is_main(self):
        return demangle(self.fn) == 'main'

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
            elif c.startswith('ocl-'):
                ty = 'ocl'
                break

            ty = TYPE_TBL.get(c, None)
            if ty:
                break
        return ty

    def is_block(self):
        b = False
        for c in self.cats:
            if c == 'compound-statement' or c.endswith('-block'):
                b = True
                break
        return b

    def get_block_cat(self):
        cat = None
        for c in self.cats:
            if c == 'compound-statement' or c.endswith('-block'):
                cat = c
                break
        return cat

    def is_constr_head(self, child):
        b = all([child.is_pp_ifx(),
                 self.get_start_line() == child.get_start_line(),
                 ])
        return b

    def is_constr_tail(self, child):
        b = all([child.is_pp_ifx(),
                 self.get_end_line() == child.get_end_line(),
                 ])
        return b

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
        if self.fn and self.cats & SUBPROGS:
            d['name'] = self.fn
        return d


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
                         conf=conf)

    def setup_aa_tbl(self):  # assumes self._node_tbl
        if not self._aa_tbl:
            logger.info('setting up array reference table...')

            tbl = {}

            query = QUERY_TBL['aa_in_loop'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                loop = row['loop']
                pe = row['pe']
                loop_cat = row['loop_cat']

                # lver = get_lver(ver)

                loop_node = self.get_node(Node(ver, loc, loop, cat=loop_cat))

                pns = tbl_get_list(tbl, loop_node.get_mkey())

                pn_ent = SourceCodeEntity(uri=pe)
                r = pn_ent.get_range()
                st = {'line': r.get_start_line(), 'ch': r.get_start_col()}
                ed = {'line': r.get_end_line(), 'ch': r.get_end_col()}
                d = {'start': st, 'end': ed}

                pns.append(d)

                for p in loop_node.get_parents_in_container():
                    if LOOPS & p.cats:
                        ppns = tbl_get_list(tbl, p.get_mkey())
                        ppns.append(d)

            self._aa_tbl = tbl

    def extract_metrics(self):
        if not self._metrics:
            logger.info('extracting metrics...')
            self._metrics = Metrics(self._proj_id,
                                    self._method, pw=self._pw, port=self._port)
            self._metrics.calc()
            logger.info('done.')

            try:

                fop_tbl = self._metrics.get_item_tbl(metrics.N_FP_OPS)
                logger.info('fop_tbl has {} items'.format(len(fop_tbl)))
                # for k in fop_tbl.keys():
                #     print('!!! %s' % (k,))
                aa0_tbl = self._metrics.get_item_tbl(metrics.N_A_REFS[0])
                logger.info('aa0_tbl has {} items'.format(len(aa0_tbl)))
                # for k in aa0_tbl.keys():
                #     print('!!! %s' % (k,))

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

        # print('!!! %s(%d) -> %s(%d)' % (p,
        #                                 len(p.get_children()),
        #                                 c,
        #                                 len(c.get_children())))

        if mark and LOOPS & c.cats:
            mkey = c.get_mkey()
            try:
                mtbl = self.get_metrics_tbl(mkey)
                bf0 = mtbl[metrics.BF[0]]
                bf1 = mtbl[metrics.BF[1]]
                bf2 = mtbl[metrics.BF[2]]
                if bf0 or bf1 or bf2:
                    self.mark_node(c)

            except KeyError:
                # pass
                self.mark_node(c)

        elif mark and self._all_sps and c.cats & SUBPROGS and p.cats & CALLS:
            self.mark_node(c)

    def setup_cg(self, mark=True):
        logger.info('searching for call relations...')

        logger.debug('fd_fd')
        query = QUERY_TBL['fd_fd'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            fd = row.get('fd', None)
            fn = row.get('fn', None)

            call = row['call']
            call_cat = row['call_cat']

            callee_name = norm_callee_name(row['callee_name'])

            call_node = Node(ver, loc, call, cat=call_cat, fn=fn,
                             callee_name=callee_name,
                             all_calls=self._all_calls)

            parent_cntnr = row.get('cntnr', None)

            if fd:
                fd_node = Node(ver, loc, fd, cat=row['fd_cat'], fn=fn)
                if not parent_cntnr:
                    self.add_edge(fd_node, call_node, mark=mark)

            callee = row['callee']
            callee_loc = row['callee_loc']
            callee_cat = row['callee_cat']

            callee_node = Node(ver, callee_loc, callee, cat=callee_cat,
                               fn=callee_name, all_sps=self._all_sps)

            self.add_edge(call_node, callee_node, mark=mark)

        logger.debug('cntnr_fd')
        query = QUERY_TBL['cntnr_fd'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            cntnr = row['cntnr']
            cntnr_cat = row['cat']

            fd = row.get('fd', None)
            fn = row.get('fn', None)

            cntnr_node = Node(ver, loc, cntnr, cat=cntnr_cat, fn=fn)

            call = row['call']
            call_cat = row['call_cat']

            callee_name = norm_callee_name(row['callee_name'])

            call_node = Node(ver, loc, call, cat=call_cat, fn=fn,
                             callee_name=callee_name,
                             all_calls=self._all_calls)

            self.add_edge(cntnr_node, call_node, mark=mark)

            if call_node.is_relevant():
                self._relevant_nodes.add(call_node)

            callee = row['callee']
            callee_loc = row['callee_loc']
            callee_cat = row['callee_cat']

            callee_node = Node(ver, callee_loc, callee, cat=callee_cat,
                               fn=callee_name, all_sps=self._all_sps)

            self.add_edge(call_node, callee_node, mark=mark)

        logger.info('check marks...')
        a = set()
        for marked in self._marked_nodes:
            # print('!!! marked=%s' % marked)
            ancs = marked.get_ancestors()
            a.update(ancs)

        self._marked_nodes.update(a)

    def construct_tree(self, callgraph=True,
                       other_calls=True, directives=True, gotos=True,
                       mark=True):

        self._relevant_nodes = set()

        logger.debug('cntnr_cntnr')

        query = QUERY_TBL['cntnr_cntnr'] % {'proj': self._graph_uri}

        for qvs, row in self._sparql.query(query):
            ver = row['ver']
            loc = row['loc']
            fd = row.get('fd', None)
            fn = row.get('fn', None)
            cntnr = row['cntnr']
            cat = row.get('cat', None)

            cntnr_node = Node(ver, loc, cntnr, cat=cat, fn=fn)

            if cntnr_node.is_relevant():
                self._relevant_nodes.add(cntnr_node)

            parent_cntnr = row.get('parent_cntnr', None)

            if parent_cntnr:
                parent_fn = row.get('parent_fn', None)
                parent_cat = row.get('parent_cat', None)
                parent_node = Node(ver, loc, parent_cntnr, cat=parent_cat, fn=parent_fn)
                self.add_edge(parent_node, cntnr_node, mark=mark)
                if parent_node.is_relevant():
                    self._relevant_nodes.add(parent_node)

            elif fd:
                fd_node = Node(ver, loc, fd, cat=row['fd_cat'], fn=fn)
                # fd_flag = False
                self.add_edge(fd_node, cntnr_node, mark=mark)

        #

        if directives:

            logger.debug('directives')

            query = QUERY_TBL['directives'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                fd = row.get('fd', None)
                fn = row.get('fn', None)
                dtv = row['dtv']
                cat = row.get('cat', None)

                dtv_node = Node(ver, loc, dtv, cat=cat, fn=fn)

                self._relevant_nodes.add(dtv_node)

                parent_cntnr = row.get('cntnr', None)
                if parent_cntnr:
                    self.add_edge(Node(ver, loc, parent_cntnr), dtv_node, mark=mark)

                if fd:
                    fd_node = Node(ver, loc, fd, cat=row['fd_cat'], fn=fn)
                    if not parent_cntnr:
                        self.add_edge(fd_node, dtv_node, mark=mark)

        #

        if other_calls:

            logger.debug('other calls')

            query = QUERY_TBL['other_calls'] % {'proj': self._graph_uri}

            for qvs, row in self._sparql.query(query):
                ver = row['ver']
                loc = row['loc']
                fd = row.get('fd', None)
                fn = row.get('fn', None)
                call = row['call']

                callee_name = demangle(row['callee_name'])

                cat = 'fun-call*'

                if callee_name.startswith('MPI_'):
                    cat = 'mpi-call'
                elif callee_name.startswith('omp_'):
                    cat = 'omp-call'

                call_node = Node(ver, loc, call, cat=cat, fn=fn,
                                 callee_name=callee_name,
                                 all_calls=self._all_calls)

                if call_node.is_relevant():
                    self._relevant_nodes.add(call_node)

                parent_cntnr = row.get('cntnr', None)
                if parent_cntnr:
                    self.add_edge(Node(ver, loc, parent_cntnr),
                                  call_node, mark=mark)

                if fd:
                    fd_node = Node(ver, loc, fd, cat=row['fd_cat'], fn=fn)
                    if not parent_cntnr:
                        self.add_edge(fd_node, call_node, mark=mark)

        if gotos:
            pass  # not yet

        #

        if callgraph:
            self.setup_cg(mark=mark)

        roots = []

        count = 0

        self._lines_tbl = {}
        self._fid_tbl = {}

        self.setup_aa_tbl()

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

        logger.info('%d root nodes (out of %d nodes) found' % (len(roots), count))

        tree = {'node_tbl': self._node_tbl, 'roots': roots}

        for nd in self._relevant_nodes:
            nd.relevant = True
            for a in nd.get_ancestors():
                a.relevant = True

        self.set_tree(tree)

        self._node_tbl = {}

        # def dump(lv, k):
        #     print('!!! {}{}({}){}'.format('  '*lv, k, len(k.get_children()), k.relevant))

        # for root in roots:
        #     self.iter_tree(root, dump)

        return tree

    def iter_tree(self, root, f, pre=None, post=None):
        self.__iter_tree(set(), 0, root, f, pre=pre, post=post)

    def __iter_tree(self, visited, lv, node, f, pre=None, post=None):
        if node in visited:
            return

        visited.add(node)

        if pre:
            pre(node)

        if f:
            f(lv, node)

        children = node.get_children()

        for child in children:
            if node is not child:
                self.__iter_tree(visited, lv+1, child, f, pre=pre, post=post)

        if post:
            post(node)

    def mkrow(self, lver, loc, nd, lnum, mtbl, nid):
        tbl = mtbl.copy()
        tbl['proj'] = self._proj_id
        tbl['ver'] = lver
        tbl['path'] = loc
        tbl['fn'] = nd.fn
        tbl['lnum'] = lnum
        tbl['digest'] = mtbl['meta']['digest']
        tbl['nid'] = nid
        row = []
        for k in METRICS_ROW_HEADER:
            if k != 'root_file':
                row.append(tbl[k])
        return row

    def check_root(self, root, root_entities, all_roots=False):
        if root.cats & root_entities and (all_roots or demangle(root.fn) == 'main'):
            for x in root.get_descendants():
                if LOOPS & x.cats:
                    raise Exit


def test(proj):
    ol = Outline(proj)

    tree = ol.get_tree()

    root_tbl = {}  # ver -> loc -> root (contains loop)

    def f(lv, k):
        if LOOPS & k.cats:
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

    logger.info('%d top constructs (that contain loops) found' % count)

    def dump(lv, k):
        print('%s%s' % ('  '*lv, k))

    for ver in root_tbl.keys():
        lver = get_lver(ver)

        # if lver != 'base':
        #     continue

        loc_tbl = root_tbl[ver]
        for loc in loc_tbl.keys():
            print('*** ver=%s loc=%s' % (lver, loc))
            for root in loc_tbl[loc]:
                ol.iter_tree(root, dump)


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
                        help='allow all functions to be root nodes in addition to main functions')

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

        ol.gen_data('cpp', args.outdir, omitted=set(OMITTED), all_roots=args.all_roots)

        if args.index:
            logger.info('generating topic data...')
            ol.gen_topic('cpp', args.outdir,
                         docsrc=args.docsrc,
                         index=args.index,
                         model=args.model,
                         ntopics=args.ntopics)


if __name__ == '__main__':
    pass
