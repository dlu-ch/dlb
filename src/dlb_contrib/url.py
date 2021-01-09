# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2021 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Map identifier string to URLs bijectively by patterns with placeholders, and build URL regex from
typical subexpressions."""

# URI: <https://tools.ietf.org/html/rfc3986>
# URL vs URL: <https://en.wikipedia.org/wiki/Uniform_Resource_Name#URIs,_URNs,_and_URLs>
#
# Usage example:
#
#   import re
#   import dlb_contrib.url
#
#   # HTTPS URL with DNS domain name as host, optional port number and path with only
#   # non-empty "segments" (components) other than '.' and '..':
#   url_regex = re.compile(
#       '(?i:https)://{host}(:{port}?)?{path}'.format(
#           host=dlb_contrib.url.DNS_HOST_DOMAIN_NAME_REGEX.pattern,
#           port=dlb_contrib.url.PORT_REGEX.pattern,
#           path=dlb_contrib.url.AUTHORITY_NORMALIZED_PATH_REGEX.pattern))
#
#   m = url_regex.fullmatch('https://tools.ietf.org/html/rfc3986')
#   ... = m.groupdict()  # {'dns_domain': 'tools.ietf.org', 'port': None, 'authority_path': '/html/rfc3986'}
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.url
#
#   with dlb.ex.Context():
#       # Bijectively map all repository URLs to identifier strings at a single place and
#       # configurable by environment variables.
#       #
#       # Idea: When the URLs change (e.g. due to a build in a different environment) only
#       # the environment variables have to be adapted, not the dlb script.
#
#       dlb.ex.Context.active.env.import_from_outer(
#           'URL_PATTERN_EX_1_COMP',
#           pattern='https://.+',
#           example='https://gitlab.dev.example.org/ex-1-comp-{compid:utf8}.git')
#
#       url_map = dlb_contrib.url.IdToUrlMap({
#           # id pattern:         URL pattern
#           'ex-1-comp-{compid}': dlb.ex.Context.active.env['URL_PATTERN_EX_1_COMP'],
#           'gh:{user}:{repo}':   'https://github/{user:utf8}/{repo:utf8}.git'
#       }, {
#           # placeholder name:   regex for placeholder's value
#           'compid':             r'0|[1-9][0-9]*',
#           'user':               r'[^/:]+',
#           'repo':               r'[^/:]+'
#       })
#
#       # 'git clone' repositories to directories names after their id:
#       for repo_id in ['ex-1-comp-42', 'ex-1-comp-747', 'gh:dlu-ch:dlb']:
#           # 'git clone' from these URLs to f"build/out/{repo_id}/":
#           ... = url_map.get_url_for(repo_id)
#
#       # identify repository from its cloned URLs:
#       cloned_url = ...  # 'git config --get remote.origin.url'
#       ... = url_map.get_id_for(cloned_url)

__all__ = [
    'SCHEME_WITH_SEPARATOR',
    'DNS_HOST_DOMAIN_NAME_REGEX', 'IPV4_ADDRESS_REGEX',
    'AUTHORITY_PATH_REGEX',
    'IdToUrlMap'
]

import re
import urllib.parse
from typing import Optional, Dict, Pattern, Union

# RFC 3986:
#
#   The following are two example URIs and their component parts:
#
#         foo://example.com:8042/over/there?name=ferret#nose
#         \_/   \______________/\_________/ \_________/ \__/
#          |           |            |            |        |
#       scheme     authority       path        query   fragment
#          |   _____________________|__
#         / \ /                        \
#         urn:example:animal:ferret:nose

# RFC 3986:
#
#   unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
#   sub-delims = "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="
UNRESERVED_OR_SUBDELIM_REGEX = re.compile(r"[!$&'()*+,;=A-Za-z0-9._~-]")

# RFC 3986:
#
#   pct-encoded = "%" HEXDIG HEXDIG
#
# RFC 2234:
#
#   HEXDIG = DIGIT / "A" / "B" / "C" / "D" / "E" / "F"
PCTENCODED_REGEX = re.compile(r'(?:%[0-9A-F]{2})')
assert PCTENCODED_REGEX.fullmatch('%0A')

# RFC 3986:
#
#   scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
#
#   Although schemes are case-insensitive, the canonical form is lowercase and documents that specify schemes must do
#   so with lowercase letters.
#
# RFC 2234:
#
#   ALPHA = %x41-5A / %x61-7A  ; A-Z / a-z
#   DIGIT =  %x30-39  ; 0-9
SCHEME_WITH_SEPARATOR = re.compile(r'(?P<scheme>[A-Za-z][A-Za-z0-9.+-]*)://')  # with appended '://'
assert SCHEME_WITH_SEPARATOR.match('https://example.org/').group('scheme')
assert not SCHEME_WITH_SEPARATOR.match('https')

# RFC 3986:
#
#   host = IP-literal / IPv4address / reg-name
#   reg-name = *( unreserved / pct-encoded / sub-delims )
#
#   The host subcomponent is case-insensitive.
#
#   A registered name intended for lookup in the DNS uses the syntax defined in Section 3.5 of [RFC1034]
#   and Section 2.1 of [RFC1123].
#
#   The syntax rule for host is ambiguous because it does not completely distinguish between an IPv4address and a
#   reg-name. [...] If host matches the rule for IPv4address, then it should be considered an IPv4 address literal.

# Section 3.5 of RFC 1034:
#
#   <domain> ::= <subdomain> | " "
#   <subdomain> ::= <label> | <subdomain> "." <label>
#   <label> ::= <letter> [ [ <ldh-str> ] <let-dig> ]
#   <ldh-str> ::= <let-dig-hyp> | <let-dig-hyp> <ldh-str>
#   <let-dig-hyp> ::= <let-dig> | "-"
#   <let-dig> ::= <letter> | <digit>
#   <letter> ::= any one of the 52 alphabetic characters A through Z in upper case and a through z in lower case
#   <digit> ::= any one of the ten digits 0 through 9
#
#   Labels must be 63 characters or less.
#
# Section 2.1 of RFC 1123:
#
#   [T]he restriction on the first character is relaxed to allow either a letter or a digit.
#   Host software MUST support this more liberal syntax.
#
#   Host software MUST handle host names of up to 63 characters and SHOULD handle host names of up to 255 characters.
DNS_HOST_DOMAIN_NAME_REGEX = re.compile(r'(?P<dns_domain>{0}(?:\.{0})*)'.format(
    r'[A-Za-z0-9]+(?:[A-Za-z0-9-]{1,61}[A-Za-z0-9])?'))
assert DNS_HOST_DOMAIN_NAME_REGEX.fullmatch('ch').group('dns_domain')
assert DNS_HOST_DOMAIN_NAME_REGEX.fullmatch('XX.LCS.MIT.EDU').group('dns_domain')
assert DNS_HOST_DOMAIN_NAME_REGEX.fullmatch('127.0.0.1').group('dns_domain')
assert not DNS_HOST_DOMAIN_NAME_REGEX.fullmatch('')

# RFC 3986:
#
#   IPv4address = dec-octet "." dec-octet "." dec-octet "." dec-octet
#   dec-octet   = DIGIT ; 0-9
#               / %x31-39 DIGIT         ; 10-99
#               / "1" 2DIGIT            ; 100-199
#               / "2" %x30-34 DIGIT     ; 200-249
#               / "25" %x30-35          ; 250-255
IPV4_ADDRESS_REGEX = re.compile(r'(?P<ipv4_address>{0}(?:\.{0}){{3}})'.format(
    r'(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'))
assert IPV4_ADDRESS_REGEX.fullmatch('127.0.0.1').group('ipv4_address')

# RFC 3986:
#
#   When authority is present, the path must either be empty or begin with a slash ("/") character.
#
#   hier-part  = "//" authority path-abempty
#                 / path-absolute
#                 / path-rootless
#                 / path-empty
#   path-abempty  = *( "/" segment )
#   path-absolute = "/" [ segment-nz *( "/" segment ) ]
#   path-rootless = segment-nz *( "/" segment )
#   path-empty    = 0<pchar>
#   segment       = *pchar
#   segment-nz    = 1*pchar
#   pchar         = unreserved / pct-encoded / sub-delims / ":" / "@"

PATH_SEGMENT_NZ_REGEX = re.compile(r"(?:(?:{0}|{1}|[:@])+)".format(
    UNRESERVED_OR_SUBDELIM_REGEX.pattern, PCTENCODED_REGEX.pattern))  # does not contain '?' or '#'
assert PATH_SEGMENT_NZ_REGEX.fullmatch('a%20-b')
assert not PATH_SEGMENT_NZ_REGEX.fullmatch('')

# Non-empty path when authority is present:
AUTHORITY_PATH_REGEX = re.compile(r'(?P<authority_path>(?:/{0}?)+)'.format(
    PATH_SEGMENT_NZ_REGEX.pattern))  # does not match empty in contrast to path after non-empty authority in RFC 3986
assert AUTHORITY_PATH_REGEX.fullmatch('/').group('authority_path')
assert AUTHORITY_PATH_REGEX.fullmatch('/a/b').group('authority_path')
assert AUTHORITY_PATH_REGEX.fullmatch('//a/b').group('authority_path')
assert not AUTHORITY_PATH_REGEX.fullmatch('a/b')
assert not AUTHORITY_PATH_REGEX.fullmatch('')

# Non-empty path when authority is present with only non-empty path segments other than '.' and '..'
# (not part of RFC 3986):
AUTHORITY_NORMALIZED_PATH_REGEX = re.compile(r'(?P<authority_path>/|(?:/{0}(?<!/\.)(?<!/\.\.))+/?)'.format(
    PATH_SEGMENT_NZ_REGEX.pattern))  # does not match empty in contrast to path after non-empty authority in RFC 3986
assert AUTHORITY_NORMALIZED_PATH_REGEX.fullmatch('/').group('authority_path')
assert AUTHORITY_NORMALIZED_PATH_REGEX.fullmatch('/.a/b/.../c').group('authority_path')
assert not AUTHORITY_NORMALIZED_PATH_REGEX.fullmatch('/a/.')
assert not AUTHORITY_NORMALIZED_PATH_REGEX.fullmatch('/a/../')
assert not AUTHORITY_NORMALIZED_PATH_REGEX.fullmatch('')

# RFC 3986:
#
#   port = *DIGIT
#
#   URI producers and normalizers should omit the port component and its ":" delimiter if port is empty or if its value
#   would be the same as that of the scheme's default.
PORT_REGEX = re.compile(r'(?P<port>[0-9]+)')  # does not match empty in contrast to port in RFC 3986
assert PORT_REGEX.fullmatch('8080').group('port')
assert not PORT_REGEX.fullmatch('')


BRACE_TOKEN_REGEX = re.compile(r'(?P<unbraced>(?:{{|}}|[^{}])+)|{(?P<braced>[^{}]+)}')
PLACEHOLDER_REGEX = re.compile(r'(?P<name>[a-z_][a-z0-9_]*)(?::(?P<encoding>[A-Za-z][A-Za-z0-9_-]*))?')


class MapByPattern:
    def __init__(self, id_pattern: str, url_pattern: str,
                 regex_by_placeholder: Dict[str, Union[str, Pattern]]):
        regex_by_placeholder = {n: re.compile(r) for n, r in regex_by_placeholder.items()}

        self._id_pattern, self._id_regex, id_encoding_by_name = \
            self._prepare_pattern(id_pattern, regex_by_placeholder, False)
        self._url_pattern_without_encoding, self._url_regex, self._url_encoding_by_name =\
            self._prepare_pattern(url_pattern, regex_by_placeholder, True)

        id_names = set(id_encoding_by_name)
        url_names = set(self._url_encoding_by_name)
        if url_names != id_names:
            differing_names = (url_names - id_names) | (id_names - url_names)
            raise ValueError('placeholders not in both pattern: {}'.format(
                ', '.join(repr(n) for n in sorted(differing_names))))

    @staticmethod
    def _prepare_pattern(pattern: str, regex_by_placeholder: Dict[str, Union[str, Pattern]],
                         expect_encoding: bool):
        encoding_by_name = {}
        pattern_without_encoding = ''
        regex = ''

        first_index = None
        last_index = None
        for m in BRACE_TOKEN_REGEX.finditer(pattern):
            if first_index is None:
                first_index = m.start()
                if first_index != 0:
                    raise ValueError(f"single {pattern[first_index - 1]!r} encountered in pattern: {pattern!r}")
            last_index = m.end()

            unbraced = m.group('unbraced')
            if unbraced is not None:
                pattern_without_encoding += unbraced
                regex += re.escape(unbraced)

            braced = m.group('braced')
            if braced is not None:
                m = PLACEHOLDER_REGEX.fullmatch(braced)
                if not m:
                    raise ValueError(f"invalid placeholder expression {braced!r} in pattern: {pattern!r}")
                name = m.group('name')

                encoding = m.group('encoding')
                if expect_encoding:
                    if encoding is None:
                        raise ValueError(f"encoding missing for placeholder {name!r} in pattern: {pattern!r}")
                    try:
                        b = ''.encode(encoding)
                        if not isinstance(b, bytes) or b.decode(encoding) != '':
                            raise LookupError
                    except (LookupError, TypeError):
                        raise ValueError(f"unknown text encoding {encoding!r} for "
                                         f"placeholder {name!r} in pattern: {pattern!r}") from None
                else:
                    if encoding is not None:
                        raise ValueError(f"encoding not permitted for placeholder in pattern: {pattern!r}")

                is_first_occurrence = name not in encoding_by_name
                if is_first_occurrence:
                    encoding_by_name[name] = encoding
                    try:
                        r = regex_by_placeholder[name].pattern
                    except KeyError:
                        raise ValueError(f"missing regex for placeholder: {name!r}")
                    regex += f"(?P<{name}>{r})"
                elif encoding_by_name[name] != encoding:
                    raise ValueError(f"same placeholder {name!r} with different encodings in pattern: {pattern!r}")
                else:
                    regex += f"(?P={name})"  # use backreference for all occurrences but first

                pattern_without_encoding += f"{{{name}}}"

        if last_index is None:
            raise ValueError(f"placeholder missing in pattern: {pattern!r}")
        if last_index < len(pattern):
            raise ValueError(f"single {pattern[last_index]!r} encountered in pattern: {pattern!r}")

        return pattern_without_encoding, re.compile(regex), encoding_by_name

    def map(self, value: Optional[str], reverse: bool = False) -> Optional[str]:
        if value is None:
            return

        regex, other_pattern_without_encoding = \
            (self._url_regex, self._id_pattern) if reverse else (self._id_regex, self._url_pattern_without_encoding)
        m = regex.fullmatch(value)
        if m is None:
            return

        value_by_placeholder_name = m.groupdict()
        for n, v in value_by_placeholder_name.items():
            if v in ('', '.', '..') or '\0' in v or '/' in v:
                raise ValueError(
                    f"invalid value of placeholder {n!r}: {v!r}\n"
                    "  | reason: no valid POSIX file name (you may want to fix the regex)"
                )

        other_value_by_placeholder_name = {}
        for n, v in value_by_placeholder_name.items():
            encoding = self._url_encoding_by_name[n]
            try:
                if reverse:
                    encoded_v = urllib.parse.unquote(v, errors='strict', encoding=encoding)  # URL -> id
                else:
                    encoded_v = urllib.parse.quote(v, safe='', errors='strict', encoding=encoding)  # id -> URL
            except UnicodeEncodeError as e:
                raise ValueError(
                    f"invalid value of placeholder {n!r}: {v!r}\n"  
                    f"  | reason: {e}"
                ) from None
            other_value_by_placeholder_name[n] = encoded_v

        return other_pattern_without_encoding.format(**other_value_by_placeholder_name)

    @property
    def id_pattern(self):
        return self._id_pattern

    @property
    def url_pattern(self):
        return self._url_pattern_without_encoding.format(**{
            n: f"{{{n}:{e}}}"
            for n, e in self._url_encoding_by_name.items()
        })

    @property
    def names(self):
        return set(self._url_encoding_by_name)


class IdToUrlMap:
    # A bijective map of id (strings) to URLs, defined by pattern with named placeholders and it't value's regexs.
    #
    # *url_pattern_by_id_pattern* must be a dictionary whose keys are id pattern (with at least one placeholder) and
    # whose values the corresponding URL pattern (with the same set of placeholders and added names of text encodings).
    #
    # An id pattern can contain an arbitrary number of placeholders like '{compid}' and single '{' and '}' doubled.
    # An URL pattern can contain an arbitrary number of placeholders like '{compid:utf-8}' and single '{' and '}'
    # doubled.
    #
    # *regex_by_placeholder* must map each placeholder name to a regexp (as string or compiled) that matches exactly
    # all valid values of the placeholder with fullmatch().
    # A placeholder cannot hold any non-empty string different from '.' and '..' that does not contain '/' and '\0',
    # independent of the regexp.
    #
    # Example:
    #
    #   url_map = dlb_contrib.url.IdToUrlMap({
    #       # id pattern:         URL pattern
    #       'ex-1-comp-{compid}': 'https://gitlab.dev.example.org/ex-1-comp-{compid:utf8}.git',
    #       'gh:{user}:{repo}':   'https://github/{user:utf8}/{repo:utf8}.git'
    #   }, {
    #       # placeholder name:   regex for placeholder's value
    #       'compid':             r'0|[1-9][0-9]*',
    #       'user':               r'[^/:]+',
    #       'repo':               r'[^/:]+'
    #   })

    def __init__(self, url_pattern_by_id_pattern: Dict[str, str],
                 regex_by_placeholder: Dict[str, Union[str, Pattern]]):

        self._id_to_url_maps = {
            MapByPattern(id_pattern, url_pattern, regex_by_placeholder)
            for id_pattern, url_pattern in url_pattern_by_id_pattern.items()
        }

        names = set()
        for p in self._id_to_url_maps:
            names |= p.names

        unused_names = set(regex_by_placeholder) - names
        if unused_names:
            raise ValueError('unused placeholders: {}'.format(', '.join(repr(n) for n in sorted(unused_names))))

    def map(self, value: str, reverse: bool = False) -> str:
        # Map an id (string) to its URLs if *reverse* is False,
        # or an URL to its id (string) otherwise.
        #
        # Raises ValueError if *value* or its mapped value does not match exactly one pattern.
        # Raises ValueError if no prefix of the URL (*value* or its mapped value) matches SCHEME_WITH_SEPARATOR
        # (i.e. it does not start like an URL).
        # Raises TypeError if *value* is not a str.

        if not isinstance(value, str):
            raise TypeError("'value' must be str")

        if reverse:
            def order_other_second(id_pattern, url_pattern):
                return url_pattern, id_pattern
        else:
            def order_other_second(id_pattern, url_pattern):
                return id_pattern, url_pattern

        mapped_value = None
        matching_pattern_pairs = set()
        for pb in self._id_to_url_maps:
            other = pb.map(value, reverse)
            if other is not None:
                mapped_value = other
                matching_pattern_pairs.add(order_other_second(pb.id_pattern, pb.url_pattern))

        pattern_type, other_pattern_type = order_other_second('id', 'URL')

        if mapped_value is None:
            raise ValueError(f"no {pattern_type} pattern matches {value!r}")

        if len(matching_pattern_pairs) > 1:
            matching_patterns = sorted(p[0] for p in matching_pattern_pairs)
            pattern_list_str = ', '.join(repr(p) for p in sorted(matching_patterns))
            raise ValueError(f"ambiguous {pattern_type} patterns: {pattern_list_str}\n"
                             f"  | reason: they all match {value!r}")

        url = order_other_second(value, mapped_value)[1]
        if not SCHEME_WITH_SEPARATOR.match(url):
            matching_pattern = next(iter(matching_pattern_pairs))
            matching_url_pattern = order_other_second(*matching_pattern)[1]
            raise ValueError(f"does not start like an URL: {url!r}\n"
                             f"  | reason: URL pattern invalid: {matching_url_pattern!r}")

        matching_other_pattern_pairs = set()
        for pb in self._id_to_url_maps:
            if pb.map(mapped_value, not reverse) is not None:
                matching_other_pattern_pairs.add(order_other_second(pb.id_pattern, pb.url_pattern))

        if len(matching_other_pattern_pairs) > 1:
            matching_other_patterns = sorted(p[1] for p in matching_other_pattern_pairs)
            pattern_list_str = ', '.join(repr(p) for p in sorted(matching_other_patterns))
            raise ValueError(f"ambiguous {other_pattern_type} patterns: {pattern_list_str}\n"
                             f"  | reason: they all match {mapped_value!r}")

        return mapped_value

    def get_url_for(self, id_str: str):
        return self.map(id_str)

    def get_id_for(self, url: str):
        return self.map(url, reverse=True)
