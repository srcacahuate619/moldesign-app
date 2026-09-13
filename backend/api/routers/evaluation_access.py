"""Reglas compartidas de acceso a resultados de evaluación.

Los endpoints de archivos, explicabilidad y reportes comparten UNA regla: una
molécula tiene un dueño y sólo uno, y lo pide quien lo es.

Aquí había una «excepción intencional»: las evaluaciones anónimas eran visibles
para todo el mundo, y el filtro `user_id not in {cuenta, demo}` hacía que
cualquier cuenta registrada leyera lo anónimo. Se retiró: la evaluación sin
cuenta sigue permitida (TRANS-ANON-002), pero su resultado no es de todos.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import MoleculeORM, UserORM
from db.repository import Repository


def dueno_de_la_peticion(current_user: Any | None, demo_user_id: Any) -> Any:
    """De quién es lo que esta petición produzca.

    Con sesión, de la cuenta. Sin sesión, del espacio anónimo —que TRANS-ANON-002
    conserva: sin cuenta se evalúa sin límite—. Lo que se retira no es evaluar
    sin cuenta, es que el resultado sea de todos.
    """
    return current_user.id if current_user is not None else demo_user_id


def puede_operar(molecule: Any, current_user: Any | None, demo_user_id: Any) -> bool:
    """Una molécula tiene un dueño y sólo uno.

    Aquí vivía el agujero: el filtro era `user_id not in {cuenta, demo}`, así
    que **cualquier cuenta registrada podía leer todo lo anónimo**, y la
    comprobación de IP que protege lo anónimo llegaba después de haber concedido
    el acceso. La regla ahora es de igualdad, no de pertenencia a un conjunto:

    * una cuenta ve lo suyo y nada más;
    * una petición sin sesión ve lo anónimo y nada más (la atadura por IP la
      aplica el llamador, que es quien tiene la `Request`).
    """
    return molecule.user_id == dueno_de_la_peticion(current_user, demo_user_id)


async def require_owned_molecule(
    *,
    repository: Repository,
    db: AsyncSession,
    molecule_id: uuid.UUID,
    current_user: UserORM | None,
    forbidden_detail: str,
    missing_detail: str | None = None,
) -> MoleculeORM:
    """Obtiene una molécula **de quien la pide**. Ya no hay espacio compartido."""
    molecule = await db.get(MoleculeORM, molecule_id)
    if molecule is None:
        if missing_detail is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)

    demo_user = await repository.get_or_create_test_user()
    if not puede_operar(molecule, current_user, demo_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)
    return molecule
