"""El contrato de `runtime-base-v1.1.0.zip` y del bootstrap, comprobado.

Cada prueba de aquí corresponde a una forma de fallo que ya ocurrió o que el
artefacto anterior permitía. No son pruebas de cobertura: son las catorce
afirmaciones que hay que poder sostener antes de publicar un runtime.

    python -m pytest scripts/tests -q

Lo que estas pruebas NO demuestran, y conviene decirlo aquí y no sólo en el
informe: usan un `python-embed` de mentira —cuatro archivos— porque el real
pesa 2,2 GB. Que Vina responda, que Open Babel convierta y que `/health`
conteste con el intérprete embebido lo comprueba
`npm run verify:desktop-runtime` sobre el bundle staged, y eso necesita el
runtime de verdad. Ver el punto 14 de `docs/81_HANDOFF_RUNTIME_ALPHA.md`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import bootstrap_dev_tree as boot
import build_base_archive as arch


def _zip_bruto(destino: Path, entradas: dict[str, bytes], manifiesto: dict | None) -> Path:
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifiesto is not None:
            zf.writestr(arch.NOMBRE_MANIFIESTO, json.dumps(manifiesto, ensure_ascii=False))
        for nombre, cuerpo in entradas.items():
            info = zipfile.ZipInfo(nombre, date_time=arch.FECHA_FIJA)
            info.filename = nombre
            zf.writestr(info, cuerpo)
    return destino


def _manifiesto_para(entradas: dict[str, bytes]) -> dict:
    return {
        "formato": arch.FORMATO,
        "artefacto": arch.RUNTIME_BASE.filename,
        "version": arch.RUNTIME_BASE.version,
        "componentes": [
            {"prefijo": c.prefijo, "licencia": c.licencia, "obligatorio": c.obligatorio,
             "descripcion": c.descripcion, "archivos": 0, "bytes": 0}
            for c in arch.COMPONENTES
        ],
        "archivos": {
            n: {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
            for n, b in entradas.items()
        },
    }


# ── 1-3. Lo que el artefacto NO puede contener ───────────────────────────


def test_el_artefacto_no_trae_codigo_del_repositorio(arbol, tmp_path):
    """1. El árbol de origen tiene backend/ y scripts/. El zip, no."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    nombres = arch.inspeccionar(salida).nombres

    assert nombres, "el artefacto quedó vacío"
    prohibidos = ("backend/", "frontend/", "rescoring/", "scripts/", "docs/")
    colados = [n for n in nombres if n.startswith(prohibidos)]
    assert colados == [], f"código del repositorio dentro del artefacto: {colados}"

    # Y lo mismo por la puerta de atrás: todo nombre cae en un componente.
    for nombre in nombres:
        arch.validar_destino(nombre)


