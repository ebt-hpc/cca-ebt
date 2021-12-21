#!/usr/bin/env python3


'''
  Counting operations in Fortran programs

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
import logging

from .common import AnalyzerBase, create_argparser
from .outline_for_flops import Outline as OutlineForFlops
from cca.ccautil.common import setup_logger

logger = logging.getLogger()


class Analyzer(AnalyzerBase):
    def analyze_facts(self, proj_dir, proj_id, ver, dest_root, lang='fortran'):
        ol = OutlineForFlops(proj_id,
                             method='odbc',
                             pw=self._pw,
                             port=self._port,
                             proj_dir=os.path.dirname(proj_dir),
                             ver=ver,
                             simple_layout=True)

        ol.gen_data(lang, outdir=dest_root, keep_rev=True)


def main():
    parser = create_argparser('Count ops in Fortran programs')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    setup_logger(logger, log_level)

    a = Analyzer(mem=args.mem, pw=args.pw, port=args.port)

    a.analyze_dir(args.proj_dir, proj_id=args.proj, ver=args.ver)


if __name__ == '__main__':
    pass
