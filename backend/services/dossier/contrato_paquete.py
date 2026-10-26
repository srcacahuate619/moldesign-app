"""Constantes del contrato del paquete reproducible, sin dependencias.

Las comparten quien escribe el paquete (`package.py`) y quien lo verifica (`verify.py`). Viven aparte porque
`scripts/verify_dossier_package.py` tiene que correr con un Python sin el backend instalado: lo usan los revisores
externos de FEP-06-HUM, y `package.py` arrastra el modelo del dossier y pydantic (2026-10-26).
"""

#: Versión del manifiesto. El verificador la comprueba antes de nada.
MANIFEST_VERSION = 1

#: Nombre del índice de hashes. No se hashea a sí mismo.
CHECKSUMS_NAME = "checksums.sha256"
