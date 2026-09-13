"""
core/exceptions.py

Jerarquía de excepciones custom del sistema.

Por qué excepciones custom y no usar las de Python directamente:

1. Semántica clara: `raise InvalidSMILES("CCX")` dice exactamente qué
   pasó. `raise ValueError("invalid smiles: CCX")` requiere leer el
   mensaje para entender el contexto.

2. Manejo centralizado: en api/main.py registramos exception handlers
   que convierten cada tipo de excepción en el HTTP status code correcto.
   Sin esta jerarquía, tendrías que capturar ValueError, RuntimeError,
   FileNotFoundError, etc., y adivinar cuál es un 400 y cuál un 500.

3. Logging automático: el exception handler puede loguear con el nivel
   correcto según el tipo — un InvalidSMILES es un WARNING (el usuario
   mandó algo malo), un DatabaseConnectionError es un ERROR crítico.

Estructura de la jerarquía:

    MolDesignError                     ← base de todo
    ├── ChemistryError                 ← errores del pipeline químico
    │   ├── InvalidSMILES
    │   ├── ConformerGenerationError
    │   └── PropertyCalculationError
    ├── DockingError                   ← errores de AutoDock Vina
    │   ├── DockingFailed
    │   ├── VinaExecutableNotFound
    │   └── ProteinPreparationError
    ├── ScoringError                   ← errores del motor de scoring
    ├── DatabaseError                  ← errores de SQLite
    │   ├── DatabaseConnectionError
    │   └── DatabaseQueryError
    ├── LocalStorageError              ← errores de disco local
    │   └── LocalFileNotFound
    ├── AIServiceError                 ← errores de Claude API
    ├── BlockchainError                ← errores de Solana
    │   └── TransactionFailedError
    └── AuthError                      ← errores de autenticación
        ├── InvalidCredentials
        ├── TokenExpired
        └── InsufficientPermissions

Mapeo a HTTP status codes (definido en api/main.py):
    InvalidSMILES               → 422 Unprocessable Entity
    ConformerGenerationError    → 422 Unprocessable Entity
    DockingFailed               → 500 Internal Server Error
    VinaExecutableNotFound      → 503 Service Unavailable
    ProteinPreparationError     → 500 Internal Server Error
    ScoringError                → 500 Internal Server Error
    DatabaseConnectionError     → 503 Service Unavailable
    DatabaseQueryError          → 500 Internal Server Error
    LocalFileNotFound           → 404 Not Found
    AIServiceError              → 502 Bad Gateway
    BlockchainError             → 502 Bad Gateway
    InvalidCredentials          → 401 Unauthorized
    TokenExpired                → 401 Unauthorized
    InsufficientPermissions     → 403 Forbidden
"""

from __future__ import annotations


# ── Base ──────────────────────────────────────────────────────────────────────

class MolDesignError(Exception):
    """
    Base de todas las excepciones del sistema.

    Todos los exception handlers de FastAPI capturan esta clase
    como fallback si no hay un handler más específico registrado.

    Atributos:
        message:   descripción del error legible por humanos
        detail:    información técnica adicional (stack traces, valores)
        http_code: sugerencia del HTTP status code (el handler decide)
    """

    http_code: int = 500   # cada subclase sobreescribe este valor

    def __init__(
        self,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> dict[str, str | int | None]:
        """
        Serializa la excepción para incluirla en la respuesta HTTP.

        Uso en el exception handler de main.py:
            @app.exception_handler(MolDesignError)
            async def mol_design_error_handler(request, exc):
                return JSONResponse(
                    status_code=exc.http_code,
                    content=exc.to_dict(),
                )
        """
        return {
            "error":   type(self).__name__,
            "message": self.message,
            "detail":  self.detail,
        }

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"message={self.message!r}, "
            f"detail={self.detail!r})"
        )


# ── Química ───────────────────────────────────────────────────────────────────

class ChemistryError(MolDesignError):
    """Base para errores del pipeline químico (RDKit)."""
    http_code = 422


class InvalidSMILES(ChemistryError):
    """
    El SMILES enviado por el usuario no es válido.

    Se lanza en chem/validator.py cuando RDKit no puede parsear
    el string o cuando falla la validación de valencia/aromaticidad.

    Ejemplo:
        raise InvalidSMILES(
            smiles="CCX",
            reason="átomo desconocido 'X' en posición 2"
        )
    """
    http_code = 422

    def __init__(
        self,
        smiles: str,
        reason: str,
        detail: str | None = None,
    ) -> None:
        self.smiles = smiles
        self.reason = reason
        message = f"SMILES inválido: '{smiles}' — {reason}"
        super().__init__(message=message, detail=detail)

    def to_dict(self) -> dict[str, str | int | None]:
        base = super().to_dict()
        base["smiles"] = self.smiles
        base["reason"] = self.reason
        return base


