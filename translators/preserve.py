# coding=utf-8
# author=UlionTse

"""
Pure helpers (no network) for engine fallback and do-not-translate spans.

mask() swaps every span matched by the `preserve` regexes for a placeholder
token ` QX{n}Z `; restore() puts the original spans back and verifies that
the engine kept every token exactly once.
"""

import re
from typing import Iterable, List, Optional, Tuple, Union

__all__ = ('PreserveError', 'normalize_engines', 'mask', 'restore')

_NO_SPACE_BEFORE = ",.;:!?)\uff0c\u3002\uff1b\uff1a\uff01\uff1f\uff09\u3001"
_NO_SPACE_AFTER = "(\uff08"


class PreserveError(ValueError):
    """A placeholder token was lost or duplicated by the engine."""


def normalize_engines(translator: Union[str, Iterable[str]]) -> List[str]:
    """
    :param translator: str (a comma-separated string is allowed) or an iterable of engine names.
    :return: list of engine names, in order, blanks dropped.
    """
    if isinstance(translator, str):
        translator = translator.split(',')
    return [str(t).strip() for t in translator if str(t).strip()]


def _token(n: int) -> str:
    return f' QX{n}Z '


def _token_pattern(n: int) -> 're.Pattern':
    return re.compile(r'(\s*)q\s*x\s*{}\s*z(\s*)'.format(n), re.IGNORECASE)


def mask(text: str, patterns: Optional[Iterable[str]]) -> Tuple[str, List[str]]:
    """
    Replace every match of `patterns` with a placeholder token.
    The patterns are joined into one alternation regex, so scanning is left to right
    and, at one position, the earlier pattern wins. Empty matches are ignored.
    :param text: str, query text.
    :param patterns: regex patterns, or None.
    :return: (masked_text, spans), where spans[n-1] is the original text of token n.
    """
    patterns = [p for p in (patterns or ()) if p]
    if not patterns:
        return text, []

    combined = re.compile('|'.join('(?:{})'.format(p) for p in patterns))
    spans, parts, last = [], [], 0
    for m in combined.finditer(text):
        if m.start() == m.end():
            continue
        spans.append(m.group(0))
        parts.append(text[last:m.start()])
        parts.append(_token(len(spans)))
        last = m.end()
    parts.append(text[last:])
    return ''.join(parts), spans


def restore(text: str, spans: List[str]) -> str:
    """
    Put the original spans back. Tokens match case-insensitively and tolerate inner spaces.
    :param text: str, engine output.
    :param spans: list returned by mask().
    :return: restored text.
    :raise PreserveError: a token is missing or appears more than once.
    """
    if not spans:
        return text

    problems = []
    for n in range(1, len(spans) + 1):
        cnt = len(_token_pattern(n).findall(text))
        if cnt != 1:
            problems.append('QX{}Z x{}'.format(n, cnt))
    if problems:
        raise PreserveError('placeholder tokens not kept exactly once: ' + ', '.join(problems))

    for n, span in enumerate(spans, 1):
        def _sub(m: 're.Match', _span: str = span) -> str:
            s = m.string
            left = '' if m.start() == 0 or s[m.start() - 1] in _NO_SPACE_AFTER else ' '
            right = '' if m.end() == len(s) or s[m.end()] in _NO_SPACE_BEFORE else ' '
            return left + _span + right

        text = _token_pattern(n).sub(_sub, text, count=1)
    return text
