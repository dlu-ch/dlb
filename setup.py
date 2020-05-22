# SPDX-License-Identifier: LGPL-3.0-or-later
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
import zipfile
import shutil
import setuptools
sys.path.insert(0, os.path.abspath('build'))
sys.path.insert(0, os.path.abspath('src'))
import dlb.fs
import version_from_repo


def copy_src_tree(*, src_path, dst_path):
    if dst_path.native.raw.exists():
        shutil.rmtree(dst_path.native)
    for p in src_path.list(name_filter=r'.+\.py', recurse_name_filter=r''):
        q = dst_path / p[1:]
        q[:-1].native.raw.mkdir(exist_ok=True, parents=True)
        shutil.copy(src=str(p.native), dst=str(q.native))


def replace_version(*, src_path, version, version_info):
    version_path = src_path / 'dlb/version.py'

    with version_path.native.raw.open('rb') as f:
        content = f.read()

    regex = re.compile(br'\n__version__ = [^\r\n]+')
    content, n = regex.subn(f"\n__version__ = {version!r}".encode(), content)
    assert n == 1, '__version__ line not found'

    regex = re.compile(br'\nversion_info = [^\r\n]+')
    version_info_str = '({})'.format(', '.join(str(c) for c in version_info))
    content, n = regex.subn(f"\nversion_info = {version_info_str}".encode(), content)
    assert n == 1, 'version_info line not found'

    with version_path.native.raw.open('wb') as f:
        f.write(content)


def zip_modified_src_tree(*, src_path, zip_path):
    zip_path[:-1].native.raw.mkdir(exist_ok=True, parents=True)
    try:
        zip_path.native.raw.unlink()
    except FileNotFoundError:
        pass
    with zipfile.ZipFile(zip_path.native, 'w') as zip:
        for p in src_path.list(name_filter=r'.+\.py', recurse_name_filter=r''):
            zip.write(p.native, arcname=p.relative_to(src_path).as_string())


dist_path = dlb.fs.Path('dist/')
if dist_path.native.raw.exists():
    shutil.rmtree(dist_path.native)
dist_path.native.raw.mkdir(exist_ok=True, parents=True)

out_path = dlb.fs.Path('build/out/')
dst_path = out_path / 'build/'
if dst_path.native.raw.exists():
    shutil.rmtree(dst_path.native)

modified_src_path = out_path / 'gsrc/'

version, version_info, _ = version_from_repo.get_version()
copy_src_tree(src_path=dlb.fs.Path('src/'), dst_path=modified_src_path)
replace_version(src_path=modified_src_path, version=version, version_info=version_info)
zip_modified_src_tree(src_path=modified_src_path, zip_path=out_path / 'dlb.zip')
shutil.copy(src=(out_path / 'dlb.zip').native, dst=(dist_path / f'dlb-{version}.zip').native)

setuptools.setup(
    name='dlb',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version,

    description='A Pythonic build tool',
    long_description=(
        "dlb is a Pythonic build tool that does not try to mimic Make but brings the benefits of "
        "object-oriented languages to the build process. It is inspired by djb's redo."
    ),

    # The project's main homepage.
    url='https://github.com/dlu-ch/dlb',

    # Author details
    author='dlu-ch',
    author_email='dlu-ch@users.noreply.github.com',

    # Choose your license
    license='LGPLv3+',

    # See https://pypi.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Operating System :: OS Independent',
        'Environment :: Console',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

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
    package_dir={'': modified_src_path.as_string().rstrip('/')},

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=setuptools.find_packages(where=modified_src_path.as_string().rstrip('/')),

    py_modules=[p[-2:].as_string()[:-3] for p in (modified_src_path / 'dlb_contrib/').list(name_filter=r'.*\.py')],

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
    # https://packaging.python.org/specifications/entry-points/
    entry_points={
        'console_scripts': ['dlb=dlb.launcher:main'],
    },
)
