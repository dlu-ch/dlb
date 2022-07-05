# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2022 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Usage example:
#
#    python3 check_skipped_log_for_invalid_reasons.py \
#       build/out/test/skipped.log 'requires MS Windows' 'requires POSIX filesystem'

import sys
import re
import ast

LINE_REGEX = re.compile(r'\A(?P<test>[a-z][a-z0-9_.]*( \([A-Za-z][A-Za-z0-9_.]*\))?) \.\.\. skipped (?P<reason>.+)\Z')
assert LINE_REGEX.fullmatch("test_ignores_extension (test_msvc.CppTest) ... skipped 'requires msvc'")
assert LINE_REGEX.fullmatch("test_fails_with_python2.bash ... skipped 'requires Python 2'")

skip_log = sys.argv[1]
valid_skip_reasons = set(sys.argv[2:])

tests_by_skip_reasons = {}
with open(skip_log, 'r') as f:
    for i, line in enumerate(f):
        try:
            m = LINE_REGEX.fullmatch(line.rstrip())
            skip_reason = ast.literal_eval(m['reason'])
            if not isinstance(skip_reason, str):
                raise TypeError
            test = m['test']
        except (KeyError, SyntaxError, TypeError):
            raise ValueError(f'invalid line {i + 1}: {line!r}') from None
        tests = tests_by_skip_reasons.get(skip_reason, set())
        tests.add(test)
        tests_by_skip_reasons[skip_reason] = tests

skip_reasons = set(tests_by_skip_reasons)
invalid_skip_reasons = skip_reasons - valid_skip_reasons

if invalid_skip_reasons:
    tests = set()
    for r in invalid_skip_reasons:
        tests |= tests_by_skip_reasons[r]
    tests = sorted(tests)

    reasons = ', '.join(f'{r!r}' for r in sorted(invalid_skip_reasons))

    raise ValueError(
        f'at least one test skipped with invalid skip reason: {reasons}'
        '\n  | '.join(t for t in [''] + tests)
    )
