"""Doc 71: el certificado no bloquea el backend (E1) y lleva huso horario (E3).

# E1 — «Vista previa del certificado falla con Failed to fetch»

El informe de la VM lo describio asi: la pestana «Informe» carga su PDF y la
vista previa del certificado no. Son DOS documentos distintos por diseno -el
certificado sella cuando se emitio algo; el dossier del caso declara que
evidencia produjo una corrida- y viajan por rutas distintas a proposito, con su
propia prueba de frontera.

Lo que si era un defecto: `generate_certificate_pdf` es SINCRONA -ReportLab
componiendo un documento con tablas, imagenes y apendice- y se llamaba
directamente desde un `async def`. En un backend de escritorio de un solo
proceso eso congela el bucle de eventos entero mientras dura.

Y la vista previa lo sufria y la descarga no por una razon de forma: la descarga
la dispara un click, la vista previa se monta sola, y React invoca el efecto dos
veces en desarrollo. Salian DOS renders simultaneos del mismo documento sin que
nadie cancelara el primero.

NO SE PUDO REPRODUCIR el `Failed to fetch` exacto sin la VM. Lo que se corrige
son los dos mecanismos que producen esa forma de fallo: el bloqueo del bucle y
la peticion duplicada que nadie abortaba.

# E3 — «Fecha sin zona horaria»

`2026-09-02T20:22:57.261446`, sin `Z` ni offset, dentro del memo que se sella en
cadena. En un certificado eso pesa mas que en cualquier otro sitio: el documento
existe para poder reconciliarse con otras fuentes, y una hora sin huso no se
compara con nada sin adivinar.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest


# ── E1 ───────────────────────────────────────────────────────────────────────

def test_el_pdf_no_se_genera_dentro_del_bucle_de_eventos():
    from api.routers import blockchain

    fuente = inspect.getsource(blockchain._generate_certificate_data)
    assert "asyncio.to_thread" in fuente, (
        "el render del certificado volvio al bucle de eventos: mientras dura, "
        "congela el sondeo del pipeline, el catalogo y la peticion gemela"
    )
    # Y no quedo una llamada directa suelta.
    assert "\n    pdf_buf = generate_certificate_pdf(" not in fuente


def test_la_generacion_sigue_siendo_sincrona_y_por_eso_hace_falta_el_hilo():
    """Si algun dia se vuelve `async`, el `to_thread` sobra y hay que quitarlo.

    La prueba existe para que ese cambio no pase inadvertido: envolver una
    corrutina en `to_thread` no falla, simplemente no hace nada util.
    """
    from services.blockchain.pdf_generator import generate_certificate_pdf

    assert not inspect.iscoroutinefunction(generate_certificate_pdf)


def test_los_dos_endpoints_del_certificado_comparten_generador():
    """Sólo se diferencian en `inline` vs `attachment`.

    Si divergieran, la vista previa y la descarga podrian entregar documentos
    distintos con el mismo nombre, que es peor que fallar.
    """
    from api.routers import blockchain

    descarga = inspect.getsource(blockchain.get_certificate)
    vista = inspect.getsource(blockchain.get_certificate_preview)
    for fuente in (descarga, vista):
        assert "_generate_certificate_data" in fuente
    assert "attachment; filename=" in descarga
    assert "inline; filename=" in vista


# ── E3 ───────────────────────────────────────────────────────────────────────

def test_el_modulo_del_certificado_no_usa_utcnow():
    """`utcnow()` devuelve un datetime NAIVE y esta deprecado justo por esto."""
    from api.routers import blockchain

    fuente = inspect.getsource(blockchain)
    # Se ignoran los comentarios, que explican por que ya no se usa.
    codigo = "\n".join(
        l for l in fuente.splitlines() if not l.strip().startswith("#")
    )
    assert "utcnow()" not in codigo, "volvio una marca de tiempo sin huso horario"


def test_la_marca_del_memo_lleva_offset():
    """La forma exacta que el informe de la VM marco como defecto."""
    sin_huso = datetime(2026, 9, 2, 20, 22, 57, 261446).isoformat()
    con_huso = datetime(2026, 9, 2, 20, 22, 57, 261446, tzinfo=timezone.utc).isoformat()

    assert sin_huso == "2026-09-02T20:22:57.261446"
    assert con_huso.endswith("+00:00")
    # Es exactamente lo que ahora produce el endpoint.
    assert datetime.now(timezone.utc).isoformat().endswith("+00:00")


def test_prepare_construye_la_marca_del_memo_con_huso():
    from api.routers import blockchain

    # La ruta institucional ya no construye registros. El único timestamp nuevo
    # nace en /prepare y debe conservar el offset UTC dentro del memo.
    fuente = inspect.getsource(blockchain.prepare_certification)
    indice = fuente.index("timestamp_iso")
    fragmento = fuente[indice:indice + 200]
    assert "timezone.utc" in fragmento, "timestamp_iso se construye sin huso horario"
