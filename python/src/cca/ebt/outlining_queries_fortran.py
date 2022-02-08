#!/usr/bin/env python3

'''
  A script for outlining Fortran programs

  Copyright 2013-2018 RIKEN
  Copyright 2018-2019 Chiba Institute of Technology

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


OMITTED = ['execution-part', 'do-block']

SUBPROGS = set([
    'subroutine-external-subprogram',
    'subroutine-internal-subprogram',
    'subroutine-module-subprogram',
    'function-external-subprogram',
    'function-internal-subprogram',
    'function-module-subprogram',
])

LOOPS = set(['do-construct', 'do-stmt', 'end-do-stmt', 'do-block'])

GOTOS = set(['goto-stmt', 'computed-goto-stmt', 'assigned-goto-stmt'])

CALLS = set(['call-stmt', 'function-reference', 'part-name', 'call-stmt*',
             'mpi-call'])

TYPE_TBL = {  # cat -> type
    'file': 'file',

    'do-construct':          'loop',
    'if-construct':          'branch',
    'case-construct':        'branch',
    'select-type-construct': 'branch',
    'where-construct':       'branch',

    'call-stmt':          'call',
    'function-reference': 'call',
    'part-name':          'call',

    'goto-stmt':          'goto',
    'assigned-goto-stmt': 'goto',
    'computed-goto-stmt': 'goto',

    'main-program':                   'main',
    'subroutine-external-subprogram': 'subroutine',
    'subroutine-internal-subprogram': 'subroutine',
    'subroutine-module-subprogram':   'subroutine',
    'function-external-subprogram':   'function',
    'function-internal-subprogram':   'function',
    'function-module-subprogram':     'function',

    'execution-part': 'part',

    'if-then-block':    'block',
    'else-if-block':    'block',
    'else-block':       'block',
    'case-block':       'block',
    'type-guard-block': 'block',
    'where-block':      'block',
    'do-block':         'block',
    'block-construct':  'block',

    'pp-branch':                'pp',
    'pp-branch-do':             'pp',
    'pp-branch-end-do':         'pp',
    'pp-branch-if':             'pp',
    'pp-branch-end-if':         'pp',
    'pp-branch-forall':         'pp',
    'pp-branch-end-forall':     'pp',
    'pp-branch-select':         'pp',
    'pp-branch-end-select':     'pp',
    'pp-branch-where':          'pp',
    'pp-branch-end-where':      'pp',
    'pp-branch-pu':             'pp',
    'pp-branch-end-pu':         'pp',
    'pp-branch-function':       'pp',
    'pp-branch-end-function':   'pp',
    'pp-branch-subroutine':     'pp',
    'pp-branch-end-subroutine': 'pp',
    'pp-section-elif':          'pp',
    'pp-section-else':          'pp',
    'pp-section-if':            'pp',
    'pp-section-ifdef':         'pp',
    'pp-section-ifndef':        'pp',

    'mpi-call': 'mpi',

    'call-stmt*': 'call*'
}
Q_AA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?loop ?aa ?pn ?dtor ?dtor_loc
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?pn ?aa ?loop ?pu_name ?vpu_name ?loc ?ver
    WHERE {

      ?pn a f:PartName ;
          src:parent ?aa .

      ?aa a f:ArrayAccess ;
          f:inDoConstruct ?loop .

      ?loop a f:DoConstruct ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

    } GROUP BY ?pn ?aa ?loop ?pu_name ?vpu_name ?loc ?ver
  }

  OPTIONAL {
    ?pn f:declarator ?dtor .

    ?dtor a f:Declarator ;
          f:inProgramUnitOrFragment/src:inFile ?dtor_file .

    ?dtor_file a src:File ;
               src:location ?dtor_loc ;
               ver:version ?ver .
  }

}
}
''' % NS_TBL

