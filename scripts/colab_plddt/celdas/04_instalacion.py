# ── Instalación: sólo lo que tiene corridas pendientes, cada herramienta en su entorno virtual (sus dependencias chocan) ──
PENDIENTES = pendientes()
A_INSTALAR = [h for h in ("boltz", "chai") if PENDIENTES[h]]
print("Corridas pendientes:", PENDIENTES, "→ se instala:", A_INSTALAR or "nada")
sh([sys.executable, "-m", "pip", "install", "-q", "uv", "gemmi"], check=True)
UV = shutil.which("uv") or str(Path(sys.executable).parent / "uv")
PY = {"boltz": VENVS / "boltz" / "bin" / "python", "chai": VENVS / "chai" / "bin" / "python"}
DIST = {"boltz": "boltz", "chai": "chai_lab"}
PAQUETES = {"boltz": "boltz[cuda]" + (f"=={VERSION_BOLTZ}" if VERSION_BOLTZ else ""),
            "chai": "chai_lab" + (f"=={VERSION_CHAI}" if VERSION_CHAI else "")}

INFO = """
import json, sys
from importlib import metadata
import torch
d = metadata.distribution(sys.argv[1])
licencias = [f for f in (d.files or []) if "LICEN" in str(f).upper() or "COPYING" in str(f).upper()]
print(json.dumps({
    "version": d.version,
    "licencia_metadata": d.metadata.get("License"),
    "licencia_expresion": d.metadata.get("License-Expression"),
    "clasificadores_de_licencia": [c for c in (d.metadata.get_all("Classifier") or []) if "License" in c],
    "archivos_de_licencia": {str(f): d.locate_file(f).read_text(errors="replace")[:20000] for f in licencias},
    "torch": torch.__version__, "cuda": torch.version.cuda, "python": sys.version.split()[0],
}))
"""

# Chai-1 guarda el alineamiento del servidor MSA en parquet. En la primera ejecución pandas no pudo importar pyarrow
# (instalado, 26.0.1) y resumió el error como «falta pyarrow». La sonda hace lo mismo que Chai-1 y, si falla, imprime el
# error real de cada importación.
SONDA_PARQUET = """
import os, sys, tempfile, traceback
print("LD_LIBRARY_PATH =", os.environ.get("LD_LIBRARY_PATH"))
try:
    import numpy, pandas
    ruta = os.path.join(tempfile.mkdtemp(), "sonda.parquet")
    pandas.DataFrame({"a": [1, 2]}).to_parquet(ruta)
    assert pandas.read_parquet(ruta)["a"].tolist() == [1, 2]
    print("parquet funciona con pandas", pandas.__version__, "y numpy", numpy.__version__)
except Exception:
    traceback.print_exc()
    for modulo in ("pyarrow", "pyarrow.parquet", "fastparquet"):
        try:
            __import__(modulo)
            print(modulo, "se importa")
        except Exception:
            print("--- error real al importar", modulo)
            traceback.print_exc()
    sys.exit(1)
"""
#: Lo que se prueba, en orden, si la sonda falla. Cada intento queda registrado con su salida.
ARREGLOS_PARQUET = ("pyarrow<22", "pyarrow<20", "pyarrow<18", "fastparquet")


def sondear_parquet():
    r, _ = sh([str(PY["chai"]), "-c", SONDA_PARQUET])
    return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()[-6000:]


previa = cargar_procedencia()
instalacion = dict(previa.get("instalacion", {}))
historial = list(previa.get("instalaciones_anteriores", []))
versiones = dict(previa.get("versiones", {}))
(RES / "licencias").mkdir(exist_ok=True)
instalacion["uv"] = sh([UV, "--version"])[0].stdout.strip()
for nombre in A_INSTALAR:
    dist = DIST[nombre]
    if isinstance(instalacion.get(nombre), dict):
        historial.append({"herramienta": nombre, "apartada": ahora(), **instalacion[nombre]})
    for viejo in (RES / f"instalacion_{nombre}.log", RES / f"pip_freeze_{nombre}.txt"):
        if viejo.exists():
            apartar(viejo, "anterior")
    if not PY[nombre].exists():
        sh([UV, "venv", str(VENVS / nombre), "--python", "3.11"], check=True)
    r, s = sh([UV, "pip", "install", "--python", str(PY[nombre]), PAQUETES[nombre]],
              log=RES / f"instalacion_{nombre}.log")
    if r.returncode != 0:
        raise RuntimeError(f"No se instaló {PAQUETES[nombre]}: mira {RES / f'instalacion_{nombre}.log'}")
    registro = {"paquete_pedido": PAQUETES[nombre], "segundos": s, "instalado": ahora()}
    if nombre == "chai":
        CHAI_LISTO, salida = sondear_parquet()
        intentos = [{"cambio": None, "funciona": CHAI_LISTO, "salida": salida}]
        print("Sonda de parquet en el entorno de Chai-1:\n" + salida[-2500:])
        for arreglo in ARREGLOS_PARQUET:
            if CHAI_LISTO:
                break
            log_arreglo = RES / f"instalacion_chai_arreglo_{arreglo.replace('<', '_menor_que_')}.log"
            if log_arreglo.exists():
                apartar(log_arreglo, "anterior")
            r, _ = sh([UV, "pip", "install", "--python", str(PY["chai"]), arreglo], log=log_arreglo)
            CHAI_LISTO, salida = sondear_parquet()
            intentos.append({"cambio": arreglo, "codigo_instalacion": r.returncode, "funciona": CHAI_LISTO,
                             "salida": salida})
            print(f"Con {arreglo}: {'funciona' if CHAI_LISTO else 'sigue sin funcionar'}")
        registro["parquet"] = {"funciona": CHAI_LISTO, "intentos": intentos}
        if not CHAI_LISTO:
            print("Parquet no funciona en el entorno de Chai-1 con ningún arreglo: Chai-1 no se lanzará.")
    congelado, _ = sh([UV, "pip", "freeze", "--python", str(PY[nombre])], check=True)
    (RES / f"pip_freeze_{nombre}.txt").write_text(congelado.stdout, encoding="utf-8")
    r, _ = sh([str(PY[nombre]), "-c", INFO, dist], check=True)
    info = json.loads(r.stdout.strip().splitlines()[-1])
    for archivo, texto in info.pop("archivos_de_licencia").items():
        (RES / "licencias" / f"{dist}__{Path(archivo).name}").write_text(texto, encoding="utf-8")
    instalacion[nombre] = {**registro, **info}
    versiones[dist] = info["version"]
print("Versiones registradas:", versiones)
guardar_procedencia(instalacion=instalacion, instalaciones_anteriores=historial, versiones=versiones)
respaldar()
