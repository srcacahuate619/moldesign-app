"""The language MolChat writes in: the one MolDesign shows, set once per turn and once per plan.

Texts the host writes (fixed answers, the plan card, the iteration's events, the notebook) pick their language here
instead of carrying a ``lang`` argument through every function. A turn sets it from the request; a plan keeps the one
it was proposed in, so its notebook comes out in that language even when it finishes in the background.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

LANGS = ("es", "en")
_LANG: ContextVar[str] = ContextVar("molchat_lang", default="es")


def current() -> str:
    return _LANG.get()


def tr(es: str, en: str) -> str:
    """The text in the current language. Both versions sit side by side so neither can drift unnoticed."""
    return en if _LANG.get() == "en" else es


def valid(lang: object) -> str:
    """A request's language, or Spanish when it sent none or an unknown one."""
    return lang if isinstance(lang, str) and lang in LANGS else "es"


@contextmanager
def using(lang: str) -> Iterator[None]:
    token = _LANG.set(valid(lang))
    try:
        yield
    finally:
        _LANG.reset(token)
