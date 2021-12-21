#!/usr/bin/env python3

import os

CCA_HOME = os.getenv('CCA_HOME', '/opt/cca')
VAR_DIR = os.getenv('CCA_VAR_DIR', '/var/lib/cca')

VIRTUOSO_PW = 'ebt'
VIRTUOSO_PORT = 1111

OUTDIR_NAME = '_EBT_'

#

ONT_DIR = os.path.join(CCA_HOME, 'ontologies')
FB_DIR = os.path.join(VAR_DIR, 'db')
FACT_DIR = os.path.join(VAR_DIR, 'fact')
WORK_DIR = os.path.join(VAR_DIR, 'work')
QUERIES_DIR = os.path.join(CCA_HOME, 'queries')
