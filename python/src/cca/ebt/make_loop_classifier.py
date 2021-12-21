#!/usr/bin/env python3


'''
  A script for making loop classifiers

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
import csv
import numpy as np
# import scipy as sp
from sklearn.neighbors import KNeighborsClassifier
# from sklearn.neighbors import RadiusNeighborsClassifier
from sklearn.svm import SVC
# from sklearn.svm import LinearSVC
# from sklearn.svm import NuSVC
# from sklearn.naive_bayes import GaussianNB, MultinomialNB, BernoulliNB
# from sklearn.ensemble import RandomForestClassifier
# from sklearn.ensemble import ExtraTreesClassifier
# from sklearn.ensemble import AdaBoostClassifier
# from sklearn.feature_selection import SelectKBest, SelectFromModel
# from sklearn.feature_selection import chi2, f_classif
# from sklearn import grid_search
# from sklearn import model_selection
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score)
from sklearn import preprocessing as pp
import joblib
import logging

logger = logging.getLogger()

META = [
    'proj',
    'ver',
    'path',
    'lnum',
    'sub',
    'root_file',
    'nid',
    'digest',
]

JUDGMENTS = ['judgment_M',
             # 'judgment_T',
             # 'judgment_X',
             ]

N_JUDGMENTS = len(JUDGMENTS)

METRICS = [
    'max_array_rank',
    'max_loop_level',
    'max_loop_depth',
    'max_mergeable_arrays',
    'max_fusible_loops',
    'calls',
    'branches',
    'stmts',
    'lines_of_code',
    'ops',
    'fp_ops',
    'bf0',
    'bf1',
    'bf2',
    'array_refs0',
    'array_refs1',
    'array_refs2',
    'dbl_array_refs0',
    'dbl_array_refs1',
    'dbl_array_refs2',
    'indirect_array_refs0',
    'indirect_array_refs1',
    'indirect_array_refs2',
]

SELECTED = [
    'max_loop_level',
    'max_loop_depth',
    'max_mergeable_arrays',
    'max_fusible_loops',
    'indirect_array_refs0',
    'calls',
    'bf0',
]

DERIVED = [
    # 'br_rate',
    # 'ind_aref_rate0',
    # 'array_rank_rate',
]


def rate(x, y):
    return float(x) / float(y)


DERIVED_F_TBL = {
    'br_rate':         rate,
    'ind_aref_rate0':  rate,
    'array_rank_rate': rate,
}
DERIVED_A_TBL = {
    'br_rate':         ('branches', 'stmts'),
    'ind_aref_rate0':  ('indirect_array_refs0', 'array_refs0'),
    'array_rank_rate': ('max_array_rank', 7.),
}

###

# SELECTED_MINAMI = [  # CA=.832,P=.837056,R=.971948,F1=.894753
#     'max_loop_level',
#     'max_loop_depth',
#     'max_mergeable_arrays',
#     'max_fusible_loops',
#     'indirect_array_refs0',
#     'calls',
#     'bf0',
# ]
SELECTED_MINAMI = [  # CA=.85,P=.884071,R=.929341,F1=.900756
    'max_loop_level',
    'max_loop_depth',
    'max_mergeable_arrays',
    'indirect_array_refs0',
]
DERIVED_MINAMI = []

SELECTED_TERAI = [
    'max_array_rank',
    'max_loop_depth',
    'max_mergeable_arrays',
    'max_fusible_loops',
    'calls',
    'branches',
    'stmts',
    'ops',
    'fp_ops',
    'array_refs0',
    'array_refs1',
    'dbl_array_refs0',
    'indirect_array_refs0',
]
DERIVED_TERAI = ['ind_aref_rate0']

SELECTED_MIX = [
    'max_loop_level',
    'max_loop_depth',
    'max_mergeable_arrays',
    'max_fusible_loops',
    'indirect_array_refs0',
    'calls',
    'bf0',
]
DERIVED_MIX = []

###


def fromstring(s):
    x = s
    try:
        x = int(s)
    except Exception:
        try:
            x = float(s)
        except Exception:
            pass
    return x


class Data(object):
    def __init__(self, X, y, meta):
        self.X = X
        self.y = y
        self.meta = meta


def get_derived(k, d):
    f = DERIVED_F_TBL[k]
    args = (d.get(a, a) for a in DERIVED_A_TBL[k])
    return f(*args)


def import_training_set(path, selected=SELECTED, derived=DERIVED):
    _Xs = [[] for _ in JUDGMENTS]
    _ys = [[] for _ in JUDGMENTS]
    metas = [[] for _ in JUDGMENTS]
    try:
        with open(path, newline='') as f:
            reader = csv.DictReader(f)

            count = 0

            for row in reader:
                count += 1
                cs = [row[j] for j in JUDGMENTS]
                d = dict((k, fromstring(row[k])) for k in METRICS)
                x = [d[k] for k in selected]

                for k in derived:
                    x.append(get_derived(k, d))

                meta = dict((k, row[k]) for k in META)

                for i in range(N_JUDGMENTS):
                    c = cs[i]
                    if c != 'Ignored':
                        _Xs[i].append(x)
                        _ys[i].append(c)
                        metas[i].append(meta)

            logger.info('%d rows' % count)

    except Exception as e:
        logger.warning(str(e))

    data = []
    for i in range(N_JUDGMENTS):
        X = np.array(_Xs[i])
        y = np.array(_ys[i])
        meta = metas[i]
        data.append(Data(X, y, meta))

    return data


def makeMinamiClassifier(path):
    dataset = import_training_set(path, selected=SELECTED_MINAMI,
                                  derived=DERIVED_MINAMI)
    data = dataset[0]
    logger.info('shape=%s |y|=%d' % (data.X.shape, len(data.y)))
    clf = SVC(C=32., kernel='rbf', gamma=8.)
    X = pp.scale(data.X)
    clf.fit(X, data.y)
    return clf


def makeTeraiClassifier(path):
    dataset = import_training_set(path, selected=SELECTED_TERAI,
                                  derived=DERIVED_TERAI)
    data = dataset[1]
    logger.info('shape=%s |y|=%d' % (data.X.shape, len(data.y)))
    clf = KNeighborsClassifier(6, weights='distance', metric='hamming')
    X = pp.scale(data.X)
    clf.fit(X, data.y)
    return clf


def makeMixClassifier(path):
    dataset = import_training_set(path, selected=SELECTED_MIX,
                                  derived=DERIVED_MIX)
    data = dataset[2]
    logger.info('shape=%s |y|=%d' % (data.X.shape, len(data.y)))
    clf = SVC(C=32., kernel='rbf', gamma=8.)
    X = pp.scale(data.X)
    clf.fit(X, data.y)
    return clf


def dump_classifier(clf, path):
    logger.info('dumping classifier into "%s"' % path)
    joblib.dump(clf, path)


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='make loop classifier',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-m', '--model', dest='model', metavar='MODEL',
                        type=str, default='minami',
                        choices=['minami', 'terai', 'mix'], help='model')

    parser.add_argument('-o', '--outfile', dest='outfile', metavar='PATH',
                        type=str, default='a.pkl',
                        help='dump result into PATH')

    parser.add_argument('dpath', metavar='PATH', type=str,
                        help='training dataset')

    args = parser.parse_args()

    mkclf = makeMinamiClassifier

    if args.model == 'minami':
        mkclf = makeMinamiClassifier
    elif args.model == 'terai':
        mkclf = makeTeraiClassifier
    elif args.model == 'mix':
        mkclf = makeMixClassifier
    else:
        logger.warning('"%s" is not supported. using default model' % args.model)

    clf = mkclf(os.path.abspath(args.dpath))

    dump_classifier(clf, os.path.abspath(args.outfile))


# judgment_X:
# Mean accuracy : 0.804000
# Mean precision: 0.811063
# Mean recall   : 0.966476
# Mean F1       : 0.875611

#       |
#       v

# judgment_M:
# Mean accuracy : 0.843000
# Mean precision: 0.847833
# Mean recall   : 0.973127
# Mean F1       : 0.901993

def test():
    dataset = import_training_set('survey-outline/training_set_k4.csv',
                                  selected=SELECTED_MINAMI,
                                  derived=DERIVED_MINAMI)

    # Classifiers

    # clf = SVC()
    # params = {
    #     'C': sp.stats.expon(scale=100),
    #     'gamma': sp.stats.expon(scale=.1),
    #     'kernel': ['rbf'],
    #     'class_weight': ['balanced', None],
    # }

    # clf = RandomForestClassifier(n_estimators=20)
    # params = {
    #     'max_depth': [3, None],
    #     'max_features'     : sp.stats.randint(1, 11),
    #     'min_samples_split': sp.stats.randint(1, 11),
    #     'min_samples_leaf' : sp.stats.randint(1, 11),
    #     'bootstrap': [True, False],
    #     'criterion': ['gini', 'entropy'],
    # }

    # clf = model_selection.RandomizedSearchCV(clf, params, n_iter=20)

    # clf = KNeighborsClassifier(9, weights='distance', metric='hamming')
    clf = SVC(C=32., kernel='rbf', gamma=8.)
    # clf = SVC(C=2., kernel='rbf', gamma=8.)
    # clf = AdaBoostClassifier(n_estimators=15)
    # clf = SVC(C=512., kernel='rbf', gamma=0.125)
    # clf = KNeighborsClassifier(6, weights='distance', metric='hamming')

    T = 10

    np.random.seed(0)

    data = dataset[0]  # Minami
    # data = dataset[1] # Terai
    # data = dataset[2] # Merged

    logger.info('shape=%s |y|=%d' % (data.X.shape, len(data.y)))

    X = data.X

    # Preprocessing

    X = pp.scale(X)

    # scaler = pp.MinMaxScaler()
    # X = scaler.fit_transform(X)

    # Feature Selection

    # X = SelectKBest(f_classif, k=2).fit_transform(X, data.y)

    # c = ExtraTreesClassifier()
    # c = c.fit(X, data.y)
    # model = SelectFromModel(c, prefit=True)
    # X = model.transform(X)

    # lsvc = LinearSVC(C=0.01, penalty="l1", dual=False).fit(X, data.y)
    # model = SelectFromModel(lsvc, prefit=True)
    # X = model.transform(X)

    logger.info('shape=%s' % (X.shape,))

    # Evaluation

    N = 100

    accs = 0.
    precs = 0.
    recs = 0.
    f1s = 0.

    for n in range(N):

        indices = np.random.permutation(len(X))

        X_train = X[indices[:-T]]
        y_train = data.y[indices[:-T]]

        X_test = X[indices[-T:]]
        y_test = data.y[indices[-T:]]

        clf.fit(X_train, y_train)

        # print(clf.best_estimator_)

        y_pred = clf.predict(X_test)

        print('Predicted: %s' % y_pred)
        print('Actual   : %s' % y_test)

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, pos_label='Kernel')
        rec = recall_score(y_test, y_pred, pos_label='Kernel')
        f1 = f1_score(y_test, y_pred, pos_label='Kernel')

        accs += acc
        precs += prec
        recs += rec
        f1s += f1

        print('[%d]' % n)
        print('  Accuracy : %f' % acc)
        print('  Precision: %f' % prec)
        print('  Recall   : %f' % rec)
        print('  F1       : %f' % f1)

    print
    b = float(N)
    print('Mean accuracy : %f' % (accs/b))
    print('Mean precision: %f' % (precs/b))
    print('Mean recall   : %f' % (recs/b))
    print('Mean F1       : %f' % (f1s/b))


if __name__ == '__main__':
    # test()
    main()
