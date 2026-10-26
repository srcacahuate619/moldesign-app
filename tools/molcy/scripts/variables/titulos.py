"""VARIABLE: el nombre del receptor que va en el rotulo inferior.

Sin `bpy`, para poder probarlo fuera de Blender. `rotulos.py` lo reexporta.

El TITLE del PDB viene casi siempre en MAYUSCULAS y el `.title()` de Python lo
estropea: «DNA» sale «Dna», «E. COLI» sale «E. Coli», «TRICHOSTATIN A» sale
«Trichostatin a». Solo 12 receptores tienen nombre curado; los otros 368 salian
asi en el video (el vertical de 016 decia «Dimerization Of E. Coli Dna Gyrase
B»). Aqui se capitaliza palabra a palabra respetando siglas, numerales, letras
sueltas y especies. Los titulos que ya vienen en caja mixta no se tocan: quien
los escribio sabia lo que hacia.
"""
from __future__ import annotations

import re
import textwrap

from marca.idioma import idioma_del_cierre

# Nombres editoriales cortos para casos con identidad cientifica inequivoca.
# El fallback procedural evita que un TITLE nuevo reviente el encuadre.
NOMBRES_CURADOS = {
    "1BN1": "Carbonic Anhydrase II (CA2)",
    "1C3P": "HDAC homolog (Aquifex aeolicus)",
    "1C3R": "HDAC homolog · Trichostatin A",
    "1C3S": "HDAC homolog · SAHA",
    "1CX2": "COX-2 (Cyclooxygenase-2)",
    "1FE2": "COX-1 (Cyclooxygenase-1)",
    "1F0R": "Factor Xa",
    "1GPK": "Acetylcholinesterase (AChE)",
    "1HSG": "HIV-1 Protease",
    "1HWK": "HMG-CoA Reductase",
    "2NNJ": "Cytochrome P450",
    "3ERT": "ER Alpha (Estrogen Receptor)",
}

#: Van en minuscula salvo al principio.
MENORES = frozenset({
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of",
    "on", "or", "the", "to", "with", "without", "via", "versus", "vs"})

#: Palabras de hasta tres letras que NO son siglas. Todo lo demas de tres
#: letras o menos se trata como sigla (DNA, ATP, HIV, LBD, SRC...).
CORTAS_COMUNES = frozenset({
    "apo", "bis", "new", "two", "one", "six", "ten", "rat", "pig", "cow",
    "man", "arm", "cap", "tag", "key", "low", "act", "due", "end", "its",
    "not", "off", "old", "out", "own", "per", "set", "top", "use", "all",
    "any", "but", "can", "has", "how", "non", "sub", "pre", "pro", "tri",
    "are", "was", "be", "is", "day", "big", "raw", "red", "gap", "gut",
    "hot", "dry", "wet", "fat"})

#: Siglas de cuatro letras o mas que no se pueden deducir por la longitud.
SIGLAS_LARGAS = frozenset({
    "HDAC", "SAHA", "EGFR", "PPAR", "MAPK", "NADP", "NADH", "GABA", "BACE",
    "PARP", "DHFR", "AMPA", "NMDA", "SARS", "IBMX", "ANCE", "HMGR", "BRAF",
    "KRAS", "HRAS", "NRAS", "MERS", "GPCR", "SIRT", "MTOR", "FGFR", "VEGFR",
    "PDGFR", "INSR", "TSHR", "NSAID", "KEAP", "DNMT", "PRMT", "SMAD", "STAT",
    "SCFV"})

#: Caja mixta que ninguna regla adivina.
FIJAS = {
    "ATPASE": "ATPase", "GTPASE": "GTPase", "HMG-COA": "HMG-CoA",
    "ACHE": "AChE", "CAMP": "cAMP", "CGMP": "cGMP", "MRNA": "mRNA",
    "TRNA": "tRNA", "RRNA": "rRNA", "SIRNA": "siRNA", "PH": "pH",
    "DUMP": "dUMP", "DTMP": "dTMP", "KDA": "kDa"}

