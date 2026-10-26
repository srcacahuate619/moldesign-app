"""Fotos de Molcy: la CPU toma fotos (y la GPU también), todas con Cycles, con marca y procedencia.

Decisiones del propietario (2026-10-08): el vídeo es sólo con GPU; una foto es un fotograma de la escena, de 720p a 4K; primero
las tomas sugeridas y después cualquier fotograma; toda foto lleva el emblema de MolDesign, sutil, en una esquina. El motor real
se probó a mano (D:\\mlab\\fotos, 4FK3: preparar 38 s en CPU; 4K 90 s en GPU y 13,4 min en CPU); aquí un motor falso escribe lo
que escribiría `correr_foto.py` para probar lo que MolDesign exige y entrega.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from services.molcy import fotos, installation, marca_foto, renderer

INFO = {"cpu_modelo": "x", "cpu_logicos": 8, "cpu_hilos_disponibles": 8, "cpu_hilos": 4, "cpu_hilos_maximos": 6,
        "cpu_hilos_reserva": 2, "cpu_uso_actual_pct": 0.0, "cpu_equipo_sha256": "e" * 64}
CAPACIDAD = {"disponible": True, "foto_disponible": True, "foto_gpu_disponible": True, "foto_gpu_tipo": "CUDA",
             "foto_gpu_nombres": ["GPU de prueba"], "cpu_hilos_configurables": True, "motor_commit": "a" * 40,
             "motor_licencia": "GPL-3.0-or-later"}
MOMENTOS = [{"id": "general-42", "fotograma": 42, "beat": "general", "tipo": "titulo", "etiquetas": 0, "pose": None, "orden": 1},
            {"id": "llegada_por_fundido-253", "fotograma": 253, "beat": "llegada_por_fundido", "tipo": "lectura",
             "etiquetas": 6, "pose": None, "orden": 2}]


def _png(path: Path, size, color=(20, 30, 40)) -> str:
    Image.new("RGB", size, color).save(path, format="PNG")
    return marca_foto.sha256(path)


@pytest.fixture(autouse=True)
def _python_auxiliar_falso(monkeypatch, tmp_path):
    # Las fotos lanzan correr_foto.py con el Python auxiliar (python_auxiliar.py). Aquí no se copia el Python real: el motor es falso.
    monkeypatch.setattr(fotos, "python_auxiliar", lambda: tmp_path / "python_auxiliar" / "python.exe")


class MotorFalso:
    """Lo que dejaría `correr_foto.py` en la carpeta de salida; `acta` permite estropear lo que acredita."""

    def __init__(self):
        self.llamadas: list[list[str]] = []
        self.acta: dict = {}
        self.codigo = 0
        self.fallo = "SIN_GPU_CYCLES"
        self.esquinas = {"inferior_derecha": 0, "superior_derecha": 0, "inferior_izquierda": 0, "superior_izquierda": 0}

    def __call__(self, cmd, *, env, stdout, cancel, on_start, timeout, cwd, cpu_rate=None, monitor=None):
        self.llamadas.append(list(cmd))
        args = dict(zip(cmd[3::2], cmd[4::2]))
        carpeta = Path(args["--carpeta"])
        if cmd[2] == "preparar":
            sufijo = args["--sufijo"]
            escena = {"schema": "molcy.fotos.escena/1", "pdb_id": "4FK3", "fotogramas_fuente": 389,
                      "formato": {"nombre": args["--formato"], "ancho": 1080, "alto": 1920},
                      "beats": {"general": [1, 87], "llegada_por_fundido": [192, 273]},
                      "papeles": {"general": "establecer"}, "momentos": MOMENTOS,
                      "blend": {"nombre": "x.blend", "sha256": "b" * 64}}
            if "--ajustes" in args:
                escena["ajustes"] = {"entrada": json.loads(Path(args["--ajustes"]).read_text(encoding="utf-8"))}
            escena_json = carpeta / f"escena_fotos_{sufijo}.json"
            escena_json.write_text(json.dumps(escena), encoding="utf-8")
            tomas = carpeta / f"tomas_{sufijo}"
            tomas.mkdir()
            salida = []
            for m in MOMENTOS:
                archivo = f"toma_{m['fotograma']:04d}.png"
                salida.append({**m, "archivo": archivo, "sha256": _png(tomas / archivo, (270, 480))})
            (carpeta / f"tomas_{sufijo}.json").write_text(json.dumps({
                "schema": "molcy.fotos.tomas/1", "escena": escena_json.name,
                "escena_sha256": marca_foto.sha256(escena_json), "momentos": salida,
                "render_ajustes": {"motor": "CYCLES", "dispositivo": args["--dispositivo"].upper()},
                "segundos": {"construccion": 20.0, "miniaturas": 10.0}, **self.acta}), encoding="utf-8")
        else:
            nombre = args["--nombre"]
            ancho, alto = int(args["--ancho"]), int(args["--alto"])
            png = carpeta / f"{nombre}.png"
            escena_json = Path(args["--escena"])
            acta = {"schema": "molcy.foto/1", "pdb_id": "4FK3", "guion": "sitio_activo", "formato": "social_vertical",
                    "fotograma": int(args["--fotograma"]), "fotogramas_fuente": 389, "beat": "llegada_por_fundido",
                    "momento": None, "tipo": "libre", "dispositivo": args["--dispositivo"],
                    "render_ajustes": {"motor": "CYCLES", "dispositivo": args["--dispositivo"].upper(),
                                       "muestras": int(args["--muestras"]), "hilos_cpu": int(env["MOLCY_CPU_THREADS"]),
                                       "blender": "5.2.2 LTS", "tipo_gpu": "CUDA" if args["--dispositivo"] == "gpu" else None},
                    "png": {"archivo": png.name, "sha256": _png(png, (ancho, alto)), "ancho": ancho, "alto": alto,
                            "esquinas": dict(self.esquinas)},
                    "escena": {"archivo": escena_json.name, "sha256": marca_foto.sha256(escena_json)},
                    "blend_sha256": "b" * 64, "segundos": {"escena": 10.0, "capa": 1.0, "total": 15.0}}
            for clave, valor in self.acta.items():
                destino = acta
                partes = clave.split(".")
                for parte in partes[:-1]:
                    destino = destino[parte]
                destino[partes[-1]] = valor
            (carpeta / f"{nombre}.json").write_text(json.dumps(acta), encoding="utf-8")
        if self.codigo and self.fallo:
            stdout.write(f"FALLO {self.fallo}\n")
        return SimpleNamespace(returncode=self.codigo)


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    datos = tmp_path / "data"
    datos.mkdir()
    for modulo in (installation, renderer, renderer.storage):
        monkeypatch.setattr(modulo, "data_dir", lambda: datos)
    monkeypatch.setattr(renderer.cpu, "recursos", lambda: dict(INFO))
    motor = MotorFalso()
    monkeypatch.setattr(fotos, "run_owned", motor)

    def encolar(job_id, funcion, *args):          # síncrono: la prueba ve el resultado al volver
        with renderer._lock:
            renderer._cancel_events[job_id] = threading.Event()
            renderer._reserved.add(job_id)
        funcion(*args)
    monkeypatch.setattr(renderer, "encolar", encolar)
    return SimpleNamespace(datos=datos, motor=motor, tmp=tmp_path)


def _sesion(entorno, dispositivo="cpu", orientacion="vertical", presentacion=None):
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    root = renderer.raiz_trabajo(user, job)
    root.mkdir(parents=True)
    capacidad = {**CAPACIDAD, "motor": str(entorno.tmp / "motor"), "blender": str(entorno.tmp / "blender.exe")}
    with renderer.reservar(job):
        fotos.iniciar(root, job_id=job, pdb_id="4FK3", sujeto="pose_evaluada", escena="resultado",
                      orientacion=orientacion, dispositivo=dispositivo, capacidad=capacidad,
                      fuente={"origen": "moldex", "task_id": "t" * 8, "pdb_id": "4FK3", "target_name": "BRAF",
                              "case_name": "ensa", "receptor_sha256": "r" * 64},
                      cpu_hilos=4 if dispositivo == "cpu" else None, presentacion=presentacion)
    return user, job, root, capacidad


def _pedir(user, job, capacidad, **kw):
    with renderer.reservar(job):
        return fotos.pedir(user, job, capacidad=capacidad, **{"operacion": "foto", "fotograma": 253,
                                                              "dispositivo": "cpu", "resolucion": "720p",
                                                              "cpu_hilos": 4, **kw})


# ── resoluciones ─────────────────────────────────────────────────────────
def test_las_resoluciones_van_de_720p_a_4k_en_16_9_y_9_16():
    assert fotos.dimensiones("horizontal", "720p") == (1280, 720)
    assert fotos.dimensiones("vertical", "720p") == (720, 1280)
    assert fotos.dimensiones("horizontal", "1080p") == (1920, 1080)
    assert fotos.dimensiones("horizontal", "1440p") == (2560, 1440)
    assert fotos.dimensiones("vertical", "4k") == (2160, 3840)
    todas = [fotos.dimensiones(o, r) for o in fotos.ORIENTACIONES for r in fotos.RESOLUCIONES]
    assert min(min(d) for d in todas) == 720          # el piso
    assert max(max(d) for d in todas) == 3840         # el techo
    for malo in (("vertical", "480p"), ("cuadrado", "720p"), ("vertical", "8k")):
        with pytest.raises(ValueError):
            fotos.dimensiones(*malo)


# ── marca ────────────────────────────────────────────────────────────────
def test_la_marca_va_a_la_primera_esquina_libre_de_rotulos():
    libre = dict.fromkeys(marca_foto.ESQUINAS, 0)
    assert marca_foto.elegir_esquina(libre) == "inferior_derecha"
    assert marca_foto.elegir_esquina({**libre, "inferior_derecha": 200}) == "superior_derecha"
    ocupado = {"inferior_derecha": 200, "superior_derecha": 90, "inferior_izquierda": 30, "superior_izquierda": 30}
    assert marca_foto.elegir_esquina(ocupado) == "inferior_izquierda"      # la menos ocupada; a igualdad, la preferida
    for roto in (None, {}, {"inferior_derecha": "x"}, {**libre, "inferior_derecha": 999}):
        assert marca_foto.elegir_esquina(roto) == "inferior_derecha"


def test_la_marca_es_sutil_esta_en_su_esquina_y_la_procedencia_viaja_en_el_png(tmp_path):
    origen = tmp_path / "bruto.png"
    _png(origen, (1080, 1920), (8, 12, 18))
    destino = tmp_path / "final.png"
    hecho = marca_foto.aplicar(origen, destino, esquinas=None, procedencia={"schema": "s", "fotograma": 253},
                               textos={"Title": "BRAF · 4FK3 · Molcy"})
    antes, despues = Image.open(origen).convert("RGB"), Image.open(destino)
    assert despues.size == antes.size and despues.mode == "RGB"
    assert round(despues.info["dpi"][0]) == 300
    assert marca_foto.leer_procedencia(destino) == {"schema": "s", "fotograma": 253}
    assert despues.text["Title"] == "BRAF · 4FK3 · Molcy"
    from PIL import ImageChops
    lado = round(1080 * marca_foto.LADO)
    margen = round(1080 * marca_foto.MARGEN)
    esquina = (1080 - margen - lado, 1920 - margen - lado, 1080 - margen, 1920 - margen)
    diferencia = ImageChops.difference(antes, despues.convert("RGB")).convert("L")
    assert diferencia.crop(esquina).getextrema()[1] > 10                   # el emblema está ahí...
    fondo = antes.convert("L").getpixel((0, 0))
    # ...y es sutil: ningún píxel se aclara más que el emblema al 30 % sobre el fondo.
    assert despues.convert("L").crop(esquina).getextrema()[1] <= fondo + round(255 * marca_foto.OPACIDAD) + 3
    # Fuera de su esquina, la foto no cambia.
    assert diferencia.getbbox() is not None and diferencia.crop((0, 0, 1080, 1920 - margen - lado)).getbbox() is None
    assert hecho["esquina"] == "inferior_derecha" and hecho["sha256"] == marca_foto.sha256(destino)


def test_el_emblema_es_el_de_moldesign_y_viaja_en_el_backend():
    assert marca_foto.LOGO == Path(__file__).resolve().parents[1] / "assets" / "logo.png"
    with Image.open(marca_foto.LOGO) as im:
        assert im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 0     # con transparencia


# ── sesión: preparar ─────────────────────────────────────────────────────
def test_preparar_deja_la_escena_y_las_tomas_sugeridas_verificadas(entorno):
    user, job, root, _ = _sesion(entorno)
    estado = renderer.leer_estado(user, job)
    assert estado["tipo"] == "fotos" and estado["estado"] == "completo", estado.get("motivo")
    assert [m["fotograma"] for m in estado["momentos"]] == [42, 253]
    assert estado["escena_fotos"]["fotogramas_fuente"] == 389
    cmd = entorno.motor.llamadas[0]
    assert cmd[2] == "preparar" and cmd[cmd.index("--dispositivo") + 1] == "cpu"
    assert cmd[cmd.index("--formato") + 1] == "social_vertical"
    datos = fotos.leer_png(user, job, "toma", "253")
    assert datos.startswith(b"\x89PNG")
    with pytest.raises(LookupError):
        fotos.leer_png(user, job, "toma", "7")


def test_una_miniatura_alterada_hace_fallar_la_preparacion(entorno, monkeypatch):
    real = entorno.motor.__call__

    def alterar(cmd, **kw):
        resultado = real(cmd, **kw)
        carpeta = Path(cmd[cmd.index("--carpeta") + 1])
        sufijo = cmd[cmd.index("--sufijo") + 1]
        (carpeta / f"tomas_{sufijo}" / "toma_0042.png").write_bytes(b"otra cosa")
        return resultado
    monkeypatch.setattr(fotos, "run_owned", alterar)
    user, job, _root, _ = _sesion(entorno)
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "fallido" and "miniatura" in estado["motivo"]


# ── sesión: foto ─────────────────────────────────────────────────────────
def test_una_foto_se_entrega_con_marca_y_procedencia_y_sin_el_png_sin_marca(entorno):
    user, job, root, capacidad = _sesion(entorno)
    _pedir(user, job, capacidad)
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "completo" and estado["ultima_operacion"]["estado"] == "completo", estado
    foto, = estado["fotos"]
    assert (foto["ancho"], foto["alto"]) == (720, 1280) and foto["resolucion"] == "720p"
    salida = root / "salida"
    assert foto["archivo"] == "4FK3_resultado_0253_720x1280_01.png"
    assert not (salida / f"foto_01_{job.replace('-', '')[:12]}.png").exists()     # el PNG sin marca no se queda
    procedencia = marca_foto.leer_procedencia(salida / foto["archivo"])
    assert procedencia["fotograma"] == 253 and procedencia["fuente"]["task_id"] == "t" * 8
    assert procedencia["render"]["motor"] == "CYCLES" and procedencia["ppp"] == 300
    texto = json.dumps(procedencia)
    assert "case_name" not in texto and ":\\\\" not in texto and str(entorno.tmp) not in texto   # ni rutas ni el caso
    assert fotos.leer_png(user, job, "foto", "01") == (salida / foto["archivo"]).read_bytes()
    cmd = entorno.motor.llamadas[-1]
    assert cmd[2] == "tomar" and cmd[cmd.index("--muestras") + 1] == str(fotos.MUESTRAS_FOTO)
    assert (cmd[cmd.index("--ancho") + 1], cmd[cmd.index("--alto") + 1]) == ("720", "1280")


@pytest.mark.parametrize("clave,valor,motivo", [
    ("render_ajustes.motor", "BLENDER_EEVEE", "otro renderizador"),
    ("render_ajustes.dispositivo", "GPU", "otro renderizador"),
    ("png.ancho", 1080, "otra resolución"),
    ("fotograma", 42, "otro fotograma"),
    ("escena.sha256", "0" * 64, "otra escena"),
    ("blend_sha256", "0" * 64, "otro .blend"),
    ("render_ajustes.muestras", 16, "otras muestras"),
    ("render_ajustes.hilos_cpu", 3, "otros hilos"),
])
def test_un_acta_que_no_acredita_lo_pedido_no_entrega_nada(entorno, clave, valor, motivo):
    user, job, root, capacidad = _sesion(entorno)
    entorno.motor.acta = {clave: valor}
    _pedir(user, job, capacidad)
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "completo"                      # la sesión sigue sirviendo
    assert estado["fotos"] == []
    assert estado["ultima_operacion"]["estado"] == "fallido" and motivo in estado["ultima_operacion"]["motivo"]
    assert not list((root / "salida").glob("foto_*.png"))      # ni el PNG sin marca


def test_un_fallo_del_motor_se_explica_y_la_sesion_sigue(entorno):
    user, job, root, capacidad = _sesion(entorno, dispositivo="gpu")
    entorno.motor.codigo = 1
    _pedir(user, job, capacidad, dispositivo="gpu", cpu_hilos=None)
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "completo"
    assert "Cycles no encontró la GPU" in estado["ultima_operacion"]["motivo"]
    entorno.motor.codigo = 0
    _pedir(user, job, capacidad, dispositivo="gpu", cpu_hilos=None, resolucion="1080p")
    assert len(renderer.leer_estado(user, job)["fotos"]) == 1


def test_el_motivo_de_un_fallo_no_se_hereda_del_anterior(entorno):
    """El registro es de toda la sesión: un fallo sin «FALLO …» no puede contar el motivo de otro anterior."""
    user, job, _root, capacidad = _sesion(entorno, dispositivo="gpu")
    entorno.motor.codigo = 1
    _pedir(user, job, capacidad, dispositivo="gpu", cpu_hilos=None)
    assert "Cycles no encontró la GPU" in renderer.leer_estado(user, job)["ultima_operacion"]["motivo"]
    entorno.motor.codigo, entorno.motor.fallo = 2, None
    _pedir(user, job, capacidad, dispositivo="gpu", cpu_hilos=None)
    motivo = renderer.leer_estado(user, job)["ultima_operacion"]["motivo"]
    assert "Cycles" not in motivo and "(2)" in motivo


def test_pedir_gpu_sin_cycles_en_gpu_se_rechaza_antes_de_lanzar(entorno):
    user, job, _root, capacidad = _sesion(entorno)
    antes = len(entorno.motor.llamadas)
    with pytest.raises(fotos.SesionNoDisponible, match="GPU"):
        _pedir(user, job, {**capacidad, "foto_gpu_disponible": False}, dispositivo="gpu", cpu_hilos=None)
    assert len(entorno.motor.llamadas) == antes


@pytest.mark.parametrize("fotograma", [0, 390, -1])
def test_un_fotograma_fuera_de_la_escena_se_rechaza(entorno, fotograma):
    user, job, _root, capacidad = _sesion(entorno)
    with pytest.raises(ValueError, match="entre 1 y 389"):
        _pedir(user, job, capacidad, fotograma=fotograma)


def test_pedir_exige_la_reserva_del_renderizador(entorno):
    user, job, _root, capacidad = _sesion(entorno)
    with pytest.raises(RuntimeError, match="reserva"):
        fotos.pedir(user, job, operacion="foto", fotograma=253, dispositivo="cpu", resolucion="720p",
                    capacidad=capacidad, cpu_hilos=4)


def test_un_video_no_es_una_sesion_de_fotos(entorno):
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    root = renderer.raiz_trabajo(user, job)
    root.mkdir(parents=True)
    renderer.guardar_estado(root, {"id": job, "estado": "completo", "formato": "biblioteca"})
    with pytest.raises(fotos.SesionNoDisponible, match="vídeo"):
        _pedir(user, job, CAPACIDAD)


# ── sesión: vista libre ──────────────────────────────────────────────────
def test_una_vista_libre_es_una_miniatura_sin_marca_y_se_guarda_por_fotograma(entorno):
    user, job, root, capacidad = _sesion(entorno)
    _pedir(user, job, capacidad, operacion="vista", fotograma=300, resolucion=None)
    estado = renderer.leer_estado(user, job)
    assert estado["fotos"] == [] and "300" in estado["vistas"]
    cmd = entorno.motor.llamadas[-1]
    assert (cmd[cmd.index("--ancho") + 1], cmd[cmd.index("--alto") + 1]) == ("270", "480")
    assert cmd[cmd.index("--muestras") + 1] == str(fotos.MUESTRAS_VISTA)
    assert fotos.leer_png(user, job, "vista", "300").startswith(b"\x89PNG")


def test_las_vistas_no_crecen_sin_limite(entorno, monkeypatch):
    monkeypatch.setattr(fotos, "MAXIMO_VISTAS", 2)
    user, job, root, capacidad = _sesion(entorno)
    for f in (100, 110, 120):
        _pedir(user, job, capacidad, operacion="vista", fotograma=f, resolucion=None)
    vistas = renderer.leer_estado(user, job)["vistas"]
    assert sorted(vistas) == ["110", "120"]
    assert not (root / "salida" / f"vista_0100_{job.replace('-', '')[:12]}.png").exists()


# ── interrupciones ───────────────────────────────────────────────────────
def test_una_foto_interrumpida_al_cerrar_no_estropea_la_sesion(entorno):
    user, job, root, _ = _sesion(entorno)
    estado = renderer.leer_estado(user, job)
    renderer.guardar_estado(root, {**estado, "estado": "renderizando", "fase": "foto",
                                   "operacion": {"tipo": "foto", "fotograma": 253}})
    leido = renderer.leer_estado(user, job)
    assert leido["estado"] == "completo"
    assert leido["ultima_operacion"]["estado"] == "fallido" and "cerrar" in leido["ultima_operacion"]["motivo"]


def test_una_preparacion_interrumpida_si_falla(entorno):
    user, job, root, _ = _sesion(entorno)
    renderer.guardar_estado(root, {"id": job, "tipo": "fotos", "estado": "renderizando", "fase": "preparando"})
    assert renderer.leer_estado(user, job)["estado"] == "fallido"


def test_cancelar_una_foto_deja_la_sesion_lista(entorno, monkeypatch):
    user, job, root, capacidad = _sesion(entorno)

    def cancelado(cmd, *, cancel, **kw):
        cancel.set()
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(fotos, "run_owned", cancelado)
    _pedir(user, job, capacidad)
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "completo" and estado["ultima_operacion"]["estado"] == "cancelado"


# ── tiempos medidos ──────────────────────────────────────────────────────
def test_la_estimacion_sale_de_fotos_anteriores_del_mismo_equipo(entorno):
    user, job, _root, capacidad = _sesion(entorno)
    trabajos = [renderer.leer_estado(user, job)]
    assert fotos.estimar(trabajos, orientacion="vertical", resolucion="720p", dispositivo="cpu",
                         capacidad=capacidad, cpu_hilos=4) == {"estimado_s": None, "muestras": 0}
    _pedir(user, job, capacidad)
    trabajos = [renderer.leer_estado(user, job)]
    # 10 s de escena para 0,92 MP + 5 s del resto: a 4K (8,29 MP) son 90 s de escena + 5.
    valor = fotos.estimar(trabajos, orientacion="vertical", resolucion="4k", dispositivo="cpu",
                          capacidad=capacidad, cpu_hilos=4)
    assert valor == {"estimado_s": 95, "muestras": 1}
    for distinto in ({"dispositivo": "gpu", "cpu_hilos": None}, {"cpu_hilos": 2}):
        args = {"orientacion": "vertical", "resolucion": "4k", "dispositivo": "cpu", "cpu_hilos": 4, **distinto}
        assert fotos.estimar(trabajos, capacidad=capacidad, **args)["estimado_s"] is None
    otra_cpu = dict(INFO, cpu_equipo_sha256="f" * 64)
    import services.molcy.cpu as cpu_mod
    original = cpu_mod.recursos
    try:
        cpu_mod.recursos = lambda: otra_cpu
        assert fotos.estimar(trabajos, orientacion="vertical", resolucion="4k", dispositivo="cpu",
                             capacidad=capacidad, cpu_hilos=4)["estimado_s"] is None
    finally:
        cpu_mod.recursos = original


# ── el sondeo y el motor dicen lo mismo ──────────────────────────────────
def test_el_sondeo_de_gpu_es_python_valido_y_prueba_cycles_en_el_orden_del_motor():
    compile(renderer.SONDEO_GPU, "<sondeo>", "exec")
    foto_py = Path(__file__).resolve().parents[2] / "tools" / "molcy" / "scripts" / "foto.py"
    arbol = ast.parse(foto_py.read_text(encoding="utf-8"))
    preferencia = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                       and any(getattr(t, "id", "") == "PREFERENCIA_GPU" for t in n.targets))
    assert tuple(preferencia) == renderer.TIPOS_GPU_CYCLES


def _detector(monkeypatch, tmp_path, salida_gpu: str, codigo_gpu: int = 0):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    motor = Path(__file__).resolve().parents[2] / "tools" / "molcy"
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    monkeypatch.setattr(renderer, "motor_elegido", lambda: (motor, "incluido"))
    monkeypatch.setattr(renderer.motor, "verificar_integridad", lambda _: [])
    monkeypatch.setattr(renderer.cpu, "recursos", lambda: dict(INFO))
    llamadas = []

    def fake_run(cmd, **_kw):
        llamadas.append(cmd)
        if len(llamadas) == 1:
            return subprocess.CompletedProcess(cmd, 0, 'MOLCY_BLENDER_VERSION:[5,2,2]\nMOLCY_CPU_OK\n'
                                               'MOLCY_CAPS:{"version":[5,2,2],"molecular_nodes":"520.2.0"}\n', "")
        return subprocess.CompletedProcess(cmd, codigo_gpu, salida_gpu, "")
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    renderer.invalidar()
    return renderer.detectar(forzar=True)


def test_el_detector_ofrece_fotos_en_gpu_solo_si_cycles_rindio_con_ella(monkeypatch, tmp_path):
    con = _detector(monkeypatch, tmp_path, 'MOLCY_EEVEE_OK\nMOLCY_CYCLES_GPU:{"tipo": "CUDA", "nombres": ["GTX 1660 SUPER"]}\n')
    assert con["foto_disponible"] and con["foto_gpu_disponible"] and con["gpu_disponible"]
    assert con["foto_gpu_tipo"] == "CUDA" and con["foto_gpu_nombres"] == ["GTX 1660 SUPER"]
    sin = _detector(monkeypatch, tmp_path, "MOLCY_EEVEE_OK\nMOLCY_CYCLES_GPU_FALLO:RuntimeError\n")
    assert sin["foto_disponible"] and not sin["foto_gpu_disponible"] and sin["gpu_disponible"]
    assert "CPU" in sin["motivo_foto_gpu"]
    raro = _detector(monkeypatch, tmp_path, 'MOLCY_EEVEE_OK\nMOLCY_CYCLES_GPU:{"tipo": "VULKAN", "nombres": ["x"]}\n')
    assert not raro["foto_gpu_disponible"]


def test_sin_eevee_no_hay_video_pero_si_fotos_con_la_cpu(monkeypatch, tmp_path):
    valor = _detector(monkeypatch, tmp_path, "MOLCY_EEVEE_FALLO:RuntimeError\n", codigo_gpu=0)
    assert valor["disponible"] and valor["foto_disponible"] and not valor["gpu_disponible"]
    assert "fotos" in valor["motivo_gpu"]


# ── API ──────────────────────────────────────────────────────────────────
@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    from api.dependencies import get_current_user
    from api.routers import molcy
    from core.database import get_db
    app = FastAPI()
    app.include_router(molcy.router)
    user = SimpleNamespace(id=uuid.uuid4())

    async def database():
        yield AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(renderer.cpu, "recursos", lambda: dict(INFO))
    monkeypatch.setattr(molcy, "_instalacion_estable", lambda: None)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, user=user, molcy=molcy)


@pytest.mark.parametrize("cuerpo", [
    {"dispositivo": "gpu", "cpu_hilos": 4},
    {"dispositivo": "cpu", "cpu_hilos": 99},
    {"dispositivo": "cpu", "orientacion": "cuadrada"},
    {"dispositivo": "tpu"},
])
def test_una_sesion_mal_pedida_no_sondea_blender(api, monkeypatch, cuerpo):
    monkeypatch.setattr(renderer, "detectar", lambda **_: pytest.fail("no debe sondear Blender"))
    base = {"origen": "receptor", "id": "1HSG", "escena": "receptor", "orientacion": "vertical"}
    assert api.client.post("/molcy/fotos", json={**base, **cuerpo}).status_code == 422


def test_sin_gpu_de_cycles_la_sesion_en_gpu_dice_que_use_la_cpu(api, monkeypatch):
    monkeypatch.setattr(renderer, "detectar", lambda **_: {**CAPACIDAD, "foto_gpu_disponible": False,
                                                          "motivo_foto_gpu": "Cycles no encontró una GPU compatible (CUDA, OptiX, HIP u oneAPI): las fotos se harán con la CPU."})
    r = api.client.post("/molcy/fotos", json={"origen": "receptor", "id": "1HSG", "escena": "receptor",
                                              "orientacion": "vertical", "dispositivo": "gpu"})
    assert r.status_code == 409 and "CPU" in r.json()["detail"]


@pytest.mark.parametrize("ruta,cuerpo,codigo", [
    ("fotos", {"fotograma": 1, "resolucion": "480p", "dispositivo": "cpu"}, 422),     # bajo el piso
    ("fotos", {"fotograma": 1, "resolucion": "8k", "dispositivo": "cpu"}, 422),       # sobre el techo
    ("fotos", {"fotograma": 0, "resolucion": "720p", "dispositivo": "cpu"}, 422),
    ("fotos", {"fotograma": 1, "resolucion": "720p", "dispositivo": "gpu", "cpu_hilos": 2}, 422),
    ("vista", {"fotograma": "1", "dispositivo": "cpu"}, 422),
])
def test_las_peticiones_de_foto_se_validan_antes_de_todo(api, monkeypatch, ruta, cuerpo, codigo):
    monkeypatch.setattr(renderer, "detectar", lambda **_: pytest.fail("no debe sondear Blender"))
    assert api.client.post(f"/molcy/trabajos/{uuid.uuid4()}/{ruta}", json=cuerpo).status_code == codigo


def test_una_foto_de_un_trabajo_que_no_existe_es_404(api, monkeypatch, tmp_path):
    monkeypatch.setattr(renderer, "detectar", lambda **_: dict(CAPACIDAD))
    for modulo in (renderer, renderer.storage):
        monkeypatch.setattr(modulo, "data_dir", lambda: tmp_path)
    r = api.client.post(f"/molcy/trabajos/{uuid.uuid4()}/fotos",
                        json={"fotograma": 1, "resolucion": "720p", "dispositivo": "cpu"})
    assert r.status_code == 404
    assert api.client.get(f"/molcy/trabajos/{uuid.uuid4()}/fotos/01").status_code == 404
    assert api.client.get(f"/molcy/trabajos/{uuid.uuid4()}/fotos/..%2Fx").status_code in (404, 422)


def test_la_api_entrega_la_foto_con_su_nombre_y_la_procedencia_de_la_sesion(api, entorno, monkeypatch):
    user, job, root, capacidad = _sesion(entorno)
    _pedir(user, job, capacidad)
    api.user.id = uuid.UUID(user)
    r = api.client.get(f"/molcy/trabajos/{job}/fotos/01")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert "4FK3_resultado_0253_720x1280_01.png" in r.headers["content-disposition"]
    assert api.client.get(f"/molcy/trabajos/{job}/tomas/42").status_code == 200
    procedencia = api.client.get(f"/molcy/trabajos/{job}/procedencia").json()
    assert procedencia["schema"] == "molcy.procedencia/1" and "01" in procedencia["fotos"]
    assert procedencia["build"]["schema"] == "molcy.fotos.escena/1"
    # Una foto alterada en disco ya no se entrega.
    foto = root / "salida" / "4FK3_resultado_0253_720x1280_01.png"
    foto.write_bytes(foto.read_bytes() + b"x")
    assert api.client.get(f"/molcy/trabajos/{job}/fotos/01").status_code == 409


def test_el_historial_de_una_sesion_lleva_la_ruta_de_su_ultima_foto(entorno):
    user, job, root, capacidad = _sesion(entorno)
    _pedir(user, job, capacidad)
    trabajo, = renderer.listar(user)
    assert trabajo["tipo"] == "fotos" and trabajo["foto_ruta"].endswith("_01.png")
    assert re.search(r"\.png$", trabajo["foto_ruta"])


def test_la_personalizacion_de_fotos_se_congela_se_transporta_y_se_entrega(entorno):
    user, job, root, capacidad = _sesion(entorno, presentacion={"titulo": "Serie A", "etiquetas": False,
                                                            "color_residuos": "#aabbcc"})
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "completo", estado.get("motivo")
    preparar = entorno.motor.llamadas[0]
    receta = Path(preparar[preparar.index("--ajustes") + 1])
    assert receta == root / "ajustes.json"
    assert json.loads(receta.read_text(encoding="utf-8")) == estado["ajustes"]
    assert estado["ajustes"]["presentacion"]["etiquetas"] is False
    _pedir(user, job, capacidad)
    estado = renderer.leer_estado(user, job)
    png = fotos.ultima_foto(user, job)
    procedencia = marca_foto.leer_procedencia(png)
    assert procedencia["ajustes"] == estado["ajustes"]
    assert procedencia["ajustes_sha256"] == estado["ajustes_sha256"]


def test_motor_que_omite_la_receta_no_entrega_fotos_como_personalizadas(entorno, monkeypatch):
    original = entorno.motor
    def omitir(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0][2] == "preparar":
            carpeta = Path(args[0][args[0].index("--carpeta") + 1])
            for path in carpeta.glob("escena_fotos_*.json"):
                data = json.loads(path.read_text(encoding="utf-8")); data.pop("ajustes", None)
                path.write_text(json.dumps(data), encoding="utf-8")
                # Conserva el control de hash independiente para alcanzar la guardia de receta.
                for acta in carpeta.glob("tomas_*.json"):
                    tomas = json.loads(acta.read_text(encoding="utf-8"))
                    tomas["escena_sha256"] = marca_foto.sha256(path)
                    acta.write_text(json.dumps(tomas), encoding="utf-8")
        return result
    monkeypatch.setattr(fotos, "run_owned", omitir)
    user, job, _, _ = _sesion(entorno, presentacion={"titulo": "No ignorar"})
    estado = renderer.leer_estado(user, job)
    assert estado["estado"] == "fallido"
    assert "receta" in estado["motivo"]
