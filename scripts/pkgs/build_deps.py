#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import importlib
import os
import sys
import tempfile

from pkgs.constants import (PREFIX, SW, isosx, iswindows, mkdtemp, pkg_ext,
                            set_build_dir, set_current_source, set_tdir)
from pkgs.download_sources import download, filename_for_dep
from pkgs.utils import (create_package, extract_source, fix_install_names,
                        install_package, python_build, rmtree, run_shell,
                        set_title, simple_build)

python_deps = 'pygments'.split()

all_deps = (
    # Build tools
    'pkg-config cmake '
    # Python and its dependencies
    'zlib bzip2 expat sqlite libffi openssl ncurses readline python '
    # Freetype and its dependencies
    'libpng iconv pcre glib graphite freetype fontconfig '
    # Miscellaneous dependencies
    'harfbuzz glfw '
).strip().split() + python_deps

if isosx:
    all_deps.remove('bzip2')
    all_deps.remove('iconv')
    all_deps.remove('pcre')
    all_deps.remove('glib')
    all_deps.remove('graphite')
    all_deps.remove('fontconfig')
    all_deps.remove('freetype')
    all_deps.remove('ncurses')
    all_deps.remove('readline')
else:
    all_deps.remove('cmake')
    all_deps.remove('pkg-config')
    all_deps.append('xkbcommon')
    all_deps.append('libxml2')  # needed for wayland
    all_deps.append('wayland')
    all_deps.append('wayland-protocols')


def ensure_clear_dir(dest_dir):
    if os.path.exists(dest_dir):
        rmtree(dest_dir)
    os.makedirs(dest_dir)


def pkg_path(dep):
    return os.path.join(SW, dep + '.' + pkg_ext)


def has_pkg(dep):
    return os.path.exists(pkg_path(dep))


def install_pkgs(other_deps=all_deps, dest_dir=PREFIX):
    other_deps = tuple(other_deps)
    if other_deps:
        print('Installing %d previously compiled packages:' % len(other_deps), end=' ')
        sys.stdout.flush()
        for dep in other_deps:
            pkg = pkg_path(dep)
            if os.path.exists(pkg):
                print(dep, end=', ')
                sys.stdout.flush()
                install_package(pkg, dest_dir)
        print()
        sys.stdout.flush()


def build(dep, args, dest_dir):
    set_title('Building ' + dep)
    owd = os.getcwdu()
    set_current_source(filename_for_dep(dep))
    output_dir = todir = mkdtemp(prefix=dep + '-')
    set_build_dir(output_dir)
    try:
        m = importlib.import_module('pkgs.' + dep)
    except ImportError:
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), dep + '.py')):
            raise
        m = None
    tsdir = extract_source()
    try:
        if hasattr(m, 'main'):
            m.main(args)
        else:
            if dep in python_deps:
                python_build()
                output_dir = os.path.join(output_dir, os.path.relpath(PREFIX, '/'))
            else:
                simple_build()
        if isosx:
            fix_install_names(m, output_dir)
    except Exception:
        import traceback
        traceback.print_exc()
        print('\nDropping you into a shell')
        sys.stdout.flush(), sys.stderr.flush()
        run_shell()
        raise SystemExit(1)
    create_package(m, output_dir, pkg_path(dep))
    install_package(pkg_path(dep), dest_dir)
    if hasattr(m, 'post_install_check'):
        m.post_install_check()
    os.chdir(owd)
    rmtree(todir)
    rmtree(tsdir)


def init_env(deps=all_deps, quick_build=False):
    dest_dir = PREFIX
    tdir = tempfile.tempdir if iswindows else os.path.join(tempfile.gettempdir(), 't')
    ensure_clear_dir(tdir)
    set_tdir(tdir)
    do_clear = not (quick_build and os.path.exists(dest_dir))
    if do_clear:
        ensure_clear_dir(dest_dir)
        install_pkgs(deps, dest_dir)
    return dest_dir


def main(args):
    deps = args.deps or [d for d in all_deps if not has_pkg(d)]
    if not deps:
        print('All dependencies already built, if you want to re-build, use the --clean option')
        raise SystemExit(0)

    for dep in deps:
        if dep not in all_deps:
            raise SystemExit('%s is an unknown dependency' % dep)

    set_title('Downloading...')
    download(deps)

    other_deps = frozenset(all_deps) - frozenset(deps)
    dest_dir = init_env(other_deps)

    while deps:
        dep = deps.pop(0)
        ok = False
        try:
            build(dep, args, dest_dir)
            ok = True
        finally:
            if not ok:
                deps.insert(0, dep)
            if deps:
                print('Remaining deps:', ' '.join(deps))

    # After a successful build, remove the unneeded sw dir
    rmtree(dest_dir)