def test_el_artefacto_no_trae_pesos_propios(arbol, tmp_path):
    """2. `rescoring/artifacts/*.pt` estaba dentro de base-v1.0.0.zip."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    nombres = arch.inspeccionar(salida).nombres
    pesos = [n for n in nombres if n.lower().endswith(arch.SUFIJOS_DE_PESO)]
    assert pesos == [], f"pesos entrenados dentro del runtime base: {pesos}"

    # Y el inventario tiene que DECIR dónde están, no callarlo.
    manifiesto = arch.inspeccionar(salida).manifiesto
    assert manifiesto["pesos_propios"]["gated"] is True
    assert "moldesign-rescoring" in manifiesto["pesos_propios"]["nota"]


def test_no_hay_bindings_importables_de_open_babel(arbol, tmp_path):
    """3. Ni `openbabel`, ni `pybel`, ni `_openbabel` dentro de python-embed."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    nombres = arch.inspeccionar(salida).nombres

    site = [n for n in nombres if n.startswith("python-embed/")]
    for nombre in site:
        assert arch._binding_de_open_babel(nombre) is None, nombre

    # El programa externo SÍ viaja: la frontera separa, no elimina.
    assert any(n.startswith("tools/openbabel/bin/") for n in nombres)

    # Hay DOS mecanismos, y esto comprueba los dos por separado.
    #
    # (a) La lista de nombres de `bundle_helper` excluye el paquete del wheel
    #     al copiar. El árbol de origen lo tiene —es la fuente de la que sale
    #     el binario— y el artefacto no.
    paquete = arbol / "python-embed/Lib/site-packages/openbabel/__init__.py"
    paquete.parent.mkdir(parents=True, exist_ok=True)
    paquete.write_bytes(b"# el paquete del wheel\n")
    (arbol / "python-embed/Lib/site-packages/openbabel/_x.pyd").write_bytes(b"\x00")
    salida2 = tmp_path / "art2" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida2)
    colados = [n for n in arch.inspeccionar(salida2).nombres if "openbabel" in n
               and n.startswith("python-embed/")]
    assert colados == [], f"el wheel viajó pese a la exclusión: {colados}"

    # (b) El GUARDIÁN reconoce por forma, no por lista, así que ve lo que la
    #     lista no cubre. `openbabel.py` como módulo suelto —que wheels
    #     antiguos sí traían— no está en ningún patrón de exclusión, y aun así
    #     tiene que detener el empaquetado. Si esto dejara de fallar, el
    #     guardián estaría comprobando lo mismo que la exclusión y no
    #     comprobaría nada.
    suelto = arbol / "python-embed/Lib/site-packages/openbabel.py"
    suelto.write_bytes(b"import _openbabel\n")
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        arch.empaquetar(arbol, tmp_path / "art3" / "x.zip")
    assert excinfo.value.codigo == "BINDING_DE_OPEN_BABEL"


def test_el_artefacto_no_empaqueta_sus_recibos_de_instalacion(arbol, tmp_path):
    """El recibo se escribe después de extraer y nunca se inventaría a sí mismo."""
    embed = arbol / "python-embed"
    (embed / ".runtime-base.json").write_text('{"viejo": true}', encoding="utf-8")
    (embed / ".runtime-fuente.json").write_text('{"via": "PyPI"}', encoding="utf-8")

    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    nombres = arch.inspeccionar(salida).nombres

    assert "python-embed/.runtime-base.json" not in nombres
    assert "python-embed/.runtime-fuente.json" not in nombres

# ── 4. Open Babel por CLI, con su hash ───────────────────────────────────


def test_open_babel_convierte_por_cli_y_coincide_con_su_hash(raiz_del_repositorio):
    """4. Conversión PDBQT→SDF real, con el binario resuelto del manifiesto.

    Se salta si el clon no tiene el binario —no viaja en el repositorio—, y al
    saltarse lo DICE. Saltar no es aprobar.
    """
    manifiesto = raiz_del_repositorio / "tools" / "openbabel" / "openbabel-manifest.json"
    if not manifiesto.is_file():
        pytest.skip("no hay manifiesto de Open Babel en este árbol")
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    binario = raiz_del_repositorio / "tools" / "openbabel" / datos["ejecutable"]
    if not binario.is_file():
        pytest.skip(
            "no hay binario de Open Babel en este clon (no viaja en el "
            "repositorio): la conversión real NO se comprobó"
        )

    esperado = datos["archivos"][datos["ejecutable"]]["sha256"]
    assert arch.sha256(binario) == esperado, "el binario no es el declarado"

    ok, detalle = boot.verificar_open_babel(raiz_del_repositorio)
    assert ok, detalle

    # Y ahora que funcione DE VERDAD: una conversión, por subproceso, con la
    # ruta salida del manifiesto. Que el hash cuadre no prueba que ejecute.
    # `backend/` es la raíz del paquete del backend —`utils.logger`, no
    # `backend.utils.logger`—, así que se importa como lo hace la aplicación.
    sys.path.insert(0, str(raiz_del_repositorio / "backend"))
    from services.external_tools import open_babel as adaptador

    estado = adaptador.estado_actual(verificar_version=True)
    assert estado.disponible, estado.detalle

    pdbqt = "\n".join([
        "REMARK  Name = prueba",
        "ROOT",
        "ATOM      1  C   UNL     1       0.000   0.000   0.000  0.00  0.00    "
        " 0.000 C ",
        "ATOM      2  C   UNL     1       1.500   0.000   0.000  0.00  0.00    "
        " 0.000 C ",
        "ENDROOT",
        "TORSDOF 0",
        "",
    ])
    resultado = asyncio.run(adaptador.convertir_pdbqt_a_sdf(pdbqt))
    assert adaptador.sdf_es_valido(resultado.contenido), resultado.contenido[:200]
    assert "$$$$" in resultado.contenido, "la conversión no produjo un SDF completo"
    # El informe de la conversión declara con qué binario se hizo, y coincide.
    assert resultado.sha256 == esperado
    assert resultado.licencia_spdx == "GPL-2.0-only"
    assert resultado.returncode == 0

    # Y el binario que ejecutó es el del manifiesto, no uno del PATH.
    assert Path(adaptador.directorio_de_la_herramienta()).resolve() == (
        raiz_del_repositorio / "tools" / "openbabel"
    ).resolve()