#: Generos frecuentes en el PDB: el epiteto que les sigue va en minuscula.
GENEROS = frozenset({
    "Escherichia", "Aquifex", "Thermus", "Archaeoglobus", "Saccharomyces",
    "Homo", "Mus", "Rattus", "Bos", "Drosophila", "Plasmodium",
    "Mycobacterium", "Staphylococcus", "Streptococcus", "Pseudomonas",
    "Bacillus", "Thermotoga", "Pyrococcus", "Thermococcus", "Trypanosoma",
    "Leishmania", "Candida", "Helicobacter", "Klebsiella", "Salmonella",
    "Toxoplasma", "Schistosoma", "Arabidopsis", "Caenorhabditis", "Danio",
    "Xenopus", "Gallus", "Sus", "Methanococcus", "Methanocaldococcus",
    "Sulfolobus", "Deinococcus", "Enterococcus", "Clostridium", "Haemophilus",
    "Neisseria", "Vibrio", "Yersinia", "Shigella", "Legionella", "Chlamydia",
    "Listeria", "Burkholderia", "Acinetobacter", "Streptomyces", "Aspergillus",
    "Cryptococcus", "Bacteroides", "Thermoplasma", "Trichomonas", "Giardia",
    "Entamoeba", "Cryptosporidium", "Brugia", "Onchocerca", "Torpedo",
    "Tetrahymena", "Anopheles", "Heligmosomoides"})

#: Tras estas palabras, una «A» suelta es articulo y no letra.
_ANTES_DE_ARTICULO = frozenset({
    "is", "are", "was", "be", "reveal", "reveals", "provides", "provide",
    "as", "like"})

_PREFIJOS = re.compile(
    r"^(the )?((x-ray|cryo-em) )?(crystal )?structures? (analysis )?of (the )?",
    re.IGNORECASE)


def _partes(w: str) -> tuple[str, str, str]:
    """Puntuacion delante, nucleo alfanumerico, puntuacion detras."""
    return re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$", w).groups()


def _palabra(w: str, primera: bool, previa: str | None,
             siguiente: str | None, compuesta: bool = False) -> str:
    pre, nucleo, post = _partes(w)
    if not nucleo:
        return w
    mayus = nucleo.upper()
    if "-" in nucleo and mayus not in FIJAS:
        trozos = nucleo.split("-")
        return pre + "-".join(
            _palabra(t, primera and i == 0, None, None, compuesta=True) if t else t
            for i, t in enumerate(trozos)) + post
    if mayus in FIJAS:
        out = FIJAS[mayus]
    elif any(c.isdigit() for c in nucleo):
        out = mayus
    elif mayus == "A":
        # «COMPLEXED WITH A SELECTIVE» frente a «TRICHOSTATIN A» o «GYRASE A
        # C-TERMINAL»: es articulo si le sigue algo y lo precede una
        # preposicion, un verbo o nada.
        p = (previa or "").lower().strip(",;:()")
        articulo = (not compuesta and siguiente is not None
                    and (previa is None or p in MENORES or p in _ANTES_DE_ARTICULO
                         or p.endswith(("s", "ed", "ing"))))
        out = "a" if articulo and not primera else "A"
    elif nucleo.lower() in MENORES:
        out = nucleo.capitalize() if primera else nucleo.lower()
    elif mayus in SIGLAS_LARGAS:
        out = mayus
    elif len(nucleo) <= 3 and nucleo.isalpha() and nucleo.lower() not in CORTAS_COMUNES:
        out = mayus
    elif re.fullmatch(r"[IVX]+", mayus) and len(mayus) <= 4:
        out = mayus                                   # numerales romanos
    else:
        out = nucleo[:1].upper() + nucleo[1:].lower()
    return pre + out + post


