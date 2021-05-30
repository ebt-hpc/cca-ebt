#!/usr/bin/env python3

'''
  A script for outlining C programs

  Copyright 2013-2018 RIKEN
  Copyright 2017-2020 Chiba Institute of Technology

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


from .common import NS_TBL


OMITTED = []

SUBPROGS = set([
    'function-definition',
])

LOOPS = set(['for-statement','range-based-for-statement','do-statement','while-statement'])

CALLS = set(['fun-call','fun-call-guarded','fun-call*','mpi-call','omp-call'])

TYPE_TBL = { # cat -> type
    'file'                           : 'file',

    'for-statement'                  : 'loop',
    'range-based-for-statement'      : 'loop',
    'do-statement'                   : 'loop',
    'while-statement'                : 'loop',

    'if-statement'                   : 'branch',
    'else-statement'                 : 'branch',
    'switch-statement'               : 'branch',

    'fun-call'                       : 'call',
    'fun-call-guarded'               : 'call',

    'function-definition'            : 'function',

    'compound-statement'             : 'block',
    'function-body'                  : 'block',
    'function-try-block'             : 'block',

    'pp-group'                       : 'pp',
    'pp-if-group'                    : 'pp',
    'pp-elif-group'                  : 'pp',
    'pp-else-group'                  : 'pp',

    'pp-if-section'                  : 'pp',
    'pp-if-section-broken'           : 'pp',
    'pp-if-section-broken-dtor-func' : 'pp',
    'pp-if-section-broken-func-def'  : 'pp',
    'pp-if-section-broken-if'        : 'pp',
    'pp-if-section-cond-expr'        : 'pp',
    'pp-if-section-func-def'         : 'pp',
    'pp-if-section-handler'          : 'pp',
    'pp-if-section-templ-decl'       : 'pp',
    'pp-if-section-try-block'        : 'pp',

    'pp-pragma'                      : 'pp',

    'mpi-call'                       : 'mpi',
    'omp-call'                       : 'omp',

    'fun-call*'                      : 'call*'
}


Q_AA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?loop ?aa ?pe ?loop_cat
WHERE {
GRAPH <%%(proj)s> {

  ?pe a cpp:PostfixExpression .

  ?aa a cpp:PostfixExpressionSubscr ;
      src:child0 ?pe ;
      cpp:inIterationStatement ?loop .

  ?loop a cpp:IterationStatement ;
        a ?loop_cat0 OPTION (INFERENCE NONE) ;
        cpp:inTranslationUnit ?tu .

  GRAPH <http://codinuum.com/ont/cpi> {
    ?loop_cat0 rdfs:label ?loop_cat
  }

  ?tu a cpp:TranslationUnit ;
      ver:version ?ver ;
      src:inFile/src:location ?loc .

  OPTIONAL {
    ?pe cpp:declarator ?dtor .

    ?dtor a cpp:Declarator ;
          cpp:inTranslationUnit/src:inFile ?dtor_file .

    ?dtor_file a src:File ;
               src:location ?dtor_loc ;
               ver:version ?ver .
  }

}
}
''' % NS_TBL

Q_OTHER_CALLS_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fd_cat ?fn ?call ?callee_name ?cntnr
WHERE {
GRAPH <%%(proj)s> {

  ?call a ?call_cat OPTION (INFERENCE NONE) ;
        src:child0/cpp:requires/cpp:name ?callee_name ;
        cpp:inTranslationUnit ?tu .

  FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                        cpp:PostfixExpressionFunCallGuarded
                        ))

  ?tu a cpp:TranslationUnit ;
      ver:version ?ver ;
      src:inFile/src:location ?loc .

  FILTER NOT EXISTS {
    ?call cpp:mayCall ?callee .
  }

  OPTIONAL {
    ?call cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        a ?fd_cat0 OPTION (INFERENCE NONE) ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .

    FILTER NOT EXISTS {
      ?call cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?fd_cat0 rdfs:label ?fd_cat
    }
  }

  OPTIONAL {
    ?call cpp:inContainerUnit ?cntnr .
    ?cntnr a cpp:ContainerUnit .
    FILTER EXISTS {
      {
        ?cntnr cpp:inTranslationUnit ?tu .
        FILTER NOT EXISTS {
          ?call cpp:inFunctionDefinition/cpp:inContainerUnit ?cntnr .
        }
      }
      UNION
      {
        ?call cpp:inFunctionDefinition ?fd0 .
        ?cntnr cpp:inFunctionDefinition ?fd0 .
      }
    }
    FILTER NOT EXISTS {
      ?c a cpp:ContainerUnit ;
         cpp:inContainerUnit ?cntnr .
      ?call cpp:inContainerUnit ?c .
      FILTER (?c != ?cntnr)
    }
  }

}
}
''' % NS_TBL

Q_DIRECTIVES_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fd_cat ?fn ?dtv ?cat ?cntnr
WHERE {
GRAPH <%%(proj)s> {

  ?dtv a cpp:PpDirective ;
       a ?cat0 OPTION (INFERENCE NONE) ;
       cpp:inTranslationUnitOrFunction ?tu_or_fd ;
       cpp:inTranslationUnit ?tu .

  ?tu_or_fd src:inFile/src:location ?loc .

  ?tu a cpp:TranslationUnit ;
      src:inFile/src:location ?tu_loc ;
      ver:version ?ver .

  GRAPH <http://codinuum.com/ont/cpi> {
    ?cat0 rdfs:label ?cat .
  }

  OPTIONAL {
    ?dtv cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
          a ?fd_cat0 OPTION (INFERENCE NONE) ;
          cpp:provides/(cpp:name|cpp:regexp) ?fn .

    FILTER NOT EXISTS {
      ?dtv cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?fd_cat0 rdfs:label ?fd_cat
    }
  }

  OPTIONAL {
    ?dtv cpp:inContainerUnit ?cntnr .
    ?cntnr a cpp:ContainerUnit .
    FILTER EXISTS {
      {
        ?cntnr cpp:inTranslationUnit ?tu .
        FILTER NOT EXISTS {
          ?dtv cpp:inFunctionDefinition/cpp:inContainerUnit ?cntnr .
        }
      }
      UNION
      {
        ?dtv cpp:inFunctionDefinition ?fd0 .
        ?cntnr cpp:inFunctionDefinition ?fd0 .
      }
    }
    FILTER NOT EXISTS {
      ?c a cpp:ContainerUnit ;
         cpp:inContainerUnit ?cntnr .
      ?dtv cpp:inContainerUnit ?c .
      FILTER (?c != ?cntnr)
    }
  }

}
}
''' % NS_TBL