# ── 5-8. Lo que tiene que detener el bootstrap ───────────────────────────


def test_un_hash_incorrecto_detiene_el_bootstrap(arbol, clon, tmp_path):
    """5. Un archivo local con el SHA-256 equivocado no se extrae."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)

    antes = sorted(p.name for p in clon.iterdir())
    with pytest.raises(SystemExit) as excinfo:
        boot.aprovisionar(clon, salida, "0" * 64, forzar=False)
    assert "no coincide" in str(excinfo.value).lower()
    assert not (clon / "python-embed").exists(), "se extrajo pese al hash malo"
    assert sorted(p.name for p in clon.iterdir()) == antes


def test_una_descarga_truncada_no_deja_estado_valido(arbol, clon, tmp_path):
    """6. Un zip cortado se rechaza entero; el árbol queda como estaba."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    truncado = tmp_path / "truncado.zip"
    truncado.write_bytes(salida.read_bytes()[:-300])

    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        boot.aprovisionar(clon, truncado, arch.sha256(truncado), forzar=False)
    assert excinfo.value.codigo == "ZIP_ILEGIBLE"
    assert not (clon / "python-embed").exists()
    assert boot.medir(clon).codigo == boot.AUSENTE


def test_un_zip_con_traversal_es_rechazado(clon, tmp_path):
    """7. `../` no llega a tocar el disco."""
    entradas = {"../fuera.txt": b"x"}
    malo = _zip_bruto(tmp_path / "malo.zip", entradas, _manifiesto_para(entradas))
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        boot.aprovisionar(clon, malo, arch.sha256(malo), forzar=False)
    assert excinfo.value.codigo == "TRAVERSAL"
    assert not (clon.parent / "fuera.txt").exists()


def test_un_zip_que_pisa_el_backend_es_rechazado(clon, tmp_path):
    """8. La forma de fallo que tenía `base-v1.0.0.zip`.

    Se comprueba dos veces: por la lista de destinos y, con un destino
    permitido pero rastreado, por `git ls-files`. Las dos murallas por separado.
    """
    original = (clon / "backend" / "api" / "main.py")
    assert original.is_file(), "el clon no trae backend/api/main.py"
    antes = original.read_bytes()

    entradas = {"backend/api/main.py": b"# PISADO\n"}
    malo = _zip_bruto(tmp_path / "pisa.zip", entradas, _manifiesto_para(entradas))
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        boot.aprovisionar(clon, malo, arch.sha256(malo), forzar=False)
    assert excinfo.value.codigo == "DESTINO_NO_PERMITIDO"
    assert original.read_bytes() == antes, "el backend quedó modificado"

    # Segunda muralla: un destino PERMITIDO que además está versionado.
    rastreadas = arch.rutas_rastreadas(clon)
    candidatas = [
        r for r in rastreadas
        if any(r.startswith(c.prefijo) for c in arch.COMPONENTES if not c.es_archivo)
    ]
    if not candidatas:
        pytest.skip("ningún archivo rastreado cae dentro de un destino permitido")
    victima = sorted(candidatas)[0]
    entradas = {victima: b"# PISADO\n"}
    malo2 = _zip_bruto(tmp_path / "pisa2.zip", entradas, _manifiesto_para(entradas))
    guardado = (clon / victima).read_bytes()
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        boot.aprovisionar(clon, malo2, arch.sha256(malo2), forzar=False)
    assert excinfo.value.codigo == "SOBRESCRIBIRIA_RASTREADO"
    assert (clon / victima).read_bytes() == guardado


