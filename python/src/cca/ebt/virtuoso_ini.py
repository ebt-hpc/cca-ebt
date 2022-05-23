#!/usr/bin/env python3


'''
  A script for creating Virtuoso configurations

  Copyright 2013-2017 RIKEN
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


from .common import VIRTUOSO_PORT

DEFAULT_BUFSIZES = (340000, 250000)

BUFSIZE_TBL = {
    2:  (170000, 130000),
    4:  (340000, 250000),
    8:  (680000, 500000),
    16: (1360000, 1000000),
    32: (2720000, 2000000),
    48: (4000000, 3000000),
    64: (5450000, 4000000),
}

INI_FMT = '''
[Database]
DatabaseFile                    = %(db_root)s/virtuoso.db
ErrorLogFile                    = %(db_root)s/virtuoso.log
LockFile                        = %(db_root)s/virtuoso.lck
TransactionFile                 = %(db_root)s/virtuoso.trx
xa_persistent_file              = %(db_root)s/virtuoso.pxa
ErrorLogLevel                   = 7
FileExtend                      = 200
MaxCheckpointRemap              = 2000
Striping                        = 0
TempStorage                     = TempDatabase

[TempDatabase]
DatabaseFile                    = %(db_root)s/virtuoso-temp.db
TransactionFile                 = %(db_root)s/virtuoso-temp.trx
MaxCheckpointRemap              = 2000
Striping                        = 0

[Flags]
tn_max_memory                   = 2000000000

[Parameters]
ServerPort                      = %(port)d
LiteMode                        = 0
DisableUnixSocket               = 1
DisableTcpSocket                = 0
MaxClientConnections            = 10
CheckpointInterval              = -1
O_DIRECT                        = 0
CaseMode                        = 2
MaxStaticCursorRows             = 5000
CheckpointAuditTrail            = 0
AllowOSCalls                    = 0
SchedulerInterval               = 10
DirsAllowed                     = ., /opt/virtuoso/vad, %(fact_root)s, %(ont_root)s
ThreadCleanupInterval           = 0
ThreadThreshold                 = 10
ResourcesCleanupInterval        = 0
FreeTextBatchSize               = 100000
SingleCPU                       = 0
VADInstallDir                   = /opt/virtuoso/vad/
PrefixResultNames               = 0
RdfFreeTextRulesSize            = 100
IndexTreeMaps                   = 256
MaxMemPoolSize                  = 5000000000
TransactionAfterImageLimit      = 16000000000
PrefixResultNames               = 0
MacSpotlight                    = 0
IndexTreeMaps                   = 64
MaxQueryMem                     = 3G
VectorSize                      = 1000
MaxVectorSize                   = 1000000
AdjustVectorSize                = 0
ThreadsPerQuery                 = 4
AsyncQueueMaxThreads            = 10

NumberOfBuffers = %(nbufs)d
MaxDirtyBuffers = %(mdbufs)d

[HTTPServer]
;ServerPort                      = 8890
;ServerRoot                      = /opt/virtuoso/vsp
;MaxClientConnections            = 10
MaxClientConnections            = 0
;DavRoot                         = DAV
EnabledDavVSP                   = 0
HTTPProxyEnabled                = 0
TempASPXDir                     = 0
;DefaultMailServer               = localhost:25
;ServerThreads                   = 10
;MaxKeepAlives                   = 10
;KeepAliveTimeout                = 10
;MaxCachedProxyConnections       = 10
;ProxyConnectionCacheTimeout     = 15
;HTTPThreadSize                  = 280000
HttpPrintWarningsInOutput       = 0
Charset                         = UTF-8
;MaintenancePage                 = atomic.html
;EnabledGzipContent              = 1

[AutoRepair]
BadParentLinks                  = 0

[Client]
SQL_PREFETCH_ROWS               = 100
SQL_PREFETCH_BYTES              = 16000
SQL_QUERY_TIMEOUT               = 0
SQL_TXN_TIMEOUT                 = 0

[VDB]
ArrayOptimization               = 0
NumArrayParameters              = 10
VDBDisconnectTimeout            = 1000
KeepConnectionOnFixedThread     = 0

[Replication]
ServerName                      = db-EBT
ServerEnable                    = 1
QueueMax                        = 50000

[Zero Config]
ServerName                      = virtuoso (EBT)

[URIQA]
DynamicLocal                    = 0
DefaultHost                     = localhost:8890

[SPARQL]
ResultSetMaxRows                = 1000000
MaxQueryCostEstimationTime      = 400
MaxQueryExecutionTime           = 60
DefaultQuery                    = select distinct ?Concept where {[] a ?Concept} LIMIT 100
DeferInferenceRulesInit         = 0
'''


def gen_ini(db_root, fact_root, ont_root, outfile, mem=4, port=VIRTUOSO_PORT):
    nbufs, mdbufs = BUFSIZE_TBL.get(mem, DEFAULT_BUFSIZES)
    ini = INI_FMT % {'db_root':   db_root,
                     'port':      port,
                     'fact_root': fact_root,
                     'ont_root':  ont_root,
                     'nbufs':     nbufs,
                     'mdbufs':    mdbufs
                     }

    with open(outfile, 'w') as f:
        f.write(ini)