Q_CNTNR_CNTNR_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fd_cat ?fn ?cntnr ?cat ?parent_cntnr ?parent_cat ?parent_fn
WHERE {
GRAPH <%%(proj)s> {

  ?cntnr a cpp:ContainerUnit ;
             cpp:inTranslationUnitOrFunction ?tu_or_fd ;
             cpp:inTranslationUnit ?tu .

  ?tu_or_fd cpp:inTranslationUnit*/src:inFile/src:location ?loc .

  ?tu a cpp:TranslationUnit ;
      src:inFile/src:location ?tu_loc ;
      ver:version ?ver .

  FILTER EXISTS {
    ?cntnr cpp:inFunctionDefinition [] .
  }

  OPTIONAL {
    SELECT DISTINCT ?cntnr (GROUP_CONCAT(DISTINCT ?c; SEPARATOR="&") AS ?cat)
    WHERE {
      ?cntnr a ?cat0 OPTION (INFERENCE NONE) .

      GRAPH <http://codinuum.com/ont/cpi> {
        ?cat0 rdfs:label ?c .
      }
    } GROUP BY ?cntnr
  }

  OPTIONAL {
    ?cntnr cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        a ?fd_cat0 OPTION (INFERENCE NONE) ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .

    FILTER NOT EXISTS {
      ?cntnr cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?fd_cat0 rdfs:label ?fd_cat .
    }
  }

  OPTIONAL {
    ?cntnr cpp:inContainerUnit ?parent_cntnr .
    ?parent_cntnr a cpp:ContainerUnit .

    FILTER (?cntnr != ?parent_cntnr)

    FILTER NOT EXISTS {
      ?cntnr cpp:inContainerUnit ?p0 .
      ?p0 a cpp:ContainerUnit ;
          cpp:inContainerUnit ?parent_cntnr .
      FILTER (?p0 != ?cntnr && ?p0 != ?parent_cntnr)
    }

    FILTER NOT EXISTS {
      ?cntnr cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inContainerUnit ?parent_cntnr .
      FILTER (?fd0 != ?cntnr && ?fd0 != ?parent_cntnr)
    }

    {
      SELECT DISTINCT ?parent_cntnr (GROUP_CONCAT(DISTINCT ?c0; SEPARATOR="&") AS ?parent_cat)
      WHERE {
        ?parent_cntnr a ?parent_cat0 OPTION (INFERENCE NONE) .

        GRAPH <http://codinuum.com/ont/cpi> {
          ?parent_cat0 rdfs:label ?c0 .
        }
      } GROUP BY ?parent_cntnr
    }

    OPTIONAL {
      ?parent_cntnr cpp:inTranslationUnit ?parent_tu .
    }

    OPTIONAL {
      ?parent_cntnr cpp:inFunctionDefinition ?parent_fd .
      ?parent_fd a cpp:FunctionDefinition ;
                 cpp:provides/(cpp:name|cpp:regexp) ?parent_fn .

      FILTER NOT EXISTS {
        ?parent_cntnr cpp:inFunctionDefinition ?fd0 .
        ?fd0 cpp:inFunctionDefinition ?parent_fd .
        FILTER (?parent_fd != ?fd0)
      }
    }
  }

}
}
''' % NS_TBL

Q_CNTNR_FD_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fd_cat ?fn ?cntnr ?cat ?call ?call_cat
?callee ?callee_name ?callee_loc ?callee_cat
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?cntnr ?callee ?cat ?call ?call_cat
    WHERE {

      ?call a ?call_cat0 OPTION (INFERENCE NONE) ;
            cpp:inContainerUnit ?cntnr ;
            cpp:mayCall ?callee .

      FILTER (?call_cat0 IN (cpp:PostfixExpressionFunCall,
                             cpp:PostfixExpressionFunCallGuarded
                             ))

      ?cntnr a cpp:ContainerUnit ;
             a ?cat0 OPTION (INFERENCE NONE) ;
             cpp:inTranslationUnitOrFunction ?tu_or_fd ;
             cpp:inTranslationUnit ?tu .

      ?tu_or_fd cpp:inTranslationUnit*/src:inFile/src:location ?loc .

      FILTER NOT EXISTS {
        ?c a cpp:ContainerUnit ;
           cpp:inContainerUnit+ ?cntnr .
        ?call cpp:inContainerUnit+ ?c .
        FILTER (?c != ?cntnr)
      }

      ?tu a cpp:TranslationUnit ;
          ver:version ?ver ;
          src:inFile/src:location ?tu_loc .

      GRAPH <http://codinuum.com/ont/cpi> {
        ?cat0 rdfs:label ?cat .
        ?call_cat0 rdfs:label ?call_cat .
      }

    } GROUP BY ?ver ?loc ?cntnr ?callee ?cat ?call ?call_cat
  }

  {
    SELECT DISTINCT ?callee ?callee_cat ?callee_loc ?ver
    (GROUP_CONCAT(DISTINCT ?fn; SEPARATOR=":") AS ?callee_name)
    WHERE {

      ?callee a cpp:FunctionDefinition ;
              a ?callee_cat0 OPTION (INFERENCE NONE) ;
              cpp:provides/(cpp:name|cpp:regexp) ?fn ;
              cpp:inTranslationUnit/src:inFile ?callee_file .

      ?callee_file a src:File ;
                   src:location ?callee_loc ;
                   ver:version ?ver .
      
      GRAPH <http://codinuum.com/ont/cpi> {
        ?callee_cat0 rdfs:label ?callee_cat
      }

    } GROUP BY ?callee ?callee_cat ?callee_loc ?ver
  }

  OPTIONAL {
    ?cntnr cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        a ?fd_cat0 OPTION (INFERENCE NONE) ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .

    FILTER NOT EXISTS {
      ?cntnr cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?fd_cat0 rdfs:label ?fd_cat
    }
  }

}
}
''' % NS_TBL

