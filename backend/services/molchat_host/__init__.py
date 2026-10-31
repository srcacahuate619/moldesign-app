"""Host mínimo de MolChat (Fase 6): localizar, verificar y supervisar el sidecar.

MolDesign no importa este programa: lo ejecuta por subproceso en loopback
(`launcher`) y se comunica por HTTP versionado. La frontera se defiende con
`backend/tests/test_frontera_molchat.py`: nada de `backend/` importa
`molchat_agent` y nada de `tools/molchat/` importa `backend`.
"""
