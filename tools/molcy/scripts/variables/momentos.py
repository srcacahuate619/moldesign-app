"""VARIABLE: los instantes de una escena que valen una foto.

Una foto es UN fotograma del guion (el del `.blend`). Las pausas del montaje no
cuentan: una pausa repite un fotograma que ya existe. Los momentos sugeridos no
salen de una lista escrita a mano, sino de la propia escena, porque son los
instantes en que el vídeo ya decidió que había algo que mirar:

- cada pausa del montaje: un grupo de etiquetas acaba de entrar entero
  (`lectura`) o la cámara se detiene sobre el sitio (`imagen_fija`);
- el plano general con el título, a mitad del tramo en que se ve entero;
- la mitad de cada beat de recorrido que no tiene pausa propia (la vuelta final
  de Resultado, la búsqueda en curso, la retirada).

Fuera de esa lista, el selector libre admite cualquier fotograma de 1 a n.

Sin bpy: se prueba fuera de Blender (`pruebas/test_momentos.py`).
"""
from __future__ import annotations

#: Papeles de beat cuya mitad es una toma: la cámara recorre algo que no se ve en
#: ninguna pausa. `aproximar` no entra: es el viaje hacia el sitio, a medio camino.
PAPELES_DE_RECORRIDO = ("explorar", "establecer")


def beat_de(fotograma: int, rangos: dict) -> str | None:
    """El beat que contiene `fotograma` (rangos inclusivos), o None."""
    for nombre, (a, b) in rangos.items():
        if a <= fotograma <= b:
            return nombre
    return None


def _ventana_entera(titulo: dict) -> tuple[int, int] | None:
    """El tramo en que el título se ve entero: su ventana sin los fundidos."""
    a, b = (int(x) for x in titulo["ventana"])
    for f0, f1, v0, v1 in titulo.get("fundido") or []:
        if v0 < v1:          # entra: entero desde que acaba de entrar
            a = max(a, int(f1))
        elif v0 > v1:        # sale: entero hasta que empieza a salir
            b = min(b, int(f0))
    return (a, b) if a <= b else None


def sugeridos(rangos: dict, pausas: list, n: int, *, titulo: dict | None = None,
              papeles: dict | None = None, rotulos_por_pose: dict | None = None,
              firma=None) -> list[dict]:
    """Los momentos sugeridos, en el orden en que ocurren.

    `rangos`: beat -> (inicio, fin) en fotogramas fuente. `pausas`: las del
    montaje (`pausas.montar(...)["pausas"]`), con `fuente`, `tipo` y `etiquetas`.
    `titulo`: la entrada del rótulo de pantalla del plano general (`ventana`,
    `fundido`), si el guion lo pone. `papeles`: beat -> papel. `rotulos_por_pose`:
    rango de la pose -> ids de sus etiquetas, para decir de qué pose es una pausa.
    `firma`: fotograma -> algo comparable que es igual sólo si la imagen es la
    misma (`salida/firmas.py`, escena y capa de rótulos). Con ella, una toma que
    se vería idéntica a otra ya sugerida no se repite: en un receptor sin ligando
    el sitio vacío y la llegada del sujeto (que no llega) son la misma imagen.
    """
    if n < 1:
        raise ValueError("momentos: la escena no tiene fotogramas")
    papeles = papeles or {}
    por_pose = {int(r): set(ids) for r, ids in (rotulos_por_pose or {}).items()}
    out: list[dict] = []
    ocupados: set[str] = set()

    def anadir(fotograma: int, tipo: str, etiquetas=(), pose=None) -> None:
        fotograma = max(1, min(n, int(fotograma)))
        beat = beat_de(fotograma, rangos)
        out.append({"id": f"{beat or 'escena'}-{fotograma}", "fotograma": fotograma,
                    "beat": beat, "tipo": tipo, "etiquetas": len(etiquetas),
                    "pose": pose})
        if beat:
            ocupados.add(beat)

    for p in pausas:
        ids = set(p.get("etiquetas") or ())
        pose = next((r for r, suyos in sorted(por_pose.items()) if ids and ids & suyos), None)
        anadir(p["fuente"], p.get("tipo", "lectura"), ids, pose)
    if titulo:
        tramo = _ventana_entera(titulo)
        if tramo:
            anadir((tramo[0] + tramo[1]) // 2, "titulo")
    for nombre, (a, b) in rangos.items():
        if nombre in ocupados or papeles.get(nombre) not in PAPELES_DE_RECORRIDO:
            continue
        anadir((a + b) // 2, "recorrido")

    vistos: dict[int, dict] = {}
    for m in sorted(out, key=lambda m: m["fotograma"]):
        vistos.setdefault(m["fotograma"], m)      # dos sugerencias en el mismo fotograma: la primera
    unicos: list[dict] = []
    imagenes: set = set()
    for m in vistos.values():
        clave = firma(m["fotograma"]) if firma is not None else None
        if clave is not None and clave in imagenes:
            continue                               # la misma imagen que una toma anterior
        if clave is not None:
            imagenes.add(clave)
        unicos.append(m)
    return [dict(m, orden=i) for i, m in enumerate(unicos, start=1)]


def validar_fotograma(fotograma, n: int) -> int:
    """El fotograma libre que pide la interfaz, o ValueError: entero de 1 a n."""
    if type(fotograma) is not int or not 1 <= fotograma <= n:
        raise ValueError(f"El fotograma tiene que ser un entero entre 1 y {n}.")
    return fotograma
