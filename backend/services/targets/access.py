"""Política única de visibilidad para receptores públicos y privados."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status

from core.models import UserORM


TARGET_NOT_FOUND = "No existe el receptor solicitado."
_RCSB_PDB_ID = re.compile(r"^[A-Z0-9]{4}$")


def is_rcsb_pdb_id(value: str) -> bool:
    return _RCSB_PDB_ID.fullmatch(value) is not None


def target_is_accessible(target: Any, current_user: UserORM | None) -> bool:
    """Un receptor privado sólo existe para la cuenta que figura como creadora."""
    if not bool(getattr(target, "is_private", False)):
        return True
    creator_id = getattr(target, "creator_id", None)
    pdb_id = str(getattr(target, "pdb_id", "")).strip().upper()
    if creator_id is None and is_rcsb_pdb_id(pdb_id):
        # Compatibilidad con filas históricas: versiones anteriores marcaron
        # PDB públicos de RCSB como privados pero nunca guardaron creador.
        # El dato estructural es público; sigue fuera del catálogo si no está
        # curado, pero no debe bloquear corridas legítimas al reabrirlas.
        return True
    return (
        current_user is not None
        and creator_id is not None
        and creator_id == current_user.id
    )


def require_target_object_access(
    target: Any,
    current_user: UserORM | None,
    *,
    missing_detail: str = TARGET_NOT_FOUND,
) -> Any:
    """No distingue entre inexistente y privado ajeno para evitar enumeración."""
    if target is None or not target_is_accessible(target, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, missing_detail)
    return target


async def get_target_for_user(
    repository: Any,
    pdb_id: str,
    current_user: UserORM | None,
    *,
    allow_missing: bool = False,
) -> Any | None:
    """Resuelve un PDB ID y aplica la misma regla en todas las superficies."""
    normalized_id = pdb_id.strip().upper()
    target = await repository.get_target_by_pdb_id(normalized_id)
    if target is None and allow_missing and is_rcsb_pdb_id(normalized_id):
        # Los PDB públicos desconocidos pueden auto-ingestarse. Los USR_* son
        # identificadores internos y siempre deben estar respaldados por una
        # fila con propietario; nunca deben resolverse sólo desde el disco.
        return None
    return require_target_object_access(target, current_user)


async def get_target_for_user_id(
    repository: Any,
    pdb_id: str,
    user_id: str | None,
    *,
    allow_missing: bool = False,
) -> Any | None:
    """Variante para servicios internos que reciben la identidad autenticada."""
    normalized_id = pdb_id.strip().upper()
    target = await repository.get_target_by_pdb_id(normalized_id)
    if target is None and allow_missing and is_rcsb_pdb_id(normalized_id):
        return None
    creator_id = getattr(target, "creator_id", None) if target is not None else None
    is_legacy_public = (
        target is not None
        and bool(getattr(target, "is_private", False))
        and creator_id is None
        and is_rcsb_pdb_id(normalized_id)
    )
    if target is None or (
        bool(getattr(target, "is_private", False))
        and not is_legacy_public
        and (not user_id or creator_id is None or str(creator_id) != str(user_id))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, TARGET_NOT_FOUND)
    return target