class ConformerGenerationError(ChemistryError):
    """
    RDKit no pudo generar una estructura 3D válida para la molécula.

    Ocurre con macrociclos, quiralidad compleja, o moléculas
    con restricciones geométricas que ETKDG no puede resolver.

    Ejemplo:
        raise ConformerGenerationError(
            smiles="C1CC2CCCC3CCCC1C23",
            attempts=3,
        )
    """
    http_code = 422

    def __init__(
        self,
        smiles: str,
        attempts: int,
        detail: str | None = None,
    ) -> None:
        self.smiles = smiles
        self.attempts = attempts
        message = (
            f"No se pudo generar confórmero 3D para '{smiles}' "
            f"después de {attempts} intento(s). "
            "La molécula puede tener restricciones geométricas "
            "que ETKDG no puede resolver."
        )
        super().__init__(message=message, detail=detail)


class PropertyCalculationError(ChemistryError):
    """
    Fallo inesperado calculando una propiedad fisicoquímica con RDKit.

    Distinto de InvalidSMILES: el SMILES es válido, pero RDKit
    lanza una excepción interna al calcular (ej. logP en moléculas
    con átomos exóticos sin parámetros de Crippen).
    """
    http_code = 500

    def __init__(
        self,
        property_name: str,
        smiles: str,
        detail: str | None = None,
    ) -> None:
        self.property_name = property_name
        self.smiles = smiles
        message = (
            f"Error calculando '{property_name}' "
            f"para la molécula '{smiles}'"
        )
        super().__init__(message=message, detail=detail)


# ── Docking ───────────────────────────────────────────────────────────────────

class DockingError(MolDesignError):
    """Base para errores del pipeline de docking (AutoDock Vina)."""
    http_code = 500


class DockingFailed(DockingError):
    """
    AutoDock Vina terminó con error o retornó resultados vacíos.

    Puede ocurrir si la molécula no cabe en el grid box,
    si el archivo .pdbqt del ligando está malformado,
    o si Vina no encontró ninguna pose válida.

    Ejemplo:
        raise DockingFailed(
            molecule_id="abc-123",
            target_pdb_id="7E2Y",
            vina_exit_code=1,
            detail=stderr_output,
        )
    """
    http_code = 500

    def __init__(
        self,
        molecule_id: str,
        target_pdb_id: str,
        vina_exit_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.molecule_id = molecule_id
        self.target_pdb_id = target_pdb_id
        self.vina_exit_code = vina_exit_code
        message = (
            f"Docking falló para molécula '{molecule_id}' "
            f"contra target '{target_pdb_id}'"
        )
        if vina_exit_code is not None:
            message += f" (Vina exit code: {vina_exit_code})"
        super().__init__(message=message, detail=detail)

    def to_dict(self) -> dict[str, str | int | None]:
        base = super().to_dict()
        base["molecule_id"]   = self.molecule_id
        base["target_pdb_id"] = self.target_pdb_id
        base["vina_exit_code"] = self.vina_exit_code
        return base


class VinaExecutableNotFound(DockingError):
    """
    El ejecutable de AutoDock Vina no existe en la ruta configurada.

    Se lanza al arrancar la app si vina_executable_path no existe.
    Es un 503 porque el servicio de docking no está disponible,
    no porque el usuario hizo algo mal.
    """
    http_code = 503

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            message=f"AutoDock Vina no encontrado en '{path}'",
            detail=(
                "Verifica que Vina esté instalado y que "
                "VINA_EXECUTABLE_PATH en .env sea correcto. "
                "En Docker, el Dockerfile debe instalar Vina."
            ),
        )


class ProteinPreparationError(DockingError):
    """
    Fallo preparando el archivo de proteína para Vina.

    Ocurre en services/docking/preparer.py cuando la estructura
    del PDB tiene problemas: residuos faltantes, cadenas múltiples
    sin especificar, o fallo en la protonación.
    """
    http_code = 500

    def __init__(
        self,
        pdb_id: str,
        step: str,
        detail: str | None = None,
    ) -> None:
        self.pdb_id = pdb_id
        self.step = step
        message = (
            f"Error preparando proteína '{pdb_id}' "
            f"en el paso '{step}'"
        )
        super().__init__(message=message, detail=detail)


# ── Scoring ───────────────────────────────────────────────────────────────────

