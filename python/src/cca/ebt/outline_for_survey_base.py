#!/usr/bin/env python3

'''
  A script for outlining C programs

  Copyright 2013-2018 RIKEN
  Copyright 2017-2021 Chiba Institute of Technology

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
import sys
import json
from urllib.request import pathname2url
import re
import csv
import codecs
from time import time
import msgpack
import logging

from .sourcecode_metrics_for_survey_base import get_lver
from . import sourcecode_metrics_for_survey_base as metrics
from .search_topic_for_survey import search

from cca.ccautil.cca_config import PROJECTS_DIR, Config, VKIND_VARIANT, VKIND_GITREV
from cca.ccautil import project
from cca.ccautil.sparql import get_localname
from cca.ccautil import sparql
from cca.ccautil.ns import FB_NS, NS_TBL
from cca.ccautil.siteconf import GIT_REPO_BASE
from cca.ccautil import Git2
from cca.ccautil.virtuoso import VIRTUOSO_PW, VIRTUOSO_PORT
from cca.factutil.entity import SourceCodeEntity

###

logger = logging.getLogger()

MARKER_CALLEE_PAT = re.compile('^.*(dgemm|timer|start|begin).*$')

PP_IFX_SET = set(['pp-if', 'pp-ifdef', 'pp-ifndef', 'pp-elif', 'pp-else', 'pp-endif'])

QN_SEP = ','

NID_SEP = '_'

LEADING_DIGITS_PAT = re.compile(r'^\d+')


def remove_leading_digits(s):
    r = LEADING_DIGITS_PAT.sub('', s)
    return r


GITREV_PREFIX = NS_TBL['gitrev_ns']

OUTLINE_DIR = 'outline'
OUTLINE_FILE_FMT = '{}.msg'

TOPIC_DIR = 'topic'
TOPIC_FILE_FMT = '{}.json'

METRICS_DIR = 'metrics'
METRICS_FILE_FMT = '{}-{}.csv'


def demangle(s):
    return remove_leading_digits(s)


def is_compiler_directive(cats):
    b = False
    for cat in cats:
        if cat[0:4] in ('omp-', 'acc-', 'ocl-', 'xlf-', 'dec-'):
            b = True
            break
    return b


def ensure_dir(d):
    b = True
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception as e:
            logger.warning(str(e))
            b = False
    return b


def get_url(x):
    u = pathname2url(os.path.join(os.pardir, x))
    return u


class IdGenerator(object):
    def __init__(self, prefix=''):
        self._prefix = prefix
        self._count = 0

    def gen(self):
        i = '%s%x' % (self._prefix, self._count)
        self._count += 1
        return i


class IndexGenerator(object):
    def __init__(self, init=0):
        self._count = init

    def gen(self):
        i = self._count
        self._count += 1
        return i


def node_list_to_string(li):
    return '\n'.join(['{}: {}'.format(i, x) for i, x in enumerate(li)])


def index(idx_gen, data, callees_tbl):

    def scan(d):
        children = d['children']
        for c in children:
            scan(c)
        i = idx_gen.gen()
        d['idx'] = i
        if children:
            d['lmi'] = children[0]['lmi']
        else:
            d['lmi'] = i

        if children == [] and callees_tbl:
            callee_name = d.get('callee', None)
            if callee_name:
                callees = callees_tbl.get(callee_name, [])
                if callees:
                    d['nlinks'] = len(callees)
                else:
                    logger.debug('!!! not found: "{}"'.format(callee_name))

    scan(data)


class NodeBase(object):
    SUBPROGS = set()
    CALLS = set()
    LOOPS = set()
    GOTOS = set()

    def __init__(self, ver, loc, uri, cat='', callee_name=None,
                 all_sps=False, all_calls=False):

        self.relevant = False
        self.ver = ver
        self.loc = loc
        self.uri = uri
        self.cat = cat
        if cat is not None:
            self.cats = set(cat.split('&'))
        else:
            logger.warning('None cat: %s:%s:%s' % (get_localname(ver), loc,
                                                   get_localname(uri)))
            self.cats = set()

        self._callee_name = callee_name

        self.key = (ver, loc, get_localname(uri))

        self._ent = None
        self._fid = None
        self._start_line = None
        self._end_line = None

        self._parents = set()
        self._children = set()

        self.ancestors = set()
        self.descendants = set()

        self._mkey = None

        self._container = None
        self._parents_in_container = set()  # exclude self
        self._nparent_loops_in_container = None
        self._max_chain = None

        self._all_sps = all_sps
        self._all_calls = all_calls

    def __eq__(self, other):
        if isinstance(other, NodeBase):
            e = self.uri == other.uri
        else:
            e = False
        return e

    def __ne__(self, other):
        e = not self.__eq__(other)
        return e

    def __lt__(self, other):
        l0 = self.get_start_line()
        l1 = other.get_start_line()
        return l0 < l1

    def __gt__(self, other):
        l0 = self.get_start_line()
        l1 = other.get_start_line()
        return l0 > l1

    def __le__(self, other):
        self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other):
        self.__eq__(other) or self.__gt__(other)

    def __hash__(self):
        return hash(self.key)

    def __str__(self):
        sl = self.get_start_line()
        el = self.get_end_line()
        if sl == el:
            r = '%d' % sl
        else:
            r = '%d-%d' % (sl, el)

        s = '{}[{}:{}:{}]'.format(self.cat,
                                  r,
                                  self.get_name(),
                                  os.path.basename(self.loc))

        return s

    def is_relevant(self):
        b = False
        if self.cats & self.LOOPS:
            b = True
        elif self.cats & self.GOTOS:
            b = True
        elif self._all_sps and self.cats & self.SUBPROGS:
            b = True
        elif self.cats & self.CALLS:
            if self._all_calls:
                b = True
            else:
                m = MARKER_CALLEE_PAT.match(self._callee_name)
                if m:
                    b = True
                else:
                    b = any([self._callee_name.startswith(h) for h in ['mpi_',
                                                                       'MPI_',
                                                                       'omp_']]
                            )
        return b

    def get_container(self):
        return self._container

    def count_parent_loops_in_container(self):
        if self._nparent_loops_in_container is None:
            ps = self.get_parents_in_container()
            count = 0
            for p in ps:
                if self.LOOPS & p.cats:
                    count += 1
            self._nparent_loops_in_container = count

            logger.debug('%s <- {%s}' % (self, ';'.join(str(x) for x in ps)))

        return self._nparent_loops_in_container

    def get_parents_in_container(self):
        self.get_container()
        return self._parents_in_container

    def score_of_chain(self, chain):
        return 0

    def is_main(self):
        return False

    def get_max_chain(self, visited_containers=[]):  # chain of call or subprog
        if self._max_chain is None:

            container = self.get_container()

            if container is None:
                pass

            elif container is self:
                if container in visited_containers:
                    raise Exit

                if container.is_main():
                    self._max_chain = [self]

                elif container.cats & self.SUBPROGS:
                    calls = container.get_parents()

                    max_chain = []
                    in_file_call = False
                    start_line = sys.maxsize
                    loc = None

                    skip_count = 0

                    for call in calls:
                        callc = call.get_container()

                        if callc:
                            try:
                                chain = callc.get_max_chain(visited_containers+[container])
                            except Exit:
                                skip_count += 1
                                continue

                            if container in chain:
                                pass
                            else:
                                chain_ = [container, call] + chain

                                loc_ = call.loc

                                in_file_call_ = False
                                if chain:
                                    in_file_call_ = loc_ == container.loc

                                start_line_ = call.get_start_line()

                                score_ = self.score_of_chain(chain_)

                                max_score = self.score_of_chain(max_chain)

                                cond0 = score_ > max_score
                                cond1 = score_ == max_score and in_file_call_ \
                                    and not in_file_call
                                cond2 = score_ == max_score and loc == loc_ \
                                    and start_line_ < start_line

                                logger.debug('cond0:%s, cond1:%s, cond2:%s' % (cond0, cond1, cond2))

                                if cond0 or cond1 or cond2:
                                    max_chain = chain_
                                    in_file_call = in_file_call_
                                    start_line = start_line_
                                    loc = loc_

                    if skip_count < len(calls):
                        self._max_chain = max_chain
                    else:
                        return []

                else:  # another root (e.g. pp-directive)
                    pass

            else:  # container is not self
                self._max_chain = container.get_max_chain()

        return self._max_chain

    def get_mkey(self):
        if not self._mkey:
            self._mkey = (get_lver(self.ver), self.loc, str(self.get_start_line()))
        return self._mkey

    def is_root(self):
        b = len(self._parents) == 0
        return b

    def is_leaf(self):
        b = len(self._children) == 0
        return b

    def get_parents(self):
        return self._parents

    def add_parent(self, parent):
        self._parents.add(parent)

    def get_children(self):
        return self._children

    def add_child(self, child):
        self._children.add(child)

    def get_ent(self):
        if not self._ent:
            self._ent = SourceCodeEntity(uri=self.uri)
        return self._ent

    def get_fid(self):
        if not self._fid:
            try:
                self._fid = self.get_ent().get_file_id().get_value()
            except Exception:
                logger.debug('!!! uri={}'.format(self.uri))
        return self._fid

    def get_start_line(self):
        if not self._start_line:
            ent = self.get_ent()
            self._start_line = ent.get_range().get_start_line()
        return self._start_line

    def get_end_line(self):
        if not self._end_line:
            ent = self.get_ent()
            self._end_line = ent.get_range().get_end_line()
        return self._end_line

    def clear_ancestors(self):
        self.ancestors = set()

    def get_ancestors(self):
        if not self.ancestors:
            self.ancestors = set([self])
            self._iter_ancestors(self.ancestors)
        return self.ancestors

    def _iter_ancestors(self, ancs):
        for x in self._parents - ancs:
            ancs.add(x)
            x._iter_ancestors(ancs)

    def clear_descendants(self):
        self.descendants = set()

    def get_descendants(self):
        if not self.descendants:
            self.descendants = set([self])
            self._iter_descendants(self.descendants)
        return self.descendants

    def _iter_descendants(self, decs):
        for x in self._children - decs:
            decs.add(x)
            x._iter_descendants(decs)

    def get_record(self, children):
        d = {
            'cat':      self.cat,
            'loc':      self.loc,
            'sl':       self.get_start_line(),
            'el':       self.get_end_line(),
            'children': children,
        }
        return d

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
        return ty

    def is_statement(self):
        b = False
        for c in self.cats:
            if c.endswith('-statement'):
                b = True
                break
        return b

    def is_pp(self):
        b = False
        for c in self.cats:
            if c.startswith('pp-'):
                b = True
                break
        return b

    def is_pp_ifx(self):
        return self.cats & PP_IFX_SET

    def set_extra(self, d):
        return

    def get_name(self):
        return ''

    def check_children(self, children_l):
        return children_l

    def to_dict(self, ancl, ntbl,
                elaborate=None,
                idgen=None,
                collapsed_caller_tbl={},
                expanded_callee_tbl={},
                parent_tbl=None,
                is_marked=None,
                omitted=set()):
        # ntbl: caller_name * func node * level -> visited

        logger.debug('! {}'.format(self))

        ancl_ = ancl
        lv = len(ancl)

        if self.cats & self.SUBPROGS:
            ancl_ = [self] + ancl
            if lv > 0:
                ntbl[(ancl[0].get_name(), self, lv)] = True
                logger.debug('[REG] %s:%s:%d' % (ancl[0].get_name(),
                                                 self.get_name(), lv))

        _children_l = sorted(list(self._children))

        logger.debug('len(_children)={}'.format(len(self._children)))

        children_l = list(filter(lambda c: c not in ancl and c.relevant,
                                 _children_l))

        children_l = self.check_children(children_l)

        is_caller = self.cats & self.CALLS

        is_filtered_out = False

        self.ignored_callee_count = 0

        if is_caller:
            logger.debug('callee_name={}'.format(self._callee_name))

            ancl_ = [self] + ancl

            cand = list(filter(lambda c: c.loc == self.loc, children_l))
            if cand:
                children_l = cand

            def filt(c):
                max_chain = c.get_max_chain()

                if max_chain is None:
                    return False

                max_lv = len(max_chain)

                chain_ = [c] + ancl_
                lv_ = len(chain_)

                b = True

                if max_lv == lv_:
                    for i in range(lv_):
                        if chain_[i] != max_chain[i]:
                            b = False
                            break
                else:
                    b = False

                logger.debug('[LOOKUP] {}:{}:{}'.format(self.get_name(),
                                                        c,
                                                        len(ancl_)))
                hit = (self.get_name(), c, len(ancl_)) in ntbl

                b = b and (not hit)

                logger.debug('[FILT] ({}->){} (lv={}) --> {} (hit={}, max_lv={})'
                             .format(self.get_name(),
                                     c.get_name(),
                                     lv_,
                                     b,
                                     hit,
                                     max_lv))
                return b

            before = len(children_l)
            children_l = list(filter(filt, children_l))
            if before > len(children_l):
                is_filtered_out = True
                logger.debug('filtered_out -> True')

            def check_mark(nd):
                b = is_marked(nd)
                if not b and nd.cats & self.SUBPROGS:
                    self.ignored_callee_count += 1
                return b

            if is_marked:
                children_l = list(filter(check_mark, children_l))

        # children = [c.to_dict(ancl_, ntbl,
        #                       elaborate=elaborate,
        #                       idgen=idgen,
        #                       parent_tbl=parent_tbl,
        #                       is_marked=is_marked) for c in children_l]

        children = []

        for c in children_l:
            x = c.to_dict(ancl_, ntbl,
                          elaborate=elaborate,
                          idgen=idgen,
                          collapsed_caller_tbl=collapsed_caller_tbl,
                          expanded_callee_tbl=expanded_callee_tbl,
                          parent_tbl=parent_tbl,
                          is_marked=is_marked,
                          omitted=omitted)

            if omitted & c.cats:
                # print('!!! %s (%d)' % (c, len(c.get_children())))
                children += x.get('children', [])
            else:
                children.append(x)

        # print('!!! %s (%d:%s -> %d)' % (self,
        #                                 len(self._children),
        #                                 '&'.join([c.cat for c in self._children]),
        #                                 len(children)))

        if is_caller and children != []:
            try:
                li = expanded_callee_tbl[self._callee_name]
                expanded = li + [x for x in children if x not in li]
                expanded_callee_tbl[self._callee_name] = expanded
                logger.debug('expanded_callee_tbl: {} -> [{}]'
                             .format(self._callee_name,
                                     ';'.join([x['id'] for x in expanded])))
            except KeyError:
                expanded_callee_tbl[self._callee_name] = children
                logger.debug('expanded_callee_tbl: {} -> [{}]'
                             .format(self._callee_name,
                                     ';'.join([x['id'] for x in children])))

        d = self.get_record(children)

        if self.ignored_callee_count:
            d['ignored_callee_count'] = self.ignored_callee_count

        self.set_extra(d)

        if self._callee_name:
            d['callee'] = self._callee_name

        ty = self.get_type()
        if ty:
            d['type'] = ty

        if idgen:
            nid = idgen.gen()
            d['id'] = nid

            if parent_tbl is not None:
                for c in d.get('children', []):
                    cid = c['id']
                    # print('!!! parent_tbl: %s(%s) -> %s(%s)' % (cid, c['cat'], nid, d['cat']))
                    parent_tbl[cid] = nid

            if is_caller and self._children != [] and children == [] and is_filtered_out:
                v = (d, len(ancl))
                logger.debug('{} -> {}'.format(self._callee_name, v[1]))
                try:
                    collapsed_caller_tbl[self._callee_name].append(v)
                except KeyError:
                    collapsed_caller_tbl[self._callee_name] = [v]

        if elaborate:
            if self.cats & omitted:
                pass
            else:
                elaborate(self, d)

        return d


class Exit(Exception):
    pass


def tbl_get_list(tbl, key):
    try:
        li = tbl[key]
    except KeyError:
        li = []
        tbl[key] = li
    return li


def tbl_get_set(tbl, key):
    try:
        s = tbl[key]
    except KeyError:
        s = set()
        tbl[key] = s
    return s


def tbl_get_dict(tbl, key):
    try:
        d = tbl[key]
    except KeyError:
        d = {}
        tbl[key] = d
    return d


def gen_conf_a(proj_id, ver, proj_dir=PROJECTS_DIR):
    logger.info(f'generating conf for "{proj_id}" (ver="{ver}")')
    conf = Config()
    conf.proj_id = proj_id
    conf.proj_path = os.path.join(proj_dir, proj_id)
    conf.vkind = VKIND_VARIANT
    conf.vers = [ver]
    conf.nversions = 1
    conf.use_internal_parser()
    conf.finalize()
    return conf


def gen_conf(proj_id, commits=['HEAD'], proj_dir=None):
    logger.info('generating conf for "%s" (commits=[%s])' % (proj_id,
                                                             ','.join(commits)
                                                             ))
    conf = Config()
    conf.proj_id = proj_id

    if proj_dir:
        conf.proj_path = os.path.join(proj_dir, re.sub(r'_git$', '', proj_id))

    conf.gitweb_proj_id = re.sub(r'_git$', '.git', proj_id)
    conf.vkind = VKIND_GITREV
    conf.vers = commits
    conf.nversions = len(commits)
    conf.use_internal_parser()
    conf.finalize()
    return conf


class SourceFiles(object):
    def __init__(self, conf, gitrepo=GIT_REPO_BASE, proj_dir=PROJECTS_DIR):

        proj_id = conf.proj_id

        self.repo = None
        self.proj_dir = None

        if conf.is_vkind_gitrev():
            repo_path = os.path.normpath(os.path.join(gitrepo,
                                                      conf.gitweb_proj_id))
            try:
                self.repo = Git2.Repository(repo_path)
            except Exception:
                pid = re.sub(r'_git$', '', proj_id)
                repo_path = os.path.normpath(os.path.join(gitrepo, pid))
                self.repo = Git2.Repository(repo_path)

        else:
            self.proj_dir = os.path.join(proj_dir, proj_id)

    def get_file(self, file_spec):
        lines = []

        try:

            if self.repo:
                blob = self.repo.get_blob(file_spec['fid']).data
                decoded = codecs.decode(blob, 'utf-8', 'replace')
                lines = decoded.splitlines()

            elif self.proj_dir:
                path = os.path.join(self.proj_dir, file_spec['ver_dir_name'],
                                    file_spec['path'])
                with codecs.open(path, encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()

        except Exception as e:
            logger.warning(str(e))

        return lines


def norm_callee_name(orig):
    norm = orig
    if orig:
        norm = ':'.join(sorted(orig.split(':')))
    return norm


def is_x_dict(s, d):
    b = False
    cat = d.get('cat', None)
    if cat:
        if set(cat.split('&')) & s:
            b = True
    return b


class OutlineBase(object):
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
                 SUBPROGS=set(),
                 CALLS=set(),
                 get_root_entities=None,
                 METRICS_ROW_HEADER=[],
                 add_root=False,
                 conf=None):

        self.SUBPROGS = SUBPROGS
        self.CALLS = CALLS
        self.get_root_entities = get_root_entities
        self.METRICS_ROW_HEADER = METRICS_ROW_HEADER
        self.add_root = add_root

        self._proj_id = proj_id
        self._graph_uri = FB_NS + proj_id
        self._sparql = sparql.get_driver(method, pw=pw, port=port)
        self._method = method
        self._pw = pw
        self._port = port
        self._gitrepo = gitrepo
        self._proj_dir = proj_dir

        self._outline_dir = os.path.join(OUTLINE_DIR, self._proj_id)
        self._outline_v_dir = None
        self._metrics_dir = os.path.join(METRICS_DIR, self._proj_id)

        self._simple_layout = simple_layout
        self._all_sps = all_sps
        self._all_calls = all_calls

        if conf is None:
            self._conf = project.get_conf(proj_id)
            if not self._conf:
                if proj_id.endswith('_git'):
                    self._conf = gen_conf(proj_id, commits=commits,
                                          proj_dir=gitrepo)
                else:
                    self._conf = gen_conf_a(proj_id, ver, proj_dir)
        else:
            self._conf = conf

        self._hash_algo = self._conf.hash_algo

        self._tree = None

        self._node_tbl = {}  # (ver * loc * uri) -> node

        self._lines_tbl = {}  # ver -> loc -> line set
        self._fid_tbl = {}  # (ver * loc) -> fid

        self._metrics = None

        self._marked_nodes = set()

        self._aa_tbl = {}  # (ver * loc * start_line) -> range list

    def setup_aa_tbl(self):
        return

    def get_aref_ranges(self, mkey):
        # self.setup_aa_tbl()
        rs = None
        try:
            rs = self._aa_tbl[mkey]
        except KeyError:
            pass
        return rs

    def is_caller(self, d):
        return is_x_dict(self.CALLS, d)

    def is_subprog(self, d):
        return is_x_dict(self.SUBPROGS, d)

    def iter_d(self, f, d, lv=0):
        f(lv, d)
        d_is_caller = self.is_caller(d)
        for c in d.get('children', []):
            lv_ = lv
            if d_is_caller and self.is_subprog(c):
                lv_ = lv + 1
            self.iter_d(f, c, lv=lv_)

    def get_max_loop_level(self, ent):
        m = self.get_metrics()
        lv = m.get_max_loop_level(ent)
        return lv

    def get_metrics(self):
        if self._metrics is None:
            self.extract_metrics()
        return self._metrics

    def extract_metrics(self):
        return

    def get_metrics_tbl(self, key):
        if self._metrics is None:
            self.extract_metrics()

        ftbl = self._metrics.find_ftbl(key)
        return ftbl

    def get_file_spec(self, verURI, path):
        spec = {}
        if self._conf.is_vkind_gitrev():
            spec['fid'] = self._fid_tbl[(verURI, path)]
        else:
            if self._simple_layout:
                spec['ver_dir_name'] = ''
            else:
                spec['ver_dir_name'] = self.get_ver_dir_name(verURI)
            spec['path'] = path

        return spec

    def get_line_text_tbl(self, source_files, verURI, strip=True):
        line_text_tbl = {}  # loc -> line -> text

        lines_tbl = self._lines_tbl.get(verURI, {})

        for (loc, lines) in lines_tbl.items():

            logger.debug(f'scanning "{loc}"...')

            max_line = max(lines)

            text_tbl = tbl_get_dict(line_text_tbl, loc)  # line -> text

            file_spec = self.get_file_spec(verURI, loc)

            ln = 0

            for _line in source_files.get_file(file_spec):
                ln += 1

                if ln > max_line:
                    break

                if ln in lines:
                    if strip:
                        text_tbl[ln] = _line.strip()
                    else:
                        text_tbl[ln] = _line

        return line_text_tbl

    def get_vindex(self, uri):
        vi = None
        try:
            vi = self._conf.versionURIs.index(uri)
        except Exception:
            pass
        return vi

    def get_ver_dir_name(self, verURI):
        v = self._conf.versions[self.get_vindex(verURI)]
        vdn = self._conf.get_ver_dir_name(v)
        return vdn

    def get_node(self, obj, check=None):
        node = self._node_tbl.get(obj.key, None)
        if not node:
            node = obj
            self._node_tbl[obj.key] = obj
        elif check:
            check(obj, node)
        return node

    def mark_node(self, nd):
        self._marked_nodes.add(nd)

    def add_edge(self, parent, child, mark=True):
        return

    def get_tree(self, callgraph=True,
                 other_calls=True, directives=True, gotos=True,
                 mark=True):

        if not self._tree:
            logger.info('constructing trees...')
            self._tree = self.construct_tree(callgraph=callgraph,
                                             other_calls=other_calls,
                                             directives=directives,
                                             gotos=gotos,
                                             mark=mark)
        return self._tree

    def set_tree(self, tree):
        self._tree = tree

    def setup_cg(self, mark=True):
        return

    def construct_tree(self, callgraph=True,
                       other_calls=True, directives=True, gotos=True,
                       mark=True):
        return {}

    def iter_tree(self, root, f, pre=None, post=None):
        return

    def __iter_tree(self, visited, lv, node, f, pre=None, post=None):
        return

    def gen_topic_file_name(self):
        fn = TOPIC_FILE_FMT.format(self._proj_id)
        return fn

    def gen_data_file_name(self, fid):
        fn = OUTLINE_FILE_FMT.format(fid)
        return fn

    def gen_metrics_file_name(self, lver, lang):
        fn = METRICS_FILE_FMT.format(lver, lang)
        return fn

    def get_measurement(self, mtbl, ms):
        d = {}
        for m in ms:
            v = mtbl[m]
            k = metrics.abbrv_tbl[m]
            d[k] = v
        return d

    def gen_topic(self, lang, outdir='.', docsrc=None, index=None, model='lsi', ntopics=32):

        topic_dir = os.path.join(outdir, TOPIC_DIR)

        if not ensure_dir(topic_dir):
            return

        if index and docsrc:
            proj = re.sub(r'_git$', '', self._proj_id)
            dpath = os.path.join(docsrc, proj)
            logger.info(f'reading from "{dpath}"')
            opath = os.path.join(topic_dir, self.gen_topic_file_name())
            search(index, model, dpath, ntopics=ntopics, lang=lang, outfile=opath)

    def mkrow(self, lver, loc, nd, lnum, mtbl, nid):
        return []

    def gen_index_tables(self):
        path_list_tbl = {}  # ver -> path list
        fid_list_tbl = {}   # ver -> fid list

        path_idx_tbl_tbl = {}  # ver -> path -> idx
        fid_idx_tbl_tbl = {}   # ver -> fid -> idx

        vers = set()

        for ((ver, path), fid) in self._fid_tbl.items():
            vers.add(ver)
            try:
                path_list = path_list_tbl[ver]
            except KeyError:
                path_list = []
                path_list_tbl[ver] = path_list

            try:
                fid_list = fid_list_tbl[ver]
            except KeyError:
                fid_list = []
                fid_list_tbl[ver] = fid_list

            try:
                path_idx_tbl = path_idx_tbl_tbl[ver]
            except KeyError:
                path_idx_tbl = {}
                path_idx_tbl_tbl[ver] = path_idx_tbl

            try:
                fid_idx_tbl = fid_idx_tbl_tbl[ver]
            except KeyError:
                fid_idx_tbl = {}
                fid_idx_tbl_tbl[ver] = fid_idx_tbl

            if path not in path_list:
                path_idx = len(path_list)
                path_list.append(path)
                path_idx_tbl[path] = path_idx

            if fid not in fid_list:
                fid_idx = len(fid_list)
                fid_list.append(fid)
                fid_idx_tbl[fid] = fid_idx

        self._path_list_tbl = path_list_tbl
        self._fid_list_tbl = fid_list_tbl

        self._path_idx_tbl_tbl = path_idx_tbl_tbl
        self._fid_idx_tbl_tbl = fid_idx_tbl_tbl

    def check_root(self, root, root_entities):
        raise Exit

    def set_extra2(self, d, mkey):
        return

    def gen_data(self, lang, outdir='.', extract_metrics=True, omitted=set(),
                 all_roots=False):

        outline_dir = os.path.join(outdir, self._outline_dir)
        self._outline_v_dir = os.path.join(outline_dir, 'v')

        if not ensure_dir(self._outline_v_dir):
            return

        if extract_metrics:
            self.extract_metrics()

        tree = self.get_tree()

        self.gen_index_tables()

        root_tbl = {}  # ver -> loc -> root (contains loop) list

        count = 0

        if self.get_root_entities is not None:
            root_entities = self.get_root_entities(full=all_roots)

        # filter out trees that do not contain loops
        for root in tree['roots']:
            try:
                self.check_root(root, root_entities)
            except Exit:
                count += 1

                loc_tbl = tbl_get_dict(root_tbl, root.ver)

                roots = tbl_get_list(loc_tbl, root.loc)

                roots.append(root)

        logger.info(f'{count} root nodes found')

        metrics_dir = None

        if extract_metrics:
            self.extract_metrics()
            metrics_dir = os.path.join(outdir, self._metrics_dir)

        source_files = SourceFiles(self._conf, gitrepo=self._gitrepo,
                                   proj_dir=self._proj_dir)

        for ver in root_tbl.keys():

            if ver not in self._conf.versionURIs:
                continue

            path_idx_tbl = self._path_idx_tbl_tbl.get(ver, {})
            fid_idx_tbl = self._fid_idx_tbl_tbl.get(ver, {})

            path_list = self._path_list_tbl.get(ver, [])
            fid_list = self._fid_list_tbl.get(ver, [])

            lver = get_lver(ver)

            loc_tbl = root_tbl[ver]

            json_ds = []

            logger.info('generating line text table for "%s"...' % lver)

            line_text_tbl = self.get_line_text_tbl(source_files, ver)

            relevant_node_tbl = {}  # loc -> lnum -> nid list
            nodes = set()
            csv_rows = []

            def reg_nid(loc, lnum, nid):
                try:
                    ltbl = relevant_node_tbl[loc]
                except KeyError:
                    ltbl = {}
                    relevant_node_tbl[loc] = ltbl
                try:
                    nids = ltbl[lnum]
                except KeyError:
                    nids = []
                    ltbl[lnum] = nids
                if nid not in nids:
                    nids.append(nid)

            def is_marked(node):
                b = node in self._marked_nodes
                return b

            def elaborate(node, d):
                fid = node.get_fid()
                loc = node.loc
                d['fid'] = fid_idx_tbl[fid]
                d['loc'] = path_idx_tbl[loc]

                start_line = node.get_start_line()
                if node.is_block():
                    d['code'] = '<span class="cat">%s</span>' % node.get_block_cat()
                else:
                    try:
                        code = line_text_tbl[loc][start_line]
                        d['code'] = code

                    except KeyError:
                        pass

                mkey = (lver, loc, str(start_line))

                self.set_extra2(d, mkey)

                aref_ranges = self.get_aref_ranges(mkey)
                if aref_ranges:
                    for aref_range in aref_ranges:
                        df = aref_range.get('def', None)
                        if df:
                            ln = df.get('line', None)
                            p = df.get('path', None)
                            if ln and p:
                                try:
                                    df['code'] = line_text_tbl[p][ln]
                                except KeyError:
                                    pass
                            if 'fid' in df:
                                del df['fid']

                    d['aref_ranges'] = json.dumps(aref_ranges)

                try:
                    mtbl = self.get_metrics_tbl(mkey)

                    bf0 = round(mtbl[metrics.BF[0]], 2)
                    bf1 = round(mtbl[metrics.BF[1]], 2)
                    bf2 = round(mtbl[metrics.BF[2]], 2)

                    if bf0 > 0 or bf1 > 0 or bf2 > 0:
                        logger.debug('%s: %s -> %3.2f|%3.2f|%3.2f' % (node.cat,
                                                                      mkey,
                                                                      bf0,
                                                                      bf1,
                                                                      bf2))

                        md = self.get_measurement(mtbl, [
                            metrics.N_BRANCHES,
                            metrics.N_STMTS,
                            metrics.N_FP_OPS,
                        ] + metrics.N_IND_A_REFS +
                            metrics.N_A_REFS +
                            metrics.N_DBL_A_REFS
                        )

                        d['bf0'] = bf0
                        d['bf1'] = bf1
                        d['bf2'] = bf2

                        d['other_metrics'] = md
                        d['relevant'] = True

                        nid = d['id']
                        reg_nid(d['loc'], d['sl'], nid)

                        if node not in nodes:
                            row = self.mkrow(lver, loc, node, start_line, mtbl,
                                             nid)
                            csv_rows.append(row)

                        nodes.add(node)

                except KeyError:
                    # print('!!! not found: {}'.format(mkey))
                    pass

            idgen = IdGenerator()

            nid_tbl = {}
            parent_tbl = {}

            root_collapsed_caller_tbl = {}
            root_expanded_callee_tbl = {}

            d_tbl = {}

            logger.info(f'converting trees into JSON for "{lver}"...')

            for loc in loc_tbl.keys():
                logger.debug(f'loc={loc}')
                ds = []

                fid = None

                for root in loc_tbl[loc]:
                    logger.debug(f'root={root}')
                    if not fid:
                        fid = root.get_fid()

                    collapsed_caller_tbl = {}
                    root_collapsed_caller_tbl[root] = collapsed_caller_tbl

                    expanded_callee_tbl = {}
                    root_expanded_callee_tbl[root] = expanded_callee_tbl

                    ancls = [root] if self.add_root else []

                    d = root.to_dict(ancls, {},
                                     elaborate=elaborate,
                                     idgen=idgen,
                                     collapsed_caller_tbl=collapsed_caller_tbl,
                                     expanded_callee_tbl=expanded_callee_tbl,
                                     parent_tbl=parent_tbl,
                                     is_marked=is_marked,
                                     omitted=omitted)
                    ds.append(d)

                    d_tbl[d['id']] = root

                    logger.debug('collapsed_caller_tbl: {}'
                                 .format(list(collapsed_caller_tbl.keys())))

                nid = idgen.gen()

                for d in ds:
                    parent_tbl[d['id']] = nid

                loc_d = {
                    'id':       nid,
                    'text':     loc,
                    'loc':      path_idx_tbl[loc],
                    'children': ds,
                    'fid':      fid_idx_tbl[fid],
                    'cat':      'file',
                    'type':     'file',
                }

                nid_tbl[nid] = loc

                json_ds.append(loc_d)

            def copy_dict(d, hook=(lambda x: None), info={}):
                children = [copy_dict(c, hook=hook, info=info)
                            for c in d['children']]
                try:
                    info['count'] += 1
                except KeyError:
                    pass
                copied = dict.copy(d)
                hook(copied)
                copied['children'] = children
                return copied

            root_callees_tbl = {}

            logger.debug('* root_collapsed_caller_tbl:')
            for (r, collapsed_caller_tbl) in root_collapsed_caller_tbl.items():
                logger.debug(f'* root={r}:')

                callees_tbl = {}
                root_callees_tbl[r] = callees_tbl

                while collapsed_caller_tbl:
                    new_collapsed_caller_tbl = {}

                    for (callee, d_lv_list) in collapsed_caller_tbl.items():

                        logger.debug(f' callee="{callee}"')

                        expanded_callee_tbl = \
                            root_expanded_callee_tbl.get(r, {})

                        callee_dl = expanded_callee_tbl.get(callee, [])
                        if callee_dl:
                            callees_tbl[callee] = [d['id'] for d in callee_dl]
                            logger.debug('  callees_tbl: {} -> [{}]'
                                         .format(callee,
                                                 ','.join(callees_tbl[callee]))
                                         )
                            logger.debug(' -> skip')
                            continue

                        callee_dl = []
                        collapsed_caller_tbl_ = {}

                        for (r_, tbl) in root_expanded_callee_tbl.items():
                            callee_dl = tbl.get(callee, [])
                            if callee_dl:
                                logger.debug('{} callee dicts found in {}'
                                             .format(len(callee_dl), r_))
                                collapsed_caller_tbl_ \
                                    = root_collapsed_caller_tbl.get(r_, {})
                                break

                        if callee_dl:
                            nid_callee_lv_tbl = {}

                            for callee_d in callee_dl:
                                def chk(lv_, d):
                                    callee_ = d.get('callee', None)
                                    if callee_ and d.get('children', []) == []:
                                        d_lv_list_ = collapsed_caller_tbl_\
                                            .get(callee_, [])
                                        for (d_, _) in d_lv_list_:
                                            nid_ = d_['id']
                                            try:
                                                nid_callee_lv_tbl[nid_]\
                                                    .append((callee_, lv_))
                                            except KeyError:
                                                nid_callee_lv_tbl[nid_] \
                                                    = [(callee_, lv_)]
                                self.iter_d(chk, callee_d)

                            max_lv = 0
                            selected = None
                            for (d, lv) in d_lv_list:
                                if lv > max_lv:
                                    max_lv = lv
                                    selected = d
                                logger.debug('    nid={} lv={}'.format(d['id'],
                                                                       lv))

                            selected_id = selected['id']
                            logger.debug('    -> selected %s' % selected_id)

                            copied_dl = []

                            try:
                                base = '{}{}'.format(selected_id, NID_SEP)
                                idl = selected_id.split(NID_SEP)

                                def conv_id(i):
                                    return base+i

                                def hook(x):
                                    xid = x['id']
                                    if xid in idl:
                                        return
                                    for (c, lv) in nid_callee_lv_tbl.get(xid, []):
                                        lv_ = max_lv + lv + 1
                                        try:
                                            li = new_collapsed_caller_tbl[c]
                                            if not any([x_['id'] == xid
                                                        and lv_ == lv__
                                                        for (x_, lv__) in li]):
                                                li.append((x, lv_))
                                        except KeyError:
                                            new_collapsed_caller_tbl[c] = [(x, lv_)]
                                    x['id'] = conv_id(xid)

                                for callee_d in callee_dl:
                                    info = {'count': 0}
                                    copied = copy_dict(callee_d, hook=hook,
                                                       info=info)
                                    copied_dl.append(copied)
                                    logger.debug('{} nodes copied'
                                                 .format(info['count']))

                                selected['children'] = copied_dl
                                callees_tbl[callee] = [d['id'] for d in copied_dl]
                                logger.debug('callees_tbl: {} -> [{}]'
                                             .format(callee,
                                                     ','.join(callees_tbl[callee])))
                            except Exception as e:
                                logger.warning(str(e))

                    if new_collapsed_caller_tbl:
                        collapsed_caller_tbl = new_collapsed_caller_tbl
                        logger.debug('new_collapsed_caller_tbl:')
                    else:
                        collapsed_caller_tbl = {}

                    for (callee, d_lv_list) in new_collapsed_caller_tbl.items():
                        logger.debug('callee=%s' % callee)
                        for (d, lv) in d_lv_list:
                            logger.debug('%s (lv=%d)' % (d['id'], lv))

            logger.debug('* root_callees_tbl:')
            for r, t in root_callees_tbl.items():
                logger.debug(f' {r}:')
                for k, v in t.items():
                    logger.debug(f'  {k} -> {v}')

            if metrics_dir:
                if ensure_dir(metrics_dir):

                    metrics_file_name = self.gen_metrics_file_name(lver, lang)
                    metrics_path = os.path.join(metrics_dir, metrics_file_name)

                    logger.info(f'dumping metrics into "{metrics_path}"...')
                    logger.info('{} rows found'.format(len(csv_rows)))

                    try:
                        with open(metrics_path, 'w') as metricsf:
                            csv_writer = csv.writer(metricsf)
                            csv_writer.writerow(self.METRICS_ROW_HEADER)
                            nid_i = self.METRICS_ROW_HEADER.index('nid')
                            for row in csv_rows:
                                root_nid = row[nid_i]
                                while True:
                                    try:
                                        root_nid = parent_tbl[root_nid]
                                    except KeyError:
                                        break

                                if root_nid not in nid_tbl:
                                    print(row)

                                row.append(nid_tbl[root_nid])

                                csv_writer.writerow(row)

                    except Exception as e:
                        logger.warning(str(e))

            # clean up relevant_node_tbl
            p_to_be_del = []
            for (p, ltbl) in relevant_node_tbl.items():
                ln_to_be_del = []
                for (ln, nids) in ltbl.items():
                    if len(nids) < 2:
                        ln_to_be_del.append(ln)
                for ln in ln_to_be_del:
                    del ltbl[ln]
                if len(ltbl) == 0:
                    p_to_be_del.append(p)
            for p in p_to_be_del:
                del relevant_node_tbl[p]

            #

            json_ds.sort(key=lambda x: x['text'])

            lver_dir = os.path.join(self._outline_v_dir, lver)

            path_tbl = {}  # path -> fid

            idx_range_tbl = {}  # fidi -> (lmi * idx)

            if ensure_dir(lver_dir):
                try:
                    with open(os.path.join(lver_dir, 'path_list.json'), 'w') as plf:
                        plf.write(json.dumps(path_list))

                except Exception as e:
                    logger.warning(str(e))

                try:
                    with open(os.path.join(lver_dir, 'fid_list.json'), 'w') as flf:
                        flf.write(json.dumps(fid_list))

                except Exception as e:
                    logger.warning(str(e))

                idx_gen = IndexGenerator(init=1)

                for json_d in json_ds:
                    json_d['node_tbl'] = relevant_node_tbl
                    json_d['state'] = {'opened': True}

                    callees_tbl = None

                    logger.debug('root_callees_tbl:')
                    for r, t in root_callees_tbl.items():
                        logger.debug(f' {r}:')
                        for k, v in t.items():
                            logger.debug(f'  {k} -> {v}')

                    for d in json_d['children']:
                        try:
                            r = d_tbl[d['id']]
                            logger.debug(f'root={r}')
                            callees_tbl = root_callees_tbl[r]
                            if callees_tbl:
                                logger.debug('callees_tbl found')
                                logger.debug(' keys=[{}]'
                                             .format(','
                                                     .join(callees_tbl
                                                           .keys())))
                                json_d['callees_tbl'] = callees_tbl
                        except KeyError:
                            pass

                    fidi = json_d['fid']
                    loci = json_d['loc']

                    fid = fid_list[fidi]
                    loc = path_list[loci]

                    path_tbl[loci] = fidi

                    data_file_name = self.gen_data_file_name(fid)

                    lver_loc_dir = os.path.join(lver_dir, loc)

                    if ensure_dir(lver_loc_dir):

                        data_path = os.path.join(lver_loc_dir, data_file_name)

                        logger.debug('indexing for "%s"...' % data_path)
                        st = time()

                        index(idx_gen, json_d, callees_tbl)

                        idx = json_d.get('idx', None)
                        lmi = json_d.get('lmi', None)
                        logger.debug(f'idx={idx}')
                        logger.debug(f'lmi={lmi}')
                        if idx and lmi:
                            idx_range_tbl[fidi] = (lmi, idx, loci)

                        logger.debug('done. (%0.3f sec)' % (time() - st))

                        logger.info(f'dumping object into "{data_path}"...')

                        try:
                            with open(data_path, 'wb') as f:
                                msgpack.pack(json_d, f)

                        except Exception as e:
                            logger.warning(str(e))
                            continue

            #

            is_gitrev = self._conf.is_vkind_gitrev()
            vid = get_localname(ver) if is_gitrev else self.get_ver_dir_name(ver)

            vitbl = {
                'path_tbl': path_tbl,
                'vid':      vid,
            }
            try:
                with open(os.path.join(lver_dir, 'index.json'), 'w') as vif:
                    vif.write(json.dumps(vitbl))

            except Exception as e:
                logger.warning(str(e))

            try:
                with open(os.path.join(lver_dir, 'idx_range.json'), 'w') as irf:
                    irf.write(json.dumps(idx_range_tbl))

            except Exception as e:
                logger.warning(str(e))

        #

        pitbl = {
            'hash_algo': self._hash_algo,
            'ver_kind':  self._conf.vkind,
        }
        try:
            with open(os.path.join(outline_dir, 'index.json'), 'w') as pif:
                pif.write(json.dumps(pitbl))

        except Exception as e:
            logger.warning(str(e))


if __name__ == '__main__':
    pass