def _capitalizar(s: str) -> str:
    ws = s.split(" ")
    s = " ".join(_palabra(w, i == 0, ws[i - 1] if i else None,
                          ws[i + 1] if i + 1 < len(ws) else None)
                 for i, w in enumerate(ws))
    # especie abreviada y binomial: E. COLI -> E. coli, Aquifex aeolicus
    s = re.sub(r"\b([A-Z])\. ([A-Z][a-z]+)\b",
               lambda m: f"{m.group(1)}. {m.group(2).lower()}", s)
    s = re.sub(r"\b(" + "|".join(sorted(GENEROS)) + r") ([A-Z][a-z]+)\b",
               lambda m: f"{m.group(1)} {m.group(2).lower()}", s)
    s = re.sub(r"\bFactor ([IVX]+)A\b", r"Factor \1a", s)    # Factor Xa, VIIa
    return re.sub(r"(\d)KDA\b", r"\1 kDa", s)


def nombre_legible(nombre: str) -> str:
    """Convierte un TITLE PDB en un nombre editorial legible."""
    s = re.sub(r"\s+", " ", str(nombre or "")).strip(" .")
    letras = [c for c in s if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.8:
        s = _capitalizar(s)
    s = _PREFIJOS.sub("", s)
    # El exportador trunca algunos TITLE a media frase: fuera la cola
    # colgante («...Domain with», «...Bis-1,»). Solo minusculas: una «A»
    # mayuscula al final es una letra («Trichostatin A»), no un articulo.
    while True:
        t = re.sub(r"[\s,;:\-]+$", "", s)
        cabeza, _, ult = t.rpartition(" ")
        if cabeza and ult in MENORES:
            t = cabeza
        if t == s:
            break
        s = t
    return (s[:1].upper() + s[1:]) or "Molecular target"


#: Etiqueta de la sección del catálogo que declara `scene.json` (`receptor.seccion`), por idioma
#: del cierre. Sólo «demostracion» se rotula aquí: el vídeo dice lo que dice la aplicación.
ETIQUETAS_DE_SECCION = {"demostracion": {"es": "Demostración", "en": "Demonstration"}}


def titulo_pantalla(pdb_id: str, nombre: str, resolucion=None,
                    base: float = 0.78, ancho: int = 42,
                    seccion: str | None = None, idioma: str | None = None, *,
                    alias: str | None = None) -> tuple[str, float]:
    """Devuelve texto y escala seguros para el rotulo inferior.

    Con `seccion="demostracion"` añade una línea con la etiqueta del catálogo en el idioma del
    cierre (`marca.idioma`), para que el título y el vídeo digan lo mismo que la aplicación.
    Un `alias` (el título que eligió el usuario) sustituye al nombre y no se recorta, pero no
    quita esa línea: el título propio no puede ocultar que el receptor es de demostración.
    """
    corto = alias if alias is not None else NOMBRES_CURADOS.get(str(pdb_id).upper(), nombre_legible(nombre))
    res = f" · {resolucion} Å" if resolucion else ""
    completo = f"{corto}   ·   {pdb_id}{res}"
    lineas = textwrap.wrap(completo, width=ancho, break_long_words=alias is not None,
                           break_on_hyphens=False) or [completo]
    if len(lineas) > 2 and alias is None:
        lineas = lineas[:2]
        lineas[-1] = textwrap.shorten(lineas[-1], width=ancho,
                                      placeholder="…")
    etiqueta = ETIQUETAS_DE_SECCION.get(seccion or "", {}).get(idioma or idioma_del_cierre())
    if etiqueta:
        lineas.append(etiqueta)
    mayor = max(len(x) for x in lineas)
    factor = min(1.0, max(0.72, 38.0 / max(mayor, 1)))
    if len(lineas) > 1:
        factor = min(factor, 0.90)
    return "\n".join(lineas), base * factor
