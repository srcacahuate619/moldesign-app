"""Molcy como un usuario nuevo: instalar Blender y Molecular Nodes desde la app, y rendir de verdad.

Recorre por la API, con el backend del árbol y python-embed, el camino que sigue alguien que
acaba de instalar MolDesign y abre Molcy por primera vez:

1. lo que ve el renderizador con una carpeta de datos vacía;
2. el modo «administrado» y la descarga de Blender que hace la app (con su SHA-256);
3. la instalación de Molecular Nodes desde el repositorio oficial de extensiones de Blender;
4. una sesión de fotos con CPU y una foto 720p, que lleva la marca de MolDesign;
5. un vídeo de previsualización con GPU, que no se da por completo sin el cierre.

No toca el Blender ni los datos del usuario: todo vive en `--datos`, que debe estar vacía.
Escribe `informe.json`, la foto y el vídeo en `--salida`.

Uso:
    python-embed/python.exe scripts/qa_molcy_usuario_nuevo.py --datos D:/moldesign-qa/molcy-datos \
        --salida D:/moldesign-qa/molcy-salida [--pdb 8HFI] [--sin-video]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
os.environ.setdefault("MOLDESIGN_GATE_PYTHON", str(Path(sys.executable)))
sys.path.insert(0, str(RAIZ / "scripts"))
import accept_evaluation_runtime as gate  # noqa: E402


class Backend:
    def __init__(self, datos: Path):
        self.datos = datos

    def __enter__(self) -> "Backend":
        vina_tmp = self.datos / "vina-tmp"
        vina_tmp.mkdir(parents=True, exist_ok=True)
        env = gate.entorno_runtime(self.datos, vina_tmp)
        # Lo que añade `spawn_backend` (frontend/src-tauri/src/backend.rs) para Molcy y Open Babel.
        env.update({"MOLDESIGN_MOLCY_DIR": str(RAIZ / "tools" / "molcy"),
                    "MOLDESIGN_OPENBABEL_DIR": str(RAIZ / "tools" / "openbabel"),
                    "TABPFN_NO_BROWSER": "true"})
        env.pop("MOLDESIGN_MOLCY_OUTPUTS", None)
        env.pop("MOLDESIGN_CASE_REGISTRY", None)
        self.port = gate._free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc, self.log = gate._start_backend(env, self.port, self.datos / "backend.log")
        gate._wait_ready(self.base, self.proc, timeout=180)
        self.token = gate._auth(self.base, f"molcy{int(time.time())}")
        return self

    def __exit__(self, *exc: Any) -> None:
        gate._stop_backend(self.proc, self.log)

    def get(self, path: str, **kw: Any) -> dict[str, Any]:
        return gate._json(self.base, "GET", path, token=self.token, **kw)

    def send(self, method: str, path: str, body: dict[str, Any] | None = None, expected=None) -> dict[str, Any]:
        return gate._json(self.base, method, path, token=self.token, body=body, expected=expected or {200, 202})

    def bytes(self, path: str) -> bytes:
        _, payload, _ = gate._request(self.base, "GET", path, token=self.token, timeout=600)
        return payload


def esperar(leer, terminado, *, limite_s: float, cada_s: float = 3.0, etiqueta: str) -> dict[str, Any]:
    t0 = time.monotonic()
    ultimo = None
    while True:
        valor = leer()
        fase = (valor.get("estado"), valor.get("fase"))
        if fase != ultimo:
            print(f"  [{time.monotonic() - t0:7.1f} s] {etiqueta}: {fase}", flush=True)
            ultimo = fase
        if terminado(valor):
            return valor
        if time.monotonic() - t0 > limite_s:
            raise TimeoutError(f"{etiqueta}: sin terminar tras {limite_s:.0f} s ({fase})")
        time.sleep(cada_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--pdb", default="8HFI")
    parser.add_argument("--sin-video", action="store_true")
    args = parser.parse_args()
    if args.datos.exists() and any(args.datos.iterdir()):
        parser.error(f"--datos debe estar vacía (un usuario nuevo no tiene nada): {args.datos}")
    args.datos.mkdir(parents=True, exist_ok=True)
    args.salida.mkdir(parents=True, exist_ok=True)
    informe: dict[str, Any] = {"pdb": args.pdb, "datos": str(args.datos), "pasos": {}}

    def paso(nombre: str, valor: Any, t0: float) -> None:
        informe["pasos"][nombre] = {"segundos": round(time.monotonic() - t0, 1), "resultado": valor}
        (args.salida / "informe.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    with Backend(args.datos) as b:
        t = time.monotonic()
        print("1. Lo que ve un usuario nuevo", flush=True)
        inicial = {"renderizador": b.get("/molcy/renderizador?recomprobar=true", timeout=300),
                   "blender": b.get("/molcy/blender"), "addon": b.get("/molcy/addon")}
        paso("1_estado_inicial", inicial, t)

        t = time.monotonic()
        print("2. Blender administrado: descarga e instalación desde la app", flush=True)
        b.send("PUT", "/molcy/configuracion", {"modo": "administrado"})
        b.send("POST", "/molcy/blender")
        blender = esperar(lambda: b.get("/molcy/blender"), lambda v: v.get("estado") != "instalando",
                          limite_s=3600, etiqueta="blender")
        paso("2_blender", blender, t)
        if blender.get("estado") != "completo":
            raise RuntimeError(f"Blender no se instaló: {blender.get('motivo')}")

        t = time.monotonic()
        print("3. Molecular Nodes desde el repositorio oficial de extensiones", flush=True)
        b.send("POST", "/molcy/addon")
        addon = esperar(lambda: b.get("/molcy/addon"), lambda v: v.get("estado") != "instalando",
                        limite_s=1800, etiqueta="addon")
        render = b.get("/molcy/renderizador?recomprobar=true", timeout=300)
        paso("3_addon", {"addon": addon, "renderizador": render}, t)
        if addon.get("estado") != "completo" or not render.get("disponible"):
            raise RuntimeError(f"Molcy no quedó disponible: {addon.get('motivo')} / {render.get('motivo')}")

        t = time.monotonic()
        print(f"4. Fotos con CPU de {args.pdb}", flush=True)
        sesion = b.send("POST", "/molcy/fotos", {"origen": "receptor", "id": args.pdb, "escena": "receptor",
                                                  "orientacion": "horizontal", "dispositivo": "cpu"})
        ruta = f"/molcy/trabajos/{sesion['id']}"
        lista = esperar(lambda: b.get(ruta), lambda v: v.get("estado") in {"completo", "fallido", "cancelado"},
                        limite_s=3600, etiqueta="preparar")
        if lista.get("estado") != "completo":
            raise RuntimeError(f"La sesión de fotos falló: {lista.get('motivo')}")
        momento = lista["momentos"][0]
        b.send("POST", f"{ruta}/fotos", {"fotograma": momento["fotograma"], "resolucion": "720p", "dispositivo": "cpu"})
        tomada = esperar(lambda: b.get(ruta), lambda v: v.get("estado") in {"completo", "fallido", "cancelado"},
                         limite_s=3600, etiqueta="foto")
        if tomada.get("estado") != "completo" or not tomada.get("fotos"):
            raise RuntimeError(f"La foto falló: {tomada.get('motivo')}")
        foto = tomada["fotos"][-1]
        png = b.bytes(f"{ruta}/fotos/{foto['id']}")
        (args.salida / f"foto_{args.pdb}_cpu_720p.png").write_bytes(png)
        paso("4_foto_cpu", {"momentos": len(lista["momentos"]), "preparacion": lista.get("preparacion"),
                            "foto": foto, "png_bytes": len(png)}, t)

        if not args.sin_video:
            t = time.monotonic()
            print(f"5. Vídeo de previsualización con GPU de {args.pdb}", flush=True)
            if not render.get("gpu_disponible"):
                paso("5_video_gpu", {"omitido": render.get("motivo_gpu") or "sin GPU"}, t)
            else:
                trabajo = b.send("POST", "/molcy/trabajos", {"origen": "receptor", "id": args.pdb, "escena": "receptor",
                                                             "formato": "previsualizacion", "dispositivo": "gpu"})
                ruta = f"/molcy/trabajos/{trabajo['id']}"
                video = esperar(lambda: b.get(ruta), lambda v: v.get("estado") in {"completo", "fallido", "cancelado"},
                                limite_s=5400, cada_s=5.0, etiqueta="video")
                if video.get("estado") != "completo":
                    raise RuntimeError(f"El vídeo falló: {video.get('motivo')}")
                mp4 = b.bytes(f"{ruta}/video")
                (args.salida / f"video_{args.pdb}_gpu_previsualizacion.mp4").write_bytes(mp4)
                paso("5_video_gpu", {"estado": {k: video.get(k) for k in
                                                ("estado", "video_sha256", "duracion_s", "cierre", "formato", "segundos")},
                                     "mp4_bytes": len(mp4)}, t)
    print(json.dumps({k: v["segundos"] for k, v in informe["pasos"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
