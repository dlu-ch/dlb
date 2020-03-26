import re
import subprocess

# each annotated tag starting with 'v' followed by a decimal digit must match this (after 'v'):
VERSION_REGEX = re.compile(
    r'^'
    r'(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<micro>0|[1-9][0-9]*)'
    r'((?P<post>[abc])(?P<post_number>0|[1-9][0-9]*))?'
    r'$')


def _version_from_describe(describe_word):
    m = re.compile(r'v(?P<version>[0-9a-z.]+)-(?P<n>[0-9]+)-g(?P<hash>[0-9a-f]+)').fullmatch(describe_word)
    if not m:
        raise ValueError("git describe: {}".format(repr(describe_word)))

    last_version = m.group('version')
    commits_since_tag = int(m.group('n'), base=10)
    commit_hash = m.group('hash')

    m = VERSION_REGEX.fullmatch(last_version)
    if not m:
        raise ValueError(f'annotated tag is not a valid version tag: {last_version!r}')

    gd = m.groupdict()
    version_info = (int(gd['major']), int(gd['minor']), int(gd['micro']))
    if gd['post']:
        version_info = version_info + (gd['post'], int(gd['post_number']))

    if commits_since_tag > 0:
        # PEP 440
        version = '{}.dev{}+{}'.format(last_version, commits_since_tag, commit_hash[:4])
    else:
        version = last_version

    return version, version_info


def get_version():
    s = subprocess.check_output(['git', 'describe', '--match', 'v[0-9]*', '--long', '--abbrev=40']).decode()
    return _version_from_describe(s.strip())


assert _version_from_describe('v1.2.3-35-g13afa33') == ('1.2.3.dev35+13af', (1, 2, 3))
assert _version_from_describe('v1.2.3a4-35-g13afa33') == ('1.2.3a4.dev35+13af', (1, 2, 3, 'a', 4))
