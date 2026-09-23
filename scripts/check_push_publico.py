#!/usr/bin/env python3
r"""Guarda de publicación: ningún push lleva al remoto material retenido.

# Qué vigila

El repositorio público (`github.com/srcacahuate619/moldesign-app`) empieza en
un commit huérfano porque el historial de desarrollo contiene manuscritos sin
enviar, el deck y registros internos. La vía para publicar es replicar los
commits sobre la rama `publico`; la rama de desarrollo NO se empuja.

Esa regla vivía sólo en la memoria de los agentes, y el 2026-09-21 se rompió:
`codex/release-hygiene` y el tag `v1.0.1` llegaron al remoto con las 56 rutas
retenidas y con la contraseña del servidor en tres commits del historial.

Dos comprobaciones por cada ref que se empuja:

    P1  el HISTORIAL del commit no toca ninguna ruta de retenidos_del_publico.txt
        (no basta con la punta: `git rm` no borra del historial)
    P2  los commits que el remoto todavía no tiene no AÑADEN una credencial
        literal (valor por defecto de environ.get, clave privada, token).
        Las muestras falsas de las pruebas se declaran por su SHA-256 en
        credenciales_de_prueba.txt; nunca por su valor.

Borrar una ref remota siempre se permite: es la vía de reparación.

# Por qué lleva autotest

Porque un guardián que no demuestra que ve no sirve (AGENTS.md, restricción 2).
Antes de mirar el push, el script monta un repositorio temporal con un
historial limpio y otro sucio, y aborta si no distingue los dos; cada detector
de P2 se prueba contra muestras que debe y que no debe marcar; y, si las ramas
existen, `publico` tiene que pasar y `codex/release-hygiene` tiene que caer.

Las muestras de credenciales se construyen concatenando trozos, para que este
mismo archivo no dispare P2 cuando se publique.

# Uso

    python scripts/check_push_publico.py --instalar     # escribe .git/hooks/pre-push
    python scripts/check_push_publico.py --autotest     # sólo el autotest
    python scripts/check_push_publico.py --ref <ref>    # ¿se podría empujar <ref>?

El hook llama a este archivo por ruta absoluta, así que también protege los
worktrees cuya rama no trae el script (por ejemplo, los que salen de `publico`).

Exit code: 0 = se puede empujar, 1 = bloqueado.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover - un worktree puede no traer el ayudante
    def consola_utf8() -> None:
        for _flujo in (sys.stdout, sys.stderr):
            _reconfigurar = getattr(_flujo, "reconfigure", None)
            if _reconfigurar is not None:
                try:
                    _reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
LISTA = Path(__file__).resolve().parent / "retenidos_del_publico.txt"
CERO = "0" * 40
MARCA_DEL_HOOK = "Instalado por scripts/check_push_publico.py --instalar"

#: Detectores de P2. Cada uno tiene muestras en `_autotest_detectores`.
CREDENCIALES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("valor por defecto de una credencial en environ.get", re.compile(
        r"""environ\.get\(\s*["'][A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)"""
        r"""[A-Z0-9_]*["']\s*,\s*["'][^"']+["']""")),
    ("clave privada", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("token de GitHub", re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("token de Hugging Face", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("clave de API sk-", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}")),
    ("clave de NVIDIA", re.compile(r"\bnvapi-[A-Za-z0-9_-]{20,}")),
)


class GuardaCiega(SystemExit):
    """El autotest falló: la guarda no distingue lo que debe distinguir."""


def leer_retenidos(lista: Path = LISTA) -> list[str]:
    if not lista.is_file():
        raise GuardaCiega(f"✗ falta {lista}: sin la lista, la guarda no ve nada")
    rutas = [
        linea.strip()
        for linea in lista.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]
    if not rutas:
        raise GuardaCiega(f"✗ {lista} está vacía: sin rutas, la guarda no ve nada")
    return rutas


def git(*args: str, cwd: Path) -> str:
    resultado = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=False,
        text=True, encoding="utf-8", errors="replace",
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}…: {resultado.stderr.strip()}")
    return resultado.stdout


# ── P1: el historial no toca rutas retenidas ─────────────────────────────

def p1_historial_con_retenidos(sha: str, rutas: list[str], cwd: Path) -> list[str]:
    """Un «<commit> <ruta>» por cada commit del historial de `sha` que toca una ruta retenida."""
    salida = git("log", "--format=COMMIT %h", "--name-only", sha, "--", *rutas, cwd=cwd)
    hallazgos: list[str] = []
    commit = None
    for linea in salida.splitlines():
        if linea.startswith("COMMIT "):
            commit = linea[len("COMMIT "):]
        elif linea.strip() and commit:
            hallazgos.append(f"{commit} {linea.strip()}")
    return hallazgos


# ── P2: los commits nuevos no añaden credenciales ────────────────────────

MUESTRAS_FALSAS = Path(__file__).resolve().parent / "credenciales_de_prueba.txt"


def leer_muestras_falsas(lista: Path = MUESTRAS_FALSAS) -> frozenset[str]:
    """SHA-256 de las muestras falsas declaradas. Sin archivo, ninguna excepción."""
    if not lista.is_file():
        return frozenset()
    hashes = set()
    for linea in lista.read_text(encoding="utf-8").splitlines():
        campo = linea.split("#", 1)[0].split()
        if campo:
            if not re.fullmatch(r"[0-9a-f]{64}", campo[0]):
                raise GuardaCiega(f"✗ {lista.name}: «{campo[0][:20]}…» no es un SHA-256")
            hashes.add(campo[0])
    return frozenset(hashes)


def credenciales_en(texto: str, ignorar: frozenset[str] = frozenset()) -> list[str]:
    """Detectores que casan en `texto`, salvo coincidencias cuyo SHA-256 esté en `ignorar`."""
    import hashlib
    return [
        nombre for nombre, patron in CREDENCIALES
        if any(hashlib.sha256(m.group(0).encode("utf-8")).hexdigest() not in ignorar
               for m in patron.finditer(texto))
    ]


def p2_credenciales_nuevas(sha: str, cwd: Path, remoto: str | None) -> list[str]:
    """Un «<commit> <archivo>: <detector>» por línea añadida con una credencial.

    Sólo mira los commits que el remoto todavía no tiene. Nunca imprime el valor.
    """
    excluir = f"--remotes={remoto}" if remoto else "--remotes"
    salida = git(
        "log", "-p", "--no-color", "--no-ext-diff", "--unified=0",
        "--format=COMMIT %h", sha, "--not", excluir, cwd=cwd,
    )
    hallazgos: list[str] = []
    commit = archivo = None
    falsas = leer_muestras_falsas()
    for linea in salida.splitlines():
        if linea.startswith("COMMIT "):
            commit = linea[len("COMMIT "):]
        elif linea.startswith("+++ "):
            archivo = linea[len("+++ b/"):] if linea.startswith("+++ b/") else linea[4:]
        elif linea.startswith("+"):
            for nombre in credenciales_en(linea[1:], falsas):
                hallazgos.append(f"{commit} {archivo}: {nombre}")
    return hallazgos


# ── Decisión sobre un push ───────────────────────────────────────────────

def revisar_push(lineas: list[str], remoto: str | None, cwd: Path, rutas: list[str]) -> list[str]:
    """Lee las líneas que git pasa a pre-push y devuelve los motivos de bloqueo."""
    problemas: list[str] = []
    for linea in lineas:
        partes = linea.split()
        if len(partes) != 4:
            continue
        ref_local, sha_local, ref_remota, _ = partes
        if sha_local == CERO:
            continue  # borrar una ref remota es la vía de reparación
        p1 = p1_historial_con_retenidos(sha_local, rutas, cwd)
        if p1:
            problemas.append(
                f"{ref_local} → {ref_remota}: su historial toca {len(p1)} vez/veces "
                f"rutas retenidas (primera: {p1[-1]})"
            )
            continue  # con P1 roto no hace falta leer diffs enormes
        for hallazgo in p2_credenciales_nuevas(sha_local, cwd, remoto):
            problemas.append(f"{ref_local} → {ref_remota}: {hallazgo}")
    return problemas


# ── Autotest ─────────────────────────────────────────────────────────────

def _autotest_detectores() -> None:
    debe_marcar = {
        "valor por defecto de una credencial en environ.get":
            "PWD = os.environ" + '.get("MI_REMOTE_PASSWORD", "hunter2")',
        "clave privada": "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
        "token de GitHub": "ghp_" + "a1B2" * 9,
        "token de Hugging Face": "hf_" + "Zx9" * 11,
        "clave de API sk-": "sk-" + "ant-" + "q7" * 20,
        "clave de NVIDIA": "nvapi-" + "k3" * 15,
    }
    no_debe_marcar = (
        'PWD = os.environ.get("MOLDESIGN_REMOTE_PASSWORD")',
        'HOST = os.environ.get("MOLDESIGN_REMOTE_HOST", "localhost")',
        r'r"\b(sk-ant-[A-Za-z0-9]{2,}-|sk-proj-|sk-|gsk_|AIza|ghp_|xoxb-)[A-Za-z0-9\-_]{8,}"',
        "-----BEGIN PUBLIC KEY-----",
        "token = obtener_token()",
    )
    for esperado, muestra in debe_marcar.items():
        if esperado not in credenciales_en(muestra):
            raise GuardaCiega(f"✗ autotest: «{esperado}» no marca su muestra positiva")
    for muestra in no_debe_marcar:
        if credenciales_en(muestra):
            raise GuardaCiega(f"✗ autotest: falso positivo sobre {muestra!r}")

    # Una muestra falsa declarada por su hash pasa; la misma forma sin declarar
    # sigue cayendo. Si la excepción tapara todo lo que se parece, no serviría.
    import hashlib
    declarada = "sk-" + "Zq8" * 12
    otra = "sk-" + "Wm4" * 12
    ignorar = frozenset({hashlib.sha256(declarada.encode("utf-8")).hexdigest()})
    if credenciales_en(f"clave {declarada} en un test", ignorar):
        raise GuardaCiega("✗ autotest: una muestra falsa declarada sigue bloqueando")
    if not credenciales_en(f"clave {otra} en un test", ignorar):
        raise GuardaCiega("✗ autotest: la excepción deja pasar una cadena no declarada")
    if not credenciales_en(f"{declarada} y {otra}", ignorar):
        raise GuardaCiega("✗ autotest: una declarada en la misma línea tapa a otra que no lo está")


def _autotest_git(rutas: list[str]) -> None:
    with tempfile.TemporaryDirectory(prefix="guarda-push-") as tmp:
        repo = Path(tmp)

        def g(*args: str) -> str:
            return git(*args, cwd=repo)

        def commit(mensaje: str) -> str:
            g("add", "-A")
            g("commit", "-q", "-m", mensaje)
            return g("rev-parse", "HEAD").strip()

        g("init", "-q")
        g("config", "user.name", "autotest")
        g("config", "user.email", "autotest@invalid")
        (repo / "LEEME.md").write_text("limpio\n", encoding="utf-8")
        limpio = commit("limpio")

        retenido = repo / rutas[0]
        retenido.parent.mkdir(parents=True, exist_ok=True)
        retenido.write_text("manuscrito\n", encoding="utf-8")
        commit("entra un retenido")
        g("rm", "-q", rutas[0])
        sucio = commit("sale de la punta, no del historial")

        g("checkout", "-q", "-b", "otra", limpio)
        (repo / "runner.py").write_text(
            "PWD = os.environ" + '.get("X_PASSWORD", "hunter2")\n', encoding="utf-8")
        con_credencial = commit("una credencial")

        if p1_historial_con_retenidos(limpio, rutas, repo):
            raise GuardaCiega("✗ autotest: P1 marca un historial limpio")
        if not p1_historial_con_retenidos(sucio, rutas, repo):
            raise GuardaCiega("✗ autotest: P1 no ve un retenido que salió de la punta")
        if p2_credenciales_nuevas(limpio, repo, None):
            raise GuardaCiega("✗ autotest: P2 marca un commit limpio")
        if not p2_credenciales_nuevas(con_credencial, repo, None):
            raise GuardaCiega("✗ autotest: P2 no ve una credencial añadida")

        borrar = [f"(delete) {CERO} refs/heads/x {sucio}"]
        empujar = [f"refs/heads/x {sucio} refs/heads/x {CERO}"]
        if revisar_push(borrar, None, repo, rutas):
            raise GuardaCiega("✗ autotest: bloquea el borrado de una ref remota")
        if not revisar_push(empujar, None, repo, rutas):
            raise GuardaCiega("✗ autotest: deja pasar un push con retenidos")


def _existe(ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "-q", ref + "^{commit}"],
        cwd=RAIZ, capture_output=True, check=False,
    ).returncode == 0