# ── 9. `--check` no toca el artefacto canónico ───────────────────────────


def test_check_no_modifica_un_artefacto_canonico_previo(arbol, monkeypatch, capsys):
    """9. El defecto que dejó corrupto `dist/base-v1.0.0.zip`.

    Se crea un artefacto canónico en `dist/`, se le escribe un contenido
    reconocible, se corre `--check`, y se comprueba byte a byte que sigue igual.
    """
    canonico = arbol / "dist" / arch.RUNTIME_BASE.filename
    canonico.parent.mkdir(parents=True, exist_ok=True)
    canonico.write_bytes(b"NO ME TOQUES" * 100)
    huella_antes = arch.sha256(canonico)
    tam_antes = canonico.stat().st_size

    monkeypatch.setattr(sys, "argv", ["build_base_archive.py", "--check",
                                      "--raiz", str(arbol)])
    codigo = arch.main()
    capsys.readouterr()

    assert codigo == 0
    assert canonico.stat().st_size == tam_antes
    assert arch.sha256(canonico) == huella_antes, (
        "`--check` reescribió el artefacto canónico: es exactamente el defecto "
        "que corrompió base-v1.0.0.zip"
    )


def test_check_falla_si_el_verificador_no_ve(monkeypatch):
    """9b. Un guardián tiene que demostrar que ve (AGENTS.md, restricción 2)."""
    assert arch.autotest() == [], "el verificador no detecta sus propias muestras"

    # Se rompe el detector a propósito: `--check` tiene que fallar.
    monkeypatch.setattr(arch, "validar_destino", lambda nombre: arch.COMPONENTES[0])
    assert arch.autotest() != [], (
        "con el detector de destinos anulado, el autotest siguió pasando: "
        "entonces no comprueba nada"
    )


# ── 10-11. Idempotencia y clon limpio ────────────────────────────────────


