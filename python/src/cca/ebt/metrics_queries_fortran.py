#!/usr/bin/env python3

'''
  Source code metrics for Fortran programs

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

from .common import NS_TBL

Q_LOOP_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?child_loop ?child_vname ?loop_d ?child_loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {

      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?child_loop a f:DoConstruct ;
                src:treeDigest ?child_loop_d ;
                f:inDoConstruct ?loop .

    OPTIONAL {
      ?child_loop f:variableName ?child_vname .
    }
    FILTER (?child_loop != ?loop)
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

}
}
''' % NS_TBL

Q_LOOP_SP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?loop ?vname ?callee ?callee_loc ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?pu ?loop ?vname ?callee ?loc ?loop_d
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            f:inDoConstruct ?loop ;
            f:mayCall ?callee .

      FILTER (?call_cat IN (f:CallStmt, f:FunctionReference, f:PartName))

      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc .

    } GROUP BY ?pu ?loop ?vname ?callee ?loc ?loop_d
  }

  ?callee a f:Subprogram ;
          src:inFile ?callee_file .

  ?callee_file a src:File ;
               src:location ?callee_loc ;
               ver:version ?ver .

  FILTER EXISTS {
    ?pu ver:version ?ver .
  }

}
}
''' % NS_TBL

Q_SP_SP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?callee ?callee_loc
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?sp ?callee
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            f:inSubprogram ?sp ;
            f:mayCall ?callee .

      ?sp a f:Subprogram ;
          src:inFile ?file .

      FILTER NOT EXISTS {
        ?call f:inSubprogram ?sp0 .
        ?sp0 f:inSubprogram ?sp .
        FILTER (?sp != ?sp0)
      }

      ?file a src:File ;
            src:location ?loc ;
            ver:version ?ver .

      FILTER (?call_cat IN (f:CallStmt, f:FunctionReference, f:PartName))

    } GROUP BY ?ver ?loc ?sp ?callee
  }

  ?callee a f:Subprogram ;
          src:inProgramUnit*/src:inFile ?callee_file .

  ?callee_file a src:File ;
               src:location ?callee_loc ;
               ver:version ?ver .

}
}
''' % NS_TBL

Q_ARRAYS_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sub ?loop ?vname ?aname ?rank ?edecl ?tyc ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?pu ?loop ?vname ?pn ?aname ?loop_d
     WHERE {

       ?pn a f:PartName ;
           src:parent ?aa ;
           f:name ?aname .

       ?aa a f:ArrayAccess ;
           f:inDoConstruct ?loop .

       ?loop a f:DoConstruct ;
             src:treeDigest ?loop_d ;
             f:inProgramUnit ?pu .

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

     } GROUP BY ?pu ?loop ?vname ?pn ?aname ?loop_d
  }

  ?loop f:inProgramUnitOrSubprogram ?pu_or_sp .

  ?pu_or_sp src:inFile/src:location ?loc .

  # FILTER NOT EXISTS {
  #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
  #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
  # }

  ?pu a f:ProgramUnit ;
      src:inFile/src:location ?pu_loc ;
      ver:version ?ver .

  {
    SELECT DISTINCT ?pn ?rank ?aname ?edecl ?tyc
    WHERE {

      ?pn f:declarator ?edecl .

      ?edecl a f:EntityDecl ;
             f:rank ?rank ;
             f:name ?aname ;
             f:declarationTypeSpec ?tspec .

      ?tspec a f:TypeSpec ;
             a ?tyc OPTION (INFERENCE NONE) .

    } GROUP BY ?pn ?rank ?aname ?edecl ?tyc
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

}
}
''' % NS_TBL

Q_FFR_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?fref ?fname ?nargs ?h ?loop_d
WHERE {
GRAPH <%%(proj)s> {
  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?fref ?h ?fname (COUNT(DISTINCT ?arg) AS ?nargs)
    WHERE {

      ?fref a f:FunctionReference OPTION (INFERENCE NONE) ;
           src:treeDigest ?h ;
           f:inDoConstruct ?loop ;
           f:name ?fname .

      ?arg src:parent ?fref .
      
      ?farg a f:Expr ;
            src:parent+ ?fref .
      
      FILTER (?fname IN ("real", "dble") ||
              EXISTS { ?farg a f:RealLiteralConstant } ||
              EXISTS {
                ?farg f:declarator ?dtor .
                ?dtor a f:Declarator ;
                      f:declarationTypeSpec [ a f:FloatingPointType ] .
              }
              )

    } GROUP BY ?loop ?fref ?h ?fname
  }
}
}
''' % NS_TBL

