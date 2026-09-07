"""Translation provider abstraction — no external AI APIs in initial release."""

from __future__ import annotations

import re
from typing import Protocol

from term_dictionary import apply_term_dictionary, restore_term_dictionary

PLACEHOLDER_ONLY_RE = re.compile(r"^(\s|__TERM_\d+__)*$")


class TranslationProvider(Protocol):
    def translate(self, text: str, source_locale: str, target_locale: str) -> str:
        ...


class MockTranslationProvider:
    """Deterministic stub for tests and local builds without AI APIs."""

    def translate(self, text: str, source_locale: str, target_locale: str) -> str:
        if source_locale == "jp" and target_locale == "en":
            return f"[en]{text}[/en]"
        if source_locale == "en" and target_locale == "jp":
            return f"[jp]{text}[/jp]"
        return text


def translate_with_dictionary(
    text: str,
    entries: list,
    provider: TranslationProvider,
    source_locale: str = "jp",
    target_locale: str = "en",
) -> str:
    protected, placeholders = apply_term_dictionary(text, entries)
    if placeholders and PLACEHOLDER_ONLY_RE.fullmatch(protected):
        translated = protected
    else:
        translated = provider.translate(protected, source_locale, target_locale)
    return restore_term_dictionary(translated, placeholders)