def _autotest_en_vivo(rutas: list[str]) -> None:
    for ref, debe_caer in (("publico", False), ("codex/release-hygiene", True)):
        if not _existe(ref):
            print(f"  -  {ref}: no existe en este clon; salto la muestra real")
            continue
        cae = bool(p1_historial_con_retenidos(ref, rutas, RAIZ))
        if cae != debe_caer:
            estado = "cae" if cae else "pasa"
            raise GuardaCiega(f"✗ autotest: la rama real {ref} {estado} y no debería")
        print(f"  ✓  {ref}: {'cae' if cae else 'pasa'}, como debe")


def autotest(rutas: list[str]) -> None:
    _autotest_detectores()
    _autotest_git(rutas)
    _autotest_en_vivo(rutas)
    print(f"  ✓  autotest: {len(CREDENCIALES)} detectores y P1 sobre un historial sucio")


# ── Instalación del hook ─────────────────────────────────────────────────

def instalar() -> int:
    comun = Path(git("rev-parse", "--git-common-dir", cwd=RAIZ).strip())
    if not comun.is_absolute():
        comun = (RAIZ / comun).resolve()
    hook = comun / "hooks" / "pre-push"
    if hook.exists() and MARCA_DEL_HOOK not in hook.read_text(encoding="utf-8", errors="replace"):
        print(f"✗ ya hay un pre-push ajeno en {hook}; no lo sobrescribo")
        return 1
    python = Path(sys.executable).as_posix()
    script = Path(__file__).resolve().as_posix()
    hook.write_text(
        "#!/bin/sh\n"
        f"# {MARCA_DEL_HOOK}. No editar a mano.\n"
        f'exec "{python}" "{script}" --hook "$@"\n',
        encoding="utf-8", newline="\n",
    )
    print(f"✓ hook instalado en {hook}")
    return 0


