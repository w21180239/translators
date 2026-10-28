# coding=utf-8
# author=UlionTse

"""
Credentials for keyed (official API) engines.

A keyed engine joins `translators_pool` only when all its required fields are set. Sources, later wins:
  1. file: $TRANSLATORS_CREDENTIALS, else ~/.config/translators/credentials.toml
       [deeplApi]
       api_key = "xxxx:fx"
  2. environment: TRANSLATORS_<ENGINE>_<FIELD>, e.g. TRANSLATORS_DEEPLAPI_API_KEY
  3. keyword arguments of the engine call, e.g. api_key='...'
Keep the file private (chmod 600); a group/world-readable file triggers a warning.
"""

import os
import re
import stat
import warnings
import configparser
from typing import Dict, Optional, Tuple

__all__ = ('KEYED_ENGINES', 'default_path', 'load', 'get', 'is_configured')

# engine name -> (required fields, optional fields)
KEYED_ENGINES: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {}


def default_path() -> str:
    return os.environ.get('TRANSLATORS_CREDENTIALS') or os.path.join(
        os.path.expanduser('~'), '.config', 'translators', 'credentials.toml')


def _read_file(path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.isfile(path):
        return {}
    mode = os.stat(path).st_mode
    if os.name == 'posix' and mode & (stat.S_IRWXG | stat.S_IRWXO):
        warnings.warn(f'{path} is readable by other users; run `chmod 600 {path}`.')
    try:
        import tomllib  # Python 3.11+
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        return {k: {fk: str(fv) for fk, fv in v.items()} for k, v in data.items() if isinstance(v, dict)}
    except ImportError:
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # keep field case
        parser.read(path, encoding='utf-8')
        return {s: {k: v.strip().strip('"\'') for k, v in parser[s].items()} for s in parser.sections()}


def load(path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    :param path: credentials file, default `default_path()`.
    :return: {engine: {field: value}} merged from file and environment, for engines in KEYED_ENGINES.
    """
    data = _read_file(path or default_path())
    out = {}
    for engine, (required, optional) in KEYED_ENGINES.items():
        fields = dict(data.get(engine, {}))
        for field in required + optional:
            env = 'TRANSLATORS_{}_{}'.format(re.sub(r'\W', '', engine).upper(), field.upper())
            if os.environ.get(env):
                fields[field] = os.environ[env]
        fields = {k: v for k, v in fields.items() if v}
        if fields:
            out[engine] = fields
    return out


def get(engine: str, field: str, kwargs: Optional[dict] = None, creds: Optional[dict] = None) -> Optional[str]:
    """Call kwargs win over loaded credentials."""
    if kwargs and kwargs.get(field):
        return kwargs[field]
    return (creds if creds is not None else load()).get(engine, {}).get(field)


def is_configured(engine: str, creds: Optional[dict] = None) -> bool:
    required = KEYED_ENGINES.get(engine, ((), ()))[0]
    fields = (creds if creds is not None else load()).get(engine, {})
    return bool(required) and all(fields.get(f) for f in required)
