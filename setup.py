# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject

Run with build-package.bash
"""

import sys
import re
import os.path
import subprocess
import setuptools
import shutil
sys.path.insert(0, os.path.abspath('src'))
import dlb.fs
del sys.path[0]


def get_version_from_git():
    s = subprocess.check_output(['git', 'describe', '--match', 'v*', '--long', '--abbrev=40']).decode().strip()
    m = re.compile(r'v(?P<version>[0-9.]+)-(?P<n>[0-9]+)-g(?P<hash>[0-9a-f]+)').fullmatch(s)
    if m is None:
        print("git describe: {}".format(repr(s)))

    last_version = m.group('version')
    commits_since_tag = int(m.group('n'), base=10)
    commit_hash = m.group('hash')

    if commits_since_tag > 0:
        # PEP 440
        version = '{}.dev{}+{}'.format(last_version, commits_since_tag, commit_hash[:4])
    else:
        version = last_version

    return version


def build_modified_src_tree(version):
    dst_path = dlb.fs.Path('out/gsrc/')
    if dst_path.native.raw.exists():
        shutil.rmtree(dst_path.native)

    src_path = dlb.fs.Path('src/')
    for p in src_path.list(name_filter=r'.+\.py', recurse_name_filter=r''):
        q = dst_path / p[1:]
        q[:-1].native.raw.mkdir(exist_ok=True, parents=True)
        if p == src_path / 'dlb/version.py':
            with p.native.raw.open('rb') as f:
                content = f.read()
            content = content.replace(b"__version__ = '?'", f"__version__ = {version!r}".encode())
            with q.native.raw.open('wb') as f:
                f.write(content)
        else:
            shutil.copy(src=str(p.native), dst=str(q.native))


dist_path = dlb.fs.Path('dist/')
if dist_path.native.raw.exists():
    shutil.rmtree(dist_path.native)

dst_path = dlb.fs.Path('build/')
if dst_path.native.raw.exists():
    shutil.rmtree(dst_path.native)

version = get_version_from_git()
build_modified_src_tree(version)


setuptools.setup(
    name='dlb',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version,

    description='A Pythonic build tool',
    long_description=(
        "dlb is a Pythonic build tool which does not try to mimic Make, but brings the benefits of "
        "object-oriented languages to the build process. It is inspired by djb's redo."
    ),

    # The project's main homepage.
    url='https://github.com/dlu-ch/dlb',

    # Author details
    author='dlu-ch',
    author_email='dlu-ch@users.noreply.github.com',

    # Choose your license
    license='GPLv3',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],

    zip_safe=True,

    # What does your project relate to?
    keywords='build development',

    # https://docs.python.org/3/distutils/setupscript.html#listing-whole-packages
    package_dir={'': 'out/gsrc'},

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=setuptools.find_packages(where='out/gsrc'),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={},

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={},

    scripts=['script/dlb']
)
