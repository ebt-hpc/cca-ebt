#!/usr/bin/env python3


'''
  Common functions

  Copyright 2013-2018 RIKEN
  Copyright 2018-2021 Chiba Institute of Technology

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
import os
import re
import tarfile
import shutil
from subprocess import call
import time
from datetime import datetime
from collections import namedtuple
import psutil
from uuid import uuid4
import traceback

from .conf import CCA_HOME, FB_DIR, WORK_DIR, FACT_DIR, ONT_DIR
from .conf import OUTDIR_NAME, VIRTUOSO_PW, VIRTUOSO_PORT

try:
    from conf import *
    print('local conf imported')
except:
    pass

###

TEMP_DIRS = [
    WORK_DIR,
    FACT_DIR,
]

STAT_FILE_NAME = 'status'

###

QUERY_DIR = os.path.join(CCA_HOME, 'queries', 'tuning')

CMD_PATH = os.path.join(CCA_HOME, 'bin')
PARSESRC_CMD  = os.path.join(CMD_PATH, 'parsesrc')

FB_FILES = [ os.path.join(FB_DIR, 'virtuoso'+x) for x in ['-temp.db',
                                                          '.db',
                                                          '.log',
                                                          '.pxa',
                                                          '.trx',
                                                          '.ini',
                                                      ]]

from cca.ccautil import virtuoso, proc, load_into_virtuoso, load_ont_into_virtuoso
from cca.ccautil.ns import NS_TBL
from . import materialize_fact_for_tuning
from . import virtuoso_ini


###

def get_timestamp():
    ts = datetime.now().isoformat()
    return ts

def get_custom_timestamp():
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    return ts

def gen_password():
    return 'x'+uuid4().hex[0:7]

def log(mes, out=sys.stdout):
    s = traceback.extract_stack()
    sf = s[-3]
    mname = sf[2]
    fname = sf[0]
    #l = sf[1]

    mstr = ''
    if mname != '<module>':
        mstr = '[%s]' % mname

    m = os.path.basename(fname)

    out.write('[%s][%s]%s %s\n' % (get_timestamp(), m, mstr, mes))
    #out.flush()


def mktar(path, tarname, dirname):
    try:
        with tarfile.open(os.path.join(path, tarname), 'w:gz') as tar:
            for (p, dns, fns) in os.walk(os.path.join(path, dirname)):
                for fn in fns:
                    fp = os.path.join(p, fn)
                    with open(fp, 'rb') as f:
                        info = tar.gettarinfo(fileobj=f)
                        relp = os.path.relpath(fp, path)
                        info.name = relp
                        tar.addfile(info, f)
        return 0

    except Exception as e:
        log('failed to tar: %s' % str(e))
        return 1


def touch(path):
    p = None
    try:
        with open(path, 'w') as f:
            f.write(os.path.basename(path))
            p = path
    except Exception as e:
        pass
    return p


def rm(path):
    stat = 0
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            log('failed to remove "%s"' % path)
            stat = 1
    return stat


def rmdir(path):
    stat = 0
    if os.path.isdir(path):
        try:
            if os.path.islink(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
        except Exception as e:
            log('failed to remove "%s"' % path)
            stat = 1
    return stat


def ensure_dir(d):
    b = True
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception as e:
            log('%s' % str(e))
            b = False
    return b


def cca_path(n):
    return os.path.join(CCA_HOME, n)


def is_virtuoso_running():
    b = False
    for p in psutil.process_iter():
        if p.name() == 'virtuoso-t':
            b = True
            break
    return b


def start_virtuoso(mem=4, pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):
    stat = 0
    if is_virtuoso_running():
        log('virtuoso is already running')
        stat = 1
    else:
        if ensure_dir(FB_DIR):
            fname = os.path.join(FB_DIR, 'virtuoso.ini')
            virtuoso_ini.gen_ini(FB_DIR, FACT_DIR, ONT_DIR, fname,
                                 mem=mem, port=port)

            v = virtuoso.base(dbdir=FB_DIR, port=port)
            rc = v.start_server()
            if rc == 0:
                rc = v.set_password(pw)
            if rc != 0:
                stat = 1
    return stat

def load_fact(proj_id, pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):
    fdir = os.path.join(FACT_DIR, proj_id)
    rc = load_into_virtuoso.load(proj_id,
                                 FB_DIR,
                                 fdir,
                                 ['.nt.gz'],
                                 pw=pw,
                                 port=port)
    return rc

def load_ont(pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):
    return load_ont_into_virtuoso.load(FB_DIR, ONT_DIR, pw=pw, port=port)

def materialize(proj_id, pw=VIRTUOSO_PW, port=VIRTUOSO_PORT):
    return materialize_fact_for_tuning.materialize(proj_id, pw=pw, port=port)

def clear_fb():
    stat = 0
    for f in FB_FILES:
        if os.path.exists(f):
            log('removing "%s"...' % f)
            rc = rm(f)
            if rc != 0:
                stat = rc
    return stat

def clear_dir(dpath, exclude=[]):
    stat = 0
    if os.path.isdir(dpath):
        for fn in os.listdir(dpath):
            if fn not in exclude:
                p = os.path.join(dpath, fn)
                rc = 0
                log('removing "%s"...' % p)
                if os.path.isdir(p):
                    rc = rmdir(p)
                else:
                    rc = rm(p)
                if rc != 0:
                    stat = rc
    return stat

def clear_temp():
    stat = 0
    for dpath in TEMP_DIRS:
        rc = clear_dir(dpath)
        if rc != 0:
            stat = rc
    return stat


def reset_virtuoso(pw=VIRTUOSO_PW, port=VIRTUOSO_PORT, backup_fb=None):
    stat = 0
    if is_virtuoso_running():
        v = virtuoso.base(dbdir=FB_DIR, pw=pw, port=port)
        rc = v.shutdown_server()
        if rc != 0 or is_virtuoso_running():
            return 1

    if backup_fb:
        try:
            shutil.copytree(FB_DIR, backup_fb, symlinks=True)
        except:
            return 1

    stat = clear_fb()

    return stat
        

def parse(proj_dir, proj_id, ver):
    args = ' -fact -fact:ast'
    args += ' -cache %s' % os.path.join(WORK_DIR, 'parsesrc')
    args += ' -fact:into-directory %s' % os.path.join(FACT_DIR, proj_id)
    args += ' -fact:project %s' % proj_id
    args += ' -fact:project-root %s' % proj_dir
    args += ' -fact:version VARIANT:%s -fact:add-versions' % ver
    args += ' -fact:encoding:FDLCO -fact:size-thresh 100000'
    #args += ' -parser:cpp'
    #args += ' -parser:fortran'
    args += ' %s' % proj_dir

    cmd = '%s%s' % (PARSESRC_CMD, args)
    log('cmd={}'.format(cmd))

    rc = proc.system(cmd)

    return rc


def build_fb(proj_dir, proj_id, mem=4, pw=VIRTUOSO_PW, port=VIRTUOSO_PORT,
             set_status=None, skip_materialize=False):

    if set_status == None:
        set_status = lambda mes: log(mes)

    # start virtuoso
    set_status('starting virtuoso...')
    rc = start_virtuoso(mem=mem, pw=pw, port=port)
    if rc != 0:
        set_status('failed to start virtuoso')
        return rc

    # load facts
    set_status('loading facts...')
    rc = load_fact(proj_id, pw=pw, port=port)
    if rc != 0:
        set_status('faild to load facts')
        return rc

    # load ontologies
    set_status('loading ontologies...')
    rc = load_ont(pw=pw, port=port)
    if rc != 0:
        set_status('faild to load ontologies')
        return rc

    if not skip_materialize:
        # materialize facts
        set_status('materializing facts...')
        rc = materialize(proj_id, pw=pw, port=port)
        if rc != 0:
            set_status('faild to materialize facts')
            return rc

    return 0


def create_argparser(desc):
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description=desc,
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('proj_dir', type=str, metavar='DIR',
                        help='set directory that subject programs reside')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-k', '--keep-fb', dest='keep_fb', action='store_true',
                        help='keep FB')

    parser.add_argument('-m', '--mem', dest='mem', metavar='GB', type=int,
                        choices=[2, 4, 8, 16, 32, 48, 64], default=4,
                        help='set available memory (GB)')

    parser.add_argument('-p', '--port', dest='port', default=VIRTUOSO_PORT,
                        metavar='PORT', type=int, help='set port number')

    parser.add_argument('--proj', dest='proj', metavar='PROJ_ID', default=None,
                        help='set project id (generated from proj_dir by default)')

    parser.add_argument('--pw', dest='pw', metavar='PASSWORD', default=None,
                        help='set password to access FB (generated by default)')

    return parser

def make_status_setter(path):
    def set_status(mes):
        log(mes)
        try:
            with open(path, 'w') as f:
                f.write(mes)
        except Exception as e:
            log(str(e))
    return set_status

def get_dest_root(proj_dir):
    dest_root = os.path.join(proj_dir, OUTDIR_NAME)
    return dest_root


class AnalyzerBase(object):
    def __init__(self, mem=4, pw=None, port=VIRTUOSO_PORT):
        self._mem = mem
        self._port = port

        if pw == None:
            self._pw = gen_password()
        else:
            self._pw = pw

        log('pw=%s port=%d' % (self._pw, self._port))

    def analyze_facts(self, proj_dir, proj_id, ver, dest_root):
        pass

    def analyze_dir(self, proj_dir, proj_id=None, keep_fb=False,
                    skip_build=False, skip_materialize=False, skip_outline=False, cleanup=False):
        log('analyzing "%s"...' % proj_dir)

        dest_root = get_dest_root(proj_dir)

        log('dest_root: "%s"' % dest_root)

        stat_path = os.path.join(dest_root, STAT_FILE_NAME)

        set_status = make_status_setter(stat_path)

        if not ensure_dir(dest_root):
            set_status('failed to create directory: "%s"' % dest_root)
            return

        if proj_id == None:
            proj_id = os.path.basename(os.path.abspath(proj_dir))

        set_status('analysis started for "%s"' % proj_id)

        ver = get_custom_timestamp()

        clear_dir(dest_root, exclude=['log'])

        # parse
        set_status('parsing source files...')
        rc = parse(proj_dir, proj_id, ver)
        if rc != 0:
            set_status('faild to parse source files')
            return

        if not skip_build:
            # build FB
            set_status('building FB...')
            rc = build_fb(proj_dir, proj_id,
                          mem=self._mem, pw=self._pw, port=self._port,
                          set_status=set_status, skip_materialize=skip_materialize)
            if rc != 0:
                return

        backup_fb = None
        if keep_fb:
            backup_fb = os.path.join(dest_root, 'fb')

        if not skip_outline:
            # analyze facts
            set_status('analyzing facts...')
            try:
                self.analyze_facts(proj_dir, proj_id, ver, dest_root)
            except Exception as e:
                set_status('failed to analyze facts: %s' % e)
                reset_virtuoso(pw=self._pw, port=self._port, backup_fb=backup_fb)
                return

        if cleanup:
            # cleanup
            set_status('cleaning up temporary files...')
            reset_virtuoso(pw=self._pw, port=self._port, backup_fb=backup_fb)
            clear_temp()

        set_status('finished.')
