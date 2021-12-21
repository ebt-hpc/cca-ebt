#!/usr/bin/env python3


'''
  A script for EBT fact materialization

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

import os.path

from cca.ccautil.materialize_fact import Materializer
from .common import VIRTUOSO_PORT
from .conf import QUERIES_DIR

QUERY_DIR = os.path.join(QUERIES_DIR, 'tuning')

QUERIES = {
    'fortran': [
        'materialize_expr_sig_in_loop.rq',
        'materialize_program_unit_in_srctree.rq',
        'materialize_module_ref.rq',
        'materialize_transitive_provide.rq',
        'materialize_reference.rq',
        'materialize_symbol_resolution.rq',
        'materialize_logical_unit_fj.rq',
        'materialize_logical_unit_tc.rq',
        'materialize_loop_ctl.rq',
        'materialize_stride.rq',
        'materialize_stmt_in_loop.rq',
        'materialize_loop_in_loop.rq',
        'materialize_array_ref_sig0.rq',
        'materialize_array_ref_sig1.rq',
        'materialize_array_ref_sig2_0.rq',
        'materialize_array_ref_sig2_1.rq',
        'materialize_type_spec.rq',
        'materialize_compo_type_spec.rq',
        'materialize_included_module_subprogram.rq',
        'materialize_macro_type_spec.rq',
        'materialize_c_func_req.rq',
        'materialize_callee.rq',
    ],
    'cpp': [
        'materialize_expr_sig_in_loop.rq',
        'materialize_translation_unit_in_srctree.rq',
        'materialize_reference.rq',
        'materialize_symbol_resolution.rq',
        'materialize_stmt_in_loop.rq',
        'materialize_loop_in_loop.rq',
        'materialize_array_ref_sig0.rq',
        'materialize_array_ref_sig1_0.rq',
        'materialize_array_ref_sig1_1.rq',
        'materialize_array_ref_sig2_0.rq',
        'materialize_array_ref_sig2_1.rq',
        'materialize_type_spec.rq',
        'materialize_type_spec_memb.rq',
        'materialize_callee.rq',
        'materialize_call.rq',
    ],
}


def materialize(proj_id, pw=None, port=VIRTUOSO_PORT):
    m = Materializer(QUERY_DIR, QUERIES, proj_id, pw=pw, port=port)
    rc = m.materialize()
    return rc


if __name__ == '__main__':
    pass
