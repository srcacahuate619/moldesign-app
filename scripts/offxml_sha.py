#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""offxml_sha.py — Reporta ruta y SHA-256 del force field Sage instalado en el contenedor."""
import hashlib
import os
import sys
import site

from openff.toolkit import ForceField

print(f"python: {sys.executable}")
print(f"site:   {site.getsitepackages()}")
print(f"env FF dir: {os.environ.get('OPENFF_FORCE_FIELD_DIR', '<unset>')}")

# Cargar y extraer la ruta real desde el propio ForceField
ff = ForceField("openff-2.2.1.offxml")
path = None
for root, _, files in os.walk(site.getsitepackages()[0]):
    if "openff-2.2.1.offxml" in files:
        path = os.path.join(root, "openff-2.2.1.offxml")
        break

if path is None:
    # Último recurso: rastrear qué archivo abrió el toolkit
    try:
        from openff.toolkit.typing.engines.smirnoff.forcefield import _get_offxml_path
        path = _get_offxml_path("openff-2.2.1.offxml")
    except Exception as e:
        print(f"fallback fallido: {e}")

print(f"path:   {path}")
if path and os.path.exists(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    print(f"size:   {os.path.getsize(path)} bytes")
    print(f"sha256: {h.hexdigest()}")
else:
    print("NO_ENCONTRADO")