def test_dos_aprovisionamientos_dan_el_mismo_inventario(arbol, clon, tmp_path):
    """10. Y el segundo no hace nada, porque ya está hecho."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    huella = arch.sha256(salida)

    assert boot.aprovisionar(clon, salida, huella, forzar=False) == 0
    recibo = clon / "python-embed" / boot.NOMBRE_RECIBO
    primero = recibo.read_bytes()
    assert boot.medir(clon).codigo == boot.COMPLETO

    assert boot.aprovisionar(clon, salida, huella, forzar=False) == 0
    assert recibo.read_bytes() == primero, "el recibo cambió sin cambiar nada"

    # Y forzando la reinstalación entera, el inventario sigue siendo el mismo.
    assert boot.aprovisionar(clon, salida, huella, forzar=True) == 0
    assert recibo.read_bytes() == primero
    assert boot.medir(clon, con_hashes=True).codigo == boot.COMPLETO


def test_un_clon_limpio_se_aprovisiona_en_un_temporal(arbol, clon, tmp_path):
    """11. Sin depender de `D:\\` ni del perfil de usuario."""
    assert boot.medir(clon).codigo == boot.AUSENTE

    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    assert boot.aprovisionar(clon, salida, arch.sha256(salida), forzar=False) == 0

    estado = boot.medir(clon, con_hashes=True)
    assert estado.codigo == boot.COMPLETO
    assert estado.faltan_obligatorios == []
    assert (clon / "python-embed" / "python.exe").is_file()
    assert (clon / "tools" / "openbabel" / "bin" / "obabel.exe").is_file()

    # Y —lo que de verdad importa— NINGÚN archivo versionado ha cambiado.
    estado_git = subprocess.run(
        ["git", "-C", str(clon), "status", "--porcelain"],
        capture_output=True, text=True, timeout=120,
    )
    lineas = [l for l in estado_git.stdout.splitlines() if l.strip()]
    modificados = [l for l in lineas if not l.startswith("??")]
    assert modificados == [], (
        f"el aprovisionamiento tocó archivos versionados: {modificados}"
    )

    # Lo que sí puede quedar es ruido no rastreado, y sólo dentro de un destino
    # declarado. Medido el 2026-09-06: `tools/openbabel/bin/` aparece porque
    # `.gitignore` cubre sus binarios por extensión pero no sus tablas de datos.
    # Es cosmético y la línea que falta está en docs/81; que aparezca AQUÍ, en
    # una prueba, es lo que impide que se olvide.
    prefijos = tuple(c.prefijo for c in arch.COMPONENTES)
    fuera = [
        l for l in lineas
        if l.startswith("??") and not l[3:].strip().strip('"').startswith(prefijos)
    ]
    assert fuera == [], f"ruido fuera de los destinos declarados: {fuera}"


def test_ninguna_ruta_de_maquina_esta_escrita_en_el_codigo(raiz_del_repositorio):
    """11b. Ni `D:\\moldesign-build` ni `C:\\Users\\...` dentro de los scripts."""
    sospechas = []
    for nombre in ("bootstrap_dev_tree.py", "build_base_archive.py",
                   "stage_openbabel_tool.py", "check_openbabel_boundary.py",
                   "lock_embedded_runtime.py", "verify_release_source_offer.py",
                   "bundle_helper.py"):
        ruta = raiz_del_repositorio / "scripts" / nombre
        if not ruta.is_file():
            continue
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            desnuda = linea.split("#")[0]
            for patron in (":\\Users", ":/Users", "moldesign-build", "\\Temp\\"):
                if patron in desnuda:
                    sospechas.append(f"{nombre}:{numero}  {linea.strip()[:80]}")
    assert sospechas == [], "hay rutas de una máquina concreta:\n" + "\n".join(sospechas)


# ── 12-13. Portabilidad y PATH ───────────────────────────────────────────


def test_el_inventario_usa_rutas_portables(arbol, tmp_path):
    """12. Separadores `/`, sin unidades, sin `..`, sin nombres reservados."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    manifiesto = arch.empaquetar(arbol, salida)

    for nombre in manifiesto["archivos"]:
        assert "\\" not in nombre, f"separador de Windows en el inventario: {nombre}"
        assert not nombre.startswith("/"), nombre
        arch.validar_nombre(nombre)

    with zipfile.ZipFile(salida) as zf:
        for entrada in zf.namelist():
            assert "\\" not in entrada, entrada

    # Un inventario con separador invertido se rechaza. Es la única puerta por
    # la que puede entrar: `zipfile` normaliza `\` a `/` al leer las entradas.
    entradas = {"python-embed/x.pyd": b"x"}
    man = _manifiesto_para(entradas)
    man["archivos"] = {"python-embed\\x.pyd": man["archivos"]["python-embed/x.pyd"]}
    malo = _zip_bruto(tmp_path / "raro.zip", entradas, man)
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        arch.inspeccionar(malo)
    assert excinfo.value.codigo == "SEPARADOR_NO_PORTABLE"