Q_DFR_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?fname ?h ?loop_d
WHERE {
GRAPH <%%(proj)s> {
  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?fref ?h ?fname
    WHERE {

      ?fref a f:FunctionReference OPTION (INFERENCE NONE) ;
           src:treeDigest ?h ;
           f:inDoConstruct ?loop ;
           f:name ?fname .

    } GROUP BY ?loop ?fref ?h ?fname
  }

  FILTER (
          EXISTS {
            ?farg a f:RealLiteralConstant ;
                  f:value ?val ;
                  src:parent+ ?fref .
            FILTER (CONTAINS(STR(?val), "d") || CONTAINS(STR(?val), "D"))
          } || 
          EXISTS {
            ?farg a f:Expr ;
                  f:declarator ?dtor ;
                  src:parent+ ?fref .

            ?dtor a f:Declarator ;
                  f:declarationTypeSpec ?tspec .

            ?tspec a ?cat OPTION (INFERENCE NONE) .

            FILTER (?cat = f:DoublePrecision || 
                    (?cat = f:Real && 
                     EXISTS {
                       ?tspec src:children/rdf:first/src:children/rdf:first/f:value 8
                     })
                    )
          }
          )

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

}
}
''' % NS_TBL

Q_FOP_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?nfop ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?h) AS ?nfop)
    WHERE {
      ?fop a f:IntrinsicOperator ;
           src:treeDigest ?h ;
           a ?fop_cat OPTION (INFERENCE NONE);
           f:inDoConstruct ?loop .

      FILTER (?fop_cat NOT IN (f:Not, f:And, f:Or, f:Concat))
      FILTER NOT EXISTS {
        ?fop a f:RelOp .
      }
      FILTER NOT EXISTS {
        ?fop a f:EquivOp .
      }

      ?opr a f:Expr ;
           src:parent+ ?fop .

      FILTER (EXISTS {
        ?opr a f:RealLiteralConstant
      } || EXISTS {
        ?opr a f:FunctionReference ;
             f:name ?fname .
        FILTER (?fname IN ("real", "dble"))
      } || EXISTS {
        ?opr f:declarator ?dtor .
        ?dtor a f:Declarator ;
              f:declarationTypeSpec [a f:FloatingPointType] .
      } || EXISTS {
        ?opr f:typeSpec ?tspec .
        FILTER (?tspec IN ("Real", "DoublePrecision", "DoubleComplex", "Complex"))
      })

    } GROUP BY ?loop
  }

}
}
''' % NS_TBL

