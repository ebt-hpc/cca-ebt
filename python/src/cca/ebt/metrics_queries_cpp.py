#!/usr/bin/env python3

'''
  Source code metrics for C programs

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

Q_LOOP_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?child_loop ?loop_d ?child_loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?loop_d
    WHERE {

      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?loop_d
  }

  OPTIONAL {
    ?child_loop a cpp:IterationStatement ;
                src:treeDigest ?child_loop_d ;
                cpp:inIterationStatement ?loop .

    FILTER (?child_loop != ?loop)
  }

  OPTIONAL {
    ?loop cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .
    FILTER NOT EXISTS {
      ?loop cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }
  }

}
}
''' % NS_TBL

Q_LOOP_FD_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?loop ?callee ?callee_loc ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?tu ?loop ?callee ?loc ?loop_d
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            cpp:inIterationStatement ?loop ;
            cpp:mayCall ?callee .

      FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                            cpp:PostfixExpressionFunCallGuarded))

      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc .

    } GROUP BY ?tu ?loop ?callee ?loc ?loop_d
  }

  ?callee a cpp:FunctionDefinition ;
          cpp:inTranslationUnit/src:inFile ?callee_file .

  ?callee_file a src:File ;
               src:location ?callee_loc ;
               ver:version ?ver .

  FILTER EXISTS {
    ?tu ver:version ?ver .
  }

}
}
''' % NS_TBL

Q_FD_FD_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?callee ?callee_loc
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?fd ?callee
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            cpp:inFunctionDefinition ?fd ;
            cpp:mayCall ?callee .

      FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                            cpp:PostfixExpressionFunCallGuarded))

      ?fd a cpp:FunctionDefinition ;
          cpp:inTranslationUnit/src:inFile ?file .

      FILTER NOT EXISTS {
        ?call cpp:inFunctionDefinition ?fd0 .
        ?fd0  cpp:inFunctionDefinition ?fd .
        FILTER (?fd != ?fd0)
      }

      ?file a src:File ;
            src:location ?loc ;
            ver:version ?ver .

    } GROUP BY ?ver ?loc ?fd ?callee
  }

  ?callee a cpp:FunctionDefinition ;
          cpp:inTranslationUnit*/src:inFile ?callee_file .

  ?callee_file a src:File ;
               src:location ?callee_loc ;
               ver:version ?ver .

}
}
''' % NS_TBL

Q_ARRAYS_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fn ?loop ?aname ?rank ?dtor ?tyc ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?tu ?loop ?a ?aname ?loop_d ?aa ?acat
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0* ?a ;
          cpp:inIterationStatement ?loop .

      FILTER NOT EXISTS {
        ?aa src:parent+ ?aa0 .
        ?aa0 a cpp:PostfixExpressionSubscr .
      }

      ?a a ?acat OPTION (INFERENCE NONE) ;
         cpp:name ?aname .

      FILTER NOT EXISTS {
        ?a0 src:parent+ ?a ;
            cpp:name [] .
      }

      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

    } GROUP BY ?tu ?loop ?a ?aname ?loop_d ?aa ?acat
  }

  ?tu a cpp:TranslationUnit ;
      src:inFile/src:location ?loc ;
      ver:version ?ver .

  {
    SELECT DISTINCT ?aa (COUNT(DISTINCT ?aa0) AS ?rank)
    WHERE {
      ?aa0 a cpp:PostfixExpressionSubscr ;
           src:parent* ?aa .
    } GROUP BY ?aa
  }

  {
    SELECT DISTINCT ?a ?dtor ?dcat ?tyc ?ty
    WHERE {

      ?a cpp:declarator ?dtor .

      ?dtor a ?dcat OPTION (INFERENCE NONE) ;
            cpp:type ?ty ;
            cpp:declarationTypeSpec ?tspec .

      ?tspec a ?tyc OPTION (INFERENCE NONE) .

    } GROUP BY ?a ?dtor ?dcat ?tyc ?ty
  }

  OPTIONAL {
    ?loop cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .
    FILTER NOT EXISTS {
      ?loop cpp:inFunctionDefinition ?fd0 .
      ?fd0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }
  }

}
}
''' % NS_TBL

Q_FFR_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?fref ?fname ?nargs ?h ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?loop_d
  }

  OPTIONAL {
    ?loop cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .
    FILTER NOT EXISTS {
      ?loop cpp:inFunctionDefinition ?fd0 .
      ?sp0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }
  }

  {
    SELECT DISTINCT ?loop ?fref ?h ?fname (COUNT(DISTINCT ?arg) AS ?nargs) ?p
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            src:treeDigest ?h ;
            src:child0 ?fref ;
            src:child1 ?arg ;
            src:child1 ?farg ;
            cpp:inIterationStatement ?loop .

      FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                            cpp:PostfixExpressionFunCallGuarded))

      ?fref cpp:requires/cpp:name ?fname .

      ?farg a ?facat OPTION (INFERENCE NONE) .

      FILTER (EXISTS { ?farg a cpp:FloatingLiteral } ||
              EXISTS {
                ?farg cpp:declarator ?dtor .
                ?dtor a ?dcat OPTION (INFERENCE NONE) ;
                      cpp:declarationTypeSpec ?tspec .
                ?tspec a ?tcat OPTION (INFERENCE NONE) .
                FILTER (?tcat IN (cpp:Double, cpp:Float))
              }
              )

    } GROUP BY ?loop ?fref ?h ?fname ?p
  }

}
}
''' % NS_TBL