Q_OTHER_CALLS_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog ?call ?callee_name ?constr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu ?pu_name ?vpu_name ?call ?callee_name
    WHERE {

      ?call a f:CallStmt ;
            f:name ?callee_name ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      FILTER NOT EXISTS {
        ?call f:mayCall ?callee .
      }

    } GROUP BY ?ver ?loc ?pu ?pu_name ?vpu_name ?call ?callee_name
  }

  OPTIONAL {
    ?call f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?call f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat
    }
  }

  OPTIONAL {
    ?call f:inContainerUnit ?constr .
    ?constr a f:ContainerUnit .
    FILTER EXISTS {
      {
        ?constr f:inProgramUnit ?pu .
        FILTER NOT EXISTS {
          ?call f:inSubprogram/f:inContainerUnit ?constr .
        }
      }
      UNION
      {
        ?call f:inSubprogram ?sp0 .
        ?constr f:inSubprogram ?sp0 .
      }
    }
    FILTER NOT EXISTS {
      ?c a f:ContainerUnit ;
         f:inContainerUnit ?constr .
      ?call f:inContainerUnit ?c .
      FILTER (?c != ?constr)
    }
  }

  OPTIONAL {
    ?call f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

}
}
''' % NS_TBL

Q_GOTOS_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog ?goto ?goto_cat ?label ?constr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu ?pu_name ?vpu_name ?goto ?label ?goto_cat
    WHERE {

      ?goto a f:ActionStmt ;
            a ?goto_cat0 OPTION (INFERENCE NONE) ;
            # f:inDoConstruct [] ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      FILTER (?goto_cat0 IN (f:GotoStmt, f:AssignedGotoStmt, f:ComputedGotoStmt))

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      OPTIONAL {
        ?goto src:children/rdf:first ?x .
        ?x a f:Label ;
           f:label ?label .
      }

      GRAPH <http://codinuum.com/ont/cpi> {
        ?goto_cat0 rdfs:label ?goto_cat
      }

    } GROUP BY ?ver ?loc ?pu ?pu_name ?vpu_name ?goto ?label ?goto_cat
  }

  OPTIONAL {
    ?goto f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?goto f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat
    }
  }

  OPTIONAL {
    ?goto f:inContainerUnit ?constr .
    ?constr a f:ContainerUnit .
    FILTER EXISTS {
      {
        ?constr f:inProgramUnit ?pu .
        FILTER NOT EXISTS {
          ?goto f:inSubprogram/f:inContainerUnit ?constr .
        }
      }
      UNION
      {
        ?goto f:inSubprogram ?sp0 .
        ?constr f:inSubprogram ?sp0 .
      }
    }
    FILTER NOT EXISTS {
      ?c a f:ContainerUnit ;
         f:inContainerUnit ?constr .
      ?goto f:inContainerUnit ?c .
      FILTER (?c != ?constr)
    }
  }

  OPTIONAL {
    ?goto f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

}
}
''' % NS_TBL

Q_DIRECTIVES_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog ?dtv ?cat ?constr
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu ?pu_name ?vpu_name ?dtv ?cat
    WHERE {

      ?dtv a f:CompilerDirective ;
           a ?cat0 OPTION (INFERENCE NONE) ;
           f:inProgramUnitOrSubprogram ?pu_or_sp ;
           f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      GRAPH <http://codinuum.com/ont/cpi> {
        ?cat0 rdfs:label ?cat .
      }

    } GROUP BY ?ver ?loc ?pu ?pu_name ?vpu_name ?dtv ?cat
  }

  OPTIONAL {
    ?dtv f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?dtv f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat
    }
  }

  OPTIONAL {
    ?dtv f:inContainerUnit ?constr .
    ?constr a f:ContainerUnit .
    FILTER EXISTS {
      {
        ?constr f:inProgramUnit ?pu .
        FILTER NOT EXISTS {
          ?dtv f:inSubprogram/f:inContainerUnit ?constr .
        }
      }
      UNION
      {
        ?dtv f:inSubprogram ?sp0 .
        ?constr f:inSubprogram ?sp0 .
      }
    }
    FILTER NOT EXISTS {
      ?c a f:ContainerUnit ;
         f:inContainerUnit ?constr .
      ?dtv f:inContainerUnit ?c .
      FILTER (?c != ?constr)
    }
  }

  OPTIONAL {
    ?dtv f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

}
}
''' % NS_TBL

Q_CONSTR_CONSTR_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog
?constr ?cat
?parent_constr ?parent_cat ?parent_sub ?parent_prog ?parent_pu_name ?parent_vpu_name
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu ?pu_name ?vpu_name ?constr
    WHERE {

      ?constr a f:ContainerUnit ;
              f:inProgramUnitOrSubprogram ?pu_or_sp ;
              f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

    } GROUP BY ?ver ?loc ?pu ?pu_name ?vpu_name ?constr
  }

  OPTIONAL {
    SELECT DISTINCT ?constr (GROUP_CONCAT(DISTINCT ?c; SEPARATOR="&") AS ?cat)
    WHERE {
      ?constr a ?cat0 OPTION (INFERENCE NONE) .

      GRAPH <http://codinuum.com/ont/cpi> {
        ?cat0 rdfs:label ?c .
      }
    } GROUP BY ?constr
  }

  OPTIONAL {
    ?constr f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?constr f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    # FILTER NOT EXISTS {
    #   ?constr f:inMainProgram ?m0 .
    #   ?m0 f:inContainerUnit ?parent_constr .
    #   FILTER (?m0 != ?constr && ?m0 != ?parent_constr)
    # }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat .
    }
  }

  OPTIONAL {
    ?constr f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

  OPTIONAL {
    ?constr f:inContainerUnit ?parent_constr .
    ?parent_constr a f:ContainerUnit .

    FILTER (?constr != ?parent_constr)

    FILTER NOT EXISTS {
      ?constr f:inContainerUnit ?p0 .
      ?p0 a f:ContainerUnit ;
          f:inContainerUnit ?parent_constr .
      FILTER (?p0 != ?constr && ?p0 != ?parent_constr)
    }

    FILTER NOT EXISTS {
      ?constr f:inSubprogram ?sp0 .
      ?sp0 f:inContainerUnit ?parent_constr .
      FILTER (?sp0 != ?constr && ?sp0 != ?parent_constr)
    }

    {
      SELECT DISTINCT ?parent_constr (GROUP_CONCAT(DISTINCT ?c0; SEPARATOR="&") AS ?parent_cat)
      WHERE {
        ?parent_constr a ?parent_cat0 OPTION (INFERENCE NONE) .

        GRAPH <http://codinuum.com/ont/cpi> {
          ?parent_cat0 rdfs:label ?c0 .
        }
      } GROUP BY ?parent_constr
    }

    OPTIONAL {
      ?parent_constr f:inProgramUnit ?parent_pu .
      ?parent_pu f:name ?parent_pu_name .
    }

    OPTIONAL {
      ?parent_constr f:inProgramUnit/f:includedInProgramUnit ?parent_vpu .
      ?parent_vpu f:name ?parent_vpu_name .
    }

    OPTIONAL {
      ?parent_constr f:inMainProgram ?parent_main .
      ?parent_main a f:MainProgram .
      OPTIONAL {
        ?parent_main f:name ?parent_prog .
      }
    }

    OPTIONAL {
      ?parent_constr f:inSubprogram ?parent_sp .
      ?parent_sp a f:Subprogram ;
                 f:name ?parent_sub .

      FILTER NOT EXISTS {
        ?parent_constr f:inSubprogram ?sp0 .
        ?sp0 f:inSubprogram ?parent_sp .
        FILTER (?parent_sp != ?sp0)
      }
    }
  }

}
}
''' % NS_TBL

