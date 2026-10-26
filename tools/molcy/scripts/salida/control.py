"""Puerta de calidad ANTES de renderizar. Barata y obligatoria.

Un encuadre malo cuesta lo mismo de construir que uno bueno —tres segundos— y
media hora de render. Los numeros que delatan el fallo YA estan en `medidas`;
lo unico que faltaba era el umbral.

Caso real que motivo este modulo: en 005 (1HWK) y 006 (1CX2) la distancia de
primer plano salio MAYOR que la del plano general (33.5 vs 15.7, y 64.3 vs
13.3). La camara se alejaba en vez de acercarse, la proteina quedaba oscura y
los hotspots flotaban fuera de la estructura. Todo por una causa: el centroide
de residuo no filtraba por cadena, asi que en un receptor multicadena el
"hotspot" caia en el promedio entre copias, fuera de la proteina. Nadie lo vio
hasta tener los videos hechos.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Aviso:
    gravedad: str        # "fatal" | "alerta"
    id: str
    detalle: str


@dataclass
class Informe:
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def fatales(self) -> list[Aviso]:
        return [a for a in self.avisos if a.gravedad == "fatal"]

    @property
    def ok(self) -> bool:
        return not self.fatales

    def como_lista(self) -> list[dict]:
        return [{"gravedad": a.gravedad, "id": a.id, "detalle": a.detalle}
                for a in self.avisos]


def revisar(medidas: dict, formato, guion=None) -> Informe:
    inf = Informe()
    D1 = medidas.get("dist_general") or 0.0
    D0 = medidas.get("dist_primer_plano") or 0.0
    arco = medidas.get("arco") or {}
    vis = medidas.get("visibilidad_azimut")
    radio = medidas.get("radio_dianas") or 0.0
    # El guion puede DECLARAR que su primer plano encuadra algo ancho a
    # proposito (la escena x encuadra la CAJA de acoplamiento, que puede ser
    # mas ancha que el core del receptor). Entonces dar un paso atras es el
    # encuadre correcto, y el umbral de dispersion es el del volumen buscado.
    permite_alejamiento = bool(getattr(guion, "QC_PERMITE_ALEJAMIENTO", False))
    factor_dianas = float(getattr(guion, "QC_DIANAS_FACTOR", 0.35))

    if D0 and D1 and D0 >= D1 * 0.85 and not permite_alejamiento:
        inf.avisos.append(Aviso(
            "fatal", "camara_se_aleja",
            f"la distancia de primer plano ({D0:.2f}) no es menor que la del "
            f"plano general ({D1:.2f}): la aproximacion seria un alejamiento. "
            "Casi siempre significa que las dianas estan dispersas — revisa el "
            "filtrado por cadena de los hotspots en receptores multicadena."))

    if radio and D1 and radio > D1 * factor_dianas:
        inf.avisos.append(Aviso(
            "fatal", "dianas_dispersas",
            f"el radio de las dianas ({radio:.2f}) es el "
            f"{100 * radio / D1:.0f}% de la distancia del plano general. Un "
            "sitio activo no ocupa media proteina: hay dianas mal situadas."))

    if (not formato.bucle) and arco.get("minimo") is not None             and arco["minimo"] < 0.40:
        inf.avisos.append(Aviso(
            "alerta", "arco_ocluido",
            f"la visibilidad minima del arco es {arco['minimo']:.3f}: durante "
            "parte del plano final el sujeto queda tapado."))

    if vis is not None and vis < 0.5:
        inf.avisos.append(Aviso(
            "alerta", "aproximacion_ocluida",
            f"el azimut de aproximacion solo ve el {vis:.0%} del sitio."))

    if formato.bucle:
        # En un formato en bucle el plano que se ve es la ORBITA, no el arco
        # de primer plano: mirar `arco.minimo` era medir lo que no se usa.
        orb = medidas.get("orbita") or {}
        minimo = orb.get("minimo")
        if minimo is not None and minimo < 0.45:
            inf.avisos.append(Aviso(
                "alerta", "bucle_con_punto_ciego",
                f"la orbita del bucle baja a {minimo:.3f} de visibilidad "
                f"(elevacion {orb.get('elevacion')}): parte de cada vuelta "
                "deja el sujeto tapado, y en un bucle eso se repite."))

    return inf
