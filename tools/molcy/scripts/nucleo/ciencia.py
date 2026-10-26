"""La capa CONSTANTE: el contrato cientifico de MolDesign.

No sabe nada de Blender. Lee un paquete de escena producido por
`moldesign-build/scripts/scene_export/build_scene_package.py` y expone sus
datos, pero sobre todo **hace cumplir** `no_dibujar`.

La diferencia entre leer el contrato y hacerlo cumplir es la que separa esta
arquitectura de una promesa. Si el guion pide un plano que el contrato prohibe
para ese receptor, aqui se levanta `Prohibido` y el constructor se abstiene de
ese plano, lo registra con su razon, y sigue. Nunca lo dibuja en silencio.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Angstrom -> unidades de Blender. Verificado contra el caso 001: Molecular
#: Nodes importa con escala 0.1 exacta, sin traslacion ni rotacion (el centroide
#: de Thr766 coincidio a 0.04 A). Esto es lo que hace que `encuadre.objetivo`
#: del contrato sea directamente utilizable como pivote de camara.
ESCALA = 0.1


class Prohibido(RuntimeError):
    """El contrato de este receptor prohibe lo que el guion pide."""

    def __init__(self, id_regla: str, razon: str, alternativa: str = ""):
        self.id_regla, self.razon, self.alternativa = id_regla, razon, alternativa
        super().__init__(f"{id_regla}: {razon}")


@dataclass
class Hotspot:
    cadena: str
    resname: str
    numero: int
    importancia: float

    @property
    def etiqueta(self) -> str:
        return f"{self.resname.capitalize()}{self.numero}"

    def etiqueta_con_cadena(self, mostrar: bool = False) -> str:
        """Con la letra de cadena si el sitio esta repartido entre varias.

        En un dimero como la proteasa del VIH, Asp25 existe en A y en B: dos
        etiquetas identicas apuntando a sitios distintos no dicen nada.
        """
        return f"{self.etiqueta} {self.cadena}" if mostrar else self.etiqueta

    def rotulo(self, mostrar_cadena: bool = False) -> str:
        """Etiqueta 3D del hotspot: el residuo con la tipografia de las
        interacciones (LYS483) y un segundo renglon que dice QUE es. Sin distancia
        ni clase: un hotspot es evidencia del catalogo sobre el receptor, no una
        medida contra la pose, y con el aspecto de «LYS483 / POLAR 3.11 Å» se
        confundia con una interaccion.
        """
        cadena = f":{self.cadena}" if mostrar_cadena and self.cadena else ""
        return f"{self.resname.upper()}{self.numero}{cadena}\nHOTSPOT"

    @property
    def seleccion(self) -> str:
        """Seleccion MDAnalysis de la cadena lateral, para las varillas."""
        return f"segid {self.cadena} and resid {self.numero} and not backbone"


@dataclass
class Hueco:
    cadena: str
    desde: int
    hasta: int
    distancia_a: float
    residuos_ausentes: int


@dataclass
class Paquete:
    raiz: Path
    datos: dict[str, Any] = field(repr=False)

    # ── carga ───────────────────────────────────────────────────────────
    @classmethod
    def cargar(cls, raiz: str | Path) -> "Paquete":
        raiz = Path(raiz)
        contrato = raiz / "scene.json"
        if not contrato.exists():
            raise FileNotFoundError(f"no hay scene.json en {raiz}")
        return cls(raiz=raiz, datos=json.loads(contrato.read_text(encoding="utf-8")))

    # ── identidad ───────────────────────────────────────────────────────
    @property
    def pdb_id(self) -> str:
        return self.datos["receptor"]["pdb_id"]

    @property
    def nombre(self) -> str:
        return self.datos["receptor"].get("nombre") or self.pdb_id

    @property
    def familia(self) -> str:
        return self.datos["receptor"].get("familia_estructural") or "desconocida"

    @property
    def resolucion(self) -> float | None:
        return self.datos["receptor"].get("resolucion_a")

    @property
    def seccion(self) -> str | None:
        """La sección del catálogo que declaró el backend («demostracion», «verificado»), o None."""
        return self.datos["receptor"].get("seccion")

    @property
    def cadena_principal(self) -> str:
        return self.datos["receptor"].get("cadena_principal") or "A"

    @property
    def sitio_multicadena(self) -> bool:
        return bool(self.datos["receptor"].get("sitio_multicadena"))

    # ── geometria ───────────────────────────────────────────────────────
    def ruta(self, cual: str) -> Path:
        """cual: 'deposited' | 'prepared' | 'site_ligand'"""
        p = self.raiz / "geometry" / f"{cual}.pdb"
        return p if p.exists() else None

    #: Codigos HET que son COFACTORES, no farmacos. Si el exportador designa
    #: uno de estos como "ligando del sitio", el video es honesto —esta ahi de
    #: verdad— pero la adjudicacion del sitio merece revision aguas arriba.
    #: Caso real: 1CX2 (COX-2) designa HEM, no el inhibidor SC-558.
    COFACTORES = {
        "HEM", "HEC", "HEA", "NAD", "NAP", "NDP", "FAD", "FMN", "ADP", "ATP",
        "GDP", "GTP", "AMP", "SAM", "SAH", "COA", "PLP", "TPP", "BTN", "B12",
    }

    @property
    def es_cofactor(self) -> bool:
        return (self.codigo_het or "").upper() in self.COFACTORES

    @property
    def codigo_het(self) -> str | None:
        """Codigo HET del ligando cocristalizado (MK1, AQ4...)."""
        g = self.datos["geometria"].get("site_ligand") or {}
        return g.get("codigo_het")

    @property
    def tiene_ligando(self) -> bool:
        return self.ruta("site_ligand") is not None

    @property
    def atomos_prepared(self) -> int:
        return self.datos["geometria"]["prepared"]["atomos"]

    @property
    def cadenas_conservadas(self) -> list[str]:
        return self.datos["geometria"]["prepared"].get("cadenas_conservadas") or []

    # ── encuadre ────────────────────────────────────────────────────────
    @property
    def objetivo_a(self) -> tuple[float, float, float]:
        """Centro de la caja de acoplamiento adjudicada, en Angstrom."""
        return tuple(self.datos["encuadre"]["objetivo"])

    @property
    def objetivo(self) -> tuple[float, float, float]:
        """El mismo punto en coordenadas de Blender. Aqui apunta la camara."""
        return tuple(v * ESCALA for v in self.objetivo_a)

    @property
    def caja_a(self) -> tuple[float, float, float]:
        return tuple(self.datos["encuadre"]["caja"])

    # ── docking: datos calculados por molDesign-build, si vienen ──
    #: Contrato del archivo `docking.json` del paquete. No es una parte del
    #: scene.json a proposito: la geometria y su contrato salen de la
    #: estructura; el acoplamiento es una CORRIDA aparte, con su motor, su
    #: semilla y su hash, y tiene que poder decir "aqui no hay docking" sin
    #: falsificar la estructura.
    SCHEMA_DOCK = "moldesign.dock/1"

    @property
    def dock(self) -> dict[str, Any] | None:
        """El acoplamiento calculado por molDesign-build, o None.

    None es la respuesta honesta de tres ausencias distintas: el archivo no
    esta, no declara el contrato `moldesign.dock/1`, o no trae ni caja ni
    poses. El sujeto que lo necesita se abstiene diciendo cual falta; nadie
    tiene por que dibujar un docking que no se puede leer.
        """
        ruta = self.raiz / "docking.json"
        if not ruta.exists():
            return None
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if d.get("schema") != self.SCHEMA_DOCK:
            return None
        caja = d.get("caja") or {}
        poses = d.get("poses") or []
        if not (caja.get("centro") and caja.get("tamano") and poses):
            return None
        return d

    def ruta_dock(self, cual: str) -> Path | None:
        """Ruta verificada de un archivo citado por docking.json.
        Solo se acepta que caiga DENTRO del paquete: un docking.json no puede
        mandarte a leer ni arriba ni fuera de su carpeta.
        """
        d = self.dock
        if d is None:
            return None
        p = (self.raiz / cual).resolve()
        try:
            p.relative_to(self.raiz.resolve())
        except ValueError:
            return None
        return p if p.is_file() else None

    #: Contrato del archivo `ensamble.json`: las conformaciones de entrada, las
    #: poses entregadas por el ensamble de Vina y los controles físicos de cada
    #: una. Es aparte de `docking.json` por la misma razón que éste lo es de
    #: `scene.json`: una corrida de ensamble tiene K corridas de Vina detrás y
    #: ningún archivo de poses único, así que no cabe en `moldesign.dock/1`.
    SCHEMA_ENSAMBLE = "moldesign.ensamble/1"

    @property
    def ensamble(self) -> dict[str, Any] | None:
        """El ensamble conformacional de molDesign-build, o None.

        None es la respuesta honesta de cuatro ausencias distintas: el archivo
        no está, no declara el contrato, no trae la caja o no trae conformaciones
        y poses. El sujeto que lo necesita se abstiene diciendo cuál falta.
        """
        ruta = self.raiz / "ensamble.json"
        if not ruta.exists():
            return None
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(d, dict) or d.get("schema") != self.SCHEMA_ENSAMBLE:
            return None
        caja = d.get("caja") or {}
        if not (caja.get("centro") and caja.get("tamano")
                and d.get("conformeros") and d.get("poses")):
            return None
        return d

    def ruta_ensamble(self, cual: str) -> Path | None:
        """Ruta verificada de un archivo citado por ensamble.json.

        Sólo se acepta que caiga DENTRO del paquete, igual que `ruta_dock`.
        """
        if self.ensamble is None or not isinstance(cual, str) or not cual:
            return None
        p = (self.raiz / cual).resolve()
        try:
            p.relative_to(self.raiz.resolve())
        except ValueError:
            return None
        return p if p.is_file() else None

    # ── que destacar ────────────────────────────────────────────────────
    #: Residuos cuya cadena lateral no da nada que dibujar. GLY no tiene, y
    #: ALA solo un metilo: etiquetarlos deja la etiqueta apuntando al vacio.
    SIN_CADENA_LATERAL = {"GLY", "ALA"}

    def hotspots(self, cuantos: int | None = None,
                 solo_dibujables: bool = True) -> list[Hotspot]:
        out = []
        for h in self.datos["resaltar"]["hotspots"]:
            if not h.get("parseado"):
                continue
            if solo_dibujables and h["resname"].upper() in self.SIN_CADENA_LATERAL:
                continue
            out.append(Hotspot(h["cadena"], h["resname"], int(h["numero"]),
                               float(h.get("importancia") or 0.0)))
        out.sort(key=lambda h: -h.importancia)
        return out[:cuantos] if cuantos else out

    @property
    def huecos(self) -> list[Hueco]:
        out = []
        for g in (self.datos["declarado"].get("huecos_de_cadena") or []):
            a, b = g["entre_residuos"]
            out.append(Hueco(g["cadena"], int(a), int(b),
                             float(g.get("distancia_ca_ca_a") or 0.0),
                             int(g.get("residuos_ausentes") or 0)))
        return out

    def rangos_continuos(self, cadena: str, minimo: int, maximo: int) -> list[tuple[int, int]]:
        """Tramos de residuo sin rotura, para dibujar la cinta por segmentos.

        Dibujar un solo cartoon sobre una cadena rota inventa conectividad que
        la estructura no resuelve; pasa en el 51% del catalogo. Partiendo el
        estilo en estos rangos, la cinta se corta sola en cada hueco.
        """
        cortes = [h for h in self.huecos if h.cadena == cadena]
        tramos, inicio = [], minimo
        for h in sorted(cortes, key=lambda x: x.desde):
            if inicio <= h.desde:
                tramos.append((inicio, h.desde))
            inicio = h.hasta
        if inicio <= maximo:
            tramos.append((inicio, maximo))
        return tramos

    # ── aguas ───────────────────────────────────────────────────────────
    @property
    def aguas(self) -> dict[str, Any]:
        return self.datos["declarado"].get("aguas") or {}

    # ── EL CONTRATO ─────────────────────────────────────────────────────
    @property
    def prohibido(self) -> dict[str, dict[str, str]]:
        return {n["id"]: n for n in self.datos.get("no_dibujar", [])}

    @property
    def condicionado(self) -> dict[str, dict[str, str]]:
        return {n["id"]: n for n in self.datos.get("declarar_si_se_dibuja", [])}

    def exigir(self, *ids: str) -> None:
        """Levanta `Prohibido` si alguna regla esta en la lista dura.

        Esto es lo que hace vinculante el contrato. El guion declara que
        permisos necesita cada plano; si el receptor no los concede, el plano
        no se monta.
        """
        for i in ids:
            regla = self.prohibido.get(i)
            if regla is not None:
                raise Prohibido(i, regla.get("razon", ""),
                                regla.get("permitido_en_su_lugar", ""))

    def declaraciones(self, *ids: str) -> list[str]:
        """Condiciones que hay que rotular si se dibuja eso."""
        return [self.condicionado[i]["condicion"] for i in ids if i in self.condicionado]

    # ── procedencia ─────────────────────────────────────────────────────
    @property
    def procedencia(self) -> dict[str, Any]:
        return self.datos.get("procedencia", {})

    def resumen(self) -> dict[str, Any]:
        return {
            "pdb_id": self.pdb_id,
            "nombre": self.nombre,
            "familia": self.familia,
            "resolucion_a": self.resolucion,
            "atomos_prepared": self.atomos_prepared,
            "objetivo_a": [round(v, 3) for v in self.objetivo_a],
            "objetivo_blender": [round(v, 4) for v in self.objetivo],
            "hotspots": len(self.hotspots()),
            "huecos": len(self.huecos),
            "tiene_ligando": self.tiene_ligando,
            "sitio_multicadena": self.sitio_multicadena,
            "prohibido": sorted(self.prohibido),
            "condicionado": sorted(self.condicionado),
        }