Q_DFR_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?fname ?h ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?loop_d
  }

  OPTIONAL {
    ?loop cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .
    FILTER NOT EXISTS {
      ?loop cpp:inFunctionDefinition ?fd0 .
      ?sp0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }
  }

  {
    SELECT DISTINCT ?loop ?fref ?h ?fname (COUNT(DISTINCT ?arg) AS ?nargs) ?p
    WHERE {

      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            src:treeDigest ?h ;
            src:child0 ?fref ;
            src:child1 ?arg ;
            src:child1 ?farg ;
            cpp:inIterationStatement ?loop .

      FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                            cpp:PostfixExpressionFunCallGuarded))

      ?fref cpp:requires/cpp:name ?fname .

      ?farg a ?facat OPTION (INFERENCE NONE) .

      FILTER (EXISTS { ?farg a cpp:FloatingLiteral } ||
              EXISTS {
                ?farg cpp:declarator ?dtor .
                ?dtor a ?dcat OPTION (INFERENCE NONE) ;
                      cpp:declarationTypeSpec ?tspec .
                ?tspec a ?tcat OPTION (INFERENCE NONE) .
                FILTER (?tcat IN (cpp:Double))
              }
              )

    } GROUP BY ?loop ?fref ?h ?fname ?p
  }

}
}
''' % NS_TBL

Q_FOP_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?nfop ?loop_d
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

    } GROUP BY ?ver ?loc ?loop ?loop_d
  }

  OPTIONAL {
    ?loop cpp:inFunctionDefinition ?fd .
    ?fd a cpp:FunctionDefinition ;
        cpp:provides/(cpp:name|cpp:regexp) ?fn .
    FILTER NOT EXISTS {
      ?loop cpp:inFunctionDefinition ?fd0 .
      ?sp0 cpp:inFunctionDefinition ?fd .
      FILTER (?fd != ?fd0)
    }
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?h) AS ?nfop)
    WHERE {

      ?fop a ?fop_cat OPTION (INFERENCE NONE) ;
           src:treeDigest ?h ;
           cpp:inIterationStatement ?loop .

      FILTER (?fop_cat IN (cpp:MultiplicativeExpressionMult,
                           cpp:MultiplicativeExpressionDiv,
                           cpp:MultiplicativeExpressionMod,
                           cpp:AdditiveExpressionAdd,
                           cpp:AdditiveExpressionSubt
                           ))

      ?opr a cpp:Expression ;
           src:parent+ ?fop .

      FILTER (EXISTS {
        ?opr a cpp:FloatingLiteral .
      } || EXISTS {
        ?opr cpp:declarator/cpp:declarationTypeSpec ?tspec .
        ?tspec a ?tcat OPTION (INFERENCE NONE) .
        FILTER (?tcat IN (cpp:Double,cpp:Float))
      })

    } GROUP BY ?loop
  }

}
}
''' % NS_TBL

