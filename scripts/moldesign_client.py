#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moldesign_client.py — Cliente Python de alto nivel para el servidor de cómputo científico.

Uso rápido:
    from scripts.moldesign_client import MolDesignClient

    with MolDesignClient() as c:
        info = c.server_info()
        c.run("python scripts/mi_script.py --arg valor")
        c.upload("data/mi_archivo.sdf", "data/mi_archivo.sdf")
        c.download_artifacts("scripts/artifacts_science/RS-03-PARAM-B", "scripts/artifacts_science/RS-03-PARAM-B")

CLI:
    python scripts/moldesign_client.py status
    python scripts/moldesign_client.py run "python scripts/run_rs03_param_b.py --inside-container"
    python scripts/moldesign_client.py upload data/pdbbind data/pdbbind
    python scripts/moldesign_client.py fetch scripts/artifacts_science/RS-03-PARAM-B
    python scripts/moldesign_client.py shell
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import stat
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import paramiko


# ---------------------------------------------------------------------------
# Configuración del servidor (sobreescribible con variables de entorno)
# ---------------------------------------------------------------------------

_DEFAULTS = {
    # Sin valor por defecto A PROPOSITO. Antes traia la IP privada del servidor
    # del autor, que en un repositorio publico es infraestructura ajena expuesta
    # y en cualquier otra red apunta a una maquina que no es la que se cree.
    "host":      os.environ.get("MOLDESIGN_HOST",      ""),
    "user":      os.environ.get("MOLDESIGN_USER",      "srcacahuate619"),
    # La autenticacion por llave del agente/usuario es la via normal. Una
    # contrasena solo se acepta si se proporciona explicitamente por entorno.
    "password":  os.environ.get("MOLDESIGN_PASSWORD"),
    "port":      int(os.environ.get("MOLDESIGN_PORT",  "22")),
    "image":     os.environ.get("MOLDESIGN_IMAGE",     "moldesign-science:latest"),
    "workspace": os.environ.get("MOLDESIGN_WORKSPACE", "/home/srcacahuate619/moldesign-env"),
}

# Raíz del proyecto local (para rutas relativas automáticas)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Resultado de una ejecución remota en Docker."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __repr__(self):
        status = "OK" if self.ok else f"FAIL({self.exit_code})"
        return f"<RunResult [{status}] {self.duration_s:.1f}s cmd={self.command!r}>"


@dataclass
class ServerInfo:
    """Información del estado del servidor remoto."""
    hostname: str
    uptime: str
    docker_containers: List[Dict]
    workspace_files: List[str]
    science_container_running: bool
    raw: Dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