# ── Entrada ──────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--hook", nargs="*", metavar="ARG", help="lo invoca git como pre-push")
    modo.add_argument("--autotest", action="store_true")
    modo.add_argument("--ref", action="append", help="comprueba una ref sin empujar")
    modo.add_argument("--instalar", action="store_true")
    args = parser.parse_args()

    if args.instalar:
        return instalar()

    rutas = leer_retenidos()
    print(f"Guarda de publicación: {len(rutas)} rutas retenidas")
    autotest(rutas)
    if args.autotest:
        return 0

    cwd = Path.cwd()
    if args.hook is not None:
        remoto = args.hook[0] if args.hook else None
        lineas = sys.stdin.read().splitlines()
    else:
        remoto = "origin"
        lineas = [f"{ref} {git('rev-parse', ref, cwd=cwd).strip()} {ref} {CERO}" for ref in args.ref]

    problemas = revisar_push(lineas, remoto, cwd, rutas)
    if not problemas:
        print("✓ nada retenido ni credenciales nuevas: se puede empujar")
        return 0
    print("✗ PUSH BLOQUEADO")
    for problema in problemas:
        print(f"  - {problema}")
    print(
        "\nLa rama de desarrollo no se empuja. Se publica replicando commits sobre\n"
        "`publico` en un worktree (git cherry-pick --empty=drop <base>..<rama>)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