class ScoringError(MolDesignError):
    """
    Fallo en el cálculo del score compuesto.

    Generalmente indica que los datos de entrada están incompletos
    (affinity o propiedades son None cuando no deberían serlo)
    o que los pesos no suman 1.0 (debería estar bloqueado por config.py).
    """
    http_code = 500

    def __init__(
        self,
        molecule_id: str,
        missing_component: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.molecule_id = molecule_id
        self.missing_component = missing_component
        message = f"Error calculando score para molécula '{molecule_id}'"
        if missing_component:
            message += f": componente faltante '{missing_component}'"
        super().__init__(message=message, detail=detail)


# ── Base de datos ─────────────────────────────────────────────────────────────

class DatabaseError(MolDesignError):
    """Base para errores de SQLite y de sus sesiones SQLAlchemy."""
    http_code = 500


class DatabaseConnectionError(DatabaseError):
    """
    No se puede abrir la base SQLite.

    503 porque el servicio de DB no está disponible,
    no porque la lógica de negocio falló.
    """
    http_code = 503


class DatabaseQueryError(DatabaseError):
    """
    Una query SQL falló en tiempo de ejecución.

    Puede ser un constraint violation, un deadlock,
    o un error de tipado en la query.
    """
    http_code = 500


# ── Almacenamiento local ─────────────────────────────────────────────────────

class LocalStorageError(MolDesignError):
    """Base para errores del almacenamiento local en disco."""
    http_code = 500


class LocalFileNotFound(LocalStorageError):
    """
    Un archivo no existe en el directorio de datos local.

    404 porque es una entidad que no se encontró,
    equivalente a un registro que no existe en la DB.
    """
    http_code = 404

    def __init__(
        self,
        filename: str,
        detail: str | None = None,
    ) -> None:
        self.filename = filename
        super().__init__(
            message=f"Archivo '{filename}' no encontrado en el almacenamiento local",
            detail=detail,
        )


# ── Servicio de IA ────────────────────────────────────────────────────────────

class AIServiceError(MolDesignError):
    """
    Error llamando a la API de Claude.

    502 Bad Gateway porque el error viene de un servicio externo
    (Anthropic), no de nuestro código.
    El reporte IA es opcional — el sistema debe degradarse
    limpiamente si esta excepción ocurre.
    """
    http_code = 502

    def __init__(
        self,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            message="El servicio de generación de reportes no está disponible",
            detail=detail,
        )


# ── Blockchain ────────────────────────────────────────────────────────────────

class BlockchainError(MolDesignError):
    """Base para errores de Solana."""
    http_code = 502


class TransactionFailedError(BlockchainError):
    """
    La transacción en Solana falló o fue rechazada.

    Puede ocurrir por saldo insuficiente, red congestionada,
    o timeout esperando confirmación.
    """
    http_code = 502

    def __init__(
        self,
        smiles_hash: str,
        reason: str,
        detail: str | None = None,
    ) -> None:
        self.smiles_hash = smiles_hash
        self.reason = reason
        message = (
            f"Transacción blockchain falló para molécula '{smiles_hash[:8]}...': "
            f"{reason}"
        )
        super().__init__(message=message, detail=detail)


# ── Autenticación ─────────────────────────────────────────────────────────────

class AuthError(MolDesignError):
    """Base para errores de autenticación y autorización."""
    http_code = 401


class InvalidCredentials(AuthError):
    """
    Email o password incorrectos en el login.

    El mensaje genérico es intencional — no decir si el email
    existe o no para evitar user enumeration attacks.
    """
    http_code = 401

    def __init__(self) -> None:
        super().__init__(
            message="Credenciales inválidas",
            detail="Email o contraseña incorrectos",
        )


class TokenExpired(AuthError):
    """El JWT de acceso expiró. El cliente debe usar el refresh token."""
    http_code = 401

    def __init__(self) -> None:
        super().__init__(message="El token de acceso ha expirado")


class InsufficientPermissions(AuthError):
    """
    El usuario autenticado no tiene permiso para esta acción.
    Ej: intentar acceder a moléculas de otro usuario.
    """
    http_code = 403

    def __init__(
        self,
        action: str,
        resource: str,
    ) -> None:
        self.action = action
        self.resource = resource
        super().__init__(
            message=f"Sin permisos para '{action}' en '{resource}'",
        )


# ── Target ────────────────────────────────────────────────────────────────────

class SyntheticInfeasibilityError(ChemistryError):
    """
    La molécula tiene un SA Score > 7.0, lo que indica que no es
    sintetizable por métodos estándar de química medicinal.
    El pipeline se detiene porque continuar (docking, scoring) no
    tiene sentido práctico para una molécula que no se puede sintetizar.
    """
    http_code = 422

    def __init__(
        self,
        smiles: str,
        sa_score: float,
        detail: str | None = None,
    ) -> None:
        self.smiles = smiles
        self.sa_score = sa_score
        message = (
            f"Inviabilidad sintética: SA Score {sa_score:.2f} > 7.0 "
            f"para SMILES '{smiles[:40]}'. "
            "La síntesis de esta molécula no es viable por métodos estándar."
        )
        super().__init__(message=message, detail=detail)


class TargetNotFound(MolDesignError):
    """
    El target biológico solicitado no existe en la DB.
    Separado de DatabaseQueryError porque tiene semántica de negocio.
    """
    http_code = 404

    def __init__(self, pdb_id: str) -> None:
        self.pdb_id = pdb_id
        super().__init__(
            message=f"Target biologico '{pdb_id}' no encontrado",
            detail=(
                "Verifica que el PDB ID sea valido (4 caracteres alfanumericos). "
                "Usa GET /targets/ para ver los 19+ targets pre-cargados, o "
                "POST /targets/upload para agregar un receptor personalizado. "
                "Si el target existe en RCSB (https://www.rcsb.org), el sistema "
                "lo descargara automaticamente en el primer uso."
            ),
        )