class MolDesignClient:
    """
    Cliente de alto nivel para el servidor de cómputo científico MolDesign.

    Expone operaciones simples:
        .status()           → imprime estado del servidor y contenedores
        .run(cmd)           → ejecuta un comando en el contenedor Docker
        .run_script(path)   → sube un script local y lo ejecuta
        .upload(local, remote)   → sube archivo(s) al workspace remoto
        .download(remote, local) → descarga archivo(s) del workspace remoto
        .download_artifacts(experiment_id) → descarga artefactos de un experimento
        .shell()            → abre un SSH interactivo básico
        .ssh(cmd)           → ejecuta un comando SSH raw (sin Docker)
    """

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = None,
        image: Optional[str] = None,
        workspace: Optional[str] = None,
        timeout: int = 20,
        verbose: bool = True,
    ):
        self.host      = host      or _DEFAULTS["host"]
        self.user      = user      or _DEFAULTS["user"]
        self.password  = password  or _DEFAULTS["password"]
        self.port      = port      or _DEFAULTS["port"]
        self.image     = image     or _DEFAULTS["image"]
        self.workspace = workspace or _DEFAULTS["workspace"]
        self.timeout   = timeout
        self.verbose   = verbose

        self._ssh:  Optional[paramiko.SSHClient]  = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    # ── Conexión ─────────────────────────────────────────────────────────────

    def connect(self) -> "MolDesignClient":
        """Abre la conexión SSH+SFTP. Idempotente."""
        if self._ssh is not None:
            return self
        if self.verbose:
            print(f"[MolDesign] Conectando a {self.user}@{self.host}:{self.port}...")
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        kwargs = {
            "hostname": self.host, "port": self.port, "username": self.user,
            "timeout": self.timeout, "allow_agent": True, "look_for_keys": True,
        }
        if self.password:
            kwargs["password"] = self.password
        ssh.connect(**kwargs)
        self._ssh  = ssh
        self._sftp = ssh.open_sftp()
        if self.verbose:
            print(f"[MolDesign] Conectado. Workspace: {self.workspace}")
        return self

    def close(self):
        """Cierra SSH y SFTP."""
        for conn in (self._sftp, self._ssh):
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        self._sftp = self._ssh = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    # ── Estado del servidor ───────────────────────────────────────────────────

    def status(self) -> ServerInfo:
        """
        Imprime y retorna el estado del servidor (hostname, Docker, workspace).

        Ejemplo:
            info = c.status()
            print(info.science_container_running)
        """
        self.connect()

        hostname  = self._ssh_str("hostname").strip()
        uptime    = self._ssh_str("uptime -p").strip()
        containers_raw = self._ssh_str(
            'docker ps --format \'{"id":"{{.ID}}","image":"{{.Image}}","status":"{{.Status}}","name":"{{.Names}}"}\''
        )
        containers = []
        for line in containers_raw.strip().splitlines():
            line = line.strip()
            if line:
                try:
                    containers.append(json.loads(line))
                except Exception:
                    pass

        files_raw = self._ssh_str(f"ls {self.workspace} 2>/dev/null || echo ''")
        files = [f for f in files_raw.strip().splitlines() if f]

        science_running = any(
            _DEFAULTS["image"].split(":")[0] in c.get("image", "") for c in containers
        )

        info = ServerInfo(
            hostname=hostname,
            uptime=uptime,
            docker_containers=containers,
            workspace_files=files,
            science_container_running=science_running,
        )

        if self.verbose:
            self._print_status(info)

        return info

    def _print_status(self, info: ServerInfo):
        sci_tag = "RUNNING" if info.science_container_running else "stopped"
        print(f"== Servidor MolDesign {'=' * 35}")
        print(f"   Host:      {self.host}  ({info.hostname})")
        print(f"   Uptime:    {info.uptime}")
        print(f"   Workspace: {self.workspace}")
        print(f"   Science:   [{sci_tag}]  ({self.image})")
        print(f"-- Contenedores Docker ({len(info.docker_containers)} activos) {'-' * 20}")
        for c in info.docker_containers:
            tag = " << SCIENCE" if _DEFAULTS["image"].split(":")[0] in c.get("image","") else ""
            print(f"   [{c['id'][:8]}] {c['name']:30s}  {c['status']}{tag}")
        print("=" * 55)

    # ── Ejecución en Docker ───────────────────────────────────────────────────

    def run(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        stream: bool = True,
        line_callback: Optional[Callable[[str], None]] = None,
    ) -> RunResult:
        """
        Ejecuta un comando DENTRO del contenedor Docker (montando workspace).

        Args:
            command:       Comando completo. Ej: "python scripts/run_rs03.py --inside-container"
            env:           Variables de entorno extra para el contenedor.
            stream:        Si True, imprime stdout en tiempo real.
            line_callback: Función opcional que recibe cada línea de salida.

        Returns:
            RunResult con exit_code, stdout, stderr y duración.

        Ejemplo:
            result = c.run("python --version")
            result = c.run("python scripts/mi_script.py", env={"MY_VAR": "123"})
        """
        self.connect()
        self._ssh_str(f"chmod -R 777 {self.workspace} 2>/dev/null || true", silent=True)

        env_flags = ""
        if env:
            env_flags = " ".join(f'-e {k}="{v}"' for k, v in env.items()) + " "

        docker_cmd = (
            f"docker run --rm "
            f"-v {self.workspace}:/workspace "
            f"-w /workspace "
            f"{env_flags}"
            f"{self.image} "
            f"{command}"
        )

        if self.verbose:
            print(f"[MolDesign] $ {command}")
            print("-" * 60)

        t0 = time.time()
        stdin, stdout, stderr = self._ssh.exec_command(docker_cmd, get_pty=True)

        lines = []
        for line in iter(stdout.readline, ""):
            lines.append(line)
            if line_callback:
                line_callback(line)
            elif stream:
                self._safe_print(line)

        exit_code = stdout.channel.recv_exit_status()
        err_str   = stderr.read().decode("utf-8", errors="replace")
        duration  = time.time() - t0

        if self.verbose:
            print("-" * 60)
            print(f"[MolDesign] Exit {exit_code} | {duration:.1f}s")

        return RunResult(
            command=command,
            exit_code=exit_code,
            stdout="".join(lines),
            stderr=err_str,
            duration_s=duration,
        )

    def run_script(
        self,
        local_script: str | Path,
        args: str = "",
        upload_inputs: Optional[List[Tuple[str | Path, str]]] = None,
        download_artifacts: Optional[Tuple[str, str | Path]] = None,
        stream: bool = True,
    ) -> RunResult:
        """
        Pipeline completo: sube script → ejecuta en Docker → descarga resultados.

        Args:
            local_script:        Ruta local al script .py
            args:                Argumentos extra para el script
            upload_inputs:       Lista de (local_path, remote_rel_path) a subir antes
            download_artifacts:  (remote_rel_dir, local_dir) de artefactos a descargar
            stream:              Imprimir salida en tiempo real

        Ejemplo:
            c.run_script(
                "scripts/run_rs03_param_b.py",
                args="--inside-container",
                upload_inputs=[("data/pdbbind/1abc/1abc_ligand.sdf", "data/pdbbind/1abc/1abc_ligand.sdf")],
                download_artifacts=("scripts/artifacts_science/RS-03-PARAM-B", "scripts/artifacts_science/RS-03-PARAM-B")
            )
        """
        self.connect()
        script_path = Path(local_script).resolve()

        # 1. Subir script
        remote_script_rel = f"scripts/{script_path.name}"
        remote_script_abs = posixpath.join(self.workspace, remote_script_rel)
        if self.verbose:
            print(f"[MolDesign] Subiendo script: {script_path.name}...")
        self._sftp_put(script_path, remote_script_abs)

        # 2. Subir inputs opcionales
        if upload_inputs:
            if self.verbose:
                print(f"[MolDesign] Subiendo {len(upload_inputs)} archivo(s) de entrada...")
            n_up = 0
            for i, (loc, rel) in enumerate(upload_inputs, 1):
                n_up += self.upload(loc, rel, _silent=True)
                if self.verbose and (i % 20 == 0 or i == len(upload_inputs)):
                    print(f"\r  [{i}/{len(upload_inputs)}]", end="", flush=True)
            if self.verbose:
                print(f"\n[MolDesign] {n_up} archivo(s) actualizados.")

        # 3. Ejecutar
        cmd = f"python {remote_script_rel} {args}".strip()
        result = self.run(cmd, stream=stream)

        # 4. Descargar artefactos opcionales
        if download_artifacts:
            remote_art, local_art = download_artifacts
            n = self.download(remote_art, local_art)
            if self.verbose:
                print(f"[MolDesign] {n} artefacto(s) descargados a {local_art}")

        return result

    # ── Transferencia de archivos ─────────────────────────────────────────────

    def upload(
        self,
        local: str | Path,
        remote_rel: str,
        _silent: bool = False,
    ) -> int:
        """
        Sube un archivo o directorio al workspace remoto.

        Args:
            local:      Ruta local (archivo o carpeta)
            remote_rel: Ruta relativa destino dentro del workspace

        Returns:
            Número de archivos subidos.

        Ejemplo:
            c.upload("data/pdbbind", "data/pdbbind")
            c.upload("scripts/mi_nuevo_script.py", "scripts/mi_nuevo_script.py")
        """
        self.connect()
        local_path = Path(local)
        if not _silent and self.verbose:
            print(f"[MolDesign] Subiendo: {local_path} → {remote_rel}")

        if local_path.is_file():
            remote_abs = posixpath.join(self.workspace, remote_rel.replace("\\", "/"))
            self._ensure_dir(posixpath.dirname(remote_abs))
            changed = self._sftp_put(local_path, remote_abs)
            return 1 if changed else 0
        elif local_path.is_dir():
            count = 0
            for root, _, files in os.walk(local_path):
                for f in files:
                    full = Path(root) / f
                    rel_part = full.relative_to(local_path)
                    rem = posixpath.join(self.workspace, remote_rel.replace("\\", "/"), str(rel_part).replace("\\", "/"))
                    self._ensure_dir(posixpath.dirname(rem))
                    if self._sftp_put(full, rem):
                        count += 1
            return count
        else:
            raise FileNotFoundError(f"No existe: {local_path}")

    def download(
        self,
        remote_rel: str,
        local: str | Path,
    ) -> int:
        """
        Descarga un archivo o directorio desde el workspace remoto.

        Args:
            remote_rel: Ruta relativa dentro del workspace remoto
            local:      Destino local (archivo o carpeta)

        Returns:
            Número de archivos descargados.

        Ejemplo:
            c.download("scripts/artifacts_science/RS-03-PARAM-B", "scripts/artifacts_science/RS-03-PARAM-B")
            c.download("data/output.json", "output.json")
        """
        self.connect()
        local_path = Path(local)
        remote_abs = posixpath.join(self.workspace, remote_rel.replace("\\", "/"))

        if self.verbose:
            print(f"[MolDesign] Descargando: {remote_rel} → {local_path}")

        # ¿es archivo o directorio?
        try:
            attr = self._sftp.stat(remote_abs)
            if stat.S_ISDIR(attr.st_mode):
                return self._download_dir(remote_abs, local_path)
            else:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self._sftp.get(remote_abs, str(local_path))
                return 1
        except IOError as e:
            print(f"[MolDesign] No se pudo acceder a {remote_abs}: {e}")
            return 0

    def download_artifacts(
        self,
        experiment_id: str,
        local_base: Optional[str | Path] = None,
    ) -> int:
        """
        Descarga los artefactos de un experimento por su ID.

        Args:
            experiment_id: ID del experimento. Ej: "RS-03-PARAM-B"
            local_base:    Ruta base local. Default: scripts/artifacts_science/<experiment_id>

        Ejemplo:
            c.download_artifacts("RS-03-PARAM-B")
        """
        remote_rel = f"scripts/artifacts_science/{experiment_id}"
        if local_base is None:
            local_base = _PROJECT_ROOT / "scripts" / "artifacts_science" / experiment_id
        return self.download(remote_rel, local_base)

    # ── SSH raw (sin Docker) ──────────────────────────────────────────────────

    def ssh(self, command: str, stream: bool = True) -> Tuple[int, str]:
        """
        Ejecuta un comando SSH directo en el servidor (sin Docker).

        Args:
            command: Comando shell a ejecutar en el servidor.
            stream:  Si True, imprime salida en tiempo real.

        Returns:
            (exit_code, stdout_str)

        Ejemplo:
            c.ssh("df -h")
            c.ssh("docker images")
            c.ssh("docker logs <container_id> --tail 50")
        """
        self.connect()
        if self.verbose:
            print(f"[MolDesign:ssh] $ {command}")

        stdin, stdout, stderr = self._ssh.exec_command(command)
        lines = []
        for line in iter(stdout.readline, ""):
            lines.append(line)
            if stream:
                self._safe_print(line)

        exit_code = stdout.channel.recv_exit_status()
        return exit_code, "".join(lines)

    def shell(self):
        """
        Abre una sesión SSH interactiva básica con el servidor.
        Escribe 'exit' o Ctrl+D para salir.
        """
        self.connect()
        print(f"[MolDesign] Shell interactivo → {self.user}@{self.host}")
        print("  Escribe 'exit' para salir.\n")
        chan = self._ssh.invoke_shell()
        import select
        import termios
        import tty
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            interactive = True
        except Exception:
            interactive = False

        try:
            while True:
                if interactive:
                    r, _, _ = select.select([chan, sys.stdin], [], [])
                    if chan in r:
                        data = chan.recv(1024)
                        if not data:
                            break
                        sys.stdout.buffer.write(data)
                        sys.stdout.flush()
                    if sys.stdin in r:
                        x = sys.stdin.read(1)
                        if not x:
                            break
                        chan.send(x)
                else:
                    cmd_in = input("ssh> ").strip()
                    if cmd_in in ("exit", "quit"):
                        break
                    _, out = self.ssh(cmd_in)
        finally:
            if interactive:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _ssh_str(self, cmd: str, silent: bool = False) -> str:
        _, stdout, _ = self._ssh.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        stdout.channel.recv_exit_status()
        return out

    def _sftp_put(self, local_path: Path, remote_path: str) -> bool:
        """Sube un archivo si el tamaño difiere. Retorna True si se actualizó."""
        local_size = local_path.stat().st_size
        try:
            if self._sftp.stat(remote_path).st_size == local_size:
                return False
        except IOError:
            pass
        self._sftp.put(str(local_path), remote_path)
        return True

    def _ensure_dir(self, remote_dir: str):
        parts = []
        cur = remote_dir
        while cur and cur != "/":
            try:
                self._sftp.stat(cur)
                break
            except IOError:
                parts.append(cur)
                cur = posixpath.dirname(cur)
        for d in reversed(parts):
            try:
                self._sftp.mkdir(d)
            except IOError:
                pass

    def _download_dir(self, remote_abs: str, local_dir: Path) -> int:
        count = 0
        local_dir.mkdir(parents=True, exist_ok=True)
        try:
            entries = self._sftp.listdir_attr(remote_abs)
        except IOError:
            return 0
        for attr in entries:
            r_item = posixpath.join(remote_abs, attr.filename)
            l_item = local_dir / attr.filename
            if stat.S_ISDIR(attr.st_mode):
                count += self._download_dir(r_item, l_item)
            else:
                self._sftp.get(r_item, str(l_item))
                count += 1
        return count

    @staticmethod
    def _safe_print(line: str):
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except UnicodeEncodeError:
            sys.stdout.write(line.encode("ascii", errors="replace").decode("ascii"))
            sys.stdout.flush()


