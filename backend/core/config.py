"""Configuración del runtime MolDesign Desktop."""
from functools import lru_cache
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_secret_key() -> str:
    """Persiste la secret_key local para no invalidar sesiones entre reinicios."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key and len(env_key) >= 32:
        return env_key

    key_dir = Path.home() / ".moldesign"
    key_file = key_dir / "secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()

    new_key = os.urandom(32).hex()
    key_dir.mkdir(parents=True, exist_ok=True)
    key_file.write_text(new_key, encoding="utf-8")
    return new_key


class Settings(BaseSettings):
    """
    Configuración global del runtime desktop: SQLite, almacenamiento local y
    dispatcher local. ``APP_MODE`` antiguo se acepta pero se normaliza a
    ``DESKTOP`` para que una variable de entorno residual no cambie el camino
    del pipeline en una instalación de escritorio.
    """

    model_config = SettingsConfigDict(
        # .env.desktop contains safe desktop defaults. A repository-local .env
        # may add development secrets (for example the devnet sponsor key), but
        # bundle_helper.py explicitly excludes every .env file from installers.
        env_file=(".env.desktop", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Modo de ejecución ────────────────────────────────────────────────────
    app_mode: Literal["DESKTOP"] = Field(
        default="DESKTOP",
        description="MolDesign Build es exclusivamente DESKTOP.",
    )

    # ── Aplicación ──────────────────────────────────────────────────────────
    environment: Literal["development", "production", "testing"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(
        default_factory=lambda: _resolve_secret_key(),
        min_length=32,
        description="Clave para firmar JWT, persistida en disco si no se provee.",
    )
    supabase_jwt_secret: str | None = None

    # ── Base de datos ────────────────────────────────────────────────────────
    # En DESKTOP se ignora database_url y se usa SQLite (ver db_factory.py)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./moldesign_local.db",
        description="Ignorado en modo DESKTOP — usa SQLite vía db_factory.py",
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, ge=5)
    db_echo_sql: bool = False

    # ── Directorio de datos local ────────────────────────────────────────────
    local_data_dir: str = Field(
        default_factory=lambda: str(Path.home() / "MolDesign" / "data"),
        description="Carpeta donde se guardan poses, PDFs y el SQLite en modo DESKTOP.",
    )

    # ── Estado efímero local ─────────────────────────────────────────────────
    # Nunca es fuente de verdad: se pierde al reiniciar y se puede recalcular.
    runtime_cache_docking_ttl: int = Field(default=86400, ge=60)
    runtime_cache_properties_ttl: int = Field(default=3600, ge=60)

    # El dispatcher local reemplaza por completo las colas remotas.

    # ── Docking (AutoDock Vina) ──────────────────────────────────────────────
    vina_executable_path: str = Field(
        default="tools/vina/vina.exe",
        description="Ruta al ejecutable de AutoDock Vina 1.2.7 nativo (FP64). Vina-GPU fue removido por divergencia FP32/FP64 (RMSD 0.3-1.5A).",
    )
    qvina2_executable_path: str = Field(
        default="qvina2",
        description="Ruta a QuickVina 2 (experimental). Si no existe, cae a Vina con exhaustiveness=4.",
    )
    docking_engine: str = Field(
        default="vina",
        description="Motor de docking: 'vina' (clasico) o 'qvina2' (experimental)",
    )
    meeko_prepare_receptor_path: str = "mk_prepare_receptor.py"
    meeko_prepare_ligand_path: str = "mk_prepare_ligand"
    meeko_export_path: str = "mk_export"
    meeko_default_altloc: str = "A"
    vina_exhaustiveness: int = Field(default=8, ge=1, le=128)  # 8 = sweet spot, >16 no mejora ranking
    vina_calibration_exhaustiveness: int = Field(default=32, ge=8, le=64)
    vina_num_poses: int = Field(default=5, ge=1, le=20)
    vina_seed: int = Field(default=42, ge=0)  # 42 = reproducible (cambio a 0 para random)
    vina_cpu: int = Field(default=0, ge=0)  # 0 = auto-detect cores
    docking_max_consistency_error_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    docking_allow_stdout_fallback: bool = False  # False = rigor científico: rechazar si el parsing falla
    vina_temp_dir: str = Field(
        default_factory=lambda: str((Path(tempfile.gettempdir()) / "vina").resolve())
    )

    default_target_pdb_id: str = "7E2Y"
    default_target_chain: str = "R"
    vina_center_x: float = 103.03
    vina_center_y: float = 114.79
    vina_center_z: float = 108.36
    vina_size_x: float = 25.0
    vina_size_y: float = 25.0
    vina_size_z: float = 25.0

    # ── Servicios externos opcionales ────────────────────────────────────────
    diffdock_api_url: str | None = None
    esmfold_api_url: str | None = Field(
        default="http://localhost:8100",
        description="En DESKTOP: sidecar ESMFold corriendo localmente.",
    )
    esmfold_desktop_port: int = Field(
        default=8100,
        description="Puerto del sidecar ESMFold en modo DESKTOP.",
    )
    colabfold_api_url: str | None = None
    peptide_refinement_enabled: bool = False  # Requiere OpenMM — desactivado en MVP
    esmfold_prior_weight: float = Field(default=0.7, ge=0.0, le=1.0)

    # ── ESMFold-Pro (RFdiffusion experimental, GPU requerida) ──────────────
    esmfold_pro_api_url: str | None = Field(
        default="http://localhost:8300",
        description="Sidecar ESMFold-Pro (RFdiffusion) en puerto 8300. Requiere GPU.",
    )
    esmfold_pro_desktop_port: int = Field(
        default=8300,
        description="Puerto del sidecar ESMFold-Pro en modo DESKTOP.",
    )

    # ── Rescoring (sidecar local en DESKTOP) ────────────────────────────────
    rescoring_url: str = Field(
        default="http://localhost:8001",
        description="En DESKTOP: sidecar de rescoring corriendo localmente.",
    )
    rescoring_api_key: str = Field(
        default="",
        description="API key del sidecar de rescoring local.",
    )

    # ── MolChat / LLM local (llama-server.exe sidecar) ─────────────────────
    # Migración v1.x: el wrapper `services/ai/local_llm.py` lanza el binario
    # oficial `llama-server.exe` (build de ggerganov/llama.cpp) como subproceso
    # HTTP en el puerto reservado 8400. Protocolo OpenAI-compatible.
    # Documentación: docs/33_MIGRATION_LLAMA_SERVER.md
    llama_server_executable_path: str = Field(
        default="tools/llama/llama-server.exe",
        description="Ruta al binario CPU portable de llama.cpp empaquetado en tools/llama/. Un build CUDA puede configurarse opcionalmente, pero no forma parte del runtime mínimo.",
    )
    llama_server_port: int = Field(
        default=8400,
        ge=1024,
        le=65535,
        description="Puerto del sidecar `llama-server.exe` en DESKTOP. 8400 por convención (siguiente libre tras 8001/8100/8300).",
    )

    # ── Pesos del score compuesto ────────────────────────────────────────────
    score_weight_affinity: float = Field(default=0.45, ge=0.0, le=1.0)
    score_weight_adme: float = Field(default=0.30, ge=0.0, le=1.0)
    score_weight_druglikeness: float = Field(default=0.25, ge=0.0, le=1.0)

    @field_validator("score_weight_druglikeness")
    @classmethod
    def weights_must_sum_to_one(cls, druglikeness: float, info) -> float:
        data = info.data
        affinity = data.get("score_weight_affinity", 0)
        adme = data.get("score_weight_adme", 0)
        total = round(affinity + adme + druglikeness, 10)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Los pesos del score deben sumar 1.0, pero suman {total:.4f}"
            )
        return druglikeness

    # ── IA ───────────────────────────────────────────────────────────────────
    provider_config_path: str = Field(
        default_factory=lambda: str(Path.home() / ".moldesign" / "provider_config.json"),
        description="Ruta al archivo JSON donde se persisten las API keys encriptadas.",
    )
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_tokens: int = Field(default=2000, ge=100, le=8192)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = "gpt-4o-mini"
    groq_api_key: str | None = Field(None, description="Clave gratuita de Groq (console.groq.com)")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_default_model: str = "llama-3.1-8b-instant"
    lmstudio_url: str = "http://localhost:1234"
    lmstudio_model: str = "local-model"

    # ── Auth ─────────────────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=43200, ge=5)  # 30 días en desktop
    jwt_refresh_token_expire_days: int = Field(default=365, ge=1)      # 1 año en desktop
    google_client_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_tenant_id: str | None = "common"

    # ── Validación de moléculas ──────────────────────────────────────────────
    strict_science_mode: bool = True
    strict_single_fragment_only: bool = True
    max_total_formal_charge_abs: int = Field(default=2, ge=0, le=10)
    max_atom_formal_charge_abs: int = Field(default=2, ge=0, le=6)
    # ── El tamaño de molécula ya NO se configura aquí ───────────────────
    #
    # Estos tres ajustes decidían qué moléculas entraban al producto:
    #
    #     mol_max_heavy_atoms      = 80     <- ERROR, detenía la corrida
    #     mol_max_molecular_weight = 800.0  <- aviso
    #     mol_min_molecular_weight = 100.0  <- aviso
    #
    # Ninguno de los tres números corresponde a un criterio publicado. El 800
    # no es frontera de nada y el 80 —el único que bloqueaba— no aparece en
    # ninguna regla de drug-likeness. Y estaban en `Settings`, es decir
    # presentados como parámetros ajustables, cuando lo que fijaban era el
    # alcance científico de la aplicación.
    #
    # Se sustituyen por las fronteras de la literatura —Rule of Five,
    # Beyond-Ro5 y el rango de átomos de Ghose— que viven en
    # `chem/regimenes.py` con su cita al lado, y NO como ajustes: cambiarlas es
    # cambiar de qué habla el producto.
    conformer_max_attempts: int = Field(default=3, ge=1, le=10)

    # ── CORS (modo DESKTOP: solo localhost) ──────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]

    # ── Comunidad (integración opcional, no participa del pipeline) ─────────
    community_api_url: str | None = Field(
        default=None,
        description="URL base opcional para compartir targets con una comunidad externa.",
    )

    # ── Blockchain (opcional en desktop) ────────────────────────────────────
    solana_rpc_url: str = "https://api.devnet.solana.com"

    # ── Integraciones dormidas ──────────────────────────────────────────────
    #
    # Tres routers describen capacidades que ESTA instalación no tiene:
    #
    #   /steam/*             verificación de compra vía Steam Web API. Canal de
    #                        distribución previsto para ~Q4 2026; sin
    #                        STEAM_WEB_API_KEY responde `verified: true` a
    #                        cualquiera que llame.
    #   /docking/diffdock/*  proxy HTTP a un servicio de DiffDock. El motor no
    #                        se instala ni se levanta: `diffdock_api_url` es
    #                        None por defecto.
    #   /docking/colabfold/* proxy HTTP a ColabFold. Igual, y además necesita
    #                        una base de datos MSA que no viaja en el
    #                        instalador.
    #
    # Estaban montados. `docs/37_INTEGRATION_POLICY.md` §Steam ya decía
    # «mantener desactivado hasta la decisión de lanzamiento Q4 2026» y el
    # inventario de `/evaluation/engines` ya declara DiffDock y ColabFold como
    # no disponibles, así que la interfaz los enseña apagados — pero la ruta
    # HTTP contestaba igual a quien la llamara directamente. En una máquina sin
    # red eso es un `httpx` con timeout de 300 s ocupando un hilo del pool, y en
    # el caso de Steam una respuesta afirmativa que nadie verificó.
    #
    # NO SE BORRA NADA. Los routers y sus servicios siguen enteros en el árbol:
    # las tres integraciones están en el plan del producto y volverán cuando
    # exista el motor detrás. Lo único que cambia es que hay que pedirlas.
    #
    #     MONTAR_ROUTERS_DORMIDOS=1
    #
    # `services/diffdock/`, `services/colabfold/` y `api/routers/steam.py` se
    # siguen importando en las pruebas, que es lo que impide que se pudran sin
    # que nadie se entere.
    montar_routers_dormidos: bool = Field(
        default=False,
        description=(
            "Monta /steam, /docking/diffdock y /docking/colabfold. Apagados por "
            "defecto: describen motores y servicios que esta instalación no trae."
        ),
    )

    # ── Propiedades helpers ──────────────────────────────────────────────────
    @field_validator("app_mode", mode="before")
    @classmethod
    def normalize_legacy_app_mode(cls, _value: object) -> str:
        """Evita que APP_MODE=CLOUD heredado active caminos ya retirados."""
        return "DESKTOP"

    @property
    def is_desktop(self) -> bool:
        return True

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton; installed builds receive secrets only through the environment."""
    return Settings()