Q_CONSTR_SP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog
?constr ?cat ?call ?call_cat
?callee ?callee_name ?callee_loc ?callee_cat ?callee_pu_name
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?constr ?callee ?cat ?call ?call_cat
    WHERE {

      ?call a ?call_cat0 OPTION (INFERENCE NONE) ;
            f:inContainerUnit ?constr ;
            f:mayCall ?callee .

      FILTER (?call_cat0 IN (f:CallStmt, f:FunctionReference, f:PartName))

      ?constr a f:ContainerUnit ;
              a ?cat0 OPTION (INFERENCE NONE) ;
              f:inProgramUnitOrSubprogram ?pu_or_sp ;
              f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      FILTER NOT EXISTS {
        ?c a f:ContainerUnit ;
           f:inContainerUnit+ ?constr .
        ?call f:inContainerUnit+ ?c .
        FILTER (?c != ?constr)
      }

      ?pu a f:ProgramUnit ;
          ver:version ?ver ;
          src:inFile/src:location ?pu_loc .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      GRAPH <http://codinuum.com/ont/cpi> {
        ?cat0 rdfs:label ?cat .
        ?call_cat0 rdfs:label ?call_cat .
      }

    } GROUP BY ?ver ?loc ?pu_name ?vpu_name ?constr ?callee ?cat ?call ?call_cat
  }

  {
    SELECT DISTINCT ?callee ?callee_cat ?callee_loc ?ver ?callee_pu_name
    (GROUP_CONCAT(DISTINCT ?cn; SEPARATOR=":") AS ?callee_name)
    WHERE {

      ?callee a f:Subprogram ;
              a ?callee_cat0 OPTION (INFERENCE NONE) ;
              f:name ?cn ;
              src:inFile ?callee_file .

      ?callee_file a src:File ;
                   src:location ?callee_loc ;
                   ver:version ?ver .

      GRAPH <http://codinuum.com/ont/cpi> {
        ?callee_cat0 rdfs:label ?callee_cat
      }

      OPTIONAL {
        ?callee f:inProgramUnit/f:name ?callee_pu_name .
      }

    } GROUP BY ?callee ?callee_cat ?callee_loc ?ver ?callee_pu_name
  }

  OPTIONAL {
    ?constr f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?constr f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat
    }
  }

  OPTIONAL {
    ?constr f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

}
}
''' % NS_TBL

Q_SP_SP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp ?sp_cat ?sub ?main ?prog
?callee ?callee_name ?callee_loc ?callee_cat ?call ?call_cat ?constr ?callee_pu_name
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?pu ?pu_name ?vpu_name ?callee ?call ?call_cat
    WHERE {

      ?call a ?call_cat0 OPTION (INFERENCE NONE) ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu ;
            f:mayCall ?callee .

      ?pu_or_sp src:inFile/src:location ?loc .

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      FILTER (?call_cat0 IN (f:CallStmt, f:FunctionReference, f:PartName))

      FILTER NOT EXISTS {
        ?call f:inContainerUnit [] .
      }

      GRAPH <http://codinuum.com/ont/cpi> {
        ?call_cat0 rdfs:label ?call_cat .
      }

    } GROUP BY ?ver ?loc ?pu ?pu_name ?vpu_name ?callee ?call ?call_cat
  }

  {
    SELECT DISTINCT ?callee ?callee_cat ?callee_loc ?ver ?callee_pu_name
    (GROUP_CONCAT(DISTINCT ?cn; SEPARATOR=":") AS ?callee_name)
    WHERE {

      ?callee a f:Subprogram ;
              a ?callee_cat0 OPTION (INFERENCE NONE) ;
              f:name ?cn ;
              src:inFile ?callee_file .

      ?callee_file a src:File ;
                   src:location ?callee_loc ;
                   ver:version ?ver .

      GRAPH <http://codinuum.com/ont/cpi> {
        ?callee_cat0 rdfs:label ?callee_cat
      }

      OPTIONAL {
        ?callee f:inProgramUnit/f:name ?callee_pu_name .
      }

    } GROUP BY ?callee ?callee_cat ?callee_loc ?ver ?callee_pu_name
  }

  OPTIONAL {
    ?call f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        a ?sp_cat0 OPTION (INFERENCE NONE) ;
        f:name ?sub .

    FILTER NOT EXISTS {
      ?call f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }

    GRAPH <http://codinuum.com/ont/cpi> {
      ?sp_cat0 rdfs:label ?sp_cat
    }
  }

  OPTIONAL {
    ?call f:inMainProgram ?main .
    ?main a f:MainProgram .
    OPTIONAL {
      ?main f:name ?prog .
    }
  }

}
}
''' % NS_TBL

