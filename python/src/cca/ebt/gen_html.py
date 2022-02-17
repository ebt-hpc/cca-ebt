#!/usr/bin/env python3

'''
  A script for generating HTML files from outlines

  Copyright 2022 Chiba Institute of Technology

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
import json
import itertools
from urllib.request import pathname2url
from html.parser import HTMLParser
import msgpack
import logging

from cca.ccautil.common import setup_logger

logger = logging.getLogger()

HTML_DIR = 'html'

TREE_PREFIX = 'T-'
DESC_PREFIX = 'D-'

TREE_DIR_NAME = 'T'
DESC_DIR_NAME = 'D'

INDENT = 2

TREE_ROOT = f'/{TREE_DIR_NAME}/'
DESC_ROOT = f'/{DESC_DIR_NAME}/'

HTML_TEMPL = '''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>{name:}</title>
<link rel="stylesheet" href="/doc.css">
</head>
<body>
<h1>{name:}</h1>
<ul>
{items:}
</ul>
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
<script>
$(document).ready(function(){{
  $('.call + ul').hide();
    $(".call").click(function(){{
      $('.call + ul').not($(this).next("ul").toggle()).hide();
    }});
}});
</script>
</body>
</html>'''

INDEX_TEMPL = '''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Root nodes</title>
<link rel="stylesheet" href="/doc.css">
</head>
<body>
<h1>Root nodes</h1>
<h2>Programs</h2>
<ul>
{progs:}
</ul>
<h2>Subprograms</h2>
<ul>
{subs:}
</ul>
</body>
</html>'''

CSS = '''
body {
    font-family: Verdana, Arial, Helvetica, sans-serif ;
    font-size: 10pt ;
    line-height: 18pt ;
    color: black;
    background: white ;
    margin: 0 ;
}
h1 {
    text-align:center ;
    font-size: 14pt;
    line-height: 24pt ;
    font-weight: bold;
    color:#000;
    background:#CADFF4;
    padding: 0 ;
    margin: 0 ;
    padding-left: 1ex;
    padding-right: 1ex;
    text-align:center;
}
h2 {
    font-size: 12pt;
    line-height: 16pt;
    font-size: 110%;
    font-weight: bold;
    color: #003399;
    background:#CADFF4;
    margin-bottom:5px;
    padding-left: 1ex;
    padding-right: 1ex;
}

h3, h4, h5 {
    font-size: 100%;
    font-weight: bold;
    margin-bottom:3px;
}
ul { list-style-type: ""; }
A:link { color: rgb(0, 0, 255) }
A:hover { color: rgb(255, 0, 0) }
pre {
    font-family: monospace;
    font-size: 10pt ;
    line-height: 14pt ;
    margin-top: 1 ;
    margin-bottom: 1 ;
    margin-left: 5ex ;
    }