Q_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?vname ?loop_d ?nbr ?nes ?nop ?nc
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?h) AS ?nop)
    WHERE {
      ?op a cpp:Expression ;
          src:treeDigest ?h ;
          cpp:inIterationStatement ?loop .

    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?br) AS ?nbr)
    WHERE {
      ?br a cpp:SelectionStatement ;
          a ?br_cat OPTION (INFERENCE NONE) ;
          cpp:inIterationStatement ?loop .
    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?stmt) AS ?nes)
    WHERE {
      ?stmt a cpp:Statement ;
            a ?stmt_cat OPTION (INFERENCE NONE) ;
            cpp:inIterationStatement ?loop .
    } GROUP BY ?loop
  }

  OPTIONAL {
    SELECT DISTINCT ?loop (COUNT(DISTINCT ?call) AS ?nc)
    WHERE {
      ?call a ?call_cat OPTION (INFERENCE NONE) ;
            cpp:inIterationStatement ?loop .

      FILTER (?call_cat IN (cpp:PostfixExpressionFunCall,
                            cpp:PostfixExpressionFunCallGuarded))

    } GROUP by ?loop
  }

}
}
''' % NS_TBL


Q_AREF0_AA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          cpp:arrayRefSig0 ?asig0 ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:NumericType .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF0_IAA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          src:child1 ?idx ;
          cpp:arrayRefSig0 ?asig0 ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:NumericType .
      }

      FILTER (EXISTS {
        ?x a cpp:Expression ;
           src:children [] ;
           src:parent+ ?idx0 .

        ?aa0 a cpp:PostfixExpressionSubscr ;
             src:child1 ?idx0 ;
             src:parent+ ?aa .

        FILTER (?x != ?aa)
      } || EXISTS {
        ?x a cpp:Expression ;
           src:children [] ;
           src:parent+ ?idx .
      })

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF0_DAA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          src:child1 ?idx ;
          cpp:arrayRefSig0 ?asig0 ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(IF(BOUND(?assign), CONCAT(",", ?asig0), ?asig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:Double .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_AA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          src:child1 ?idx ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?aa cpp:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:NumericType .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_IAA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          src:child1 ?idx ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?aa cpp:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:NumericType .
      }

      FILTER (EXISTS {
        ?x a cpp:Expression ;
           src:children [] ;
           src:parent+ ?idx0 .

        ?aa0 a cpp:PostfixExpressionSubscr ;
             src:child1 ?idx0 ;
             src:parent+ ?aa .

        FILTER (?x != ?aa)
      } || EXISTS {
        ?x a cpp:Expression ;
           src:children [] ;
           src:parent+ ?idx .
      })

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL

Q_AREF12_DAA_IN_LOOP_C = '''DEFINE input:inference "ont.cpi"
PREFIX cpp: <%(cpp_ns)s>
PREFIX ver: <%(ver_ns)s>
PREFIX src: <%(src_ns)s>
SELECT DISTINCT ?ver ?loc ?fd ?fn ?loop ?loop_d ?sig
WHERE {
GRAPH <%%(proj)s> {

  {
    SELECT DISTINCT ?ver ?loc ?loop ?fd ?fn ?loop_d
    WHERE {
      ?loop a cpp:IterationStatement ;
            src:treeDigest ?loop_d ;
            cpp:inTranslationUnit ?tu .

      ?tu a cpp:TranslationUnit ;
          src:inFile/src:location ?loc ;
          ver:version ?ver .

      OPTIONAL {
        ?loop cpp:inFunctionDefinition ?fd .
        ?fd a cpp:FunctionDefinition ;
            cpp:provides/(cpp:name|cpp:regexp) ?fn .
        FILTER NOT EXISTS {
          ?loop cpp:inFunctionDefinition ?fd0 .
          ?sp0 cpp:inFunctionDefinition ?fd .
          FILTER (?fd != ?fd0)
        }
      }

    } GROUP BY ?ver ?loc ?loop ?fd ?fn ?loop_d
  }

  {
    SELECT DISTINCT ?loop ?sig
    WHERE {

      ?aa a cpp:PostfixExpressionSubscr ;
          src:child0 ?a ;
          src:child1 ?idx ;
          cpp:inIterationStatement ?loop .

      OPTIONAL {
        ?aa cpp:arrayRefSig%%(level)d ?asig .
      }
      OPTIONAL {
        ?assign a cpp:AssignmentOperatorExpression ;
                src:child0 ?aa .
      }
      BIND(COALESCE(?asig, "") AS ?sig0)
      BIND(IF(BOUND(?assign) && ?sig0 != "", CONCAT(",", ?sig0), ?sig0) AS ?sig)

      FILTER EXISTS {
         ?a cpp:declarator/cpp:declarationTypeSpec ?tspec .
         ?tspec a cpp:Double .
      }

    } GROUP BY ?loop ?sig
  }

}
}
''' % NS_TBL


QUERY_TBL = {
    'loop_loop'      : Q_LOOP_LOOP_C,
    'arrays'         : Q_ARRAYS_C,
    'ffr_in_loop'    : Q_FFR_IN_LOOP_C,
    'dfr_in_loop'    : Q_DFR_IN_LOOP_C,
    'fop_in_loop'    : Q_FOP_IN_LOOP_C,
    'in_loop'        : Q_IN_LOOP_C,

    'aref0_in_loop'  : { 'aa' : Q_AREF0_AA_IN_LOOP_C,
                         'iaa': Q_AREF0_IAA_IN_LOOP_C,
                         'daa': Q_AREF0_DAA_IN_LOOP_C,
    },

    'aref12_in_loop' : { 'aa' : Q_AREF12_AA_IN_LOOP_C,
                         'iaa': Q_AREF12_IAA_IN_LOOP_C,
                         'daa': Q_AREF12_DAA_IN_LOOP_C,
    },

    'loop_fd'        : Q_LOOP_FD_C,
    'fd_fd'          : Q_FD_FD_C,
}
