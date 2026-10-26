"""VARIABLE: que se cuenta, y en que orden.

Un guion es una lista de `Beat`. Cada beat declara:
  - su PESO relativo, no segundos: el formato reparte su presupuesto
  - su PAPEL semantico, para que el formato sepa cual puede descartar
  - los PERMISOS que necesita del contrato del receptor

El reparto y la aplicacion del contrato viven aqui, no en cada guion, para que
escribir un modo nuevo sea solo declarar beats.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field

from nucleo.ciencia import Prohibido

#: Papeles que el formato entiende. `pausa` es el unico que exige camara
#: quieta, y por tanto el unico que un formato sin etiquetas puede tirar.
PAPELES = ("establecer", "aproximar", "pausa", "explorar", "reposo")


@dataclass(frozen=True)
class Beat:
    id: str
    peso: float
    papel: str
    permisos: tuple[str, ...] = ()
    alternativa: str | None = None
    #: Si el dato que necesita no esta, se omite en vez de fallar.
    requiere: str | None = None
    #: Minimo de fotogramas por debajo del cual no merece la pena incluirlo.
    minimo_fotogramas: int = 6


@dataclass
class Acta:
    """Lo que se decidio y por que. Va entero al build.json."""
    decisiones: list[dict] = field(default_factory=list)

    def anota(self, **kw) -> None:
        self.decisiones.append(kw)


def resolver(beats, paq, disponible: dict[str, bool], formato, acta: Acta):
    """Aplica el contrato, la disponibilidad de datos y el formato.

    Devuelve los beats que sobreviven. Todo descarte o degradacion queda
    registrado con su razon literal.
    """
    vivos = []
    for b in beats:
        if b.requiere and not disponible.get(b.requiere, False):
            acta.anota(beat=b.id, decision="omitido", motivo="dato ausente",
                       razon=f"el paquete no trae `{b.requiere}`")
            continue
        if formato.papeles is not None and b.papel not in formato.papeles:
            acta.anota(beat=b.id, decision="omitido", motivo="formato",
                       razon=f"el formato `{formato.nombre}` solo admite los "
                             f"papeles {', '.join(formato.papeles)}; este es "
                             f"`{b.papel}`")
            continue
        if b.papel == "pausa" and not formato.etiquetas_3d:
            acta.anota(beat=b.id, decision="omitido", motivo="formato",
                       razon=f"el formato `{formato.nombre}` no admite etiquetas "
                             "ancladas, y una pausa sin etiquetas es tiempo muerto")
            continue
        if b.permisos:
            try:
                paq.exigir(*b.permisos)
            except Prohibido as p:
                if b.alternativa is None:
                    acta.anota(beat=b.id, decision="omitido", motivo="contrato",
                               regla=p.id_regla, razon=p.razon)
                    continue
                acta.anota(beat=b.id, decision="degradado", a=b.alternativa,
                           motivo="contrato", regla=p.id_regla, razon=p.razon,
                           alternativa=p.alternativa)
                vivos.append(Beat(b.alternativa, b.peso, b.papel))
                continue
        vivos.append(b)
    return vivos


def repartir(beats, formato) -> tuple[dict[str, tuple[int, int]], int]:
    """Convierte pesos relativos en rangos de fotogramas.

    El formato pone el presupuesto total; los pesos deciden como se parte. Asi
    el mismo guion da 22.7 s en `biblioteca` y 3 s en `previsualizacion` sin
    tocar una linea del guion.
    """
    total_peso = sum(b.peso for b in beats) or 1.0
    presupuesto = formato.fotogramas
    crudo = [(b, presupuesto * b.peso / total_peso) for b in beats]
    # descartar los que no llegan al minimo y repartir su parte entre el resto
    utiles = [(b, n) for b, n in crudo if n >= b.minimo_fotogramas]
    if not utiles:
        utiles = crudo
    total2 = sum(n for _, n in utiles) or 1.0
    rangos, f = {}, 1
    for i, (b, n) in enumerate(utiles):
        cuantos = presupuesto - f + 1 if i == len(utiles) - 1 \
            else max(b.minimo_fotogramas, int(round(presupuesto * n / total2)))
        rangos[b.id] = (f, f + cuantos - 1)
        f += cuantos
    return rangos, f - 1


# ── registro ─────────────────────────────────────────────────────────────
def disponibles() -> dict:
    import guiones
    out = {}
    for m in pkgutil.iter_modules(guiones.__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"guiones.{m.name}")
        if hasattr(mod, "NOMBRE") and hasattr(mod, "BEATS"):
            out[mod.NOMBRE] = mod
    return out


def catalogo() -> dict[str, dict]:
    """Los guiones registrados SIN ejecutarlos: para mostrarlos donde Blender
    no esta (la interfaz). Se leen las constantes de modulo desde el fuente;
    las funciones de escena solo corren dentro de Blender, no aqui.
    """
    import ast
    from pathlib import Path

    import guiones
    out = {}
    for arch in sorted(Path(guiones.__path__[0]).glob("[!_]*.py")):
        try:
            arbol = ast.parse(arch.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        nombres = set()
        meta = {}
        for nodo in arbol.body:
            if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 \
                    and isinstance(nodo.targets[0], ast.Name):
                nombres.add(nodo.targets[0].id)
                if isinstance(nodo.value, ast.Constant) \
                        and isinstance(nodo.value.value, str):
                    meta[nodo.targets[0].id] = nodo.value.value
        if {"NOMBRE", "BEATS"} <= nombres:
            out[meta["NOMBRE"]] = {"DESCRIPCION": meta.get("DESCRIPCION", ""),
                                   "SUJETO": meta.get("SUJETO")}
    return out


def cargar(nombre: str):
    todos = disponibles()
    if nombre not in todos:
        raise SystemExit(f"guion desconocido: {nombre}. "
                         f"Hay: {', '.join(sorted(todos))}")
    return todos[nombre]