Q_CONSTR_QSPN_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?qspn ?constr
WHERE {
GRAPH <%%(proj)s> {
  {
    SELECT DISTINCT ?ver ?loc ?pu_name ?vpu_name ?sp0 ?constr
    (GROUP_CONCAT(DISTINCT CONCAT(STR(?dist), ?n); SEPARATOR=",") AS ?qspn)
    WHERE {

      ?constr a f:ContainerUnit ;
              f:inSubprogram ?sp0 ;
              f:inProgramUnit ?pu .

      ?sp0 src:inFile/src:location ?loc .

      FILTER NOT EXISTS {
        ?constr f:inSubprogram/f:inSubprogram ?sp0 .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?pu f:name ?pu_name .
      }

      OPTIONAL {
        ?pu f:includedInProgramUnit ?vpu .
        ?vpu f:name ?vpu_name .
      }

      ?sp0 a f:Subprogram ;
           f:name ?sp0_name .

      ?spx f:name ?n .

      {
        SELECT ?x ?sp
        WHERE {
          ?x a f:Subprogram ;
             f:inSubprogram ?sp .
        }
      } OPTION(TRANSITIVE,
               T_IN(?x),
               T_OUT(?sp),
               T_DISTINCT,
               T_MIN(0),
               T_NO_CYCLES,
               T_STEP (?x) AS ?spx,
               T_STEP ('step_no') AS ?dist
               )
      FILTER (?x = ?sp0)

    } GROUP BY ?ver ?loc ?sp0 ?constr ?pu_name ?vpu_name
  }
}
}
''' % NS_TBL


QUERY_TBL = {
    'aa_in_loop':    Q_AA_IN_LOOP_F,
    'other_calls':   Q_OTHER_CALLS_F,
    'gotos':         Q_GOTOS_F,
    'directives':    Q_DIRECTIVES_F,
    'constr_constr': Q_CONSTR_CONSTR_F,
    'constr_sp':     Q_CONSTR_SP_F,
    'sp_sp':         Q_SP_SP_F,
    'constr_qspn':   Q_CONSTR_QSPN_F,
}


def get_root_entities(full=False):
    s = set(['main-program'])
    if full:
        s |= set([
            'subroutine-external-subprogram',
            'subroutine-module-subprogram',
            'function-external-subprogram',
            'function-module-subprogram',
        ])
    return s