Q_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?nbr ?nop ?nc ?nes
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?sp ?sub ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop f:inSubprogram ?sp .
        ?sp a f:Subprogram ;
            f:name ?sub .
        FILTER NOT EXISTS {
          ?loop f:inSubprogram ?sp0 .
          ?sp0 f:inSubprogram ?sp .
          FILTER (?sp != ?sp0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?vname ?sp ?sub ?loop_d
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?h) AS ?nop)
    WHERE {
      ?op a f:IntrinsicOperator ;
          src:treeDigest ?h ;
          f:inDoConstruct ?loop .

    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?br) AS ?nbr)
    WHERE {
      ?br a f:Stmt ;
          a ?br_cat OPTION (INFERENCE NONE) ;
          f:inDoConstruct ?loop .

      FILTER (?br_cat IN (f:IfStmt,
                          f:IfThenStmt,
                          f:ElseStmt,
                          f:ElseIfStmt,
                          f:CaseStmt,
                          f:WhereStmt,
                          f:ElsewhereStmt,
                          f:TypeGuardStmt))
    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?es) AS ?nes)
    WHERE {
      ?es a f:ExecutableStmt ;
          f:inDoConstruct ?loop .

    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?call) AS ?nc)
    WHERE {
      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            f:inDoConstruct ?loop ;
            f:name ?callee_name .

      FILTER (?call_cat IN (f:CallStmt, f:FunctionReference))

#      FILTER EXISTS {
#        ?call f:refersTo ?callee .
#      }

    } GROUP by ?loop
  }

}
}
''' % NS_TBL


Q_AREF0_AA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?pn a f:PartName ;
          src:parent ?aa .

      ?aa a f:ArrayAccess ;
          f:name ?an ;
          f:arrayRefSig0 ?asig0 ;
          f:inDoConstruct ?loop .

      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?aa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF0_IAA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {
      ?pn a f:PartName ;
          src:parent ?iaa .

      ?iaa a f:ArrayAccess ;
           f:name ?an ;
           f:arrayRefSig0 ?asig0 ;
           f:inDoConstruct ?loop .

      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?iaa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

      FILTER EXISTS {
        ?x a ?cat ; 
           src:parent+ ?iaa .
        FILTER (?x != ?iaa)
        FILTER (?cat IN (f:ArrayElement, f:ArraySection, f:FunctionReference))
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF0_DAA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?loop a f:DoConstruct .

      {
        SELECT DISTINCT ?pn ?aa ?an ?asig0 ?loop
        WHERE {

          ?pn a f:PartName ;
              src:parent ?aa .

          ?aa a f:ArrayAccess ;
              f:name ?an ;
              f:arrayRefSig0 ?asig0 ;
              f:inDoConstruct ?loop .

        } GROUP BY ?pn ?aa ?an ?asig0 ?loop
      }

      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?aa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:TypeSpec ;
               a ?tyc OPTION (INFERENCE NONE) .

        FILTER (?tyc = f:DoublePrecision || ?tyc = f:Complex || ?tyc = f:DoubleComplex ||
                  (?tyc = f:Real && 
                     EXISTS {
                       ?tspec src:children/rdf:first/src:children/rdf:first/f:value 8
                     })
          )
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_AA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?pn a f:PartName ;
          src:parent ?aa .

      ?aa a f:ArrayAccess ;
          f:name ?an ;
          f:inDoConstruct ?loop .

      OPTIONAL {
        ?aa f:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?aa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_IAA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {
      ?pn a f:PartName ;
          src:parent ?iaa .

      ?iaa a f:ArrayAccess ;
           f:name ?an ;
           f:inDoConstruct ?loop .

      OPTIONAL {
        ?iaa f:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?iaa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:NumericType .
      }

      FILTER EXISTS {
        ?x a ?cat ; 
           src:parent+ ?iaa .
        FILTER (?x != ?iaa)
        FILTER (?cat IN (f:ArrayElement, f:ArraySection, f:FunctionReference))
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_DAA_IN_LOOP_F = '''DEFINE input:inference "ont.cpi"
PREFIX f:   <%(f_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?sp ?sub ?loop ?vname ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?vname ?loop_d
    WHERE {
      ?loop a f:DoConstruct ;
            src:treeDigest ?loop_d ;
            f:inProgramUnitOrSubprogram ?pu_or_sp ;
            f:inProgramUnit ?pu .

      ?pu_or_sp src:inFile/src:location ?loc .

      # FILTER NOT EXISTS {
      #   ?pos f:inProgramUnitOrSubprogram+ ?pu_or_sp .
      #   ?loop f:inProgramUnitOrSubprogram+ ?pos .
      # }

      OPTIONAL {
        ?loop f:variableName ?vname .
      }

      ?pu a f:ProgramUnit ;
          src:inFile/src:location ?pu_loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?vname ?loop_d
  }

  OPTIONAL {
    ?loop f:inSubprogram ?sp .
    ?sp a f:Subprogram ;
        f:name ?sub .
    FILTER NOT EXISTS {
      ?loop f:inSubprogram ?sp0 .
      ?sp0 f:inSubprogram ?sp .
      FILTER (?sp != ?sp0)
    }
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?loop a f:DoConstruct .

      {
        SELECT DISTINCT ?pn ?aa ?an ?loop
        WHERE {

          ?pn a f:PartName ;
              src:parent ?aa .

          ?aa a f:ArrayAccess ;
              f:name ?an ;
              f:inDoConstruct ?loop .

        } GROUP BY ?pn ?aa ?an ?loop
      }

      OPTIONAL {
        ?aa f:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a f:AssignmentStmt ;
                src:children/rdf:first ?aa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
        ?pn f:declarator ?dtor .

        ?dtor a f:Declarator ;
              f:declarationTypeSpec ?tspec .

        ?tspec a f:TypeSpec ;
               a ?tyc OPTION (INFERENCE NONE) .

        FILTER (?tyc = f:DoublePrecision || ?tyc = f:Complex || ?tyc = f:DoubleComplex ||
                  (?tyc = f:Real && 
                     EXISTS {
                       ?tspec src:children/rdf:first/src:children/rdf:first/f:value 8
                     }) ||
                  (?tyc = f:PpMacroTypeSpec &&
                     EXISTS {
                       ?tspec f:body ?body .
                       FILTER (CONTAINS(?body, "double") || CONTAINS(?body, "complex"))
                     })
          )
      }
    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL


QUERY_TBL = {
    'loop_loop'      : Q_LOOP_LOOP_F,
    'arrays'         : Q_ARRAYS_F,
    'ffr_in_loop'    : Q_FFR_IN_LOOP_F,
    'dfr_in_loop'    : Q_DFR_IN_LOOP_F,
    'fop_in_loop'    : Q_FOP_IN_LOOP_F,
    'in_loop'        : Q_IN_LOOP_F,

    'aref0_in_loop'  : { 'aa' : Q_AREF0_AA_IN_LOOP_F,
                         'iaa': Q_AREF0_IAA_IN_LOOP_F,
                         'daa': Q_AREF0_DAA_IN_LOOP_F,
    },

    'aref12_in_loop' : { 'aa' : Q_AREF12_AA_IN_LOOP_F,
                         'iaa': Q_AREF12_IAA_IN_LOOP_F,
                         'daa': Q_AREF12_DAA_IN_LOOP_F,
    },

    'loop_sp'        : Q_LOOP_SP_F,
    'sp_sp'          : Q_SP_SP_F,
}
