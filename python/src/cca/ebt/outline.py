#!/usr/bin/env python3

'''
  Outlining C/C++/Fortran programs

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

from .common import VIRTUOSO_PORT
from .common import log, cca_path, create_argparser, AnalyzerBase
from .outline_for_survey_cpp import Outline as OutlineForSurveyCpp
from .outline_for_survey_fortran import Outline as OutlineForSurveyFortran
from .outline_for_survey_base import gen_conf_a, METRICS_DIR
from .select_targets import predict_kernels, TARGET_DIR_NAME
from .collect_readme_for_survey import collect_readme
from cca.ccautil.common import setup_logger

logger = logging.getLogger()

MODEL = 'minami'

BF0L, BF0U = 0.0, float('inf')
BF1L, BF1U = -0.1, float('inf')
BF2L, BF2U = -0.1, float('inf')

OUTLINE_TBL = {
    'cpp':     OutlineForSurveyCpp,
    'fortran': OutlineForSurveyFortran,
}

OMIT_TBL = {
    'cpp':     set(['compound-statement', ]),
    'fortran': set(['execution-part', 'do-block']),
}


class Analyzer(AnalyzerBase):

    def __init__(self, mem=4, pw=None, port=VIRTUOSO_PORT,
                 all_roots=False, all_sps=False):
        super().__init__(mem=mem, pw=pw, port=port)
        self._all_roots = all_roots
        self._all_sps = all_sps

    def analyze_facts(self, proj_dir, proj_id, ver, dest_root,
                      bf0l=BF0L, bf0u=BF0U,
                      bf1l=BF1L, bf1u=BF1U,
                      bf2l=BF2L, bf2u=BF2U,
                      langs=['cpp', 'fortran']):

        proj_parent_dir = os.path.dirname(os.path.abspath(proj_dir))
        index = cca_path(os.path.join('lsi', 'survey-lsi-160.index'))

        conf = gen_conf_a(proj_id, ver, proj_dir)

        for lang in langs:
            logger.info('outlining {} source code...'.format(lang))
            ol = OUTLINE_TBL[lang](proj_id,
                                   method='odbc',
                                   pw=self._pw,
                                   port=self._port,
                                   proj_dir=proj_parent_dir,
                                   ver=ver,
                                   simple_layout=True,
                                   all_sps=self._all_sps,
                                   conf=conf)

            ol.gen_data(lang, dest_root, omitted=OMIT_TBL[lang],
                        all_roots=self._all_roots)

            logging.info('generating topic data for "{}"...'.format(lang))
            ol.gen_topic(lang,
                         outdir=dest_root,
                         docsrc=proj_parent_dir,
                         index=index,
                         model='lsi',
                         ntopics=160)

        log('predicting kernels...')
        filt = {
            'bf0': lambda x: bf0l < x < bf0u,
            'bf1': lambda x: bf1l < x < bf1u,
            'bf2': lambda x: bf2l < x < bf2u,
        }
        metrics_file = os.path.join(dest_root, METRICS_DIR, proj_id,
                                    ol.gen_metrics_file_name(ver, lang))
        target_dir = os.path.join(dest_root, TARGET_DIR_NAME)
        clf = cca_path(os.path.join('models', MODEL, 'm.pkl'))
        predict_kernels(metrics_file, clf, model=MODEL, filt=filt,
                        target_dir=target_dir)

        collect_readme(proj_id, dest_root, conf=conf)


def main():
    parser = create_argparser('Analyze C/C++/Fortran programs for outlining')

    parser.add_argument('-a', '--all-roots', dest='all_roots',
                        action='store_true',
                        help='allow subprograms to be shown as root nodes')

    parser.add_argument('-s', '--all-sps', dest='all_sps', action='store_true',
                        help='allow loop-free subprograms to be shown')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    setup_logger(logger, log_level)

    from . import common, outline_for_survey_base
    from . import outline_for_survey_fortran, outline_for_survey_cpp
    common.logger = logger
    outline_for_survey_base.logger = logger
    outline_for_survey_fortran.logger = logger
    outline_for_survey_cpp.logger = logger

    import cca.ccautil.materialize_fact
    cca.ccautil.materialize_fact.logger = logger

    a = Analyzer(mem=args.mem, pw=args.pw, port=args.port,
                 all_roots=args.all_roots, all_sps=args.all_sps)

    langs = []
    if not args.ignore_cpp:
        langs.append('cpp')
    if not args.ignore_fortran:
        langs.append('fortran')

    a.analyze_dir(args.proj_dir, proj_id=args.proj, ver=args.ver,
                  keep_fb=args.keep_fb, langs=langs,
                  # skip_build=True, skip_materialize=True, skip_outline=False,
                  cleanup=True)


if __name__ == '__main__':
    pass
