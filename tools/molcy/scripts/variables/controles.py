"""VARIABLE: los mandos de la interfaz —barras de 0 a 100 e interruptores— y
lo que mueve cada uno en Blender.

Una sola fuente de verdad: la interfaz pinta los mandos con `como_json()` y el
maestro traduce las posiciones con `aplicar()`. Un 50 en la pantalla es el
mismo valor en el render, y la traduccion queda escrita en el acta.

La linea que no se cruza: los mandos tocan la capa de ARTE y FORMATO (calidad,
camara, look, texto). La CIENCIA —que hotspots, que contactos, que ligando, las
distancias medidas, el contrato— no tiene barra. Se puede APAGAR una capa
(no dibujar las lineas de contacto), nunca cambiar lo que dice.

Solo se aplica lo que el usuario movio: una barra en su posicion por defecto
no viaja, asi que sin ajustes el video sale exactamente como en produccion.

Sin bpy: la importan la interfaz y las pruebas.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

#: Opacidad minima del fantasma, `PISO_FANTASMA` en `guiones/sitio_activo.py`.
#: Se repite porque ese modulo importa mathutils; una prueba vigila que no se
#: desincronicen.
PISO_FANTASMA = 0.12


@dataclass(frozen=True)
class Barra:
    id: str
    etiqueta: str
    grupo: str
    ayuda: str               # que hace en Blender, en una frase
    lo: float                # valor real en la posicion 0
    hi: float                # valor real en la posicion 100
    escala: str = "lineal"   # "lineal" | "log2"
    decimales: int = 0
    unidad: str = ""
    coste: bool = False      # mueve el tiempo de render

    def valor(self, pos: float) -> float:
        p = min(100.0, max(0.0, float(pos))) / 100.0
        if self.escala == "log2":
            v = self.lo * (self.hi / self.lo) ** p
        else:
            v = self.lo + (self.hi - self.lo) * p
        return round(v, self.decimales) if self.decimales else int(round(v))

    def posicion(self, valor: float) -> int:
        v = min(max(float(valor), min(self.lo, self.hi)), max(self.lo, self.hi))
        if self.escala == "log2":
            p = math.log(v / self.lo) / math.log(self.hi / self.lo)
        else:
            p = (v - self.lo) / (self.hi - self.lo)
        return int(round(100 * p))


@dataclass(frozen=True)
class Interruptor:
    id: str
    etiqueta: str
    ayuda: str


BARRAS = (
    Barra("calidad", "Calidad de imagen", "Calidad y coste",
          "Muestras de EEVEE por fotograma. Menos muestras, más grano y más rápido.",
          16, 128, "log2", 0, "muestras", coste=True),
    Barra("sombras", "Detalle de sombras", "Calidad y coste",
          "Resolución de los mapas de sombra. Es lo más caro del primer plano.",
          0.25, 1.0, "lineal", 2, "×", coste=True),
    Barra("resolucion", "Resolución", "Calidad y coste",
          "Porcentaje de la resolución del formato. Al 50 % sirve para borradores.",
          50, 100, "lineal", 0, "%", coste=True),
    Barra("duracion", "Duración", "Cámara y movimiento",
          "Estira o encoge el guion entero; el reparto entre planos se mantiene.",
          0.5, 1.5, "lineal", 2, "×", coste=True),
    Barra("desenfoque", "Desenfoque de fondo", "Cámara y movimiento",
          "Fuerza de la profundidad de campo. 0 la apaga; 1 es la de producción.",
          0.0, 2.0, "lineal", 2, "×"),
    Barra("estela", "Estela de movimiento", "Cámara y movimiento",
          "Obturador del motion blur. 0 lo apaga.",
          0.0, 0.7, "lineal", 2, ""),
    Barra("fantasma", "Opacidad del fantasma", "Look",
          "Opacidad mínima de la cáscara que tapa el sitio (look v4). "
          "0 la vacía; más alto, más silueta.",
          0.0, 0.4, "lineal", 2, ""),
    Barra("exposicion", "Exposición", "Look",
          "Exposición de la gestión de color, en pasos de diafragma.",
          -1.0, 1.0, "lineal", 2, "EV"),
    Barra("texto", "Tamaño del texto", "Look",
          "Escala de etiquetas y título respecto a la del formato.",
          0.6, 1.4, "lineal", 2, "×"),
)

INTERRUPTORES = (
    Interruptor("titulo", "Título", "Rótulo inferior con el nombre del receptor."),
    Interruptor("etiquetas", "Etiquetas de residuos",
                "Hotspots y distancias. Sin ellas se quitan las pausas de cámara."),
    Interruptor("contactos", "Líneas de contacto",
                "Contactos polares medidos. Apagarlas no cambia lo medido: "
                "solo no se dibujan."),
    Interruptor("look_v4", "Look v4",
                "Acabado satinado y cáscara translúcida del primer plano. "
                "Apagado vuelve a la disolución anterior."),
    # No hay interruptor de «cierre»: el cierre de MolDesign (la firma 3D de la marca al final) es obligatorio en todo video.
    Interruptor("sello", "Crédito arriba",
                "«Video generado por MolDesign» quemado arriba todo el vídeo. "
                "No sustituye al cierre, que va siempre."),
)

#: Botones de una pulsacion. `produccion` es vaciar los ajustes.
PRESETS = {
    "borrador": {"calidad": 16, "sombras": 0.25, "resolucion": 50},
    "produccion": {},
    "maxima": {"calidad": 128, "sombras": 1.0, "resolucion": 100},
}

_BARRAS = {b.id: b for b in BARRAS}
_INTERRUPTORES = {i.id for i in INTERRUPTORES}


# ── valores de produccion ────────────────────────────────────────────────
def por_defecto(formato) -> dict:
    """Valor REAL de cada mando en produccion para este formato."""
    return {
        "calidad": formato.muestras,
        "sombras": formato.escala_sombras,
        "resolucion": formato.escala_render,
        "duracion": 1.0,
        "desenfoque": 1.0 if formato.profundidad_de_campo else 0.0,
        "estela": formato.obturador if formato.desenfoque_movimiento else 0.0,
        "fantasma": PISO_FANTASMA,
        "exposicion": 0.0,
        "texto": 1.0,
        "titulo": formato.rotulos_pantalla,
        "etiquetas": formato.etiquetas_3d,
        "contactos": True,
        "look_v4": True,
        "sello": formato.sello_procedencia,
    }


def preset(nombre: str) -> dict:
    """Las posiciones 0-100 de un preset (solo las barras que mueve)."""
    return {k: _BARRAS[k].posicion(v) for k, v in PRESETS[nombre].items()}


# ── traduccion ───────────────────────────────────────────────────────────
def validar(ajustes: dict) -> dict:
    """`{"barras": {id: 0-100}, "interruptores": {id: bool}}`, sin extras."""
    barras = dict(ajustes.get("barras") or {})
    inter = dict(ajustes.get("interruptores") or {})
    if any("cierre" in grupo for grupo in (barras, inter, ajustes)):
        # Con su propio mensaje: «mandos desconocidos» sugeriria que basta con escribirlo bien.
        raise ValueError("El cierre de MolDesign es obligatorio en todo video y no se puede quitar ni ajustar")
    raros = (set(barras) - set(_BARRAS)) | (set(inter) - _INTERRUPTORES) | \
        (set(ajustes) - {"barras", "interruptores", "presentacion", "ensamble_fluido"})
    if raros:
        raise ValueError(f"mandos desconocidos: {', '.join(sorted(raros))}")
    for k, v in barras.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100:
            raise ValueError(f"la barra {k} tiene que ir de 0 a 100 (llego {v!r})")
    for k, v in inter.items():
        if not isinstance(v, bool):
            raise ValueError(f"el interruptor {k} tiene que ser si/no (llego {v!r})")
    out = {"barras": barras, "interruptores": inter}
    from variables import presentacion
    if "presentacion" in ajustes:
        out["presentacion"] = presentacion.validar(ajustes["presentacion"])
    if "ensamble_fluido" in ajustes:
        out["ensamble_fluido"] = presentacion.validar_ensamble(ajustes["ensamble_fluido"])
    return out


def leer(ruta: str | Path) -> dict:
    return validar(json.loads(Path(ruta).read_text(encoding="utf-8")))



def leer_entrada(ruta: str | Path) -> dict:
    """Conserva la receta exacta; la normalización sólo va a resueltos del acta."""
    entrada = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    if not isinstance(entrada, dict):
        raise ValueError("los ajustes deben ser un objeto")
    validar(entrada)
    return entrada


def aplicar(formato, ajustes: dict | None):
    """Traduce los ajustes a un formato nuevo y a los extras que no son formato.

    Devuelve `(formato, extras, resueltos)`. `resueltos` son los valores reales
    de lo que se movio, para el acta.
    """
    a = validar(ajustes or {})
    extras = {"factor_desenfoque": 1.0, "piso_fantasma": None,
              "exposicion": None, "contactos": True, "look_v4": True}
    cambios, resueltos = {}, {}
    for k, pos in a["barras"].items():
        v = _BARRAS[k].valor(pos)
        resueltos[k] = v
        if k == "calidad":
            cambios["muestras"] = int(v)
        elif k == "sombras":
            cambios["escala_sombras"] = float(v)
        elif k == "resolucion":
            cambios["escala_render"] = int(v)
        elif k == "duracion":
            cambios["segundos"] = round(formato.segundos * v, 3)
        elif k == "desenfoque":
            if v <= 0:
                cambios["profundidad_de_campo"] = False
            extras["factor_desenfoque"] = float(v)
        elif k == "estela":
            cambios["desenfoque_movimiento"] = v > 0
            if v > 0:
                cambios["obturador"] = float(v)
        elif k == "fantasma":
            extras["piso_fantasma"] = float(v)
        elif k == "exposicion":
            extras["exposicion"] = float(v)
        elif k == "texto":
            cambios["escala_texto"] = round(formato.escala_texto * v, 3)
            if formato.escala_etiquetas_3d is not None:
                cambios["escala_etiquetas_3d"] = round(formato.escala_etiquetas_3d * v, 3)
    for k, v in a["interruptores"].items():
        resueltos[k] = v
        if k == "titulo":
            cambios["rotulos_pantalla"] = v
        elif k == "etiquetas":
            cambios["etiquetas_3d"] = v
        elif k == "sello":
            cambios["sello_procedencia"] = v
        else:                                   # contactos, look_v4
            extras[k] = v
    if "presentacion" in a:
        visual = a["presentacion"]
        extras["presentacion"] = visual
        extras["contactos"] = visual["contactos"]
        cambios["etiquetas_3d"] = visual["etiquetas"]
        resueltos["presentacion"] = visual
    if "ensamble_fluido" in a:
        extras["ensamble_fluido"] = a["ensamble_fluido"]
        resueltos["ensamble_fluido"] = a["ensamble_fluido"]
    return replace(formato, **cambios), extras, resueltos


# ── coste ────────────────────────────────────────────────────────────────
#: Calibrado el 2026-09-22 en la GTX 1660 SUPER con 016 (1EI1) y cuatro puntos
#: medidos (s por fotograma): 96 m./sombras 1.0 = 4.36; 64/0.5 = 1.62;
#: borrador 16/0.25 al 50 % = 0.35; previsualizacion 1:1 a 48 m. = 0.47.
#: Cada fotograma paga ~0.25 s fijos (sincronizar la escena, escribir el PNG):
#: sin ese termino el borrador se estimaba en 81 s y tardo 2.7 min. El resto es
#: lineal en muestras y en pixeles, y las sombras cuestan 0.1 + 0.9 * escala.
#: Un formato que solo orbita (sin primer plano) cuesta el 42 % del plano medio:
#: es lo que vale la orbita general frente a la media del vertical (1.83/4.36).
#: Error frente a lo medido: +/-12 %. Varia con el receptor: es una guia.
_FIJO_S = 0.25
_VARIABLE_S = 4.36 - _FIJO_S       # a 96 muestras, sombras 1.0, 1080x1920
_MUESTRAS_REF = 96
_PIXELES_REF = 1080 * 1920
_SOLO_ORBITA = 0.42
#: Construir la escena, encode, sello y comprobacion: ~30 s. La pasada del
#: titulo, cuando hay titulo, otros ~25 s.
_SOBRECOSTE_S = 30
_TITULO_S = 25


def estimar(formato, ajustes: dict | None = None) -> dict:
    f, _extras, _ = aplicar(formato, ajustes)
    pixeles = f.ancho * f.alto * (f.escala_render / 100) ** 2
    contenido = _SOLO_ORBITA if f.papeles == ("establecer",) else 1.0
    s = _FIJO_S + (_VARIABLE_S * contenido * (f.muestras / _MUESTRAS_REF)
                   * (0.1 + 0.9 * f.escala_sombras) * (pixeles / _PIXELES_REF))
    extra = _SOBRECOSTE_S + (_TITULO_S if f.rotulos_pantalla else 0)
    return {"por_fotograma_s": round(s, 2), "fotogramas": f.fotogramas,
            "total_s": int(round(f.fotogramas * s + extra))}


# ── para la interfaz ─────────────────────────────────────────────────────
def como_json(formatos: dict) -> dict:
    """Todo lo que la interfaz necesita para pintar los mandos."""
    return {
        "barras": [{"id": b.id, "etiqueta": b.etiqueta, "grupo": b.grupo,
                    "ayuda": b.ayuda, "lo": b.lo, "hi": b.hi, "escala": b.escala,
                    "decimales": b.decimales, "unidad": b.unidad, "coste": b.coste}
                   for b in BARRAS],
        "interruptores": [{"id": i.id, "etiqueta": i.etiqueta, "ayuda": i.ayuda}
                          for i in INTERRUPTORES],
        "presets": {n: preset(n) for n in PRESETS},
        # posicion 0-100 de produccion, por formato: ahi se pinta la marca
        "defecto": {
            nombre: {k: (_BARRAS[k].posicion(v) if k in _BARRAS else bool(v))
                     for k, v in por_defecto(f).items()}
            for nombre, f in formatos.items()},
        "defecto_real": {nombre: por_defecto(f) for nombre, f in formatos.items()},
    }
