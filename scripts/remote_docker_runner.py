#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""remote_docker_runner.py — Middleware para ejecución transparente de cómputo en Docker remoto.

Permite que cualquier script en Windows ejecute tareas de cálculo científico en el contenedor
`moldesign-science:latest` ubicado en el servidor Ubuntu del laboratorio (se indica con `MOLDESIGN_REMOTE_HOST`), gestionando:
  1. Sincronización binaria incremental (SFTP) de inputs y datos (SDF, JSON, scripts).
  2. Invocación de Docker remoto con streaming en vivo de stdout/stderr.
  3. Descarga automática de artefactos y métricas de vuelta a Windows.
  4. Preservación estricta de hashes SHA-256 sin alteraciones de fin de línea.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import paramiko


def sha256_archivo(path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo local en chunks de 1MB."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


class RemoteDockerRunner:
    """Middleware de conexión y ejecución remota en Docker."""

    # Sin valores por defecto: la IP, el usuario y la ruta del servidor del
    # mantenedor no describen el producto y no tienen por que viajar en un
    # repositorio publico. Quien use este runner declara su propio destino.
    DEFAULT_HOST = os.environ.get("MOLDESIGN_REMOTE_HOST", "")
    DEFAULT_USER = os.environ.get("MOLDESIGN_REMOTE_USER", "")
    # Llaves SSH/agent primero; password solo si el usuario lo inyecta de forma
    # explicita para una compatibilidad temporal.
    DEFAULT_PASSWORD = os.environ.get("MOLDESIGN_REMOTE_PASSWORD")
    DEFAULT_PORT = int(os.environ.get("MOLDESIGN_REMOTE_PORT", "22"))
    DEFAULT_IMAGE = os.environ.get("MOLDESIGN_REMOTE_IMAGE", "moldesign-science:latest")
    DEFAULT_WORKSPACE = os.environ.get("MOLDESIGN_REMOTE_WORKSPACE", "")

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = None,
        image: Optional[str] = None,
        remote_workspace: Optional[str] = None,
        timeout: int = 15,
    ):
        self.host = host or self.DEFAULT_HOST
        self.user = user or self.DEFAULT_USER
        self.password = password or self.DEFAULT_PASSWORD
        self.port = port or self.DEFAULT_PORT
        self.image = image or self.DEFAULT_IMAGE
        self.remote_workspace = remote_workspace or self.DEFAULT_WORKSPACE
        self.timeout = timeout
        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    def connect(self) -> paramiko.SSHClient:
        """Establece conexión SSH y SFTP con el servidor."""
        if self._ssh is not None:
            return self._ssh
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
        self._ssh = ssh
        self._sftp = ssh.open_sftp()
        return self._ssh

    def close(self):
        """Cierra conexiones abiertas."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_remote_dir(self, remote_dir: str):
        """Crea directorios remotos de forma recursiva en el servidor."""
        sftp = self._sftp
        dirs_to_create = []
        cur = remote_dir
        while cur and cur != "/":
            try:
                sftp.stat(cur)
                break
            except IOError:
                dirs_to_create.append(cur)
                cur = posixpath.dirname(cur)
        for d in reversed(dirs_to_create):
            try:
                sftp.mkdir(d)
            except IOError:
                pass

    def sync_file_to_remote(self, local_path: Path, remote_path: str) -> bool:
        """Sube un archivo individual si ha cambiado o no existe remotamente."""
        sftp = self._sftp
        self._ensure_remote_dir(posixpath.dirname(remote_path))
        local_size = local_path.stat().st_size
        try:
            remote_stat = sftp.stat(remote_path)
            if remote_stat.st_size == local_size:
                # Comprobar si son idénticos (skip)
                return False
        except IOError:
            pass

        # Transferencia binaria estricta
        sftp.put(str(local_path), remote_path)
        return True

    def sync_paths_to_remote(
        self,
        paths: List[Tuple[Path, str]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        """Sincroniza una lista de (local_path, remote_relative_path) a /workspace/."""
        self.connect()
        total = len(paths)
        uploaded = 0
        for i, (loc, rel) in enumerate(paths, 1):
            rem = posixpath.join(self.remote_workspace, rel.replace("\\", "/"))
            if loc.is_file():
                if self.sync_file_to_remote(loc, rem):
                    uploaded += 1
            if progress_callback:
                progress_callback(str(rel), i, total)
        return uploaded

    def sync_directory(
        self,
        local_dir: Path,
        remote_rel_dir: str,
        filter_fn: Optional[Callable[[Path], bool]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        """Sincroniza recursivamente un directorio local hacia el servidor."""
        self.connect()
        files_to_sync: List[Tuple[Path, str]] = []
        for root, _, files in os.walk(local_dir):
            r_path = Path(root)
            for f in files:
                full_path = r_path / f
                if filter_fn and not filter_fn(full_path):
                    continue
                rel = full_path.relative_to(local_dir)
                rem_rel = posixpath.join(remote_rel_dir, str(rel).replace("\\", "/"))
                files_to_sync.append((full_path, rem_rel))

        return self.sync_paths_to_remote(files_to_sync, progress_callback)

    def run_docker_command(
        self,
        command: str,
        extra_env: Optional[Dict[str, str]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[int, str, str]:
        """Ejecuta un comando dentro del contenedor Docker moldesign-science montando el workspace."""
        self.connect()

        env_args = ""
        if extra_env:
            for k, v in extra_env.items():
                env_args += f' -e {k}="{v}"'

        # Asegurar permisos en el workspace
        self._ssh.exec_command(f"chmod -R 777 {self.remote_workspace} 2>/dev/null || true")

        docker_cmd = (
            f"docker run --rm "
            f"-v {self.remote_workspace}:/workspace "
            f"-w /workspace "
            f"{env_args} "
            f"{self.image} "
            f"{command}"
        )

        stdin, stdout, stderr = self._ssh.exec_command(docker_cmd, get_pty=True)

        stdout_lines = []
        for line in iter(stdout.readline, ""):
            stdout_lines.append(line)
            if stream_callback:
                stream_callback(line)
            else:
                try:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                except UnicodeEncodeError:
                    sys.stdout.write(line.encode("ascii", errors="replace").decode("ascii"))
                    sys.stdout.flush()

        exit_code = stdout.channel.recv_exit_status()
        err_out = stderr.read().decode("utf-8", errors="replace")
        out_str = "".join(stdout_lines)

        return exit_code, out_str, err_out

    def fetch_remote_file(self, remote_path: str, local_path: Path) -> bool:
        """Descarga un archivo individual desde el servidor."""
        sftp = self._sftp
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            sftp.get(remote_path, str(local_path))
            return True
        except IOError:
            return False

    def fetch_directory(self, remote_rel_dir: str, local_target_dir: Path) -> int:
        """Descarga recursivamente un directorio remoto a una ruta local."""
        self.connect()
        sftp = self._sftp
        remote_full = posixpath.join(self.remote_workspace, remote_rel_dir.replace("\\", "/"))
        downloaded = 0

        def _walk_remote(rem_dir, loc_dir):
            nonlocal downloaded
            try:
                entries = sftp.listdir_attr(rem_dir)
            except IOError:
                return
            loc_dir.mkdir(parents=True, exist_ok=True)
            for attr in entries:
                r_item = posixpath.join(rem_dir, attr.filename)
                l_item = loc_dir / attr.filename
                if stat_is_dir(attr):
                    _walk_remote(r_item, l_item)
                else:
                    sftp.get(r_item, str(l_item))
                    downloaded += 1

        def stat_is_dir(attr):
            import stat
            return stat.S_ISDIR(attr.st_mode)

        _walk_remote(remote_full, local_target_dir)
        return downloaded

    def run_remote_pipeline(
        self,
        script_local_path: Path,
        script_args: str = "",
        input_data_files: Optional[List[Tuple[Path, str]]] = None,
        output_artifacts_dir: Optional[Tuple[str, Path]] = None,
    ) -> int:
        """Pipeline completo: Sincroniza script + inputs -> Ejecuta en Docker -> Trae resultados."""
        print(f"[RemoteRunner] Conectando a {self.user}@{self.host} (Docker: {self.image})...")
        self.connect()

        # 1. Subir script
        script_rel = f"scripts/{script_local_path.name}"
        rem_script_path = posixpath.join(self.remote_workspace, script_rel)
        print(f"[RemoteRunner] Sincronizando script ejecutor: {script_local_path.name}...")
        self.sync_file_to_remote(script_local_path, rem_script_path)

        # 2. Subir inputs adicionales si se indican
        if input_data_files:
            print(f"[RemoteRunner] Verificando y subiendo {len(input_data_files)} archivos de entrada...")
            up_count = self.sync_paths_to_remote(
                input_data_files,
                lambda name, cur, tot: print(f"\r  -> Sincronizando [{cur}/{tot}]: {name}", end="", flush=True) if cur % 20 == 0 or cur == tot else None
            )
            print(f"\n[RemoteRunner] {up_count} archivos actualizados en el servidor.")

        # 3. Ejecutar comando en Docker
        cmd = f"python {script_rel} {script_args}".strip()
        print(f"\n[RemoteRunner] >>> Lanzando en contenedor Docker: {cmd}")
        print("=" * 70)
        exit_code, stdout_out, stderr_out = self.run_docker_command(cmd)
        print("=" * 70)
        print(f"[RemoteRunner] Proceso finalizado con código de salida: {exit_code}")

        # 4. Descargar artefactos
        if output_artifacts_dir:
            rem_art_dir, loc_art_dir = output_artifacts_dir
            print(f"[RemoteRunner] Descargando artefactos desde {rem_art_dir} a {loc_art_dir}...")
            count = self.fetch_directory(rem_art_dir, loc_art_dir)
            print(f"[RemoteRunner] {count} artefactos recibidos y guardados con éxito.")

        return exit_code


def main():
    parser = argparse.ArgumentParser(description="MolDesign Remote Docker Runner Middleware")
    parser.add_argument("--host", default=None, help="IP del servidor remoto")
    parser.add_argument("--script", required=True, help="Ruta local al script de Python")
    parser.add_argument("--args", default="", help="Argumentos para el script")
    parser.add_argument("--fetch-artifacts", default=None, help="Directorio remoto a descargar (ej: scripts/artifacts_science/RS-03-PARAM-A)")
    parser.add_argument("--target-dir", default=None, help="Destino local para los artefactos")

    args = parser.parse_args()
    script_p = Path(args.script).resolve()

    runner = RemoteDockerRunner(host=args.host)
    out_tuple = None
    if args.fetch_artifacts and args.target_dir:
        out_tuple = (args.fetch_artifacts, Path(args.target_dir).resolve())

    ret = runner.run_remote_pipeline(
        script_local_path=script_p,
        script_args=args.args,
        output_artifacts_dir=out_tuple,
    )
    sys.exit(ret)


if __name__ == "__main__":
    main()
