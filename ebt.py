#!/usr/bin/env python3

'''
  A driver script for CCA/EBT container image

  Copyright 2013-2018 RIKEN
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

import os
import sys
import time
from datetime import datetime, timedelta
from subprocess import Popen, run
from threading import Thread
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

IMAGE_NAME = 'ebtxhpc/cca'

#

DATA_DIR_NAME = '_EBT_'
DEFAULT_SRV_PORT = 18000

CCA_HOME = '/opt/cca'
CCA_VAR = '/var/lib/cca'
PROJS_DIR = CCA_VAR+'/projects'
CCA_LOG_DIR = '/var/lib/cca/log'
WWW_DIR = '/var/www'
SRV_CMD = '/usr/local/bin/supervisord'


CONTAINER_CMD = 'docker'

TIMEOUT = 5
BUFSIZE = 0  # unbuffered

STAT_NAME = 'status'
LOG_DIR_NAME = 'log'

# WIN_HOST_FLAG = True
WIN_HOST_FLAG = sys.platform.startswith('win')
LINUX_HOST_FLAG = sys.platform == 'linux'

# timezone

TZ = None

if time.timezone != 0:
    SIGN = '+' if time.timezone > 0 else '-'

    STDOFFSET = timedelta(seconds=-time.timezone)
    if time.daylight:
        DSTOFFSET = timedelta(seconds=-time.altzone)
    else:
        DSTOFFSET = STDOFFSET

    dt = datetime.now()
    tt = (dt.year, dt.month, dt.day,
          dt.hour, dt.minute, dt.second,
          dt.weekday(), 0, 0)
    stamp = time.mktime(tt)
    tt = time.localtime(stamp)

    isdst = tt.tm_isdst > 0

    tzname = None
    offset = 0

    if isdst:
        tzname = time.tzname[1]
        offset = DSTOFFSET
    else:
        tzname = time.tzname[0]
        offset = STDOFFSET

    TZ = f'{tzname}{SIGN}{offset}'

###


def progress(proc, stat_path, timeout=TIMEOUT):
    stat_mtime = None

    print('\nmonitoring thread started.')

    while True:
        try:
            st = os.stat(stat_path)
            if st.st_mtime != stat_mtime and st.st_size > 0:
                with open(stat_path, 'r') as f:
                    mes = f.read()
                    print(f'[{mes}]')

                stat_mtime = st.st_mtime

        except OSError:
            pass

        if proc.poll() is not None:
            break

    proc.wait()
    if proc.returncode > 0:
        print('execution failed: {}'.format(proc.returncode))


def check_path(dpath):
    dpath = os.path.abspath(dpath)

    if not os.path.exists(dpath):
        print(f'"{dpath}": not found')
        return None

    return dpath


def get_proj_id(dpath):
    return os.path.basename(dpath)


def get_proj_path(dpath):
    proj_id = get_proj_id(dpath)
    proj_path = f'{PROJS_DIR}/{proj_id}'
    return proj_path


def get_container_name(subcmd_name, proj_id):
    name = f'{subcmd_name}_{proj_id}'
    return name


def get_mongo_volume_name(subcmd_name, proj_id):
    name = f'vol_mongo_{subcmd_name}_{proj_id}'
    return name


def get_image_name(image_name, devel=False):
    suffix = ''
    if devel:
        suffix = ':devel'
    image = image_name+suffix
    return image


def get_container_mem():
    cmd = f'{CONTAINER_CMD} info --format "{{{{json .MemTotal}}}}"'
    m = None
    try:
        r = run(cmd, shell=True, capture_output=True, text=True)
        r.check_returncode()
        m = int(r.stdout.strip())
    except Exception as e:
        print('[ERROR] failed to get container memory: {}'.format(str(e)))
    return m


def check_mem(mem_gb):
    container_mem = get_container_mem()
    b = True
    if container_mem is not None:
        mem = mem_gb * 1000000000
        container_mem_gb = container_mem / 1000000000
        if mem > container_mem:
            print(f'[WARNING] specified memory amount'
                  f' ({mem_gb}GB) exceeds container\'s ({container_mem_gb:.2f}GB)')
            b = False
    else:
        b = False
    return b


def run_cmd(subcmd_name, dpath, mem, dry_run=False, devel=False, keep_fb=False,
            all_roots=False, all_sps=False, all_calls=False,
            html=False, tree_url=None, desc_url=None, desc_ext=None,
            debug=True,
            image=IMAGE_NAME):

    if not check_mem(mem):
        print('aborted')
        exit(1)

    dpath = check_path(dpath)

    if dpath is None:
        return

    dest_root = os.path.join(dpath, DATA_DIR_NAME)

    if not dry_run:
        if os.path.exists(dest_root):
            print(f'You are about to overwrite "{dest_root}".')
            while True:
                a = input('Do you want to proceed (y/n)? ')
                if a == 'y':
                    break
                elif a == 'n':
                    return

        else:
            try:
                os.makedirs(dest_root)
            except Exception as e:
                print(f'"{dest_root}": faild to create: {e}')
                return

    proj_path = get_proj_path(dpath)

    subcmd_path = f'{CCA_HOME}/{subcmd_name}'
    subcmd = subcmd_path
    subcmd += f' -m {mem}'

    if keep_fb:
        subcmd += ' -k'

    if all_roots:
        subcmd += ' -r'

    if all_sps:
        subcmd += ' -s'

    if all_calls:
        subcmd += ' -c'

    if html:
        subcmd += ' --html'

    if tree_url:
        subcmd += f' --tree-url {tree_url}'

    if desc_url:
        subcmd += f' --desc-url {desc_url}'

    if desc_ext:
        subcmd += f' --desc-ext {desc_ext}'

    if debug:
        subcmd += ' -d'

    subcmd += f' {proj_path}'

    log_dir = os.path.join(dest_root, LOG_DIR_NAME)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            print(f'"{log_dir}": faild to create: {e}')
            return

    vol_opt = f'-v "{dpath}:{proj_path}"'
    vol_opt += f' -v "{log_dir}:{CCA_LOG_DIR}"'

    run_cmd = f'{CONTAINER_CMD} run'
    run_cmd += ' --rm'
    run_cmd += ' -t'

    if TZ:
        run_cmd += f' -e "TZ={TZ}"'

    if LINUX_HOST_FLAG:
        run_cmd += f' --user {os.geteuid()}:{os.getegid()}'

    run_cmd += f' {vol_opt}'
    run_cmd += f' {get_image_name(image, devel=devel)} {subcmd}'

    stat_path = os.path.join(dest_root, STAT_NAME)

    print(run_cmd)

    if not dry_run:

        if os.path.exists(stat_path):
            # print(f'removing "{stat_path}"...')
            os.remove(stat_path)

        try:
            proc = Popen(run_cmd, bufsize=BUFSIZE, shell=True,
                         universal_newlines=True)

            th = Thread(target=progress, args=(proc, stat_path))
            th.start()
            th.join()

        except (KeyboardInterrupt, SystemExit):
            print('interrupted.')

        except OSError as e:
            print(f'execution failed: {e}')


def mongo_db_exists(mongo_path):
    p = os.path.join(mongo_path, 'db', 'loop_survey.ns')
    b = os.path.exists(p)
    return b


def restore_mongo_db(vol_name, mongo_path, dry_run=False, force=False,
                     image=IMAGE_NAME):
    if not mongo_db_exists(mongo_path):
        return

    if force:
        print(f'restoring state from "{mongo_path}"...')
    else:
        while True:
            a = input(f'Do you want to restore state from "{mongo_path}" (y/n)? ')
            if a == 'y':
                break
            elif a == 'n':
                return

    run_cmd = f'{CONTAINER_CMD} run --rm -t'
    if TZ:
        run_cmd += f' -e "TZ={TZ}"'
    run_cmd += f' -v "{vol_name}:{CCA_VAR}/mongo"'
    run_cmd += f' -v "{mongo_path}:/tmp/mongo"'
    guest_cmd = f'/bin/bash -c "rm -rf {CCA_VAR}/mongo/db; cp -a /tmp/mongo/db {CCA_VAR}/mongo/"'
    run_cmd += f' {get_image_name(image)} {guest_cmd}'
    print(run_cmd)
    if not dry_run:
        try:
            run(run_cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')


def save_mongo_db(vol_name, mongo_path, dry_run=False, force=False,
                  image=IMAGE_NAME):
    if force:
        print(f'saving state to "{mongo_path}"...')
    else:
        while True:
            a = input(f'Do you want to save state to "{mongo_path}" (y/n)? ')
            if a == 'y':
                break
            elif a == 'n':
                return

    run_cmd = f'{CONTAINER_CMD} run --rm -t'
    if TZ:
        run_cmd += f' -e "TZ={TZ}"'
    run_cmd += f' -v "{vol_name}:{CCA_VAR}/mongo"'
    run_cmd += f' -v "{mongo_path}:/tmp/mongo"'
    guest_cmd = f'/bin/bash -c "rm -rf /tmp/mongo/db; cp -a {CCA_VAR}/mongo/db /tmp/mongo/"'
    run_cmd += f' {get_image_name(image)} {guest_cmd}'
    print(run_cmd)
    if not dry_run:
        try:
            run(run_cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')


def run_tv_srv(dpath, port=DEFAULT_SRV_PORT, dry_run=False, devel=False,
               restore=False, image=IMAGE_NAME):
    subcmd_name = 'treeview'
    dpath = check_path(dpath)

    if dpath is None:
        return

    dest_root = os.path.join(dpath, DATA_DIR_NAME)

    mongo_path = os.path.join(dest_root, 'mongo')
    mongo_db_path = os.path.join(mongo_path, 'db')
    try:
        if not os.path.exists(mongo_db_path):
            os.makedirs(mongo_db_path)
    except Exception as e:
        print(f'"{mongo_db_path}": failed to create: {e}')
        return

    proj_id = get_proj_id(dpath)
    proj_path = get_proj_path(dpath)

    outline_path = os.path.join(dest_root, 'outline', proj_id)
    metrics_path = os.path.join(dest_root, 'metrics', proj_id)
    target_path = os.path.join(dest_root, 'target', proj_id)
    topic_path = os.path.join(dest_root, 'topic')
    readme_links_path = os.path.join(dest_root, 'readme_links')
    data_path_base = WWW_DIR+'/outline/treeview/'

    log_dir = os.path.join(dpath, DATA_DIR_NAME, LOG_DIR_NAME)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            print(f'"{log_dir}": faild to create: {e}')
            return

    vol_opt = f'-v "{dpath}:{proj_path}"'
    vol_opt += f' -v "{outline_path}:{data_path_base}outline/{proj_id}"'
    vol_opt += f' -v "{metrics_path}:{data_path_base}metrics/{proj_id}"'
    vol_opt += f' -v "{target_path}:{data_path_base}target/{proj_id}"'
    vol_opt += f' -v "{topic_path}:{data_path_base}topic"'
    vol_opt += f' -v "{readme_links_path}:{data_path_base}readme_links"'
    if WIN_HOST_FLAG and restore:
        vol_name = get_mongo_volume_name(subcmd_name, proj_id)
        restore_mongo_db(vol_name, mongo_path, dry_run=dry_run, force=False)
        vol_opt += f' -v "{vol_name}:{CCA_VAR}/mongo"'
    else:
        vol_opt += f' -v "{mongo_path}:{CCA_VAR}/mongo"'

    name = get_container_name(subcmd_name, proj_id)

    port_opt = f'-p {port}:80'

    run_cmd = f'{CONTAINER_CMD} run'
    run_cmd += ' -d'
    run_cmd += ' --rm'

    if LINUX_HOST_FLAG:
        run_cmd += ' --privileged'

    run_cmd += f' {port_opt}'
    run_cmd += f' --name {name}'

    if TZ:
        run_cmd += f' -e "TZ={TZ}"'

    if LINUX_HOST_FLAG:
        run_cmd += f' -e "HOST_UID={os.geteuid()}"'
        run_cmd += f' -e "HOST_GID={os.getegid()}"'

    run_cmd += f' {vol_opt}'

    srv_cmd = SRV_CMD
    if LINUX_HOST_FLAG:
        srv_cmd += ' -c /etc/supervisord-linux.conf'

    run_cmd += f' {get_image_name(image, devel=devel)} {srv_cmd}'

    print(run_cmd)
    print(f'\nport={port}')

    if not dry_run:
        try:
            run(run_cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')


def stop_tv_srv(dpath, dry_run=False, devel=False, save=False):
    subcmd_name = 'treeview'
    dpath = check_path(dpath)

    if dpath is None:
        return

    proj_id = get_proj_id(dpath)

    name = get_container_name(subcmd_name, proj_id)

    shutdown_cmd = f'{CONTAINER_CMD} exec -t {name} {CCA_HOME}/scripts/shutdown_mongo.py'

    stop_cmd = f'{CONTAINER_CMD} stop {name}'

    print(shutdown_cmd)
    print(stop_cmd)

    if not dry_run:
        try:
            run(shutdown_cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')
        try:
            run(stop_cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')

    if WIN_HOST_FLAG and save:
        vol_name = get_mongo_volume_name(subcmd_name, proj_id)
        dest_root = os.path.join(dpath, DATA_DIR_NAME)
        mongo_path = os.path.join(dest_root, 'mongo')
        save_mongo_db(vol_name, mongo_path, dry_run=dry_run, force=False)


def update(args):
    cmd = f'{CONTAINER_CMD} pull {get_image_name(args.image, devel=args.devel)}'
    print(cmd)
    if not args.dry_run:
        try:
            run(cmd, shell=True)
        except OSError as e:
            print(f'execution failed: {e}')


def opcount(args):
    run_cmd('opcount', args.proj_dir, args.mem, dry_run=args.dry_run,
            keep_fb=args.keep_fb, devel=args.devel, image=args.image)


def outline(args):
    all_roots = args.all_roots or args.all
    all_sps = args.all_sps or args.all
    all_calls = args.all_calls or args.all
    run_cmd('outline', args.proj_dir, args.mem, dry_run=args.dry_run,
            keep_fb=args.keep_fb, devel=args.devel,
            all_roots=all_roots,
            all_sps=all_sps,
            all_calls=all_calls,
            html=args.html,
            tree_url=args.tree_url,
            desc_url=args.desc_url,
            desc_ext=args.desc_ext,
            image=args.image)


def treeview_start(args):
    run_tv_srv(args.proj_dir, port=args.port, dry_run=args.dry_run,
               devel=args.devel, restore=args.restore, image=args.image)


def treeview_stop(args):
    stop_tv_srv(args.proj_dir, dry_run=args.dry_run, devel=args.devel,
                save=args.save)


def main():
    parser = ArgumentParser(description='CCA/EBT driver',
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument('-m', '--mem', dest='mem', metavar='GB', type=int,
                        choices=[2, 4, 8, 16, 32, 48, 64],
                        help='available memory (GB)', default=4)

    parser.add_argument('-n', '--dry-run', dest='dry_run', action='store_true',
                        help='only print container commands')

    parser.add_argument('-i', '--image', dest='image', type=str,
                        metavar='IMAGE', default=IMAGE_NAME,
                        help='specify container image')

    parser.add_argument('-x', '--experimental', dest='devel',
                        action='store_true', help='use experimental image')

    subparsers = parser.add_subparsers(title='subcommands')

    parser_update = subparsers.add_parser('update',
                                          description='Update docker image of CCA/EBT',
                                          formatter_class=ArgumentDefaultsHelpFormatter)

    parser_update.set_defaults(func=update)

    parser_opcount = subparsers.add_parser('opcount',
                                           description='Count operations in Fortran programs',
                                           formatter_class=ArgumentDefaultsHelpFormatter)

    parser_opcount.add_argument('proj_dir', type=str, metavar='DIR',
                                help='directory that contains subject programs')

    parser_opcount.add_argument('-k', '--keep-fb', dest='keep_fb',
                                action='store_true', help='keep FB')

    parser_opcount.set_defaults(func=opcount)

    parser_outline = subparsers.add_parser('outline',
                                           description='Outline Fortran programs',
                                           formatter_class=ArgumentDefaultsHelpFormatter)

    parser_outline.add_argument('proj_dir', type=str, metavar='DIR',
                                help='directory that contains subject programs')

    parser_outline.add_argument('-k', '--keep-fb', dest='keep_fb',
                                action='store_true', help='keep FB')

    parser_outline.add_argument('-a', '--all', dest='all', action='store_true',
                                help=('allow all subprograms and calls to be shown'
                                      ' (equivalent to "-r -s -c")'))

    parser_outline.add_argument('-r', '--all-roots', dest='all_roots', action='store_true',
                                help='allow subprograms to be shown as roots')

    parser_outline.add_argument('-s', '--all-sps', dest='all_sps', action='store_true',
                                help='allow loop-free subprograms to be shown')

    parser_outline.add_argument('-c', '--all-calls', dest='all_calls', action='store_true',
                                help='allow all calls to be shown')

    parser_outline.add_argument('--html', dest='html', action='store_true',
                                help='generate HTML files from outlines')

    parser_outline.add_argument('--tree-url', dest='tree_url', type=str, metavar='URL',
                                help='specify URL for trees in generated HTML files')

    parser_outline.add_argument('--desc-url', dest='desc_url', type=str, metavar='URL',
                                help='specify URL for description links in generated HTML files')

    parser_outline.add_argument('--desc-ext', type=str, metavar='EXT',
                                help=('specify extension for description links'
                                      ' in generated HTML files'))

    parser_outline.set_defaults(func=outline)

    parser_tv = subparsers.add_parser('treeview')

    subparsers_tv = parser_tv.add_subparsers(title='subsubcommands')

    parser_tv_start = subparsers_tv.add_parser('start',
                                               formatter_class=ArgumentDefaultsHelpFormatter)

    parser_tv_start.add_argument('proj_dir', type=str, metavar='DIR',
                                 help='directory that contains subject programs')

    parser_tv_start.add_argument('-p', '--port', dest='port', type=int,
                                 default=DEFAULT_SRV_PORT, metavar='PORT',
                                 help='service port number')

    parser_tv_start.add_argument('--restore', dest='restore',
                                 action='store_true',
                                 help='restore viewer state (Windows host only)')

    parser_tv_start.set_defaults(func=treeview_start)

    parser_tv_stop = subparsers_tv.add_parser('stop',
                                              formatter_class=ArgumentDefaultsHelpFormatter)

    parser_tv_stop.add_argument('proj_dir', type=str, metavar='DIR',
                                help='directory that contains subject programs')

    parser_tv_stop.add_argument('--save', dest='save', action='store_true',
                                help='save viewer state (Windows host only)')

    parser_tv_stop.set_defaults(func=treeview_stop)

    args = parser.parse_args()

    if args.devel:
        print('[DEVELOPMENT]')

    try:
        args.func(args)
    except Exception:
        parser.print_help()


if __name__ == '__main__':
    main()