def test_ningun_ejecutable_se_resuelve_por_path(raiz_del_repositorio):
    """13. Ningún programa científico se busca en el `PATH`.

    Se reutiliza el detector de `check_openbabel_boundary`, que es el que ya
    guarda esta regla para Open Babel, en vez de escribir un segundo detector
    que podría discrepar del primero.

    `git` es la excepción declarada y sí se invoca por `PATH`: es una consulta
    de sólo lectura del entorno de desarrollo, su resultado nunca HABILITA nada
    —sólo puede rechazar— y en un clon sin git el bootstrap dice que no
    comprobó, en vez de contar el silencio como aprobación.
    """
    sys.path.insert(0, str(raiz_del_repositorio / "scripts"))
    from check_openbabel_boundary import resuelve_por_path

    hallazgos = []
    for nombre in ("bootstrap_dev_tree.py", "build_base_archive.py",
                   "stage_openbabel_tool.py", "lock_embedded_runtime.py"):
        ruta = raiz_del_repositorio / "scripts" / nombre
        if ruta.is_file():
            hallazgos += [f"{nombre}: {h}" for h in
                          resuelve_por_path(ruta.read_text(encoding="utf-8"))]
    assert hallazgos == [], "se resuelve un ejecutable por PATH:\n" + "\n".join(hallazgos)

    fuente = (raiz_del_repositorio / "scripts" / "bootstrap_dev_tree.py").read_text(
        encoding="utf-8")
    assert "shutil.which" not in fuente
    assert '"python-embed" / "python.exe"' in fuente, (
        "el intérprete se pregunta por ruta absoluta, no por nombre"
    )


# ── Los cinco estados ────────────────────────────────────────────────────


def test_ausente_y_corrupto_no_se_confunden(arbol, clon, tmp_path):
    """12 del contrato: «ausente» se distingue de «corrupto»."""
    assert boot.medir(clon).codigo == boot.AUSENTE

    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)
    boot.aprovisionar(clon, salida, arch.sha256(salida), forzar=False)
    assert boot.medir(clon).codigo == boot.COMPLETO

    # Se rompe un archivo por dentro, sin cambiar su tamaño ni borrarlo.
    victima = clon / "tools" / "vina" / "vina.exe"
    victima.write_bytes(b"X" * victima.stat().st_size)
    assert boot.medir(clon).codigo == boot.COMPLETO, "por tamaño no se nota"
    estado = boot.medir(clon, con_hashes=True)
    assert estado.codigo == boot.CORRUPTO
    assert any("vina.exe" in d for d in estado.discrepancias)

    # Y borrarlo tampoco es «ausente»: es corrupto respecto a su recibo.
    victima.unlink()
    assert boot.medir(clon).codigo == boot.CORRUPTO


def test_una_extraccion_a_medias_no_parece_una_instalacion(arbol, clon, tmp_path):
    """10 del contrato. El recibo se escribe el último; sin él, no hay nada."""
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    manifiesto = arch.empaquetar(arbol, salida)

    # Se simula lo que deja una interrupción: componentes movidos, sin recibo.
    boot.extraer(clon, salida, forzar=False)
    assert (clon / "python-embed" / "python.exe").is_file()
    assert not (clon / "python-embed" / boot.NOMBRE_RECIBO).exists()
    assert boot.medir(clon).codigo == boot.AJENO, (
        "sin recibo, un árbol con piezas dentro NO puede declararse completo"
    )

    boot.escribir_recibo(clon, manifiesto, arch.sha256(salida))
    assert boot.medir(clon).codigo == boot.COMPLETO


def test_un_staging_abandonado_es_incompleto(clon):
    """Una ejecución interrumpida deja rastro, y el rastro se lee."""
    (clon / boot.STAGING).mkdir(parents=True)
    estado = boot.medir(clon)
    assert estado.codigo == boot.INCOMPLETO
    assert boot.STAGING in estado.detalle


