"""Receta cosmética de un trabajo Molcy; no cambia entradas ni medidas científicas."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Color = Annotated[str, Field(strict=True, pattern=r"^#[0-9a-fA-F]{6}$")]


class ColoresLineas(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    polar: Color | None = None
    apolar: Color | None = None

    @field_validator("polar", "apolar")
    @classmethod
    def canonico(cls, value):
        return value.upper() if value is not None else None


class PresentacionMolcy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["moldesign.presentacion/1"] = Field(default="moldesign.presentacion/1", alias="schema")
    titulo: str | None = Field(default=None, strict=True, min_length=1, max_length=80)
    color_receptor: Color | None = None
    color_residuos: Color | None = None
    colores_lineas: ColoresLineas = Field(default_factory=ColoresLineas)
    receptor: Literal["automatico", "visible", "oculto"] = "automatico"
    muestra_anterior: bool = True
    etiquetas: bool = True
    contactos: bool = True

    @field_validator("titulo")
    @classmethod
    def titulo_legible(cls, value):
        if value is not None and (not value.strip() or any(
                unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)):
            raise ValueError("El título debe ser legible y no puede contener caracteres de control.")
        return value.strip() if value is not None else None

    @field_validator("color_receptor", "color_residuos")
    @classmethod
    def canonico(cls, value):
        return value.upper() if value is not None else None


class EnsambleFluido(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    variante: Literal["lenta", "detallada"]
    conformero: int | None = Field(default=None, strict=True, ge=0, le=1_000_000)


def normalizar(presentacion: dict | None = None, ensamble_fluido: dict | None = None) -> dict[str, Any]:
    ajustes = {"presentacion": PresentacionMolcy.model_validate(
        presentacion if presentacion is not None else {}).model_dump(by_alias=True)}
    if ensamble_fluido is not None:
        ajustes["ensamble_fluido"] = EnsambleFluido.model_validate(ensamble_fluido).model_dump(exclude_none=True)
    return ajustes


def guardar(root: Path, estado: dict, *, presentacion: dict | None = None,
            ensamble_fluido: dict | None = None) -> None:
    """Congela la receta de ESTE trabajo; no lee preferencias globales al repetirlo."""
    ajustes = normalizar(presentacion, ensamble_fluido)
    data = json.dumps(ajustes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (root / "ajustes.json").write_bytes(data)
    estado["ajustes"] = ajustes
    estado["ajustes_sha256"] = hashlib.sha256(data).hexdigest()


def ruta_verificada(root: Path, estado: dict) -> Path | None:
    """Los trabajos heredados no tenían receta; los nuevos no pueden perderla silenciosamente."""
    if "ajustes" not in estado:
        return None
    path = root / "ajustes.json"
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != estado.get("ajustes_sha256"):
        raise ValueError("La receta visual del trabajo ya no coincide con su SHA-256.")
    if json.loads(data) != estado["ajustes"]:
        raise ValueError("La receta visual no corresponde a este trabajo.")
    return path
