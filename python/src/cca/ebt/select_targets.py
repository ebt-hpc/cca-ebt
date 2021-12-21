#!/usr/bin/env python3


'''
  A script for selecting target loops

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
import csv
import numpy as np
import json
import logging

from .sourcecode_metrics_for_survey_base import BF
from .classify_loops import classify

logger = logging.getLogger()

NSAMPLES = 0

TARGET_DIR_NAME = 'target'

#

BASE = 'survey-outline'

TARGET_DIR = os.path.join(BASE, TARGET_DIR_NAME)


def dump(ptbl, rtbl, filename_suffix='', target_dir=TARGET_DIR):
    for (proj, vtbl) in ptbl.items():
        pdir = os.path.join(target_dir, proj)

        if os.path.exists(pdir):
            if not os.path.isdir(pdir):
                logger.warning('not a directory: "%s"' % pdir)
                continue
        else:
            os.makedirs(pdir)

        print('* %s:' % pdir)

        for (ver, nids) in vtbl.items():
            path = os.path.join(pdir, ver+filename_suffix+'.json')

            print('  - %s: [%s]' % (path, ','.join(nids)))

            try:
                with open(path, 'w') as f:
                    f.write(json.dumps(nids))

            except Exception as e:
                logger.warning(str(e))
                continue

            root_file_l = list(rtbl.get(proj, {}).get(ver, []))
            if root_file_l:
                rpath = os.path.join(pdir, 'roots-%s.json' % ver)
                try:
                    with open(rpath, 'w') as rf:
                        rf.write(json.dumps(root_file_l))

                except Exception as e:
                    logger.warning(str(e))


def add_root_file(rtbl, proj, ver, root_file):
    try:
        vtbl0 = rtbl[proj]
    except KeyError:
        vtbl0 = {}
        rtbl[proj] = vtbl0

    try:
        root_files = vtbl0[ver]
    except KeyError:
        root_files = set()
        vtbl0[ver] = root_files

    root_files.add(root_file)


def add_nid(ptbl, proj, ver, nid):
    try:
        vtbl = ptbl[proj]
    except KeyError:
        vtbl = {}
        ptbl[proj] = vtbl

    try:
        nids = vtbl[ver]
    except KeyError:
        nids = []
        vtbl[ver] = nids

    nids.append(nid)


def predict_kernels(fname, clf_path, model='minami', filt={},
                    filename_suffix='', target_dir=TARGET_DIR):
    try:
        ptbl = {}  # proj -> ver -> nid list
        rtbl = {}  # proj -> ver -> root_file set

        data = classify(fname, clf_path, model=model, filt=filt, verbose=False)

        if data:
            count = 0

            for i in range(len(data.y)):
                c = data.y[i]
                if c == 'Kernel':
                    m = data.meta[i]
                    proj = m['proj']
                    ver = m['ver']
                    nid = m['nid']
                    root_file = m['root_file']

                    add_root_file(rtbl, proj, ver, root_file)
                    add_nid(ptbl, proj, ver, nid)

                    count += 1

            logger.info('predicted %d kernels' % count)

            dump(ptbl, rtbl, filename_suffix=filename_suffix,
                 target_dir=target_dir)

    except Exception as e:
        logger.error(str(e))


def sample(fname, nsamples,
           bf0_thresh_upper=None,
           bf1_thresh_upper=None,
           bf2_thresh_upper=None,
           bf0_thresh_lower=None,
           bf1_thresh_lower=None,
           bf2_thresh_lower=None,
           delim=',',
           filename_suffix=''):

    delim = delim.decode('string_escape')
    try:
        rows = []

        is_head = True

        head = None

        with open(fname, 'rb') as f:
            reader = csv.reader(f, delimiter=delim)
            for row in reader:
                if is_head:
                    head = row
                else:
                    rows.append(row)
                is_head = False

        logger.info('%d rows found' % len(rows))

        #

        projs = set()

        proj_i = head.index('proj')
        ver_i = head.index('ver')
        path_i = head.index('path')
        lnum_i = head.index('lnum')
        digest_i = head.index('digest')
        nid_i = head.index('nid')

        root_file_i = head.index('root_file')

        bf_i = [head.index(BF[lv]) for lv in range(3)]

        to_be_deleted = []

        bf_thresh_upper = [bf0_thresh_upper, bf1_thresh_upper, bf2_thresh_upper]
        bf_thresh_lower = [bf0_thresh_lower, bf1_thresh_lower, bf2_thresh_lower]

        for idx in range(len(rows)):
            row = rows[idx]
            projs.add(row[proj_i])

            del_flag = False

            for lv in range(3):
                if bf_thresh_upper[lv] is not None:
                    try:
                        if float(row[bf_i[lv]]) >= bf_thresh_upper[lv]:
                            del_flag = True

                    except Exception as e:
                        logger.warning(str(e))

                if bf_thresh_lower[lv] is not None:
                    try:
                        if float(row[bf_i[lv]]) <= bf_thresh_lower[lv]:
                            del_flag = True

                    except Exception as e:
                        logger.warning(str(e))

            if del_flag:
                to_be_deleted.append(idx)

        logger.info('%d projects found' % len(projs))

        to_be_deleted.reverse()

        for i in to_be_deleted:
            del rows[i]

        fmt = '%d rows deleted (bf_thresh: upper=%3.2f,%3.2f,%3.2f lower=%3.2f,%3.2f,%3.2f)'
        logger.warning(fmt % (len(to_be_deleted),
                              bf0_thresh_upper,
                              bf1_thresh_upper,
                              bf2_thresh_upper,
                              bf0_thresh_lower,
                              bf1_thresh_lower,
                              bf2_thresh_lower,
                              ))

        logger.info('%d rows' % len(rows))

        projs = set()
        for row in rows:
            projs.add(row[proj_i])

        logger.info('%d projects' % len(projs))

        #

        samples = []

        if 0 < nsamples < len(rows):

            np.random.seed()
            np.random.shuffle(rows)

            idxs = set()

            while True:
                idx = np.random.randint(1, len(rows))
                if idx not in idxs:
                    idxs.add(idx)
                    samples.append(rows[idx])
                    if len(idxs) == nsamples:
                        break

        else:
            samples = rows

        samples.sort(key=lambda x: x[15])

        logger.info('%d samples extracted' % len(samples))

        #

        ptbl = {}  # proj -> ver -> nid list
        rtbl = {}  # proj -> ver -> root_file set
        dtbl = {}  # digest -> (proj * ver * path * lnum) set

        for row in samples:
            proj = row[proj_i]
            ver = row[ver_i]
            path = row[path_i]
            lnum = row[lnum_i]
            nid = row[nid_i]
            digest = row[digest_i]
            root_file = row[root_file_i]

            add_root_file(rtbl, proj, ver, root_file)

            try:
                pvpls = dtbl[digest]
            except KeyError:
                pvpls = set()
                dtbl[digest] = pvpls

            pvpls.add((proj, ver, path, lnum))

            add_nid(ptbl, proj, ver, nid)

        for (d, pvpls) in dtbl.items():
            if len(pvpls) > 1:
                logger.warning('duplicate found: digest="%s"' % d)
                for pvpl in pvpls:
                    logger.warning('- %s:%s:%s:%s' % pvpl)

        dump(ptbl, rtbl, filename_suffix=filename_suffix)

    except Exception as e:
        logger.error(str(e))


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='sample target loops',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-n', '--nsamples', dest='nsamples', metavar='N',
                        type=int, default=NSAMPLES, help='number of samples')

    parser.add_argument('--bf0-thresh-upper', dest='bf0_thresh_upper',
                        metavar='R', type=float, default=float('inf'),
                        help='exclusive upper B/F threshold (lv=0)')

    parser.add_argument('--bf1-thresh-upper', dest='bf1_thresh_upper',
                        metavar='R', type=float, default=float('inf'),
                        help='exclusive upper B/F threshold (lv=1)')

    parser.add_argument('--bf2-thresh-upper', dest='bf2_thresh_upper',
                        metavar='R', type=float, default=float('inf'),
                        help='exclusive upper B/F threshold (lv=2)')

    parser.add_argument('--bf0-thresh-lower', dest='bf0_thresh_lower',
                        metavar='R', type=float, default=0.0,
                        help='exclusive lower B/F threshold (lv=0)')

    parser.add_argument('--bf1-thresh-lower', dest='bf1_thresh_lower',
                        metavar='R', type=float, default=-0.1,
                        help='exclusive lower B/F threshold (lv=1)')

    parser.add_argument('--bf2-thresh-lower', dest='bf2_thresh_lower',
                        metavar='R', type=float, default=-0.1,
                        help='exclusive lower B/F threshold (lv=2)')

    parser.add_argument('--delim', dest='delim', metavar='DELIMITER', type=str,
                        default=',', help='specify delimiter of CSV')

    parser.add_argument('-m', '--model', dest='model', metavar='MODEL',
                        type=str, default='minami',
                        help='model (minami|terai|mix)')

    parser.add_argument('-c', '--clf', dest='clf', metavar='PATH',
                        type=str, default=None, help='dumped classifier')

    parser.add_argument('-s', '--suffix', dest='suffix', metavar='SUFFIX',
                        type=str, default='',
                        help='specify suffix of output file')

    parser.add_argument('-o', '--out-dir', dest='outdir', metavar='DIR',
                        type=str, default=TARGET_DIR,
                        help='specify output directory')

    parser.add_argument('metrics_file', default='metrics.csv', nargs='?',
                        metavar='FILE', type=str, help='metrics file')

    args = parser.parse_args()

    if args.clf:
        filt = {
            'bf0': lambda x: x > args.bf0_thresh_lower and x < args.bf0_thresh_upper,
            'bf1': lambda x: x > args.bf1_thresh_lower and x < args.bf1_thresh_upper,
            'bf2': lambda x: x > args.bf2_thresh_lower and x < args.bf2_thresh_upper,
        }
        logger.info('predicting kernels...')
        predict_kernels(args.metrics_file,
                        args.clf,
                        model=args.model,
                        filt=filt,
                        filename_suffix=args.suffix,
                        target_dir=args.outdir)

    else:
        logger.info('sampling target loops...')
        sample(args.metrics_file,
               args.nsamples,
               bf0_thresh_upper=args.bf0_thresh_upper,
               bf1_thresh_upper=args.bf1_thresh_upper,
               bf2_thresh_upper=args.bf2_thresh_upper,
               bf0_thresh_lower=args.bf0_thresh_lower,
               bf1_thresh_lower=args.bf1_thresh_lower,
               bf2_thresh_lower=args.bf2_thresh_lower,
               delim=args.delim,
               filename_suffix=args.suffix)