# ---------------------------------------------------------------------------
# CLI de línea de comandos
# ---------------------------------------------------------------------------

def _cli():
    p = argparse.ArgumentParser(
        prog="moldesign_client",
        description="MolDesign Science Server CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos disponibles:
  status                           Estado del servidor y Docker
  run  "<cmd>"                     Ejecutar cmd en el contenedor
  ssh  "<cmd>"                     Ejecutar cmd SSH raw (sin Docker)
  upload  <local> <remote_rel>     Subir archivo/dir al workspace
  download  <remote_rel> [local]   Descargar archivo/dir del workspace
  fetch  <experiment_id>           Descargar artefactos de un experimento
  shell                            Sesión SSH interactiva

Ejemplos:
  python scripts/moldesign_client.py status
  python scripts/moldesign_client.py run "python --version"
  python scripts/moldesign_client.py run "python scripts/run_rs03_param_b.py --inside-container"
  python scripts/moldesign_client.py upload data/pdbbind data/pdbbind
  python scripts/moldesign_client.py fetch RS-03-PARAM-B
  python scripts/moldesign_client.py ssh "docker images"
  python scripts/moldesign_client.py ssh "df -h"
""",
    )
    p.add_argument("command", choices=["status", "run", "ssh", "upload", "download", "fetch", "shell"])
    p.add_argument("args", nargs="*", help="Argumentos del comando")
    p.add_argument("--host",      default=None)
    p.add_argument("--user",      default=None)
    p.add_argument("--password",  default=None)
    p.add_argument("--quiet", "-q", action="store_true", help="Suprimir mensajes de estado")

    ns = p.parse_args()
    client = MolDesignClient(
        host=ns.host, user=ns.user, password=ns.password,
        verbose=not ns.quiet,
    )

    with client:
        if ns.command == "status":
            client.status()

        elif ns.command == "run":
            if not ns.args:
                p.error("run requiere un comando. Ej: run \"python --version\"")
            result = client.run(" ".join(ns.args))
            sys.exit(result.exit_code)

        elif ns.command == "ssh":
            if not ns.args:
                p.error("ssh requiere un comando. Ej: ssh \"df -h\"")
            exit_code, _ = client.ssh(" ".join(ns.args))
            sys.exit(exit_code)

        elif ns.command == "upload":
            if len(ns.args) < 2:
                p.error("upload requiere: <local> <remote_rel>")
            n = client.upload(ns.args[0], ns.args[1])
            print(f"[MolDesign] {n} archivo(s) subidos.")

        elif ns.command == "download":
            if not ns.args:
                p.error("download requiere: <remote_rel> [local_dest]")
            remote_rel = ns.args[0]
            local_dest = ns.args[1] if len(ns.args) > 1 else Path(remote_rel).name
            n = client.download(remote_rel, local_dest)
            print(f"[MolDesign] {n} archivo(s) descargados a {local_dest}")

        elif ns.command == "fetch":
            if not ns.args:
                p.error("fetch requiere: <experiment_id>. Ej: fetch RS-03-PARAM-B")
            n = client.download_artifacts(ns.args[0])
            print(f"[MolDesign] {n} artefacto(s) descargados.")

        elif ns.command == "shell":
            client.shell()


if __name__ == "__main__":
    _cli()