def test_no_se_reemplaza_lo_que_el_bootstrap_no_puso(arbol, clon, tmp_path):
    """Sin `--force` no se toca nada que este artefacto no haya colocado."""
    (clon / "python-embed").mkdir()
    (clon / "python-embed" / "python.exe").write_bytes(b"MIO")
    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, salida)

    assert boot.aprovisionar(clon, salida, arch.sha256(salida), forzar=False) == 1
    assert (clon / "python-embed" / "python.exe").read_bytes() == b"MIO"

    # Con --force sí, pero lo anterior se aparta en vez de borrarse.
    assert boot.aprovisionar(clon, salida, arch.sha256(salida), forzar=True) == 0
    apartado = clon / boot.APARTADO / "python-embed"
    assert apartado.is_dir(), "lo reemplazado se borró en vez de apartarse"
    assert (apartado / "python.exe").read_bytes() == b"MIO"


def test_los_pesos_propios_tienen_contrato_pero_no_implementacion():
    """El contrato declarado, sin inventarse el repositorio que no existe."""
    pesos = arch.PESOS_PROPIOS
    assert pesos.gated is True
    assert pesos.licencia.startswith("LICENSE-MODELS")
    assert pesos.publicado is False, (
        "si esto pasa a True, alguien declaró una URL: comprueba que existe de "
        "verdad y que el error por falta de credencial es explícito"
    )
    assert "moldesign-rescoring" in pesos.nota
    assert "ausencia" in pesos.nota.lower(), (
        "la nota tiene que decir que faltar es legítimo; si no, un usuario sin "
        "credencial no sabe si le falta algo o si algo está roto"
    )


def test_el_artefacto_es_determinista(arbol, tmp_path):
    """Dos empaquetados del mismo árbol dan el mismo SHA-256."""
    uno = tmp_path / "a" / arch.RUNTIME_BASE.filename
    dos = tmp_path / "b" / arch.RUNTIME_BASE.filename
    arch.empaquetar(arbol, uno)
    arch.empaquetar(arbol, dos)
    assert arch.sha256(uno) == arch.sha256(dos)


def test_los_destinos_sin_ignorar_son_los_ya_declarados(raiz_del_repositorio):
    """Ignorar no protege de nada; que aparezca ruido nuevo, sí importa.

    La seguridad la dan la lista de destinos y `git ls-files`. Que un destino
    esté además en `.gitignore` es higiene: evita que aprovisionar llene el
    `git status` de quien clona. Esta prueba fija la lista de los que HOY no lo
    están, para que añadir un destino nuevo sin su línea se note aquí y no en
    el escritorio de alguien.
    """
    sin_ignorar = set(arch._verificar_destinos_ignorados(raiz_del_repositorio))
    conocidos = {
        # Medido el 2026-09-06. `.gitignore` cubre estos dos por EXTENSIÓN
        # (`tools/**/*.exe`, `tools/**/*.dll`) y no por directorio. La
        # consecuencia real es distinta en cada uno: los binarios de llama.cpp
        # quedan ignorados y no hacen ruido, pero las tablas de datos `.txt` de
        # Open Babel sí aparecen como no rastreadas después de aprovisionar.
        # Estar en esta lista NO significa que haya ruido: significa que la
        # regla que los cubre es por extensión y no por directorio. El árbol
        # principal ya arregló el de Open Babel con una línea que sobre
        # `6a5cabe` todavía no existe. Ver docs/81 §1.1.
        "tools/openbabel/bin/",
    }
    nuevos = sin_ignorar - conocidos
    assert nuevos == set(), (
        f"destinos sin ignorar que nadie ha declarado: {sorted(nuevos)}. "
        "Añade su línea a `.gitignore` o documéntala en docs/81."
    )


