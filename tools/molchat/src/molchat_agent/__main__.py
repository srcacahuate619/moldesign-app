"""Vendored entry point: ``python -m molchat_agent ...`` (Fase 6).

The copy staged under ``tools/molchat/`` is not pip-installed, so the host
cannot rely on the ``molchat-agent`` console script. With ``PYTHONPATH``
pointing at the vendored ``src/``, this module is the stable invocation
documented in ``molchat-manifest.json`` (``invocacion``).
"""

from .cli import main

main()