.centered {
    text-align: center;
}
.code {
    font-style: normal;
    font-size: 90%;
}
.call {
    background-color: #fff;
    color: #000;
    border-style: solid;
    border-width: thin; 
    border-color: #aaa; 
}
.call:hover {
    background-color: #efffef;
    cursor: pointer;
}
.desc {
    font-style: normal;
    color: #a1522d;
    font-size: 90%;
}
.desc > a:link {
    color: #a1522d;
}
.external {
    font-style: italic;
    font-size: 90%;
}
'''


def ensure_dir(d):
    b = True
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception as e:
            logger.warning(str(e))
            b = False
    return b


def tree_path_to_url(path):
    path = os.path.join(os.path.dirname(path),
                        TREE_PREFIX+os.path.basename(path))
    u = TREE_ROOT + pathname2url(path)
    return u


def desc_path_to_url(path):
    path = os.path.join(os.path.dirname(path),
                        DESC_PREFIX+os.path.basename(path))
    u = DESC_ROOT + pathname2url(path)
    return u


class HTMLScanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self._count = 0

    def reset(self):
        super().reset()
        self._count = 0

    def get_indent(self):
        return self._count * INDENT

    def handle_starttag(self, tag, attrs):
        if tag not in ('meta', 'link'):
            self._count += 1

    def handle_endtag(self, tag):
        self._count -= 1


def indent(html):
    scanner = HTMLScanner()
    lines = []
    indent = 0
    for line in html.split('\n'):
        scanner.feed(line)
        scanner.close()
        d_indent = scanner.get_indent()
        # logger.debug(f'{line} -> {d_indent}')
        scanner.reset()

        if d_indent < 0:
            indent += d_indent

        _line = ' '*indent + line
        # logger.debug(f'{_line}')
        lines.append(_line)

        if d_indent > 0:
            indent += d_indent

    html_ = '\n'.join(lines)
    return html_


def dump_css(path):
    if os.path.exists(path):
        logger.warning(f'{path} exists')
    else:
        logger.info(f'dumping CSS into {path}...')
        with open(path, 'w') as f:
            f.write(CSS)


def dump_html(html, path, prefix=''):
    if prefix:
        path = os.path.join(os.path.dirname(path),
                            prefix+os.path.basename(path))
    if os.path.exists(path):
        logger.warning(f'{path} exists')
    else:
        logger.info(f'dumping HTML into {path}...')
        with open(path, 'w') as f:
            if INDENT > 0:
                html = indent(html)
            f.write(html)


def is_main(node):
    cat = node.get('cat', '')
    return cat == 'main-program'


def is_subprogram(node):
    cat = node.get('cat', '')
    return cat.endswith('-subprogram')


def is_call(node):
    return node.get('type', '') == 'call'


class HtmlGenerator(object):
    def __init__(self, ver_dir, out_dir, debug=False):
        self._ver_dir = ver_dir
        self._out_dir = out_dir
        self._debug = debug
        with open(os.path.join(ver_dir, 'path_list.json')) as f:
            self._path_list = json.load(f)
        self._callees_tbl = {}
        self._nid_tbl = {}
        self._node_tbl = {}

    def node_to_str(self, node):
        li = []
        for k, v in node.items():
            if k in ('children', 'aref_ranges', 'other_metrics', 'lmi'):
                pass
            elif k == 'fid':
                try:
                    fpath = self._path_list[int(v)]
                    li.append(f'{k}: {v} -> {fpath}')
                except Exception:
                    li.append(f'{k}: {v} -> ???')
            else:
                li.append(f'{k}: {v}')
        s = '{{{}}}'.format(', '.join(li))
        return s

    def show_node(self, node, indent=0):
        if self._debug:
            ind = indent * ' '
            for k, v in node.items():
                if k in ('children', 'aref_ranges', 'other_metrics', 'lmi'):
                    pass
                elif k == 'fid':
                    try:
                        fpath = self._path_list[int(v)]
                        print(f'{ind}{k}: {v} -> {fpath}')
                    except Exception:
                        print(f'{ind}{k}: {v} -> ???')
                else:
                    print(f'{ind}{k}: {v}')
            print()

    def ensure_abs_path(self, path):
        fpath = os.path.join(self._out_dir, TREE_DIR_NAME, path)
        ensure_dir(os.path.dirname(fpath))
        return fpath

    def path_of_node_fid(self, node):
        fpath = None
        fid = node.get('fid', None)
        if fid is not None:
            try:
                fpath = self._path_list[int(fid)]
            except Exception:
                logger.error(f'failed to get path: fid={fid}')
        else:
            logger.error('failed to get fid: node={}'.format(self.node_to_str(node)))
        return fpath

    def gen_path_of_main(self, node):
        fpath = self.path_of_node_fid(node)
        pu = node.get('pu', None)
        if pu is None:
            fpath = os.path.join(fpath, 'main.html')
        else:
            fpath = os.path.join(fpath, f'{pu}.html')
        return fpath

    def gen_path_of_subprogram(self, node):
        fpath = None
        cat = node.get('cat', None)
        name = node.get('name', None)

        if is_subprogram(node) and cat is not None and name is not None:
            fpath = self.path_of_node_fid(node)
            pu = node.get('pu', '')
            ok = pu != ''
            if cat.endswith('-external-subprogram'):
                if '|' in pu:
                    pul = pu.split('|')
                    ok &= name in pul
                else:
                    ok &= name == pu
                if ok:
                    fpath = os.path.join(fpath, f'{name}.html')
            else:
                if ok:
                    fpath = os.path.join(fpath, f'{pu}-{name}.html')

        return fpath

    def tree_to_html(self, root, name, path):
        items = self.node_to_item(root, path=path, force_all=True)
        html = HTML_TEMPL.format(name=name, items=items)
        return html

    def node_to_item(self, node, path=None, force_all=False):

        ty = node.get('type', '???')
        idx = node.get('idx', None)
        children = node.get('children', [])

        if ty == 'call*':
            code_style = 'external'
        else:
            code_style = 'code'

        code = '''<span class="{}">\n{}\n</span>'''.format(code_style,
                                                           node.get('code',
                                                                    ''))
        desc = ''

        id_attr = ''

        if path is not None:
            code = '<a href="{}">\n{}\n</a>'.format(tree_path_to_url(path),
                                                    code)
            fpath = self.path_of_node_fid(node)
            sl = node.get('sl', -1)
            el = node.get('el', -1)
            code += f'\n&nbsp;[{sl}-{el}:{fpath}]'

            desc_url = desc_path_to_url(path)
            desc = '&nbsp;\n<span class="desc">\n'
            desc += f'<a href={desc_url} target="_blank">\n'
            desc += '[desc]\n</a>\n</span>'

        if idx is None:
            logger.warning('failed to get idx: {}'
                           .format(self.node_to_str(node)))
            id_attr = f' id="id_{idx}"'

        call_flag = is_call(node)

        if path is None or force_all:
            if call_flag and children == []:
                callee = node.get('callee', '')
                children = self.find_callees(callee)

        if call_flag and children:
            node_attr = 'class="node call" name="call"'
        else:
            node_attr = f'class="node" name="{ty}"'

        s = f'<li>\n<span {node_attr}{id_attr}>\n{code}{desc}\n</span>'

        if path is None or force_all:
            if children:
                s += '\n<ul>\n'
                if call_flag:
                    for child in children:
                        p = self.gen_path_of_subprogram(child)
                        s += self.node_to_item(child, path=p) + '\n'
                else:
                    for child in children:
                        s += self.node_to_item(child) + '\n'
                s += '</ul>'
        s += '\n</li>'
        return s

    def proc_tree(self, node, top=False):
        rpath = None
        if is_main(node):
            rpath = self.gen_path_of_main(node)
            fpath = self.ensure_abs_path(rpath)
            name = node.get('pu', None)
            if name is None:
                name = 'main'
            html = self.tree_to_html(node, name, rpath)
            dump_html(html, fpath, prefix=TREE_PREFIX)
            print('-', fpath)
            self.show_node(node)

        elif is_call(node):
            self.show_node(node)
            for c in node.get('children', []):
                print('-', self.gen_path_of_subprogram(c))
                self.show_node(c, indent=2)

        elif is_subprogram(node):
            rpath = self.gen_path_of_subprogram(node)
            fpath = self.ensure_abs_path(rpath)
            html = self.tree_to_html(node, node.get('name', '???'), rpath)
            dump_html(html, fpath, prefix=TREE_PREFIX)
            self.show_node(node)

        for child in node.get('children', []):
            self.proc_tree(child)

        return rpath

    def find_callees(self, callee):
        callees = []
        for nid in self._callees_tbl.get(callee, []):
            nd = self._nid_tbl.get(nid, None)
            if nd is not None:
                logger.debug('{} -> {}:{}'.format(callee,
                                                  nid,
                                                  nd.get('code', '???')))
                callees.append(nd)
        if False and callees == []:
            nd = self._node_tbl.get(callee, None)
            if nd is not None:
                logger.debug('{} -> {}'.format(callee, nd.get('code', '???')))
                callees.append(nd)
        return callees

    def setup_callees_tbl(self, root):
        self._callees_tbl = root.get('callees_tbl', {})
        idl = list(itertools.chain.from_iterable(self._callees_tbl.values()))

        def scan(node):
            if is_subprogram(node):
                name = node.get('name', None)
                if name is not None:
                    self._node_tbl[name] = node
                nid = node.get('id', None)
                if nid in idl:
                    logger.debug('{} -> {}'.format(nid, node.get('code', '???')))
                    self._nid_tbl[nid] = node
            for child in node.get('children', []):
                scan(child)

        scan(root)

    def proc_msg(self, msg_path):
        item_tbl = {'progs': [], 'subs': []}
        with open(msg_path, 'rb') as f:
            t = msgpack.unpack(f, raw=False, strict_map_key=False)
            self.show_node(t)
            self.setup_callees_tbl(t)
            roots = t.get('children', [])
            for root in roots:
                rpath = self.proc_tree(root, top=True)
                if rpath:
                    item = self.node_to_item(root, path=rpath)
                    k = 'progs' if root.get('type', '') == 'main' else 'subs'
                    item_tbl[k].append(item)
        return item_tbl

    def gen(self):
        item_tbl = {'progs': [], 'subs': []}
        for path in self._path_list:
            src_dir = os.path.join(self._ver_dir, path)
            if os.path.exists(src_dir):
                for msg in os.listdir(src_dir):
                    msg_path = os.path.join(src_dir, msg)
                    tbl = self.proc_msg(msg_path)
                    item_tbl['progs'].extend(tbl['progs'])
                    item_tbl['subs'].extend(tbl['subs'])
        index = INDEX_TEMPL.format(progs='\n'.join(item_tbl['progs']),
                                   subs='\n'.join(item_tbl['subs']))
        dump_html(index, os.path.join(self._out_dir, 'index.html'))
        dump_css(os.path.join(self._out_dir, 'doc.css'))


def gen_html(ver_dir, html_dir, debug=False):
    ensure_dir(html_dir)
    g = HtmlGenerator(ver_dir, html_dir, debug=debug)
    g.gen()


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(description='Generate HTML files from outlines',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('ver_dir', type=str, metavar='DIR',
                        help='set directory that version outline resides')

    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help='enable debug printing')

    parser.add_argument('-o', '--html-dir', type=str, metavar='DIR',
                        default=HTML_DIR, help='set output directory')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    setup_logger(logger, log_level)

    gen_html(args.ver_dir, args.html_dir, debug=args.debug)


if __name__ == '__main__':
    pass