Q_FD_FD_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fd_cat ?fn ?callee ?callee_name ?callee_loc ?callee_cat ?call ?call_cat ?cntnr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?tu ?callee ?call ?call_cat ?cntnr
    WHERE {

      ?call a ?call_cat0 OPTION (INFERENCE NONE) ;
            cpp:inTranslationUnitOrFunction ?tu_or_fd ;
            cpp:inTranslationUnit ?tu ;
            cpp:mayCall ?callee .

      ?tu_or_fd cpp:inTranslationUnit*/src:inFile/src:location ?loc .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?tu_loc ;
          ver:version ?ver .

      FILTER (?call_cat0 IN (cpp:PostfixExpressionFunCall,
                             cpp:PostfixExpressionFunCallGuarded
                             ))

      GRAPH <http://codinuum.com/ont/cpi> {
        ?call_cat0 rdfs:label ?call_cat .
      }

      OPTIONAL {
        ?call cpp:inContainerUnit ?cntnr .
      }

    } GROUP BY ?ver ?loc ?tu ?callee ?call ?call_cat ?cntnr
  }

  {
    SELECT DISTINCT ?callee ?callee_cat ?callee_loc ?ver
    (GROUP_CONCAT(DISTINCT ?fn; SEPARATOR=":") AS ?callee_name)
    WHERE {

      ?callee a cpp:FunctionDefinition ;
              a ?callee_cat0 OPTION (INFERENCE NONE) ;
              cpp:provides/(cpp:name|cpp:regexp) ?fn ;
              cpp:inTranslationUnit/src:inFile ?callee_file .

      ?callee_file a src:File ;
                   src:location ?callee_loc ;
                   ver:version ?ver .
      
      GRAPH <http://codinuum.com/ont/cpi> {
        ?callee_cat0 rdfs:label ?callee_cat
      }

    } GROUP BY ?callee ?callee_cat ?callee_loc ?ver
  }

  OPTIONAL {
    ?call cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
          a ?fd_cat0 OPTION (INFERENCE NONE) ;
          cpp:provides/(cpp:name|cpp:regexp) ?fn .

    FILTER NOT EXISTS {
      ?call cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?fd_cat0 rdfs:label ?fd_cat
    }
  }

}
}
''' % NS_TBL


QUERY_TBL = {
    'aa_in_loop'  : Q_AA_IN_LOOP_C,
    'other_calls' : Q_OTHER_CALLS_C,
    'directives'  : Q_DIRECTIVES_C,
    'cntnr_cntnr' : Q_CNTNR_CNTNR_C,
    'cntnr_fd'    : Q_CNTNR_FD_C,
    'fd_fd'       : Q_FD_FD_C,
}

def get_root_entities(full=False):
    s = set(['function-definition'])
    if full:
        s |= set([
            #
        ])
    return s
