"""Internationalization for Market Analysis.

Loads translation dictionaries from JSON files in `webapp/i18n/locales/`,
exposes a `t(key, **fmt)` function used throughout the app, and provides
helpers to detect / change the current language.

Design goals:
  - Default language is ENGLISH (fits a financial app's audience).
  - Missing keys fall back to the English value, then to the key itself,
    so a typo never crashes the UI.
  - JSON files (not inline Python dicts) so translators can edit without
    touching code.
  - `t("key", value=42, name="VST")` supports str.format kwargs for dynamic
    content.
  - Loaded once at import time; locale dicts are cached.
  - `get_supported_languages()` returns the list of available codes for
    the language selector UI.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCALES_DIR = Path(__file__).parent / 'locales'
DEFAULT_LANG = 'en'
FALLBACK_LANG = 'en'

_logger = logging.getLogger(__name__)
_missing_keys_logged: set = set()  # avoid spamming the same warning


@lru_cache(maxsize=8)
def _load_locale(lang: str) -> Dict[str, str]:
    """Read a locale JSON. Returns {} if missing."""
    f = _LOCALES_DIR / f'{lang}.json'
    if not f.exists():
        return {}
    try:
        with f.open(encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as e:
        _logger.warning(f"Could not load locale {lang}: {e}")
        return {}


def get_supported_languages() -> List[Dict[str, str]]:
    """List available locales for the selector. Returns [{code, label}, ...]."""
    out = []
    if not _LOCALES_DIR.exists():
        return out
    label_map = {'en': 'English', 'es': 'Español', 'pt': 'Português', 'fr': 'Français'}
    for f in sorted(_LOCALES_DIR.glob('*.json')):
        code = f.stem
        out.append({'code': code, 'label': label_map.get(code, code.upper())})
    return out


def get_current_lang() -> str:
    """Read current language from Streamlit session state. Defaults to DEFAULT_LANG."""
    try:
        import streamlit as st
        return st.session_state.get('lang', DEFAULT_LANG)
    except Exception:
        return DEFAULT_LANG


def set_current_lang(lang: str) -> None:
    """Persist a language choice in session state."""
    try:
        import streamlit as st
        st.session_state.lang = lang
    except Exception:
        pass


def t(key: str, lang: Optional[str] = None, **fmt: Any) -> str:
    """Translate a key into the current language.

    Args:
        key:  the translation key (e.g. 'dashboard.title')
        lang: override the active language (rarely needed)
        **fmt: str.format kwargs for dynamic substitution

    Returns:
        Translated string. Falls back to FALLBACK_LANG locale, then to the
        key itself, so missing translations never crash the UI.
    """
    if lang is None:
        lang = get_current_lang()

    locale = _load_locale(lang)
    value = locale.get(key)

    if value is None and lang != FALLBACK_LANG:
        # Try fallback locale
        fallback = _load_locale(FALLBACK_LANG)
        value = fallback.get(key)

    if value is None:
        # Log once per missing key
        if key not in _missing_keys_logged:
            _missing_keys_logged.add(key)
            _logger.warning(f"i18n: missing key '{key}' (lang={lang})")
        value = key  # last-resort: show the key

    if fmt and isinstance(value, str) and '{' in value:
        try:
            value = value.format(**fmt)
        except (KeyError, IndexError):
            pass  # leave unformatted rather than crash

    return value


def clear_cache() -> None:
    """Reload all locale files from disk. Useful in dev."""
    _load_locale.cache_clear()
    _missing_keys_logged.clear()
