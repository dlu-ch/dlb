# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Version of dlb. This entire file is meant to be replaced when dlb is packaged.
See also get_version_from_git() in Sphinx' conf.py.
This is an implementation detail - do not import it unless you know what you are doing."""

__version__ = '?'  # this is replaced by a str according to PEP 440 (e.g. '1.2.3.dev30+317f') when packaged