def test_lo_que_el_repositorio_ya_trae_no_viaja_y_se_declara(clon, tmp_path):
    """El artefacto aporta lo que falta; lo versionado se omite y se dice.

    Medido el 2026-09-06 sobre el árbol real: `tools/llama/` tiene `.gitkeep`,
    `README.md` y `SHA256SUM.txt` versionados junto a binarios que no lo están.
    La primera versión del empaquetador los metía y el artefacto habría pisado
    tres archivos del repositorio al extraerse.
    """
    # Se empaqueta DESDE el repositorio sintético, que tiene esos versionados
    # dentro de un destino permitido.
    (clon / "tools" / "llama" / "llama-server.exe").write_bytes(b"binario")
    (clon / "python-embed").mkdir(exist_ok=True)
    (clon / "python-embed" / "python.exe").write_bytes(b"MZ")
    (clon / "tools" / "vina").mkdir(parents=True, exist_ok=True)
    (clon / "tools" / "vina" / "vina.exe").write_bytes(b"v")
    (clon / "tools" / "openbabel" / "bin").mkdir(parents=True, exist_ok=True)
    (clon / "tools" / "openbabel" / "bin" / "obabel.exe").write_bytes(b"o")

    entradas, faltan, omitidos = arch.reunir(clon)
    assert faltan == []
    nombres = [n for n, _ in entradas]

    assert "tools/llama/README.md" in omitidos, (
        "el README versionado de llama.cpp tiene que omitirse explícitamente"
    )
    assert "tools/llama/README.md" not in nombres
    assert "tools/llama/llama-server.exe" in nombres, (
        "y el binario, que el repositorio NO trae, sí tiene que viajar"
    )

    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    manifiesto = arch.empaquetar(clon, salida)
    declarados = manifiesto["no_contiene"]["archivos_versionados_omitidos"]
    assert "tools/llama/README.md" in declarados, (
        "una exclusión silenciosa es indistinguible de un olvido"
    )

    contenido_versionado = (clon / "tools/llama/README.md").read_bytes()
    assert boot.aprovisionar(clon, salida, arch.sha256(salida), forzar=True) == 0
    assert (clon / "tools/llama/README.md").read_bytes() == contenido_versionado, (
        "intercambiar el directorio del runtime borro o altero un archivo de Git"
    )
    assert (clon / "tools/llama/llama-server.exe").read_bytes() == b"binario"


def test_los_pesos_de_una_dependencia_viajan_y_se_declaran(arbol, tmp_path):
    """Un `.pt` de MolDesign se para; uno de `admet_ai` viaja y se cuenta.

    Medido el 2026-09-06 sobre el árbol real: `admet_ai` vendoriza sus propios
    checkpoints en `resources/models/`. La primera versión de la regla los
    llamaba «pesos propios» y bloqueaba el empaquetado — un detector bien
    intencionado y mal apuntado. Sin ellos la capa ADMET no funciona.
    """
    ajeno = arbol / "python-embed/Lib/site-packages/admet_ai/resources/models/m_0.pt"
    ajeno.parent.mkdir(parents=True, exist_ok=True)
    ajeno.write_bytes(b"checkpoint de la dependencia")

    salida = tmp_path / "art" / arch.RUNTIME_BASE.filename
    manifiesto = arch.empaquetar(arbol, salida)
    nombres = arch.inspeccionar(salida).nombres
    assert any(n.endswith("admet_ai/resources/models/m_0.pt") for n in nombres), (
        "el peso de la dependencia no viajó: la capa ADMET quedaría rota"
    )
    declarado = manifiesto["pesos_de_terceros_dentro_de_dependencias"]["por_paquete"]
    assert declarado["admet_ai"]["archivos"] == 1, (
        "viajar sin declararse es exactamente lo que hace falta evitar"
    )

    # Y fuera de `site-packages` la regla sigue mordiendo.
    propio = arbol / "tools" / "vina" / "gnn_v2_cl_best.pt"
    propio.write_bytes(b"pesos de MolDesign")
    with pytest.raises(arch.ArchivoRechazado) as excinfo:
        arch.empaquetar(arbol, tmp_path / "art9" / "x.zip")
    assert excinfo.value.codigo == "PESO_PROPIO"
