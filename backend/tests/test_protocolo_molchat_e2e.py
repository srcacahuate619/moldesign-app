"""Dos procesos reales: sesión, contrato y cálculo desde el sidecar vendorizado.

La identidad de plataforma es una cuenta sintética y el backend sólo monta el
router de host. No usa ni modifica la base de datos ni los archivos del usuario.
"""
import socket
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, HTTPException, Request

from api.dependencies import get_current_user
from api.routers import molchat_host
from services.molchat_host import launcher, sesion


def test_session_y_propiedades_cruzan_los_dos_procesos(tmp_path, monkeypatch):
    uid = str(uuid4())
    app = FastAPI()
    app.include_router(molchat_host.router)
    llamadas = []

    def identidad(request: Request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        if token == 'operador-sintetico':
            return SimpleNamespace(id=uid)
        validado = sesion.verificar_para_plataforma(token)
        if validado and validado['sub'] == uid:
            llamadas.append(request.url.path)
            return SimpleNamespace(id=uid)
        raise HTTPException(401, 'sesión de prueba inválida')

    app.dependency_overrides[get_current_user] = identidad
    for nombre, archivo in [('MOLCHAT_MEMORY_FILE', 'memory.db'),
                            ('MOLCHAT_EXEC_STORE', 'exec.db'),
                            ('MOLCHAT_CONSENTS_FILE', 'consents.json')]:
        monkeypatch.setenv(nombre, str(tmp_path / archivo))
    monkeypatch.setenv('MOLCHAT_PROVIDER', 'fake')
    # Una credencial heredada del entorno nunca debe desplazar la cuenta del turno.
    monkeypatch.setenv('MOLDESIGN_TOKEN', 'test-old-token')
    instancia = []

    def obtener(url):
        if not instancia:
            instancia.append(launcher.Lanzador(moldesign_url=url, arranque_timeout_s=40))
        return instancia[0]

    monkeypatch.setattr(launcher, 'obtener_lanzador', obtener)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(32)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        until = time.monotonic() + 15
        while not server.started and time.monotonic() < until:
            time.sleep(0.05)
        assert server.started
        with httpx.Client(timeout=45, trust_env=False) as client:
            session = client.post(f'http://127.0.0.1:{port}/molchat-host/session',
                                  headers={'Authorization': 'Bearer operador-sintetico'})
            assert session.status_code == 200, session.text
            data = session.json()
            assert instancia[0]._moldesign_url == f'http://127.0.0.1:{port}'
            headers = {'Authorization': 'Bearer ' + data['token']}
            turn = client.post(data['url'] + '/v1/chat', headers=headers,
                               json={'text': 'Calcula propiedades de CCOC(=O)c1ccccc1'})
            assert turn.status_code == 200, turn.text
            assert 'MolDesign / RDKit' in turn.text
            assert '150.2' in turn.text  # calculado, no aparece en el dataset de demostración
            assert '/molchat-host/contract' in llamadas
            assert '/molchat-host/properties' in llamadas
            assert client.post(data['url'] + '/v1/chat', json={'text': 'hola'}).status_code == 401
    finally:
        if instancia:
            instancia[0].detener()
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        assert not thread.is_alive()
