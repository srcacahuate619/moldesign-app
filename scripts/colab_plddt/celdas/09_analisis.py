# ── Análisis: cada campo del archivo frente a la salida del modelo, con el criterio fijado arriba ──
import importlib

sys.path.insert(0, str(RAIZ))
import analisis_plddt as A

importlib.reload(A)
analisis = A.analizar_resultados(RES)
(RES / "analisis.json").write_text(json.dumps(analisis, ensure_ascii=False, indent=1), encoding="utf-8")
ejecuciones = cargar_procedencia().get("ejecuciones", [])
if ejecuciones:
    ejecuciones[-1]["fin"] = ahora()
procedencia = guardar_procedencia(fin=ahora(), ejecuciones=ejecuciones,
                                  sha256_analisis_plddt=A.sha256(RAIZ / "analisis_plddt.py"),
                                  sha256_ejecutar_chai=A.sha256(RAIZ / "ejecutar_chai.py"))
informe = A.informe_markdown(analisis, procedencia)
(RES / "CONVENCION.md").write_text(informe, encoding="utf-8")
respaldar()

from IPython.display import Markdown, display

display(Markdown(informe))
