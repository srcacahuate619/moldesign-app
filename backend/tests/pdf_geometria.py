"""Geometría de un PDF ya generado: dónde cae cada imagen y cada tramo de texto.

Las pruebas de figuras de este repositorio comprobaban que la función devolvía una `Image`. Eso no ve lo que ve quien abre el
PDF: una imagen opaca que tapa el SMILES, una figura que se sale del margen, una imagen deformada o borrosa. Estas funciones
leen el PDF (con `pypdf`, que ya usan las demás pruebas de PDF) y devuelven coordenadas en puntos, origen abajo a la izquierda,
las del propio PDF.

Dos límites declarados:

* el ancho de un tramo de texto se estima por su número de caracteres (0,55 em en monoespaciada, 0,48 em en las demás):
  basta para decidir si una imagen lo cubre, no para medir una tipografía;
* sólo se ven las imágenes que ReportLab coloca con `Do` (todas las del producto).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Caja:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def ancho(self) -> float:
        return self.x1 - self.x0

    @property
    def alto(self) -> float:
        return self.y1 - self.y0

    def solapa(self, otra: "Caja", tolerancia: float = 0.75) -> bool:
        """`True` si las dos cajas comparten un área mayor que `tolerancia` en los dos ejes."""
        dx = min(self.x1, otra.x1) - max(self.x0, otra.x0)
        dy = min(self.y1, otra.y1) - max(self.y0, otra.y0)
        return dx > tolerancia and dy > tolerancia


@dataclass(frozen=True)
class Imagen:
    caja: Caja
    px_ancho: int
    px_alto: int
    con_alfa: bool

    @property
    def dpi(self) -> float:
        return self.px_ancho / (self.caja.ancho / 72) if self.caja.ancho else 0.0

    @property
    def deformacion(self) -> float:
        """Diferencia relativa entre la proporción de la imagen y la de su caja (0 = sin deformar)."""
        if not (self.px_alto and self.caja.alto):
            return 0.0
        return abs((self.px_ancho / self.px_alto) / (self.caja.ancho / self.caja.alto) - 1)


@dataclass(frozen=True)
class Texto:
    caja: Caja
    texto: str
    tamano: float
    #: Color de relleno (r, g, b) entre 0 y 1 con el que se dibuja.
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def contraste(self) -> float:
        """Contraste WCAG de este texto sobre blanco (21 = negro; 4,5 es el mínimo de AA para texto normal)."""
        def lin(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (lin(c) for c in self.color)
        luminancia = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return 1.05 / (luminancia + 0.05)


@dataclass
class Pagina:
    ancho: float
    alto: float
    imagenes: list[Imagen] = field(default_factory=list)
    textos: list[Texto] = field(default_factory=list)

    def figuras(self) -> list[Imagen]:
        """Las imágenes que no son la marca de agua (la que lleva canal alfa y cubre media hoja)."""
        return [i for i in self.imagenes if not (i.con_alfa and i.caja.ancho > 250 and i.caja.alto > 250)]


def _mul(a: list[float], b: list[float]) -> list[float]:
    """Producto de matrices de PDF (vectores fila): `a` aplicada primero, luego `b`."""
    return [
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def _bytes(valor) -> bytes:
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor)
    if hasattr(valor, "original_bytes"):
        return valor.original_bytes
    return str(valor).encode("latin-1", "replace")


def _ancho(n_caracteres: int, tamano: float, monoespaciada: bool) -> float:
    # Estimación: 0,55 em la monoespaciada y 0,48 em la proporcional (algo por debajo del promedio de Helvetica, para no
    # acusar a un texto que termina justo antes de una figura). Basta para decidir un solape de varios puntos.
    return (0.55 if monoespaciada else 0.48) * tamano * n_caracteres


def paginas(datos: bytes) -> list[Pagina]:
    """Interpreta el flujo de contenido de cada página y devuelve dónde cae cada imagen y cada línea de texto.

    Se interpreta aquí, sin los visitantes de `pypdf.extract_text`, porque estos no acumulan bien la matriz de transformación
    dentro de las celdas de una tabla (medido: en las celdas de texto largo la `y` salía 208 pt corrida frente a PyMuPDF) y
    cambian entre versiones. Sólo hacen falta los operadores que emite ReportLab.
    """
    import pypdf
    from pypdf.generic import ContentStream

    lector = pypdf.PdfReader(io.BytesIO(datos))
    resultado: list[Pagina] = []
    for pagina in lector.pages:
        p = Pagina(float(pagina.mediabox.width), float(pagina.mediabox.height))
        recursos = pagina["/Resources"].get_object() if "/Resources" in pagina else {}
        xobjetos = recursos.get("/XObject", {})
        xobjetos = xobjetos.get_object() if hasattr(xobjetos, "get_object") else xobjetos
        fuentes = recursos.get("/Font", {})
        fuentes = fuentes.get_object() if hasattr(fuentes, "get_object") else fuentes

        ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        color = (0.0, 0.0, 0.0)
        pila: list[tuple[list[float], tuple[float, float, float]]] = []
        tm = tlm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        interlineado, tamano, mono = 0.0, 0.0, False
        contenido = pagina.get_contents()
        if contenido is None:
            resultado.append(p)
            continue
        for operandos, operador in ContentStream(contenido, lector).operations:
            if operador == b"q":
                pila.append((list(ctm), color))
            elif operador == b"Q":
                ctm, color = pila.pop() if pila else ([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], (0.0, 0.0, 0.0))
            elif operador == b"rg":
                color = (float(operandos[0]), float(operandos[1]), float(operandos[2]))
            elif operador == b"g":
                color = (float(operandos[0]),) * 3
            elif operador == b"k":
                c, m, y, k = (float(v) for v in operandos)
                color = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
            elif operador == b"cm":
                ctm = _mul([float(v) for v in operandos], ctm)
            elif operador == b"BT":
                tm = tlm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
            elif operador == b"Tm":
                tm = tlm = [float(v) for v in operandos]
            elif operador in (b"Td", b"TD"):
                tx, ty = float(operandos[0]), float(operandos[1])
                if operador == b"TD":
                    interlineado = -ty
                tlm = _mul([1.0, 0.0, 0.0, 1.0, tx, ty], tlm)
                tm = tlm
            elif operador == b"TL":
                interlineado = float(operandos[0])
            elif operador == b"T*":
                tlm = _mul([1.0, 0.0, 0.0, 1.0, 0.0, -interlineado], tlm)
                tm = tlm
            elif operador == b"Tf":
                tamano = float(operandos[1])
                fuente = fuentes.get(operandos[0])
                nombre = str(fuente.get_object().get("/BaseFont", "")) if fuente is not None else ""
                mono = any(m in nombre for m in ("Consolas", "Courier", "Mono"))
            elif operador in (b"Tj", b"'", b'"', b"TJ"):
                if operador in (b"'", b'"'):
                    tlm = _mul([1.0, 0.0, 0.0, 1.0, 0.0, -interlineado], tlm)
                    tm = tlm
                trozos = operandos[-1] if operador == b"TJ" else [operandos[-1]]
                crudo = b"".join(_bytes(t) for t in trozos if not isinstance(t, (int, float)) and not hasattr(t, "as_numeric"))
                if not crudo.strip():
                    continue
                e = _mul(tm, ctm)
                x, y = e[4], e[5]
                p.textos.append(Texto(Caja(x, y - 0.22 * tamano, x + _ancho(len(crudo), tamano, mono), y + 0.78 * tamano),
                                      crudo.decode("latin-1", "replace"), tamano, color))
            elif operador == b"Do" and operandos and operandos[0] in xobjetos:
                obj = xobjetos[operandos[0]].get_object()
                if obj.get("/Subtype") == "/Image":
                    a, d, e, f = ctm[0], ctm[3], ctm[4], ctm[5]
                    p.imagenes.append(Imagen(Caja(min(e, e + a), min(f, f + d), max(e, e + a), max(f, f + d)),
                                             int(obj["/Width"]), int(obj["/Height"]), "/SMask" in obj))
        resultado.append(p)
    return resultado


def fuentes_sin_incrustar(datos: bytes) -> list[str]:
    """Los nombres de las fuentes que el PDF declara y no lleva dentro (las 14 estándar: Helvetica, Courier, Symbol…)."""
    import pypdf

    sin_incrustar: set[str] = set()
    for pagina in pypdf.PdfReader(io.BytesIO(datos)).pages:
        recursos = pagina.get("/Resources")
        fuentes = recursos.get("/Font") if recursos else None
        for fuente in (fuentes.get_object().values() if fuentes else ()):
            fuente = fuente.get_object()
            descriptor = fuente.get("/FontDescriptor")
            if descriptor is None and "/DescendantFonts" in fuente:
                descriptor = fuente["/DescendantFonts"][0].get_object().get("/FontDescriptor")
            incrustada = descriptor is not None and any(
                clave in descriptor.get_object() for clave in ("/FontFile", "/FontFile2", "/FontFile3")
            )
            if not incrustada:
                sin_incrustar.add(str(fuente.get("/BaseFont")).lstrip("/"))
    return sorted(sin_incrustar)
