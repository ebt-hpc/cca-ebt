#!/usr/bin/env python3


'''
  A script for making topic models

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

import os.path
import re
from gensim import corpora, models, similarities
import logging

logger = logging.getLogger()

STOP_WORDS = '''
a able about across after afterwards again against all almost alone along already
also although always am among amongst amount an and another any anyhow anyone
anything anyway anywhere are around as at
back be because become becomes becoming been before beforehand behind being
below beside besides between beyond both but by
can cannot could
did do does
each eight either else elsewhere enough even ever every everyone everything everywhere
few first five for former formerly four from further furthermore
get give got
had has have having he here hereafter hereby herein her hers him his how however
i if in indeed into is it its itself
just
last later latter least less let like likely
make many may me might mine more moreover most mostly much must my namely neither
never nevertheless next nine no nobody none nor not nothing now nowhere
of off often on one once only or other others otherwise our ours ourselves out over
own
perhaps please put
rather
said same say says second seem seems seven several she should since six so some
somehow someone sometime sometimes somewhere still such
ten than that the they their them themselves then there thereafter thereby these
third this those though three through throughout thus to together too toward towards
two
up under until upon us use user uses used using usual usually
very via
want wants was we were what whatever when whenever where whereas whereby whether
which while who whoever whom whose why will with within without would
yet you your yours yourself yourselves zero
'''

STOP_WORDS2 = '''
january february march april may june july august september october november december
time version data file files byte bytes directory run build builds building compile
compiler input output contains code sec following install installation installed
see default generate generates generated common university include includes
variables variable module setting settings command commands including included
boolean scheme example examples test tests testing script scripts option options
new case info program function functions library libraries system number set real
generating create core domain model need value information informations name type
value values parameter parameters result results routine routines error errors call
note add adds added specify specifies specified runs running package creates
created g95 tex latex reset resets print prints application applications
work works working method methods assume assumes subroutine subroutines help helps
document documentation list require requires required available helper unknown
describe describes description check checks checking tuning called usage adding
format formats found find readme makefile various contribution contributions
analysis analyses define defines defined execution main written read calculate
calculation calculates compute computed computes computing edit edits emacs main
remove removes removed revision source release flag flags git svn patch png integer
program programs programmed memory latex latex2html start started benchmark benchmarks
perl nowait num length condition conditions node exit exits exited process
configuration configurations gnu copyright python fortran documents setenv true false
problem problems gfortran appropriate demonstrate demonstrates name named names
implementation implementations click interface interfaces configure configures
return commit commits imply implies ifort matlab grep plugin plugins plot plots
inputs outputs contain contained tcl windows described nmake makes maked better
dump dumps gmake icon icons dvips obtain obtains show shows showing write examine
examines download downloads downloading jpeg national support supports xcode date
cmake intel java version versions parser ibm cpu sources autoconf f2py int setup
setups ruby resulting programming publicity public filename go goes going suppose
flex bison import imports export exports web postscript rely relies relying fax
copy copies copied font fonts software hardware jpeg2000 password passwords
procedure procedures addition removal list lists listing ftn95 fortran90 fortran77
implicit end enddo endif license licensed free open opens opening dist volume quit
line total deallocate address research sequence structures evaluate evaluated
kind continue const unit iomsg iostat err eor id dispose disp status asynchronous
blank decimal delim pad round sign access action async position recl bufferred
iofocus organization organisation recordsize recordtype share newunit blocksize
maxrec readonly shared title useropen fmt nml advance pos rec size direct exist
formatted iolength named nextrec opened pending readwrite sequential stream
unformatted binary strid precision complex associate blockdata block critical enum
forall interface select submodule structure union map outer inner begin instead
parallel serial allocatable small large efficient references reference definition
section left right top bottom private temp tmp double argument arguments dimension
logical intrinsic external statement statements implied start stop bug bugs
allocate restart initial pointer warranty array thread threads auto openmp mpi
verbose loop loops openacc opencl wait waits buffer buffers configured calling
comment comments commented word words installing job jobs platform platforms
compiling mkdir ls cp cd tar cat prerequisite contact contacts packaged aim aims
aiming standalone mpirun sed preprocess preprocessed preprocesses subdirectory
executable take takes taken represent represents represented representing src
optional draft recommend recommends recommended directories plan plans planned
planning mv member members gigabytes megabytes text texts explain explains
explained request requests requested prepare prepares prepared creating linux
provide provides provided extract extracts extracting requiring regarding regarded
regards confirm confirms confirmed mpis nproc bsd scalable scalability
jan feb mar apr jun jul aug sep sept oct nov dec range ranges ranging content
contents choose chose chosen success successful fail fails failed failure failing
monitor monitors monitoring fault faults faulting ln according
cause causes causing caused necessary advantage advantages staging stage stages staged
current mkl computer computers refer refers operate operates operating term terms
feature features depend depends depending separate separates separating
load loads loaded loading save saves saved saving cycle cycles observe observes
observing observed needs needed inside outside major minor communication
communications typical process processes processed point points pointing making made
done step steps listings ip cc node nodes terminate terminates terminating normal
namelist debug debugging debugs debugged answer answers answered answering fatal
calc token wrong team teams modules measure measures measured measuring measurement
iteration email unix ask asks asking asked pentium xeon powerpc sparc mips
constant constants score scores adjust adjusts adjusted adjusting
appear appears appeared appearing execute executes executed executing period periods
initialize initializes initializing initialized performance perform performs performed
performing hope hopes hoping hoped redistribute redistribution modify modifies modified
modifying general invoke invokes invoked invoking particular publish published publishing
receive received receives receiving initialise initialising initialised initialises
initialisation modification modifications utility utilities task tasks attempt attempts
attempted attempting remap location locations plus minus elapse elapsed recv send
broadcast broadcasts broadcasted broadcasting destination destinations pjsub
blas gpu gpus think thinks thought thinking host hosts sandy cuda subprogram subprograms
given givens lapack fix calculations figure figures simulate simulates simulated
simulation simulations vector vectors arrays matrixes matrices matrix workflow mic mics
lookup class classes style styles keyword keywords licensee licensor xml develop develops
developing developed developer developers group groups history histories stat stats
primitive primitives goto feedback try tried tries trying possible algorithm algorithms
repository repositories security relating relate relates related declaration declarations
sum sums mode modes outline outlines fill fills filled filling elif io pass string strings
pure counter conters operator operators object objects character characters patent patents
ascii rule rules identification identify identified identifies
'''

STOP_LIST = set(STOP_WORDS.split()+STOP_WORDS2.split())


def isfloat(s):
    b = True
    try:
        float(s)
    except:
        b = False
    return b

PAT = re.compile(r'^[0-9].*')
def startswithdigit(s):
    b = False
    m = PAT.match(s)
    if m:
        b = True
    return b

def filt(x):
    b = x.isalnum() and not startswithdigit(x) and not x.isdigit() and len(x) > 1 and x not in STOP_LIST
    return b

def extract_words(path):
    f = open(path, 'r')

    lines = []

    incomplete = None

    for _line in f:
        line = _line.strip()
        if line:
            if not line.isdigit() and not isfloat(line):

                if incomplete:
                    line = incomplete + line

                if line.endswith('-'):
                    incomplete = line.rstrip('-')
                else:
                    incomplete = None
                    lines.append(line.lower())
    f.close()

    words = []

    for line in lines:
        l = filter(filt, line.split())
        if l:
            words += l

    return words


def lda(corpus, dictionary, ntopics=10):
    lda = models.ldamodel.LdaModel(corpus, id2word=dictionary, num_topics=ntopics, alpha='auto', eval_every=5)
    return lda

def lsi(corpus, dictionary, ntopics=10):
    tfidf = models.TfidfModel(corpus)
    corpus_tfidf = tfidf[corpus]
    lsi = models.LsiModel(corpus_tfidf, id2word=dictionary, num_topics=ntopics)
    #lsi = models.LsiModel(corpus, id2word=dictionary, num_topics=ntopics)
    return lsi

def rp(corpus, dictionary, ntopics=10):
    tfidf = models.TfidfModel(corpus)
    corpus_tfidf = tfidf[corpus]
    rp = models.RpModel(corpus_tfidf, id2word=dictionary, num_topics=ntopics)
    return rp


def get_texts(dpath, pat):
    pat = re.compile(pat, flags=re.I)
 
    texts = []

    logger.info('collecting documents...')

    for (d, dns, ns) in os.walk(dpath, followlinks=True):
        for n in ns:
            m = pat.match(n)
            if m:
                path = os.path.join(d, n)
                logger.debug('%s' % path)
                try:
                    words = extract_words(path)
                    texts.append(words)
                except Exception as e:
                    logger.warning(str(e))

    logger.info('%d documents found' % len(texts))

    return texts
    

def analyze(mkmodel, dpath, pat, ntopics=10):
    texts = get_texts(dpath, pat)

    logger.info('analyzing...')

    dictionary = corpora.Dictionary(texts)
    #dictionary.save('a.dict')

    corpus = [dictionary.doc2bow(text) for text in texts]
    #corpora.MmCorpus.serialize('a.mm', corpus)

    m = mkmodel(corpus, dictionary, ntopics=ntopics)

    return {'model':m,'corpus':corpus,'dict':dictionary}



if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='analyze topics of documents')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-p', '--pattern', dest='pat', metavar='RE', type=str,
                        default=None, help='pattern of file name')

    parser.add_argument('-m', '--model', dest='model', metavar='MODEL', type=str,
                        default='lsi', help='model (lda|lsi|rp)')

    parser.add_argument('-t', '--topics', dest='topics', metavar='N', type=int,
                        default=10, help='number of topics')

    parser.add_argument('dpath', metavar='PATH', type=str, help='directory')

    args = parser.parse_args()

    pat = r'.*readme.*'
    if args.pat:
        pat = args.pat

    model = lsi

    if args.model == 'lda':
        model = lda
    elif args.model == 'lsi':
        model = lsi
    elif args.model == 'rp':
        model = rp

    res = analyze(model, args.dpath, pat, ntopics=args.topics)

    m = res['model']
    try:
        for t in m.show_topics(args.ntopics):
            print(t)
    except Exception as e:
        print(str(e))
