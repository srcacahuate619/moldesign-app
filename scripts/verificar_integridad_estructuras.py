"""Verifica que comprimir las estructuras del catalogo no perdio NADA.

# Por que existe esta herramienta

Las 387 estructuras del catalogo viajan en gzip dentro del instalador, porque
sin comprimir el runtime pasa de 2 GiB y `makensis` no puede empaquetarlo. La
pregunta legitima que eso levanta es si se pierde calidad cientifica.

**No se pierde, y aqui esta la demostracion en vez de la afirmacion.** gzip es
sin perdida por definicion, pero una definicion no es una comprobacion: lo que
importa es si LOS ARCHIVOS QUE ENVIAMOS estan intactos.

# Las tres comprobaciones, de menos a mas exigente

1. **CRC del gzip.** El formato lleva un CRC32 del contenido original. Si
   descomprime sin error, los bytes recuperados son identicos bit a bit a los
   que se comprimieron. No es confiar en gzip: es el propio formato
   comprobandose.

2. **Contenido cientifico.** Cada archivo tiene que seguir siendo un PDB con
   coordenadas legibles. Un archivo que descomprime pero perdio los ATOM no
   serviria de nada aunque el CRC cuadre.

3. **Contraste con el ORIGEN.** Para una muestra, se vuelve a pedir la
   estructura al RCSB y se comparan los bytes descomprimidos por SHA-256. Esto
   cierra la duda que el CRC no cubre: que lo que comprimimos fuera lo correcto.
   Es la unica de las tres que necesita red.

# Resultado del 2026-09-02

    407 archivos, 407 CRC correctos, 0 corruptos
    349.1 MB originales -> 83.8 MB  (4.2x)
    407 con coordenadas, 3.065.782 atomos, 0 ilegibles
    12/12 de la muestra: SHA-256 IDENTICO al del RCSB

# Donde SI hay riesgo cientifico, que no es aqui

La compresion es inocua. Lo que si compromete la ciencia esta medido en el
doc 71: el filtro de UNA sola cadena deja a 149 de 387 objetivos acoplando
contra menos del 80% de los atomos de su caja, y a veinte contra ninguno.

# Uso

    python scripts/verificar_integridad_estructuras.py [tamano_de_muestra]
"""
import gzip
import hashlib
import pathlib
import random
import sys
import urllib.request

RAIZ = pathlib.Path("D:/moldesign-build/data/targets")
MUESTRA = int(sys.argv[1]) if len(sys.argv) > 1 else 12

print("=" * 74)
print("1) INTEGRIDAD DEL GZIP  (CRC32 del contenido original)")
print("=" * 74)
archivos = sorted(RAIZ.glob("*.pdb.gz"))
rotos, ok = [], 0
bytes_comprimidos = bytes_originales = 0
for f in archivos:
    try:
        crudo = gzip.decompress(f.read_bytes())   # lanza si el CRC no cuadra
        ok += 1
        bytes_comprimidos += f.stat().st_size
        bytes_originales += len(crudo)
    except Exception as exc:
        rotos.append((f.name, type(exc).__name__))
print(f"  archivos            : {len(archivos)}")
print(f"  CRC correcto        : {ok}")
print(f"  CORRUPTOS           : {len(rotos)}")
for n, e in rotos[:10]:
    print(f"      {n}: {e}")
print(f"  {bytes_originales/1e6:.1f} MB originales -> {bytes_comprimidos/1e6:.1f} MB "
      f"({bytes_originales/max(bytes_comprimidos,1):.1f}x)")

print()
print("=" * 74)
print("2) CONTENIDO CIENTIFICO  (sigue siendo un PDB con coordenadas)")
print("=" * 74)
sin_atomos, mal_formados, total_atomos = [], [], 0
for f in archivos:
    texto = gzip.decompress(f.read_bytes()).decode("utf-8", errors="replace")
    atomos = [l for l in texto.splitlines() if l.startswith(("ATOM", "HETATM"))]
    if not atomos:
        sin_atomos.append(f.name)
        continue
    total_atomos += len(atomos)
    try:
        for l in atomos[:50] + atomos[-50:]:
            float(l[30:38]); float(l[38:46]); float(l[46:54])
    except ValueError:
        mal_formados.append(f.name)
print(f"  estructuras con coordenadas : {len(archivos) - len(sin_atomos)}")
print(f"  SIN atomos                  : {len(sin_atomos)}  {sin_atomos[:5]}")
print(f"  coordenadas ilegibles       : {len(mal_formados)}  {mal_formados[:5]}")
print(f"  atomos totales              : {total_atomos:,}")

print()
print("=" * 74)
print(f"3) CONTRASTE CON EL RCSB  (muestra de {MUESTRA}, byte a byte)")
print("=" * 74)
random.seed(20260902)
for f in random.sample(archivos, min(MUESTRA, len(archivos))):
    pdb = f.name[:-7]
    local = gzip.decompress(f.read_bytes())
    try:
        req = urllib.request.Request(
            f"https://files.rcsb.org/download/{pdb}.pdb.gz",
            headers={"User-Agent": "MolDesign/1.0 (verificacion de integridad)"},
        )
        remoto = gzip.decompress(urllib.request.urlopen(req, timeout=60).read())
    except Exception as exc:
        print(f"  {pdb}: no se pudo contrastar ({type(exc).__name__})")
        continue
    h_local = hashlib.sha256(local).hexdigest()
    h_remoto = hashlib.sha256(remoto).hexdigest()
    veredicto = "IDENTICO" if h_local == h_remoto else "*** DIFIERE ***"
    print(f"  {pdb}: {veredicto}   sha256 local {h_local[:16]}  rcsb {h_remoto[:16]}")
