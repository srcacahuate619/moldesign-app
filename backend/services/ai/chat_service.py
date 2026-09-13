from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

from services.ai.providers.registry import get_provider_registry
from services.ai.conversation_state import Conversation, get_adaptive_params
from services.ai.intent_classifier import classify as classify_intent
from services.ai.intent_classifier import KNOWN as KNOWN_MOLECULES
from services.ai.intent_classifier import _find_name as _find_known_molecule_name
from services.ai.intent_classifier import Intent as _Intent
from utils.logger import get_logger

log = get_logger(__name__)

_KEEP_RECENT_MESSAGES = 10

def _sanitize_ascii(text: str) -> str:
    """Mantener el texto original en UTF-8 para preservar acentos y la eñe."""
    return text

# Adaptive context: se escala según n_ctx del modelo cargado.
# IMPORTANTE: este n_ctx DEBE coincidir con el que arranca el server en
# local_llm.py:546 (`-c`). Antes esto era 8192 (speed) / 32768 (reasoning),
# lo cual era incoherente con el server real (16k): en speed subutilitzaba,
# en reasoning dejaba pasar tokens que el server truncaba silenciosamente,
# rompiendo la validez del contexto que llegaba al modelo. Unificado a 16k.
def _get_adaptive_params(mode: str = "speed") -> tuple[int, int, int]:
    return get_adaptive_params(mode)

# Hallucination guard: keys que el LLM puede inventar y sus valores reales
# Los patterns EVITAN falsos positivos: rangos ("1.8/10"), reglas Lipinski ("< 500 Da"),
# y scores que no son total_score.
_VERIFIABLE_KEYS = [
    # Separador flexible (de|:|=|es|con) — captura "afinidad de -5.8",
    # "peso molecular de 151.16", "logP de 0.5", etc. Bug detectado en MT005.
    ("afinidad", "affinity_kcal", r'afinidad\s*(?:de|:|=|es|con)?\s*([-\d]+\.?\d*)\s*kcal'),
    ("score total", "total_score", r'(?:score\s*(?:total|general)|puntuacion)\s*(?:de|:|=|es|con)?\s*(\d{2,3})(?:\s*/\s*100)?'),
    ("peso molecular", "molecular_weight", r'(?:(?:peso molecular|masa molecular|MW)\s*(?:de|:|=|es|con)?\s*)(?:[^0-9]{0,40}?)(\d+\.?\d*)\s*(?:Da|g/mol)'),
    ("logp", "log_p", r'log\s*[pP]\s*(?:de|:|=|es|con)?\s*([-\d]+\.?\d*)'),
    ("tpsa", "tpsa", r'TPSA\s*(?:de|:|=|es|con)?\s*([\d]+\.?\d*)\s*(?:A|Å)'),
    ("h-bond donors", "hbd", r'H-?bond\s*[dD]onors?\s*(?:de|:|=|es|con)?\s*(\d+\.?\d*)'),
    ("h-bond acceptors", "hba", r'H-?bond\s*[aA]cceptors?\s*(?:de|:|=|es|con)?\s*(\d+\.?\d*)'),
    ("rotatable bonds", "rotatable_bonds", r'[rR]otatable\s*[bB]onds?\s*(?:de|:|=|es|con)?\s*(\d+\.?\d*)'),
    ("heavy atoms", "heavy_atoms", r'[hH]eavy\s*[aA]toms?\s*(?:de|:|=|es|con)?\s*(\d+\.?\d*)'),
    ("rings", "rings", r'(?:rings|anillos)\s*(?:de|:|=|es|con)?\s*(\d+\.?\d*)'),
]

# Fabrication guard: si la respuesta contiene UNO de estos marcadores de dato
# químico PERO el modelo NO ejecutó ninguna tool nativa en esta pasada,
# es una invención (el LLM solo puede saber estos valores via compute_properties,
# run_docking, pubchem_lookup, etc).
_FABRICATION_MARKERS = [
    # Separador flexible: acepta ':', '=', 'de', 'es', 'con' entre la keyword
    # y el número. Antes solo ':|=' falleaba para "masa molecular de 151 g/mol"
    # y "logP de 0.5" (bug detectado en MT005 del deep-replay).
    r'MW\s*(?::|=|de|es|con)?\s*\d+\.?\d*\s*(?:Da|g/mol)?',
    r'(?:peso|masa) molecular\s*(?::|=|de|es|con)?\s*\d+\.?\d*\s*(?:Da|g/mol)?',
    r'[lL]og[Pp]\s*(?::|=|de|es|con)?\s*[-\d]+\.?\d*',
    r'TPSA\s*(?::|=|de|es|con)?\s*[\d]+\.?\d*\s*(?:A|Å)?',
    r'afinidad\s*(?:de|:|=)?\s*[-\d]+\.?\d*\s*kcal',
    # Rangos de afinidad ("de -5.7 a -6.3 kcal/mol") — patrón suelto porque la
    # construcción puede ser "afinidad del paracetamol ... rango de -5.7 a -6.3 kcal".
    r'[-\d]+\.?\d*\s*(?:a|hasta)\s*[-\d]+\.?\d*\s*kcal',
    r'score\s*(?:total|general)\s*(?:de|:|=)?\s*\d{2,3}\s*/\s*100',
    r'H-?bond\s*[dD]onors?\s*(?::|=|de|es|con)?\s*\d+',
    r'H-?bond\s*[aA]cceptors?\s*(?::|=|de|es|con)?\s*\d+',
    r'[rR]otatable\s*[bB]onds?\s*(?::|=|de|es|con)?\s*\d+',
]


# ── Constantes de contexto adaptativo ───────────────────────────────

@dataclass
class FallbackInfo:
    warning: str = ""
    fallback_used: bool = False


class ChatService:
    """Estado de chat por cuenta.

    MOLCHAT-BE-004: `_conversations` y `_active_conv_id` eran atributos de
    **clase**, y `get_chat_service()` devuelve un singleton de proceso, así que
    todas las cuentas de la máquina compartían un único almacén y una única
    conversación activa. Ahora el estado es de instancia y la conversación
    activa se guarda **por cuenta**.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._active_by_user: dict[str, str] = {}

    def create_conversation(
        self,
        molecule_context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> Conversation:
        conv_id = str(uuid.uuid4())[:12]
        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            created_at=time.time(),
            updated_at=time.time(),
            molecule_context=molecule_context,
        )
        # MOLCHAT-BE-008: primero el disco. Si la base falla, la conversación
        # no llega a existir en memoria: un id que el investigador puede usar
        # pero que no sobrevive a un reinicio es peor que un error.
        from services.ai.memory_store import PersistenciaFallida, save_conversation

        try:
            save_conversation(
                conv_id=conv.id, messages=conv.messages,
                summary=conv.summary, molecule_context=conv.molecule_context,
                created_at=conv.created_at, user_id=user_id,
            )
        except PersistenciaFallida as exc:
            log.error("conversation_not_persisted", id=conv_id, error=str(exc)[:200])
            raise

        self._conversations[conv_id] = conv
        if user_id:
            self._active_by_user[user_id] = conv_id
        log.info("conversation_created", id=conv_id)
        try:
            from services.ai.limbic_system import on_conversation_opened
            on_conversation_opened()
        except ImportError:
            pass
        return conv

    def _es_de(self, conv: Conversation | None, user_id: str | None) -> bool:
        """Una conversación sin dueño no es de cualquiera (D-07)."""
        if conv is None:
            return False
        return conv.user_id == user_id

    def get_conversation(
        self,
        conv_id: str | None = None,
        user_id: str | None = None,
    ) -> Conversation | None:
        if conv_id:
            conv = self._conversations.get(conv_id)
            return conv if self._es_de(conv, user_id) else None
        activa = self._active_by_user.get(user_id) if user_id else None
        if activa:
            conv = self._conversations.get(activa)
            return conv if self._es_de(conv, user_id) else None
        return None

    def get_or_create_active(
        self,
        molecule_context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> Conversation:
        conv = self.get_conversation(user_id=user_id)
        if conv:
            return conv
        try:
            from services.ai.limbic_system import on_conversation_opened
            on_conversation_opened()
        except ImportError:
            pass
        return self.create_conversation(molecule_context, user_id=user_id)

    def load_conversation_from_db(
        self,
        conv_id: str,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> Conversation | None:
        """Carga una conversación **de esta cuenta**.

        MOLCHAT-BE-006: antes esto reasignaba `_active_conv_id`, que era un
        atributo de clase, así que **leer** una conversación cambiaba la activa
        de todo el proceso. Ahora la activa es por cuenta y sólo se mueve la de
        quien pide la lectura.
        """
        # MOLCHAT-BE-008: `None` significa «no existe o no es tuya». Un fallo
        # de la base sale como `PersistenciaFallida` y el endpoint lo convierte
        # en 503; antes los dos desenlaces eran el mismo `None` y el producto
        # no podía distinguir un 404 legítimo de un disco roto.
        from services.ai.memory_store import load_conversation

        data = load_conversation(
            conv_id, user_id=user_id, incluir_heredadas=incluir_heredadas
        )
        if not data:
            return None
        conv = Conversation(
            id=data["id"],
            user_id=user_id,
            messages=data["messages"],
            summary=data["summary"] or "",
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            molecule_context=data.get("molecule_context"),
        )
        self._conversations[conv_id] = conv
        if user_id:
            self._active_by_user[user_id] = conv_id
        log.info("conversation_loaded_from_db", id=conv_id, msg_count=len(conv.messages))
        return conv

    def delete_conversation(
        self,
        conv_id: str,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> bool:
        # El borrado en memoria sólo procede si la caché la tiene como de esta
        # cuenta; la base decide con su propio filtro de propiedad.
        en_memoria = self._conversations.get(conv_id)
        if en_memoria is not None and self._es_de(en_memoria, user_id):
            self._conversations.pop(conv_id, None)
        if user_id and self._active_by_user.get(user_id) == conv_id:
            self._active_by_user.pop(user_id, None)
        # MOLCHAT-BE-008: el endpoint contestaba «deleted» aunque no se hubiera
        # borrado nada. Ahora se devuelve lo que la base hizo de verdad, y un
        # fallo de disco sube como `PersistenciaFallida`.
        from services.ai.memory_store import delete_conversation_db

        return delete_conversation_db(
            conv_id, user_id=user_id, incluir_heredadas=incluir_heredadas
        )

    def list_conversations(
        self,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> list[dict]:
        # MOLCHAT-BE-008: un fallo del historial local sube como
        # `PersistenciaFallida` (503). Devolver una lista vacía haría creer al
        # investigador que no tiene conversaciones.
        from services.ai.memory_store import load_all_conversations

        db_convs = load_all_conversations(
            user_id=user_id, incluir_heredadas=incluir_heredadas
        )

        result = []
        activa = self._active_by_user.get(user_id) if user_id else None
        seen = set()
        for c in db_convs:
            seen.add(c["id"])
            result.append({
                "id": c["id"],
                "preview": c["preview"],
                "message_count": c["message_count"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "active": c["id"] == activa,
            })
        # La caché en memoria también se filtra por cuenta: si no, una
        # conversación ajena todavía cargada se colaría en la lista.
        for cid, conv in self._conversations.items():
            if cid not in seen and self._es_de(conv, user_id):
                preview = ""
                for m in conv.messages:
                    if m.get("role") == "user":
                        preview = m.get("content", "")[:80]
                        break
                result.append({
                    "id": cid,
                    "preview": preview,
                    "message_count": len(conv.messages),
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "active": cid == activa,
                })
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    def _persist_conv(self, conv: Conversation):
        """Guarda el turno. Si no puede, la conversación queda marcada.

        MOLCHAT-BE-008: aquí no vale lanzar. Esto corre **después** de que el
        modelo contestó, y hacer estallar el turno borraría una respuesta que ya
        existe. Pero tampoco vale callar: la conversación queda degradada y el
        turno lo dice con `aviso_de_persistencia`.
        """
        from services.ai import memory_store

        try:
            memory_store.save_conversation(
                conv_id=conv.id, messages=conv.messages,
                summary=conv.summary, molecule_context=conv.molecule_context,
                created_at=conv.created_at, user_id=conv.user_id,
            )
        except Exception as exc:
            conv.persistencia_degradada = True
            conv.persistencia_error = str(exc)[:200]
            log.error("turn_not_persisted", id=conv.id, error=str(exc)[:200])

        # Engram FTS5: indexar el último mensaje para búsqueda semántica. Es un
        # índice derivado: si falla, la conversación sigue guardada y sólo se
        # degrada la búsqueda, así que no marca la conversación.
        try:
            if conv.messages:
                last = conv.messages[-1]
                memory_store.index_chat_message(
                    conv.id,
                    last.get("role", ""),
                    last.get("content", ""),
                    user_id=conv.user_id,
                )
        except Exception as exc:
            log.warning("engram_index_failed", id=conv.id, error=str(exc)[:200])

    @staticmethod
    def aviso_de_persistencia(conv: Conversation) -> str:
        """Lo que el turno tiene que decir cuando el disco no aceptó el turno."""
        if not conv.persistencia_degradada:
            return ""
        motivo = f": {conv.persistencia_error}" if conv.persistencia_error else ""
        return (
            "\n\n⚠️ No pude guardar este turno en el historial local"
            f"{motivo}. La respuesta es válida, pero si reinicias la "
            "aplicación no estará en la conversación."
        )

    # ── Deterministic Router (sin LLM, ahorra tokens) ────────────

    _TOOL_KEYWORDS = {
        "calcula", "propiedad", "propiedades", "lipinski", "veber",
        "pains", "admet", "docking", "rescoring", "compara", "compará",
        "valida", "validá", "smiles", "afinidad", "score", "target",
        "peso", "estructura", "logp", "tpsa", "sintetiza", "síntesis",
        "molécula", "compuesto", "fármaco", "farmaco", "droga",
    }
    _MEMORY_KEYWORDS = {"recuerda", "recordas", "recuerdo", "historial", "anterior", "pasado",
                        "ultima", "semana", "ayer", "antes", "evaluacion"}
    _CLOUD_KEYWORDS = {"mejorar", "modificar", "reemplazar", "estrategia",
                       "mecanismo", "via", "reaccion", "enfermedad", "tratamiento",
                       "potencia", "selectividad", "especificidad",
                       "optimizacion", "prediccion", "receptor", "farmaco",
                       "toxicidad", "toxico", "absorcion", "metabolismo",
                       "solubilidad", "permeabilidad", "biodisponibilidad",
                       "ansiolitico", "analgesico", "antibiotico", "antiviral"}
    # Factual keywords: solo lo que NO overlap con tool/memory
    _FACTUAL_KEYWORDS = {"mw", "pesomolecular", "tpsa", "hbd", "hba", "formula",
                         "qed", "enlaces", "rotables", "hotspots"}

    def _route_user_intent(self, user_message: str) -> str:
        msg = user_message.lower().translate(str.maketrans("", "", "?!.,;:()"))
        word_count = len(msg.split())
        if word_count <= 3:
            return "complex"
        tool_hits = sum(1 for kw in self._TOOL_KEYWORDS if kw in msg.lower())
        mem_hits = sum(1 for kw in self._MEMORY_KEYWORDS if kw in msg.lower())
        cloud_hits = sum(1 for kw in self._CLOUD_KEYWORDS if kw in msg.lower())
        factual_hits = sum(1 for kw in self._FACTUAL_KEYWORDS if kw in msg.lower())
        # memory checkeado PRIMERO: si hay "recordas", va a MolGraph
        if mem_hits >= 1 and word_count >= 4:
            return "memory"
        # factual: query numerica verificable → ejecutar herramienta ANTES del LLM
        if factual_hits >= 2 and word_count >= 3:
            return "factual"
        if cloud_hits >= 2:
            return "complex_chemistry"
        if tool_hits >= 2 or (tool_hits >= 1 and word_count >= 3):
            return "tool"
        return "complex"

    @staticmethod
    def _resolve_smiles_by_name(text: str) -> str | None:
        """Buscar el SMILES de una molécula por nombre común en el texto del usuario.

        Mantiene un diccionario offline de nombres → SMILES canónicos
        (MolDesign desktop 100% offline, sin PubChem). Si el nombre aparece
        en el texto, devuelve el SMILES canónico desde el MolGraph persistente.

        Ejemplos: "ibuprofeno" → "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
                  "aspirina" → "CC(=O)Oc1ccccc1C(=O)O"

        Returns None si no se reconoce un nombre común de molécula en el texto.
        """
        KNOWN = {
            "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
            "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
            "paracetamol": "CC(=O)Nc1ccc(O)cc1",
            "cafeina": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "cafeína": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "glucosa": "OCC1OC(O)C(O)C(O)C1O",
            "etanol": "CCO",
            "morfina": "CN1CCC23C4=C1Cc1ccc(O)c(c12)OC3C(O)C=C4",
            "testosterona": "CC12CCC3C(CCC4=CC(=O)CCC34C)C1CCC2O",
            "vitaminac": "CC(C(O)C(=O)O)O",
            "ácido ascórbico": "CC(C(O)C(=O)O)O",
            "penicilina g": "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C",
            "penicillin g": "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C",
            "taxol": "CC1=C2C(O)=OCC(=O)C3=C(C2C(OC(=O)C)CC1)OC",
            "paclitaxel": "CC1=C2C(O)=OCC(=O)C3=C(C2C(OC(=O)C)CC1)OC",
            "metano": "C",
            "propanol": "CCO",
            "propanolol": "CCCO",
            "ácido propanóico": "CCC(=O)O",
            "metanfetamina": "CC(N)Cc1ccccc1",
            "anfetamina": "CC(N)Cc1ccccc1",
            "lorazepam": "ClC1=CC2C(=NC(O)C3=CC=CC=C3Cl)C(=O)Nc2cc1",
            "diazepam": "CN1C(=O)CN=C(C2=CC=CC=C2Cl)c2ccccc12",
            "zolpidem": "CN1C=CN=C2N3C=CC=C3C(=O)C1=2",
        }
        lower = text.lower()
        for name, smiles in KNOWN.items():
            if re.search(r'\b' + re.escape(name) + r'\b', lower, re.IGNORECASE):
                return smiles
        return None

    @staticmethod
    def _extract_smiles_from_message(text: str) -> str | None:
        """Detectar un SMILES en el mensaje del usuario y devolverlo canonizado.

        Estrategia: corta en espacios/puntuacion, prueba cada token largo con
        _guard_validate_smiles. El primero que pasa RDKit es el SMILES del user.
        Esto es lo que permite al pipeline FORZAR compute_properties cuando
        el usuario escribio un SMILES explicito y el modelo no llamo la tool.

        Heuristica anti-falso-positivo: minimo 2 chars (evita 'C', 'O' solos
        que son SMILES validos pero rara vez son la intencion del usuario)
        — salvo para SMILES quimicos validos largos.
        """
        import re as _re
        # Split por espacios y puntuacion comun, manteniendo tokens largos
        tokens = _re.findall(r'[A-Za-z0-9@=\-\(\)\[\]\\/#+\.]+', text)
        # Priorizar tokens que parecen SMILES (contienen atomos/bringas)
        # Letras que NO aparecen en SMILES: j, q, J, Q, R (salvo corners)
        def looks_like_smiles(t: str) -> bool:
            if len(t) < 2:
                return False
            # SMILES usa C, c, N, n, O, o, S, P, F, Cl, Br, I, digitos, (), [], =, #, @, \, /, .
            suspicious = set("jqJR") - {"R"}  # R en SMARTS, raro en SMILES comunes
            if any(ch in suspicious for ch in t):
                return False
            # debe contener al menos una letra atomica
            if not any(ch in "CcNnOoSsPFIHBrCl" for ch in t):
                return False
            return True
        # Probar candidatos en orden (largo descendente para priorizar moleculas reales)
        candidates = sorted({t for t in tokens if looks_like_smiles(t)}, key=len, reverse=True)
        try:
            from rdkit import RDLogger
            RDLogger.DisableLog("rdApp.*")  # silenciar parse-errors de tokens que no son SMILES
        except ImportError:
            pass
        try:
            from services.ai.tool_registry import _guard_validate_smiles
        except ImportError:
            return None
        for cand in candidates:
            valid, canon, err = _guard_validate_smiles(cand)
            if valid and canon:
                # Filtro semantico: descartar SMILES triviales de 1 atomo (C, O, N)
                # si la query es claramente mas compleja — evita falsear "C" como metano
                # cuando el usuario dice "calcula propiedades de cafeina" (no hay SMILES).
                # Aceptamos solo si el token vino literal del user como SMILES deliberado.
                if canon in {"C", "O", "N", "S", "P", "H", "F", "I"}:
                    continue
                return canon
        return None

    @staticmethod
    def _extract_target_pdb(text: str) -> str:
        """Detectar un PDB target ID en lenguaje natural del usuario.

        Orden (F4 target resolver):
          1. target_resolver.resolve_target() — resuelve NOMBRES COMUNES:
             "receptor de serotonina" → 7E2Y, "beta-adrenergico" → 6PS2,
             "CYP3A4" → 4NY4, "SARS-CoV-2 Mpro" → 6LU7. Fuente:
             backend/data/target_aliases.json (387 targets).
          2. Regex de PDB ID (compatibilidad):
             "contra 7E2Y" → "7E2Y", "target 6LU7" → "6LU7",
             "receptor 3CL-pro" → "3CL-pro", "la proteina 1F0R" → "1F0R".

        Patrón regex: dígito + 3+ caracteres alfanuméricos concatenados tras
        palabras clave 'contra', 'target', 'receptor', o 'proteina'.

        Returns "" si no se detecta un target plausible (ni nombre ni PDB).
        """
        try:
            from services.ai.target_resolver import resolve_target
            resolved = resolve_target(text)
            if resolved.pdb_id:
                return resolved.pdb_id
        except Exception:
            pass  # resolver no disponible → caer al regex de PDB
        import re as _re
        for pat in (
            r'contra\s+(?:la\s+(?:proteina|proteína|enzima|receptor)\s+)?(\d[0-9A-Za-z\-]{3,})',
            r'target[\s:=]+(\d[0-9A-Za-z\-]{3,})',
            r'receptor\s+(\d[0-9A-Za-z\-]{3,})',
            r'prote[íi]na\s+(\d[0-9A-Za-z\-]{3,})',
        ):
            m = _re.search(pat, text, _re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
                # Normalizar: quitar trailing '.' ',' ')' si se colaron
                raw = raw.rstrip(".,;)")
                if len(raw) >= 3:
                    return raw
        return ""

    @staticmethod
    def _extract_molgraph_target(text: str) -> str:
        """Extraer el nombre del target de una query molgraph.
        "que moleculas hay contra 5-HT1A?" → "5-HT1A"
        "moleculas activas contra CDK2" → "CDK2"
        """
        import re as _re
        # Keyword + nombre (dígito/letras/guiones), hasta 12 chars
        for pat in (
            r'contra\s+([A-Za-z0-9\-\.]{2,12})',
            r'target\s+([A-Za-z0-9\-\.]{2,12})',
            r'receptor\s+([A-Za-z0-9\-\.]{2,12})',
            r'enzima\s+([A-Za-z0-9\-\.]{2,12})',
        ):
            m = _re.search(pat, text, _re.IGNORECASE)
            if m:
                raw = m.group(1).strip().rstrip(".,;)?")
                if raw and not raw.lower().startswith(("la ", "el ", "los ", "las ")):
                    return raw
        return ""

    @staticmethod
    def _last_shared_smiles(conv) -> str:
        """Buscar el último SMILES que el usuario compartió en la conversación.

        Usado por la anáfora pura ("esa primera molécula") cuando molecule_context
        está vacío — el usuario puede haber pasado un SMILES antes en el chat sin
        haberlo subido como contexto activo (fix: antes respondía "no tengo
        registro" aunque el SMILES ya estuviera en el historial).
        """
        if not conv:
            return ""
        from services.ai.intent_classifier import _extract_smiles as _ext
        last_smiles = ""
        for msg in conv.messages:
            if msg.get("role") == "user":
                s = _ext(msg.get("content", ""))
                if s:
                    last_smiles = s
        return last_smiles

    def _should_force_tool(self, intent: str) -> bool:
        """Intent quimico → el modelo DEBE ejecutar una tool, no responder de memoria.

        Ampliado: 'docking' también fuerza tool (F2: determinismo run_docking)."""
        return intent in ("tool", "complex_chemistry", "factual", "docking")

    @staticmethod
    def _looks_factual_chemical(text: str) -> bool:
        """True si el mensaje pide datos químicos factuales (no conceptual).

        Gate del name_resolver hook (F3): evita gastar tiempo/red en
        preguntas conceptuales desconocidas. Solo disparamos resolución de
        nombre cuando el usuario claramente pide propiedades/valores.
        """
        lo = (text or "").lower()
        return any(
            kw in lo for kw in (
                "propiedades", "calcula", "calcular", "calcule", "peso",
                "masa", "mw ", "logp", "log p", "tpsa", "afinidad", "aff",
                "lipinski", "veber", "druglikeness", "admet", "solubilidad",
                "hbd", "hba", "rotatable", "anillos", "rings", "dame",
                "quiero", "necesito", "de la ", "de el ", "del ",
            )
        )

    def build_context_memory(
        self,
        user_message: str = "",
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> str:
        """Buscar en MolGraph + SAR impact. Usa user_message para FTS5.

        MOLCHAT-BE-009: esto entra en el prompt de CADA turno. Sin cuenta leía
        el archivo compartido, así que las evaluaciones de un investigador
        aparecían en el contexto de otro sin que nadie pidiera nada — la misma
        forma de fuga que el índice FTS de `ai_memory.db`.
        """
        parts = []
        try:
            from services.ai.molgraph import get_top_molecules, query_fts
            # Busqueda especifica por el mensaje del usuario
            fts_results = []
            if user_message:
                query = user_message.lower()[:100]
                words = [w for w in query.split() if len(w) > 3]
                if words:
                    fts_results = query_fts(
                        " OR ".join(words[:4]), limit=3,
                        user_id=user_id, incluir_heredadas=incluir_heredadas,
                    )
            if fts_results:
                lines = ["[MolGraph - Resultados de busqueda:]"]
                for r in fts_results:
                    smi = r.get("smiles", "")[:30]
                    name = r.get("name", "") or smi
                    props = r.get("properties", {})
                    aff = props.get("affinity_kcal", "?")
                    score = props.get("score", "?")
                    lines.append(f"  {name}: aff={aff}, score={score}")
                parts.append("\n".join(lines))
            if not fts_results:
                top = get_top_molecules(
                    by="score", limit=5,
                    user_id=user_id, incluir_heredadas=incluir_heredadas,
                )
                if top:
                    lines = ["[Evaluaciones previas - Top scores]"]
                    for t in top:
                        lines.append(
                            f"  {t['smiles'][:25]}: score={t['score']}/{100}, "
                            f"aff={t['affinity']} kcal/mol"
                        )
                    parts.append("\n".join(lines))
        except ImportError:
            pass
        try:
            from services.ai.molgraph import query_modification_impact
            impact = query_modification_impact(
                min_delta=-10.0,
                user_id=user_id, incluir_heredadas=incluir_heredadas,
            )
            if impact:
                improvements = [r for r in impact if r["delta_affinity"] < 0]
                if improvements:
                    lines = ["[SAR - Modificaciones que mejoraron afinidad]"]
                    for r in improvements[:3]:
                        lines.append(
                            f"  {r['modification']}: delta_aff={r['delta_affinity']:.1f} "
                            f"({r['parent_smiles'][:15]} -> {r['child_smiles'][:15]})"
                        )
                    parts.append("\n".join(lines))
        except ImportError:
            pass
        return "\n\n".join(parts)

    def _build_molecule_prompt(self, ctx: dict) -> str:
        """Construir un prompt legible a partir del contexto de evaluación."""
        parts = [
            "\n[Contexto: el usuario acaba de evaluar esta molécula en MolDesign]",
        ]
        smi = ctx.get("smiles", "?")
        target = ctx.get("target_name", "?")
        aff = ctx.get("affinity_kcal")
        total = ctx.get("total_score")
        mw = ctx.get("molecular_weight")
        logp = ctx.get("log_p")
        lip = ctx.get("lipinski_pass")
        veb = ctx.get("veber_pass")
        sa = ctx.get("sa_score")
        qed = ctx.get("qed")
        adme = ctx.get("adme_score")
        dl = ctx.get("druglikeness_score")
        hits = ctx.get("hotspots_hit", []) or []

        if aff is not None:
            parts.append(f"Afinidad de docking: {aff} kcal/mol (más negativo = mejor).")
        if total is not None:
            parts.append(f"Score total: {total}/100 (combina afinidad, ADME y drug-likeness).")
        parts.append(f"SMILES: {smi}")
        parts.append(f"Receptor: {target}")
        if mw:
            parts.append(f"Peso molecular: {mw} Da, LogP: {logp or '?'}.")
        if lip is not None:
            parts.append(f"Regla de Lipinski: {'APROBADA' if lip else 'FALLIDA'}.")
        if veb is not None:
            parts.append(f"Regla de Veber: {'APROBADA' if veb else 'FALLIDA'}.")
        if sa:
            parts.append(f"Accesibilidad sintética (SA Score): {sa}/10 (menor = más fácil de sintetizar).")
        if qed:
            parts.append(f"QED (drug-likeness cuantitativo): {qed:.2f} (0-1, mayor = más 'drug-like').")
        if adme is not None:
            parts.append(f"Score ADME: {adme}/100.")
        if dl is not None:
            parts.append(f"Score Drug-likeness: {dl}/100.")
        if hits:
            parts.append(f"Hotspots alcanzados: {', '.join(str(h) for h in hits[:8])}.")

        return "\n".join(parts)

    async def _web_enrich(
        self,
        user_message: str,
        _det,
        conv,
    ) -> tuple[str, bool]:
        """Enriquecimiento web con control de privacidad por smiles_source.

        Retorna (enrichment_text, ask_permission_flag):
          - (text, False)  → enriquecido OK, text ya agregado
          - ("",   False)  → no enriqueció (offline/no aplicable/error)
          - ("",   True)   → SMILES privado de context, pedir permiso al user
        """
        src = getattr(_det, "smiles_source", None) or ""
        smiles = _det.smiles or ""
        # Caso 1: SMILES privado (anáfora desde context sin nombre)
        # → NO enviar a web sin permiso explícito del user. Caller debe PREGUNTAR.
        if src == "anaphora_context":
            # permiso ya concedido para este SMILES en conv?
            if not self._smiles_web_allowed(conv, smiles):
                return "", True  # pedir permiso
            # permiso concedido → proceder como si fuera explícito
            src = "explicit"

        chunks: list[str] = []

        # Caso 1b: docking → enriquecer el TARGET con search_pdb (PRIORIDAD).
        # El PDB ID ya estaba en el texto del user (público) — NO enviamos
        # el SMILES del ligando ni los resultados del docking. Solo buscamos
        # metadata pública del receptor (título, organismo, método).
        # Va ANTES de name/explicit para que un docking con nombre conocido
        # (ej. "docking de paracetamol contra 7E2Y") enriquezca el receptor.
        if _det.tool == "run_docking" and _det.target:
            try:
                from services.ai.tools.web_tools import search_pdb
                sp = await search_pdb(_det.target, limit=3)
                if sp and "offline" not in sp and "error" not in sp:
                    chunks.append(f"\n\n📎 **RCSB PDB (receptor):** {sp[:300]}")
            except Exception:
                pass
            # si además hay smiles_source=name/explicit, enriquecemos el ligando
            # debajo (sin return acá — acumulamos ambos chunks)

        # Caso 2:smiles_source=name / anaphora_name → enriquecer por NOMBRE
        # (cero privacidad — el nombre ya está en el texto del user)
        if src in ("name", "anaphora_name"):
            name = _find_known_molecule_name(user_message.lower()) or ""
            if name:
                # Traducir es→en para PubChem/ChEMBL
                ename = self._es_to_en_for_web(name)
                try:
                    from services.ai.tools.web_tools import (
                        pubchem_description, chembl_activity,
                    )
                    pd = await pubchem_description(ename)
                    if pd and not any(m in pd for m in ("offline","error","no encontrado","inválido")):
                        chunks.append(f"\n\n📎 **PubChem:** {pd}")
                    ce = await chembl_activity(ename)
                    if ce and not any(m in ce for m in ("offline","error","no encontrado","inválido")):
                        chunks.append(f"\n\n📎 **ChEMBL:** {ce}")
                except Exception:
                    pass
            return ("".join(chunks), False)

        # Caso 3:smiles_source=explicit (user escribió SMILES en chat) → web por SMILES
        # (cero privacidad — el user ya lo compartió en chat)
        if src == "explicit":
            try:
                from services.ai.tools.web_tools import pubchem_lookup
                pl = await pubchem_lookup(smiles)
                if pl and not any(m in pl for m in ("offline","error","sin datos","inválido")):
                    chunks.append(f"\n\n📎 **PubChem:** {pl}")
            except Exception:
                pass
            return ("".join(chunks), False)

        # Caso 4:smiles_source None — no hay SMILES que enriquecer
        return ("", False)

    def _smiles_web_allowed(self, conv, smiles: str) -> bool:
        """Chequear si el user ya concedió permiso web para este SMILES."""
        allowed = getattr(conv, "allowed_smiles_web", None) or set()
        return smiles in allowed

    def _grant_smiles_web(self, conv, smiles: str) -> None:
        """Registrar permiso del user para web con este SMILES."""
        if not hasattr(conv, "allowed_smiles_web") or conv.allowed_smiles_web is None:
            conv.allowed_smiles_web = set()
        conv.allowed_smiles_web.add(smiles)
        self._persist_conv(conv)

    @staticmethod
    def _es_to_en_for_web(es_name: str) -> str:
        """Traduce nombre de fármaco es→en para PubChem/ChEMBL."""
        # Reutilizar el dict del módulo web_tools si está cargado
        try:
            from services.ai.tools.web_tools import _name_to_english
            return _name_to_english(es_name)
        except ImportError:
            return es_name

    def _match_factual_query(self, user_message: str) -> tuple[str | None, dict]:
        msg = user_message.lower()
        # MolGraph primero si hay keywords de memoria
        if any(kw in msg for kw in ("recordas", "recuerda", "evaluacion", "anterior")):
            return "query_molgraph", {"target": msg[:100]}
        if any(kw in msg for kw in ("score", "afinidad", "total_score")):
            return "query_molgraph", {"target": ""}
        if any(kw in msg for kw in ("peso", "mw", "masa", "peso molecular")):
            return "compute_properties", {"smiles": "?"}
        if any(kw in msg for kw in ("logp", "log p", "tpsa", "hbd", "hba")):
            return "compute_properties", {"smiles": "?"}
        if any(kw in msg for kw in ("smiles", "valida", "validar", "canonico")):
            return "validate_smiles", {"smiles": "?"}
        if any(kw in msg for kw in ("lipinski", "veber", "pains", "druglike")):
            return "check_druglikeness", {"smiles": "?"}
        return None, {}

    async def _handle_factual_query(self, user_message: str, conv) -> str | None:
        tool_name, params = self._match_factual_query(user_message)
        if not tool_name:
            return None
        try:
            from services.ai.tool_registry import get_tool_registry
            registry = get_tool_registry()
            tool = registry.get(tool_name)
            if not tool or not tool.fn:
                return None
            if conv.molecule_context:
                smi = conv.molecule_context.get("smiles", "")
                if smi and "smiles" in params:
                    params["smiles"] = smi
                if "target" in params:
                    params["target"] = conv.molecule_context.get("target_name", "") or ""
            result = await tool.fn(**params)
            return (
                f"[Sistema - Dato verificado por {tool_name}, ejecutado ANTES de responder]\n"
                f"{result}\n"
                f"USA EXACTAMENTE estos valores. No inventes numeros."
            )
        except Exception:
            return None

    def _prepare_messages_with_context(
        self,
        conv: Conversation,
        user_message: str,
        context_memory: str,
        relevant_context: str,
        include_tools: bool = True,
        include_engram: bool = True,
        incluir_heredadas: bool = False,
        allow_web: bool = False,
    ) -> list[dict]:
        # ── PERMANENT prefix (cacheable by llama.cpp) ─────────────
        permanent_parts = [
            "Eres un asistente experto en química medicinal y diseño de fármacos.",
            "Responde en el mismo idioma en el que se te pregunta, utilizando un español neutro profesional (evita modismos o conjugaciones de voseo).",
            "Básate en datos reales cuando los tengas disponibles.",
            "REGLA CERO — VALIDEZ CIENTÍFICA: NUNCA afirmes valores numéricos quimicos (MW, "
            "LogP, TPSA, H-Bond Donors/Acceptors, rotatable bonds, heavy atoms, rings, "
            "afinidad kcal/mol, score) ni estructuras SMILES si NO los extrajiste de una "
            "herramienta ejecutada en esta pasada. Si el sistema detecta que mencionas "
            "valores sin respaldo de herramienta, los marcará como incorrectos y se verá "
            "poco confiable.",
            "Si una query quimica NO tiene datos disponibles via tools y el RAG no resolvio "
            "la molécula, RESPONDE EXACTAMENTE: 'No tengo datos verificados para esa "
            "molécula/propiedad. Ejecuta la herramienta correspondiente o consulta PubChem.' "
            "Es preferible admitir ignorancia que inventar valores falsos.",
            "NO inventes valores numéricos ni estructuras químicas ficticias.",
            # MOLCHAT-AUD-01, eje SCI. La clase la fija el contrato de cada
            # herramienta (`ToolDef.clase`) y llega etiquetada en el bloque de
            # resultados; aquí sólo se le pide al modelo que no la borre al
            # redactar. Un número medido, uno predicho y uno traído de una base
            # externa no se pueden presentar con la misma autoridad.
            "REGLA DE PROCEDENCIA: cada resultado de herramienta llega etiquetado con "
            "su clase — cálculo, dato persistido, inferencia (predicción de modelo), "
            "recuperación externa o explicación — y con su fuente. Conserva esa "
            "distinción al responder: di 'calculado con RDKit', 'de tu evaluación "
            "<task_id>', 'predicho por el modelo ADMET', 'según PubChem'. Nunca "
            "presentes una predicción como una medida.",
            "REGLA DE ABSTENCIÓN: si una herramienta devolvió 'no se obtuvo dato', si "
            "la comprobación no pudo ejecutarse, o si el dato no existe, dilo y explica "
            "cómo obtenerlo. No rellenes el hueco con una estimación tuya, y no "
            "conviertas un 'no se pudo comprobar' en un 'no hay problema'.",
            "Si proporcionas, modificas o diseñas una estructura en formato SMILES, debes validarla obligatoriamente utilizando la herramienta 'validate_smiles' antes de presentarla al usuario. Nunca muestres un SMILES al usuario que no haya sido previamente validado con RDKit mediante esta herramienta.",
            "SÉ CONCISO. Máximo 2-3 párrafos. No repitas información del contexto.",
            "Respuestas directas, sin rodeos. Ve al punto.",
            "Conoces farmacología: mecanismos de acción, PK/PD, ADME, interacciones.",
            "Conoces fisiología: sistemas cardiovascular, nervioso, endocrino, inmune.",
            "Conoces bioinformática: secuencias, docking molecular, QSAR, proteínas.",
            # Tool hints: guía al modelo hacia qué herramienta usar según la intención
            "Tienes herramientas disponibles abajo. Úsalas proactivamente:",
            " - Para recomendar moléculas similares a una conocida: usa 'molgraph_similar' o 'generate_analogs'.",
            " - Para buscar en el knowledge graph por texto o target: usa 'query_molgraph'.",
            " - Para calcular propiedades (MW, LogP, etc.): usa 'compute_properties'.",
            " - Para validar un SMILES antes de mostrarlo: usa 'validate_smiles'.",
            " - Para verificar drug-likeness (Lipinski, PAINS): usa 'check_druglikeness'.",
            " - Para predecir ADME/Tox: usa 'predict_admet'.",
            " - Para comparar dos moléculas: usa 'compare_molecules'.",
            "NO respondas con SMILES inventados. Si no sabes una estructura, busca en las herramientas.",
        ]
        try:
            from services.ai.limbic_system import get_stage, get_level, get_state
            state = get_state()
            stage = get_stage(get_level(state.get("xp", 0)))
            if stage == "Recién Nacido":
                permanent_parts.append("Eres nuevo. Sé conciso y aprende de cada interacción.")
            elif stage == "Experto":
                permanent_parts.append("Eres un experto. Anticipa las necesidades del usuario y sugiere mejoras proactivamente.")
            elif stage == "Arquitecto":
                permanent_parts.append("Eres un arquitecto molecular. Propón estrategias de diseño de múltiples pasos.")
        except ImportError:
            pass
        try:
            from services.ai.limbic_system import build_limbic_prompt
            limbic = build_limbic_prompt()
            if limbic:
                permanent_parts.append(limbic)
        except ImportError:
            pass
        if include_tools:
            try:
                from services.ai.tool_registry import get_tool_registry
                registry = get_tool_registry()

                # Siempre incluir TODAS las tools offline (~12 tokens/tool).
                # El modelo 1.5B decide solo cual invocar via function calling.
                # Antes (v1.0-v1.4): exclude_categories + keyword matcher
                # hardcodeado (_ANALOG_KEYWORDS) excluia analog tools si la
                # query no matcheaba — bug #4 de la migracion.
                tool_section = registry.build_prompt_section(show_all=False)
                if tool_section:
                    permanent_parts.append("\n[Modo herramienta activo. Maximo 1 tool/respuesta.]")
                    permanent_parts.append(tool_section)
                    permanent_parts.append(registry.build_few_shot_example())
            except ImportError:
                pass

        messages_for_api = [
            {"role": "system", "content": "\n\n".join(permanent_parts)},
        ]

        # ── VARIABLE context (changes per turn, not cached) ──────
        variable_parts = []
        if conv.molecule_context:
            variable_parts.append(self._build_molecule_prompt(conv.molecule_context))
        if conv.summary:
            variable_parts.append(f"[Conversación anterior resumida:]\n{conv.summary}")
        if context_memory:
            variable_parts.append(f"[Memoria de evaluaciones:]\n{context_memory}")
        try:
            from services.ai.memory_store import get_all_consolidated_sessions
            past = get_all_consolidated_sessions(limit=3)
            if past:
                lines = ["[Memoria a largo plazo — sesiones anteriores:]"]
                for s in past:
                    topics = s.get("key_topics", [])[:3]
                    mols = s.get("molecules_discussed", [])[:2]
                    if topics or mols:
                        lines.append(f"- {s.get('total_messages', 0)} msgs | temas: {', '.join(topics) if topics else 'generales'}")
                variable_parts.append("\n".join(lines))
        except ImportError:
            pass
        # PubChem + ChEMBL: datos reales de farmacos conocidos.
        #
        # Gate de MolChat, criterio 3 («cero llamadas remotas sin consentimiento
        # verificable»). Esto salia a PubChem en CADA turno cuyo mensaje nombrara
        # un farmaco conocido, sin mirar `allow_web` y sin pasar por el
        # consentimiento de NET-005: era la unica llamada remota del turno que el
        # investigador no habia autorizado, y hacia ambiguo el camino offline que
        # el §8 pide inequivoco. Ahora depende del mismo interruptor que el resto.
        if allow_web or os.environ.get("MOLCHAT_ALLOW_WEB", "") == "1":
            try:
                from services.ai.tools.web_tools import pubchem_autolookup
                pubchem = pubchem_autolookup(user_message, conv.molecule_context)
                if pubchem:
                    variable_parts.append(pubchem)
            except ImportError:
                pass
        if include_engram and user_message and len(user_message) > 10:
            try:
                from services.ai.memory_store import search_chat_history
                # El índice FTS no tenía dimensión de cuenta: esta consulta
                # corre en CADA turno, así que metía en el prompt de una cuenta
                # los mensajes de otra sin que nadie pidiera nada.
                results = search_chat_history(
                    user_message,
                    limit=5,
                    user_id=conv.user_id,
                    incluir_heredadas=incluir_heredadas,
                )
            except ImportError:
                results = []
            except Exception as _err:
                # El índice de búsqueda es DERIVADO. MOLCHAT-BE-008 dejó de
                # tragarse los errores de `ai_memory.db`, y con razón para la
                # conversación —perder un turno guardado importa—; pero aquí el
                # fallo llegaba hasta el endpoint y devolvía HTTP 500. Lo
                # encontró el gate runtime con una pregunta que llevaba un
                # SMILES dentro. Si el historial no se puede buscar, se pierde
                # el historial, no el turno.
                log.warning("engram_busqueda_fallida", error=str(_err)[:200])
                results = []
            try:
                if results:
                    lines = ["[Resultados relevantes del historial:]"]
                    for r in results:
                        prefix = "Usuario" if r["role"] == "user" else "MolChat"
                        lines.append(f"- {prefix}: {r['content'][:150]}")
                    variable_parts.append("\n".join(lines))
            except ImportError:
                pass

        if variable_parts:
            messages_for_api.append(
                {"role": "system", "content": "\n\n".join(variable_parts)}
            )

        # Context Compression: solo últimos N mensajes relevantes
        recent_msgs, compressed = conv.get_recent_and_compressed(user_message)
        messages_for_api.extend(recent_msgs)
        messages_for_api.append({"role": "user", "content": user_message})

        # Token budget enforcement: mantener contexto dentro de n_ctx
        MAX_BUDGET = 14000
        est_total = sum(len(m.get("content", "")) * 0.45 for m in messages_for_api)
        retries = 10
        while est_total > MAX_BUDGET and len(messages_for_api) > 4 and retries > 0:
            removed = messages_for_api.pop(2)
            est_total -= len(removed.get("content", "")) * 0.45
            retries -= 1

        # Sanitizar non-ASCII que puede causar errores de encoding en el sidecar
        # LLM local (llama-server.exe) en Windows con ciertas locales del sistema.
        for m in messages_for_api:
            if "content" in m and isinstance(m["content"], str):
                m["content"] = _sanitize_ascii(m["content"])

        return messages_for_api

    def _resolve_provider(
        self,
        provider_id: str | None,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> tuple[Any | None, str]:
        """Resolver qué provider usar **para esta cuenta**. Returns (provider, error_msg).

        D-09: la configuración aplicada (clave, modelo y sobre todo `base_url`,
        que es el destino de los datos) es de la cuenta, no del proceso. Sin
        esto, el turno de una persona salía con la clave y hacia el servidor que
        hubiera configurado otra.
        """
        registry = get_provider_registry()
        provider = registry.resolve_for_user(provider_id, user_id, incluir_heredadas)
        if provider:
            return provider, ""
        if provider_id:
            disponibles = [p["id"] for p in registry.list_providers()]
            return None, f"Proveedor '{provider_id}' no encontrado. Disponibles: {disponibles}"
        return None, "No hay proveedor activo. Configurá uno en Opciones > Intérprete IA."

    @staticmethod
    def _consentimiento_pendiente(provider: Any, user_id: str | None) -> str:
        """MOLCHAT-NET-005: qué decir si el turno saldría a un destino sin autorizar.

        Devuelve "" cuando se puede enviar. La puerta va **antes** de tocar la
        conversación: si el destino no está autorizado no se envía, y tampoco se
        guarda el turno como si hubiera ocurrido.

        Pregunta por `motivo_de_bloqueo` y no por `hay_consentimiento` porque el
        permiso es sólo una de las dos condiciones: el modo offline manda sobre
        él, y aquí no se miraba.
        """
        from services.ai.consent import destino_de, motivo_de_bloqueo

        return motivo_de_bloqueo(destino_de(provider), user_id)

    async def _wait_for_resources(self, provider_id: str, max_wait_s: int = 60) -> bool:
        """Poll pipeline state hasta que termine. Returns True si ya está disponible."""
        try:
            from services.ai.resource_manager import get_resource_manager
            rm = get_resource_manager()
        except ImportError:
            return True

        for _ in range(max_wait_s // 2):
            if not rm.is_pipeline_busy():
                return True
            await asyncio.sleep(2)
        return False

    async def chat(
        self,
        messages: list[dict[str, str]],
        provider_id: str | None = None,
        molecule_context: dict[str, Any] | None = None,
        mode: str = "speed",
        allow_web: bool = False,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> AsyncIterator[str]:
        """El turno, más el aviso de lo que no se pudo guardar.

        MOLCHAT-AUD-01 (SCI). Aquí había un parámetro `stream` que no
        significaba «entrega de una vez» sino «no emitas»: con `stream=False`
        cada rama determinista se saltaba su `yield`, el generador terminaba
        vacío y la respuesta quedaba sólo en el historial. Desde MOLCHAT-INT-007
        ningún llamador lo usaba —el endpoint pide `True` y `chat_with_info`
        también—, así que era una trampa esperando al siguiente. Se retiró: este
        generador **siempre** emite, y quien quiera la respuesta de una pieza
        usa `chat_with_info`.

        MOLCHAT-BE-008: `_persist_conv` corre después de que el modelo contestó
        y no puede tumbar el turno, así que marca la conversación. Aquí se cobra
        esa marca: el turno termina declarando que no quedó en el historial, por
        el mismo canal `__WARNING__:` que ya usan los otros avisos.
        """
        async for token in self._turno(
            messages=messages,
            provider_id=provider_id,
            molecule_context=molecule_context,
            mode=mode,
            allow_web=allow_web,
            user_id=user_id,
            incluir_heredadas=incluir_heredadas,
        ):
            yield token

        conv = self.get_conversation(user_id=user_id)
        if conv is not None and conv.persistencia_degradada:
            yield "__WARNING__:" + self.aviso_de_persistencia(conv).strip()

    async def _turno(
        self,
        messages: list[dict[str, str]],
        provider_id: str | None = None,
        molecule_context: dict[str, Any] | None = None,
        mode: str = "speed",
        allow_web: bool = False,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
    ) -> AsyncIterator[str]:
        registry = get_provider_registry()

        provider, err = self._resolve_provider(provider_id, user_id, incluir_heredadas)
        if err:
            yield f"__WARNING__:{err}"
            return

        falta = self._consentimiento_pendiente(provider, user_id)
        if falta:
            yield f"__WARNING__:{falta}"
            return

        ok, reason = provider.validate_config()
        if not ok:
            yield f"__WARNING__:{provider.name} no está disponible. {reason}"
            return

        conv = self.get_or_create_active(molecule_context, user_id=user_id)

        # `fallback_provider` describe **este** turno, no la conversación para
        # siempre. Se marcaba al caer al motor local y no se limpiaba nunca, así
        # que el turno siguiente seguía declarándose respondido por un respaldo:
        # una afirmación falsa sobre de dónde salió esa respuesta.
        conv.fallback_provider = None

        # El frontend envía el historial completo en cada request. Solo el ÚLTIMO
        # mensaje user es el turno actual; concatenar todos produce texto pegado
        # ("jelouhola qwen...") que el modelo interpreta como input corrupto.
        user_message = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_message = m.get("content", "")
                break

        if not user_message:
            yield "Error: No se recibió mensaje del usuario."
            return

        conv.add_message("user", user_message)
        self._persist_conv(conv)

        # Sanitize user message
        user_message = _sanitize_ascii(user_message)

        # Limbic: actualizar xp y mood
        try:
            from services.ai.limbic_system import on_message_sent
            on_message_sent(user_message)
        except ImportError:
            pass

        # ── Manejar respuesta "sí/no" a permiso web anterior ──
        # Si el último system message tiene __PENDING_WEB_ASK__ smiles=X,
        # el user está respondiendo a la pregunta de enriquecimiento web.
        # Procesar antes de clasificar el intent nuevo.
        _web_perm_received = False
        try:
            for rm in reversed(conv.messages):
                if rm.get("role") == "system":
                    rc = rm.get("content", "")
                    if "__PENDING_WEB_ASK__" in rc:
                        # extraer SMILES del marcador
                        import re as _re
                        mm = _re.search(r"smiles=(\S+)", rc)
                        pending_smiles = mm.group(1).rstrip(
                            " \"'\t,)" ) if mm else ""
                        lo_resp = user_message.lower().strip().strip(".,!?¿¡")
                        if lo_resp in ("sí","si","s","sí.","si.","claro","dale","ok","vale","confirmo","envialo","envía","envíalo","acepto"):
                            self._grant_smiles_web(conv, pending_smiles)
                            ack = "✅ Permiso concedido. La próxima consulta con esta molécula incluirá datos de PubChem/ChEMBL."
                            yield ack
                            conv.add_message("assistant", ack)
                            self._persist_conv(conv)
                            return  # ← no pasar al modelo: ya respondimos
                        elif lo_resp in ("no","nope","n","cancelo","cancela","negativo"):
                            conv.messages.remove(rm)  # limpiar marca
                            ack = "👌 Perfecto, mantengo todo offline. No se enviará el SMILES a internet."
                            yield ack
                            conv.add_message("assistant", ack)
                            self._persist_conv(conv)
                            return  # ← no pasar al modelo
                        break  # tomar el último __PENDING_WEB_ASK__
        except Exception as _e:
            log.warning("web_perm_handler_fail", error=str(_e)[:200])

        intent = self._route_user_intent(user_message)

        # ── Clasificador determinista: decide tool ANTES del modelo ──
        # classify() usa regex+keyword (no LLM). Si detecta tool+SMILES,
        # ejecuta directo → 0 alucinaciones, 0 falsos positivos.
        # El modelo NUNCA decide si toolear — el wrapper lo hace.
        # Solo se pasa 1 tool al prompt (o 0 si es conceptual/anáfora).
        _det_tool_executed = False
        # Texto del tool result del turno ACTUAL (clasificador determinista o
        # tools nativas). El hallucination guard lo usa como fuente de verdad
        # para verificar los valores de la respuesta — ANTES solo miraba
        # conv.molecule_context, que suele estar vacío y dejaba pasar el caso
        # "modelo repite valores de un turno anterior" (bug MT: paracetamol
        # con MW del ibuprofeno). Se re-asigna en cada rama que ejecuta tools.
        _turn_tool_text = ""
        try:
            _det = classify_intent(user_message)
            log.info("classifier", intent=_det.name, tool=_det.tool or "none",
                      smiles=(_det.smiles or "")[:20], target=(_det.target or "")[:10])

            # ── DISEÑO MOLECULAR ESPECÍFICO (F11) ────────────────────────
            # "Dame el SMILES de un análogo de penicilina con un anillo
            # oxazolidinona fusionado y un puente tioéter entre C3 y C7" es
            # un pedido de DISEÑO con requisitos estructurales complejos que
            # el sistema no puede generar con precisión. Responder honesto
            # SIN pasar por el LLM (que alucinaría un SMILES inválido que el
            # guard F5 tendría que atrapar después — mejor responder ya).
            if _det.name == "design":
                resp = (
                    "No puedo diseñar moléculas con requisitos estructurales "
                    "específicos (anillos fusionados, puentes, sustituyentes "
                    "en posiciones concretas) con precisión química. Lo que "
                    "genere podría ser inválido o no cumplir el diseño. "
                    "Lo que SÍ puedo hacer: calcular propiedades de una "
                    "molécula conocida, generar análogos BRICS de una base "
                    "(dame el SMILES), o sugerir moléculas del knowledge graph."
                )
                log.info("design_guard_honest", user=user_message[:50])
                yield resp
                conv.add_message("assistant", resp)
                self._persist_conv(conv)
                return

            # ── FUENTE VERIFICADA (F12): "cita la fuente del LogP" ──────
            # Si el usuario pide fuente/DOI/URL de una molécula, consultar
            # PubChem/ChEMBL REALES (query_verified_source) en vez de dejar
            # que el modelo invente valores con URLs falsas (bug F8).
            if _det.tool == "query_verified_source":
                resolved_web = bool(
                    allow_web or os.environ.get("MOLCHAT_ALLOW_WEB", "") == "1"
                )
                _mol_name = _find_known_molecule_name(user_message.lower()) or ""
                if not _mol_name:
                    # fallback: extraer un token con nombre de fármaco del dict
                    _mol_name = self._resolve_smiles_by_name(user_message)
                    if _mol_name:
                        _mol_name = user_message  # usar texto para la tool
                if not resolved_web:
                    resp = (
                        "Estás en modo offline — no puedo verificar fuentes "
                        "externas (PubChem/ChEMBL). Activa el modo online para "
                        "que consulte el valor real con su URL, o pedime "
                        "propiedades calculadas localmente."
                    )
                    log.info("source_offline", user=user_message[:40])
                    yield resp
                    conv.add_message("assistant", resp)
                    self._persist_conv(conv)
                    return
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _tool = _reg.get("query_verified_source")
                    if _tool and _tool.fn:
                        _target_name = _mol_name or user_message
                        log.info("tool_source_verified", molecule=_target_name[:40])
                        _r = await _tool.fn(molecule_name=_target_name)
                        _rtxt = format_tool_results([
                            {"tool": "query_verified_source", "result": _r}
                        ])
                        _turn_tool_text = _rtxt
                        yield f"\n\n{_rtxt}"
                        conv.add_message("assistant",
                            "[query_verified_source — valores con fuente]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True
                        if _r:
                            log.info("deterministic_answer", tool="query_verified_source",
                                     intent=_det.name, chars=len(_r))
                            yield _r
                            conv.add_message("assistant", _r)
                            self._persist_conv(conv)
                            return
                except Exception as _e:
                    log.warning("source_tool_fail", error=str(_e)[:200])

            # ── NAME RESOLVER HOOK (F3) ──────────────────────────────────
            # El clasificador solo conoce ~25 nombres (dict KNOWN local).
            # Para "propiedades de nicotina" o "de dapaglifocina" (nombre
            # desconocido O mal escrito) el intent cae a "unknown" o
            # "chemical" sin smiles — y el pipeline se va al LLM, que
            # responde prosa ("necesitamos obtener el SMILES...") en vez de
            # calcular. Aquí intentamos resolver el nombre con la cadena
            # completa (dict unificado -> MolGraph FTS5 -> PubChem si
            # online -> fuzzy). Si resuelve, reescribimos el intent como
            # chemical determinista y el flujo normal de abajo lo ejecuta.
            #
            # Gate de seguridad: solo disparamos si el texto pide algo
            # factual-químico (propiedades/calcular/peso/masa/logp/afinidad/
            # tpsa/...) — no gastamos tiempo ni red en preguntas
            # conceptuales desconocidas (las caen al LLM, como debe ser).
            if _det.name in ("unknown", "chemical") and (
                not _det.smiles
            ) and self._looks_factual_chemical(user_message):
                try:
                    from services.ai.name_resolver import resolve_molecule_name
                    _nr = await resolve_molecule_name(
                        user_message,
                        allow_web=bool(
                            allow_web
                            or os.environ.get("MOLCHAT_ALLOW_WEB", "") == "1"
                        ),
                    )
                    if _nr.smiles:
                        _det = _Intent(
                            "chemical",
                            smiles=_nr.smiles,
                            target=None,
                            tool="compute_properties",
                            smiles_source="name",
                        )
                        log.info("name_resolver_hit", source=_nr.source,
                                 smiles=_nr.smiles[:25], name=(_nr.matched_dict_name or ""))
                    else:
                        log.info("name_resolver_miss",
                                 error_hint=(_nr.error_hint or "")[:80])
                except Exception as _nr_err:
                    log.warning("name_resolver_fail", error=str(_nr_err)[:150])
            # ── Anáfora: resolver con contexto previo o responder directo ──
            # "esa primera molécula" / "y del paracetamol?" referencian una
            # molécula anterior. Si el texto menciona un nombre CONOCIDO
            # ("y del paracetamol?"), usar ESE SMILES (nuevo sujeto explícito).
            # Si NO menciona nombre (anáfora pura), usar el contexto previo.
            # Si no hay ni nombre ni contexto → respuesta determinista SIN
            # modelo (0 alucinación posible).
            if _det.name == "recall_anaphoric":
                anaphora_name = _find_known_molecule_name(user_message.lower())
                if anaphora_name:
                    _det.smiles = KNOWN_MOLECULES.get(anaphora_name, "")
                    _det.smiles_source = "anaphora_name"
                else:
                    # Anáfora pura sin nombre: usar molecule_context, o el
                    # último SMILES que el usuario compartió en el chat.
                    # (fix: antes solo miraba molecule_context — si estaba
                    # vacío, respondía "no tengo registro" aunque el usuario
                    # hubiera compartido un SMILES antes en la conversación).
                    _det.smiles = (conv.molecule_context or {}).get("smiles", "") or ""
                    if not _det.smiles:
                        _det.smiles = self._last_shared_smiles(conv) or ""
                        if _det.smiles:
                            _det.smiles_source = "anaphora_history"
                    else:
                        _det.smiles_source = "anaphora_context"
                if _det.smiles:
                    lo = user_message.lower()
                    if any(k in lo for k in ("afinidad", "docking")):
                        _det.tool = "run_docking"
                        _det.target = self._extract_target_pdb(user_message)
                    elif any(k in lo for k in ("similar", "analog", "análogo")):
                        _det.tool = "molgraph_similar"
                    else:
                        _det.tool = "compute_properties"
                    log.info("classifier_anaphora_resolved", tool=_det.tool,
                              smiles=_det.smiles[:30], by_name=bool(anaphora_name))
                else:
                    resp = (
                        "No tengo registro de una molécula previa en esta conversación "
                        "para responder. Indicame el SMILES o el nombre de la molécula "
                        "y la calculo."
                    )
                    yield resp
                    conv.add_message("assistant", resp)
                    self._persist_conv(conv)
                    return
            # ── Tools SIN SMILES (sesión/historial) ──
            # rank_session_molecules y query_history no reciben SMILES: operan
            # sobre la conversación actual o la DB. El clasificador las rutea
            # directamente (determinista — el modelo no decide).
            if _det.tool in ("rank_session_molecules", "query_history"):
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _tool = _reg.get(_det.tool)
                    if _tool and _tool.fn:
                        if _det.tool == "rank_session_molecules":
                            lo = user_message.lower()
                            metric = "molecular_weight"
                            order = "asc"
                            if any(k in lo for k in ("lipofil", "logp")):
                                metric = "log_p"
                                order = "desc"
                            elif "tpsa" in lo:
                                metric = "tpsa"
                            elif any(k in lo for k in ("afinidad", "aff")):
                                metric = "affinity_kcal"
                                order = "asc"  # más negativo = mejor
                            elif any(k in lo for k in ("score", "mejor")):
                                metric = "total_score"
                                order = "desc"
                            elif any(k in lo for k in ("pesada", "grande")):
                                metric = "molecular_weight"
                                order = "desc"
                            # default: menor peso molecular
                            _args = {"metric": metric, "order": order}
                            log.info("tool_classifier_session", tool=_det.tool, args=_args)
                        else:  # query_history
                            lo = user_message.lower()
                            _args = {"sort_by": "total_score", "order": "desc"}
                            if user_id:
                                _args["user_id"] = str(user_id)
                            target = self._extract_molgraph_target(user_message)
                            if target:
                                _args["target"] = target
                            # "última/último/más reciente/recién/última evaluada" →
                            # ordenar por created_at desc y limit 1: responder
                            # directo la evaluación más reciente con su score.
                            if any(k in lo for k in (
                                "ultima", "última", "ultimo", "último",
                                "mas reciente", "más reciente", "recien",
                                "recién", "acabo de", "la ultima", "el ultimo",
                            )):
                                _args["sort_by"] = "created_at"
                                _args["order"] = "desc"
                                _args["limit"] = "1"
                            elif any(k in lo for k in ("afinidad", "aff")):
                                _args["sort_by"] = "affinity_kcal"
                            elif any(k in lo for k in ("peso", "molecular", "masa")):
                                _args["sort_by"] = "molecular_weight"
                                _args["order"] = "asc"
                            elif any(k in lo for k in ("lipinski", "drug")):
                                _args["sort_by"] = "druglikeness_score"
                            log.info("tool_classifier_history", tool=_det.tool, args=_args)
                        _r = await _tool.fn(**_args)
                        _rtxt = format_tool_results([{"tool": _det.tool, "result": _r}])
                        _turn_tool_text = _rtxt
                        yield f"\n\n{_rtxt}"
                        conv.add_message("assistant",
                            f"[{_det.tool} — clasificador determinista]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True

                        # ── OPCIÓN A: respuesta DETERMINISTA en Python ──
                        # Si la pregunta es factual/comparativa, el código
                        # construye la respuesta final — el modelo NO redacta
                        # (cero posibilidad de inversión/alucinación). Si el
                        # responder devuelve None, caemos al modelo.
                        _det_answer = ""
                        try:
                            from services.ai.deterministic_responder import (
                                build_rank_response, build_history_response,
                            )
                            if _det.tool == "rank_session_molecules":
                                _det_answer = build_rank_response(user_message, _r) or ""
                            elif _det.tool == "query_history":
                                _det_answer = build_history_response(user_message, _r) or ""
                        except ImportError:
                            _det_answer = ""
                        except Exception as _de:
                            log.warning("deterministic_responder_fail",
                                        tool=_det.tool, error=str(_de)[:150])
                            _det_answer = ""
                        if _det_answer:
                            log.info("deterministic_answer", tool=_det.tool,
                                     intent=_det.name, chars=len(_det_answer))
                            yield _det_answer
                            conv.add_message("assistant", _det_answer)
                            self._persist_conv(conv)
                            return
                except Exception as _e:
                    log.warning("session_tool_fail", tool=_det.tool, error=str(_e)[:200])
            # ── EVALUACIÓN DETALLADA (F10): "desglosa el ADME de la última" ──
            # "listame las poses con RMSD", "qué Vina se usó", "residuos".
            # Los datos REALES están en la DB — el LLM no los tiene.
            if _det.tool == "query_evaluation_details":
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _tool = _reg.get("query_evaluation_details")
                    if _tool and _tool.fn:
                        _lo = user_message.lower()
                        _args: dict = {}
                        if user_id:
                            _args["user_id"] = str(user_id)
                        # Detectar filtro por target (nombre común o PDB)
                        _tgt = self._extract_molgraph_target(user_message)
                        if _tgt:
                            _args["target"] = _tgt
                            _args["which"] = "target"
                        # "primera/más antigua" vs default última
                        if any(k in _lo for k in ("primera", "mas antigua",
                                                  "más antigua", "la primera")):
                            _args["which"] = "first"
                        log.info("tool_classifier_evaluation", args=_args)
                        _r = await _tool.fn(**_args)
                        _rtxt = format_tool_results([
                            {"tool": "query_evaluation_details", "result": _r}
                        ])
                        _turn_tool_text = _rtxt
                        yield f"\n\n{_rtxt}"
                        conv.add_message("assistant",
                            "[query_evaluation_details — datos reales de la evaluación]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True
                        # Respuesta determinista directa (los datos ya están
                        # formateados — el modelo no debe redactar sobre ellos).
                        if _r:
                            log.info("deterministic_answer", tool="query_evaluation_details",
                                     intent=_det.name, chars=len(_r))
                            yield _r
                            conv.add_message("assistant", _r)
                            self._persist_conv(conv)
                            return
                except Exception as _e:
                    log.warning("evaluation_tool_fail", tool=_det.tool, error=str(_e)[:200])
            # ── SUGERIR MOLÉCULAS (F7): "dame un smiles interesante" / ──
            # "para X receptor" / "variante de X" → tool suggest_smiles.
            # Cruza con MolGraph (selección aleatoria — nunca repite SMILES).
            if _det.tool == "suggest_smiles":
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _tool = _reg.get("suggest_smiles")
                    if _tool and _tool.fn:
                        _mode = _det.suggest_mode or "interesting"
                        _args: dict = {"mode": _mode}
                        if _mode == "for_target":
                            # Resolver nombre común del receptor → PDB ID
                            _target_pdb = self._extract_target_pdb(user_message)
                            if _target_pdb:
                                _args["target"] = _target_pdb
                            else:
                                _args["target"] = _det.suggest_target or ""
                        elif _mode == "variant":
                            # Resolver molécula base por nombre → SMILES
                            _base_smiles = _det.smiles or (
                                self._resolve_smiles_by_name(user_message) or ""
                            )
                            if _base_smiles:
                                _args["smiles"] = _base_smiles
                            else:
                                # Usar el nombre crudo como hint (el tool lo
                                # intentará resolver por nombre también)
                                _args["smiles"] = _det.suggest_target or user_message
                        log.info("tool_classifier_suggest", mode=_mode, args=_args)
                        _r = await _tool.fn(**_args)
                        _rtxt = format_tool_results([{"tool": "suggest_smiles", "result": _r}])
                        _turn_tool_text = _rtxt
                        conv.add_message("assistant",
                            f"[suggest_smiles — {_mode} determinista]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True
                        # La tool ya devuelve el resultado formateado — lo
                        # servimos UNA sola vez (el tool result envuelto en
                        # [suggest_smiles: ...] es el texto visible correcto;
                        # antes se emitía 2 veces: el _rtxt Y el _r crudo).
                        if _r:
                            log.info("deterministic_answer", tool="suggest_smiles",
                                     intent=_det.name, chars=len(_r))
                            yield f"\n\n{_rtxt}"
                            conv.add_message("assistant", _r)
                            self._persist_conv(conv)
                            return
                except Exception as _e:
                    log.warning("suggest_tool_fail", tool=_det.tool, error=str(_e)[:200])
            # ── COMPARACIÓN N-MOLÉCULAS (F6): "compárame A, B y C" ──
            # El clasificador llenó smiles_list con >=3 SMILES. Ejecutamos
            # compute_properties para CADA una (determinista, ~60ms c/u) y
            # armamos la tabla comparativa. El 1.5B no puede comparar N>2
            # sin mezclar valores (bug original: solo computó amlodipino de
            # "amlodipino, nifedipino y felodipino").
            if (
                _det.tool == "compare_molecules"
                and _det.smiles_list
                and len(_det.smiles_list) >= 3
            ):
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _compute = _reg.get("compute_properties")
                    if _compute and _compute.fn:
                        _rows: list[dict] = []
                        for _smi in _det.smiles_list:
                            _r = await _compute.fn(smiles=_smi)
                            # Nombre legible: buscar el nombre del dict por SMILES,
                            # o usar el SMILES corto si no se conoce.
                            _nm = ""
                            for _nm_cand, _sm_cand in KNOWN_MOLECULES.items():
                                if _sm_cand == _smi:
                                    _nm = _nm_cand
                                    break
                            _rows.append({
                                "smiles": _smi,
                                "name": _nm or _smi[:20],
                                "result": _r,
                            })
                        _rtxt = format_tool_results([
                            {"tool": "compute_properties", "result": r["result"]}
                            for r in _rows
                        ])
                        _turn_tool_text = _rtxt
                        yield f"\n\n{_rtxt}"
                        conv.add_message("assistant",
                            f"[Comparando {len(_rows)} moléculas — clasificador determinista]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True

                        # ── OPCIÓN A: tabla comparativa determinista ──
                        try:
                            from services.ai.deterministic_responder import (
                                build_multi_compare_response,
                            )
                            _det_answer = build_multi_compare_response(
                                user_message, _rows
                            ) or ""
                        except ImportError:
                            _det_answer = ""
                        except Exception as _de:
                            log.warning("deterministic_responder_fail",
                                        tool="compare_molecules",
                                        error=str(_de)[:150])
                            _det_answer = ""
                        if _det_answer:
                            log.info("deterministic_answer", tool="compare_molecules",
                                     intent=_det.name, chars=len(_det_answer),
                                     molecules=len(_rows))
                            yield _det_answer
                            conv.add_message("assistant", _det_answer)
                            self._persist_conv(conv)
                            return
                except Exception as _e:
                    log.warning("multi_compare_fail", error=str(_e)[:200])
            if _det.tool and _det.smiles:
                try:
                    from services.ai.tool_registry import (
                        get_tool_registry, format_tool_results,
                    )
                    _reg = get_tool_registry()
                    _tool = _reg.get(_det.tool)
                    if _tool and _tool.fn:
                        _args = {"smiles": _det.smiles}
                        # COMPARACIÓN: compare_molecules necesita AMBOS SMILES.
                        # Fix: antes el clasificador solo resolvía UN nombre y
                        # ejecutaba compute_properties con una molécula — el
                        # modelo inventaba la otra de memoria.
                        if _det.tool == "compare_molecules" and _det.smiles_b:
                            _args = {
                                "smiles_a": _det.smiles,
                                "smiles_b": _det.smiles_b,
                            }
                        # MOLGRAPH: query_molgraph busca por target o query de
                        # texto, no por SMILES. Extraer el target del mensaje.
                        elif _det.tool == "query_molgraph":
                            _target = self._extract_molgraph_target(user_message)
                            # Factor X: solo randomizar cuando el usuario pidió
                            # exploración SIN orden explícito. "top 5", "mejores",
                            # "ranking", "mayor/menor" → determinista (hechos).
                            _randomize = not any(
                                k in user_message.lower() for k in (
                                    "top", "mejores", "mejor", "ranking", "ordenar",
                                    "mayor", "menor", "maximo", "máximo", "minimo",
                                    "mínimo", "primero", "primeras",
                                )
                            )
                            if _target:
                                _args = {"target": _target}
                            else:
                                # "top 5 moleculas por score" → top global
                                import re as _re
                                top_m = _re.search(r'top\s*(\d+)', user_message, _re.IGNORECASE)
                                if top_m:
                                    _args = {"limit": top_m.group(1)}
                                    _randomize = False
                                else:
                                    _args = {"query": user_message}
                            if _randomize:
                                _args["randomize"] = "true"
                        if _det.target and _det.tool == "run_docking":
                            _args["target_pdb"] = _det.target
                        # Identidad inyectada por el servidor; nunca se acepta
                        # desde los argumentos generados por el LLM. La regla es
                        # de firma, no de lista de nombres.
                        from services.ai.tool_registry import _imponer_identidad
                        _imponer_identidad(
                            _tool, _args, str(user_id) if user_id else None
                        )
                        # ── Factor X: aleatoriedad en tools de EXPLORACIÓN ──
                        # molgraph_similar / molgraph_neighbors muestran un
                        # subset de candidatos reales. Si el usuario pidió
                        # exploración SIN orden explícito, randomizar para que
                        # MolChat nunca repita la misma lista. "top/mejor/
                        # ranking/más" → determinista (hechos verificables).
                        if _det.tool in ("molgraph_similar", "molgraph_neighbors"):
                            _lo = user_message.lower()
                            _randomize = not any(
                                k in _lo for k in (
                                    "top", "mejores", "mejor", "ranking",
                                    "ordenar", "mayor", "menor", "maximo",
                                    "máximo", "minimo", "mínimo",
                                    "primero", "primeras", "mas similar",
                                    "más similar", "mas parecida",
                                    "más parecida", "mas cercana",
                                    "más cercana",
                                )
                            )
                            if _randomize:
                                _args["randomize"] = "true"
                        log.info("tool_classifier_direct", tool=_det.tool,
                                  args={k: (v or "")[:40] for k, v in _args.items()})
                        _r = await _tool.fn(**_args)
                        # Registrar el NOMBRE de la molécula en el tool result
                        # (si se conoce) para que el guard pueda verificar las
                        # ASIGNACIONES nombre→valor, no solo que el número exista.
                        # Ej: "y del paracetamol?" → "compute_properties
                        # (paracetamol): MW: 151.2 Da, ..." — el guard usa este
                        # nombre para atrapar "paracetamol: 206.3 Da" (inversión).
                        _tool_label = (
                            anaphora_name
                            if _det.name == "recall_anaphoric" and anaphora_name
                            else _find_known_molecule_name(user_message.lower()) or ""
                        )
                        if _det.tool == "compare_molecules" and _det.smiles_b:
                            # Comparación: registrar los DOS nombres reales.
                            # (fix: antes name_b quedaba vacío o mezclaba nombres
                            # porque usaba el SMILES crudo — el guard necesita
                            # los nombres para verificar asignaciones A/B).
                            def _name_for_smiles(smi: str) -> str:
                                for nm, sm in KNOWN_MOLECULES.items():
                                    if sm == smi:
                                        return nm
                                return smi[:20]

                            name_a = _name_for_smiles(_det.smiles)
                            name_b = _name_for_smiles(_det.smiles_b)
                            _rtxt = (
                                "\n[Sistema: resultados de herramientas ejecutadas:]\n"
                                f"{_det.tool} (A={name_a} | B={name_b}): {_r}"
                            )
                        elif _tool_label:
                            _rtxt = (
                                "\n[Sistema: resultados de herramientas ejecutadas:]\n"
                                f"{_det.tool} ({_tool_label}): {_r}"
                            )
                        else:
                            _rtxt = format_tool_results([{"tool": _det.tool, "result": _r}])
                        _turn_tool_text = _rtxt
                        yield f"\n\n{_rtxt}"
                        conv.add_message("assistant",
                            f"[{_det.tool} — clasificador determinista]")
                        conv.add_message("system", _rtxt)
                        self._persist_conv(conv)
                        _det_tool_executed = True

                        # ── OPCIÓN A: respuesta DETERMINISTA en Python ──
                        # compare_molecules y compute_properties también tienen
                        # respuestas construidas por código (cero redacción libre).
                        _det_answer = ""
                        try:
                            from services.ai.deterministic_responder import (
                                build_compare_response, build_properties_response,
                            )
                            if _det.tool == "compare_molecules":
                                # build_compare_response busca el header
                                # "(A=... | B=...)" que el chat_service inyecta en
                                # _rtxt (líneas 1296-1299), NO en _r crudo.
                                # Pasar _rtxt para que el determinista matchee.
                                _det_answer = build_compare_response(user_message, _rtxt) or ""
                            elif _det.tool == "compute_properties":
                                _det_answer = build_properties_response(_rtxt) or ""
                        except ImportError:
                            _det_answer = ""
                        except Exception as _de:
                            log.warning("deterministic_responder_fail",
                                        tool=_det.tool, error=str(_de)[:150])
                            _det_answer = ""
                        if _det_answer:
                            log.info("deterministic_answer", tool=_det.tool,
                                     intent=_det.name, chars=len(_det_answer))
                            yield _det_answer
                            conv.add_message("assistant", _det_answer)
                            self._persist_conv(conv)
                            return

                    # ════════════════════════════════════════════════════
                    # WEB ENRICHMENT (FASE 1b/1c/1d)
                    # Solo cuando allow_web=Y la tool se ejecutó offline.
                    # Reglas de privacidad:
                    #   - smiles_source in {explicit, name, anaphora_name}
                    #     → seguro: user ya compartió el dato en chat → enriquecer
                    #   - smiles_source="anaphora_context"
                    #     → SMILES vino de molecule_context privado → PREGUNTAR
                    # NO enviamos target_pdb ni resultados de docking a la web —
                    # solo SMILES (o nombre) del ligando, y solo el target si la
                    # tool search_pdb lo necesita (PDB IDs ya son públicos).
                    # ═══════════════════════════════════════════════════└
                    if (
                        _det_tool_executed
                        and (allow_web or os.environ.get("MOLCHAT_ALLOW_WEB","") == "1")
                        and _det.smiles
                    ):
                        try:
                            web_text, ask_perm = await self._web_enrich(
                                user_message, _det, conv,
                            )
                            if web_text:
                                yield web_text
                                conv.add_message("system", web_text)
                                self._persist_conv(conv)
                                log.info("web_enriched", smiles_source=_det.smiles_source,
                                          extra_chars=len(web_text))
                            if ask_perm:
                                # Marcador invisible para el frontend: lo detecta y muestra
                                # botones clickeables "Sí, consultar" / "No" en lugar de
                                # obligar al user a escribir "sí"/"no" manualmente.
                                prompt = (
                                    "\n\n📎 **Modo web:** Esta molécula no está en la base local. "
                                    "Para enriquecer la respuesta con PubChem/ChEMBL enviaría "
                                    "el SMILES a internet (solo el SMILES, sin datos de docking "
                                    "ni resultados). ¿Activar enriquecimiento para esta molécula?\n\n"
                                    f"<!--__PENDING_WEB_ASK__ smiles={_det.smiles[:60]}-->"
                                )
                                yield prompt
                                conv.add_message("assistant", prompt)
                                conv.add_message("system",
                                    f"__PENDING_WEB_ASK__ smiles={_det.smiles[:60]}")
                                self._persist_conv(conv)
                        except Exception as _we:
                            log.warning("web_enrich_fail", error=str(_we)[:200])
                    elif _det_tool_executed and _det.tool == "run_docking" and _det.target:
                        # Docking sin allow_web: aún podemos enriquecer el PDB target
                        # (búsqueda pública via search_pdb, sin necesidad de permiso —
                        # el PDB ID ya estaba en el texto del user y es público).
                        # Solo si estamos en modo allow_web.
                        pass  # skip: en offline no web
                except Exception as _e:
                    log.warning("classifier_tool_fail", error=str(_e)[:200])
        except Exception as _ce:
            log.warning("classifier_failed", error=str(_ce)[:200])
            _det_tool_executed = False

        # ── Si el clasificador decidió NO-tool (conceptual/invalid/unknown/
        # recall sin contexto): el modelo NO ve ninguna tool. El clasificador
        # es autoritativo en AMBOS sentidos — decide tool (ejecuta directo)
        # O decide no-tool (bloquea tools del modelo). Esto evita que el
        # modelo 1-bit llame pubchem_lookup en "calcula propiedades de
        # KILLMEnow" (bug I005 en run ONLINE: calls=1 en query de basura).
        _det_no_tool = (
            _det_tool_executed
            or getattr(_det, "name", "") in (
                "conceptual", "invalid_smiles", "unknown",
                "recall_molecular", "docking_missing", "recall_anaphoric",
                "rank_session", "query_history",
            )
        )

        # ── Factual mode: ejecutar herramienta ANTES de que el LLM hable ──
        if intent == "factual" and conv.molecule_context:
            factual = await self._handle_factual_query(user_message, conv)
            if factual:
                conv.add_message("system", factual)
                self._persist_conv(conv)

        # Dynamic max_tokens: limitar verbosidad segun complejidad + modo
        if mode == "speed":
            max_tok = {"tool": 128, "memory": 256, "complex": 256,
                       "complex_chemistry": 512}.get(intent, 128)
        else:
            max_tok = {"tool": 256, "memory": 384, "complex": 1024,
                       "complex_chemistry": 2048}.get(intent, 1024)
        if max_tok != provider.config.max_tokens:
            provider.config.max_tokens = max_tok

        # Context compression activa via _quick_compress (local, 0 tokens LLM)
        # get_recent_and_compressed actualiza conv.summary automaticamente

        context_memory = self.build_context_memory(
            user_message, user_id=user_id, incluir_heredadas=incluir_heredadas
        )

        # ── Function calling nativo (solo provider local con --jinja) ──
        # Si el modelo responde con tool_calls, las ejecutamos y reinyectamos
        # el resultado antes de streamear la respuesta final al usuario.
        use_native_tools = False
        tool_results_injected = False
        if provider.id == "local":
            try:
                from services.ai.tool_registry import (
                    get_tool_registry, execute_tool_step, format_tool_results,
                )
                tool_registry = get_tool_registry()
                # Modo online: si allow_web=True (o env MOLCHAT_ALLOW_WEB=1),
                # exponemos TAMBIEN las tools con offline=False (PubChem, ChEMBL,
                # RCSB, UniProt, BindingDB). Antes esto estaba HARDCODEADO en
                # offline_only=True — el modelo nunca veia las tools web y por
                # eso alucinaba "de memoria" (ej. MT005 invento MW/logP del
                # paracetamol en el deep-replay porque no podia consultarlo).
                resolved_allow_web = allow_web or os.environ.get("MOLCHAT_ALLOW_WEB", "") == "1"
                tools_openai = tool_registry.get_tools_openai(offline_only=not resolved_allow_web)
                if tools_openai and hasattr(provider, "chat_with_tools"):
                    use_native_tools = True
                # Si el clasificador decidió (tool ejecutada O no-tool),
                # no pasar tools al modelo — es autoritativo en ambos sentidos.
                if _det_no_tool:
                    use_native_tools = False
            except ImportError:
                pass

        messages_for_api = self._prepare_messages_with_context(
            conv, user_message, context_memory, "",
            include_tools=not use_native_tools and not _det_no_tool,
            include_engram=True,
            incluir_heredadas=incluir_heredadas,
            allow_web=allow_web,
        )

        # Intentar function calling nativo
        if use_native_tools:
            try:
                tc_response = await provider.chat_with_tools(
                    messages=messages_for_api,
                    tools=tools_openai,
                )
                tool_calls = tc_response.get("tool_calls", [])
                if tool_calls:
                    results = []
                    for tc in tool_calls:
                        name = tc["name"]
                        args = tc["arguments"]
                        tool = tool_registry.get(name)
                        if not tool or not tool.fn:
                            results.append({"tool": name, "error": f"Tool '{name}' no encontrada"})
                            continue
                        # SMILES guard: validar antes de ejecutar.
                        # El modelo puede alucinar:
                        #  (a) un SMILES sintacticamente válido pero química
                        #      inválida (repetición de motifs: CC(=O)C(=O)C(=O)...).
                        #  (b) args JSON no parseables → wrapper mete {"_raw": "...JSON..."}
                        #      y la tool falla con "unexpected kwarg _raw".
                        # Determinismo: si no podemos extraer un SMILES válido
                        # de los args, NO ejecutamos la tool — el modelo queda
                        # sin datos, el usuario ve "no tengo datos verificados".
                        if name != "validate_smiles":
                            # Re-aplanar _raw a dict si el modelo emitió args
                            # inparesables (bug visto en R006 deep-replay).
                            if "_raw" in args and len(args) == 1:
                                try:
                                    import json as _json
                                    repaired = _json.loads(args["_raw"])
                                    if isinstance(repaired, dict):
                                        args = repaired
                                except _json.JSONDecodeError:
                                    pass
                            smiles_arg = args.get("smiles") or args.get("init_smiles")
                            if smiles_arg:
                                from services.ai.tool_registry import _guard_validate_smiles
                                valid, canon, err = _guard_validate_smiles(smiles_arg)
                                if not valid:
                                    results.append({
                                        "tool": name,
                                        "error": f"SMILES invalido '{smiles_arg[:40]}': {err}",
                                    })
                                    continue
                                for k in ("smiles", "init_smiles"):
                                    if k in args:
                                        args[k] = canon
                                        break
                            else:
                                # Args sin SMILES plausible en una tool química:
                                # el modelo alucinó o no entendió el formato.
                                # No ejecutamos la tool — safe default.
                                results.append({
                                    "tool": name,
                                    "error": (
                                        "no se pudo extraer un SMILES válido "
                                        f"de los argumentos {str(args)[:80]}"
                                    ),
                                })
                                continue
                        try:
                            # La identidad la pone el servidor para CUALQUIER
                            # herramienta que la acepte, no para una lista de
                            # nombres que hay que acordarse de ampliar: al
                            # separar el grafo (MOLCHAT-BE-009) aparecieron
                            # ocho herramientas más que la reciben.
                            from services.ai.tool_registry import _imponer_identidad
                            _imponer_identidad(
                                tool, args, str(user_id) if user_id else None
                            )
                            log.info("tool_executed_native", tool=name, args=args)
                            r = await tool.fn(**args)
                            results.append({"tool": name, "result": r})
                        except Exception as e:
                            results.append({"tool": name, "error": str(e)[:200]})

                    if results:
                        result_text = format_tool_results(results)
                        _turn_tool_text = result_text
                        yield f"\n\n{result_text}"
                        conv.add_message("assistant",
                            tc_response.get("content", "") or
                            f"[Llamando {len(tool_calls)} herramienta(s)]")
                        conv.add_message("system", result_text)
                        self._persist_conv(conv)
                        # Re-construir mensajes con resultados inyectados
                        messages_for_api = self._prepare_messages_with_context(
                            conv, user_message, context_memory, "",
                            include_tools=False,
                            include_engram=True,
                            incluir_heredadas=incluir_heredadas,
                            allow_web=allow_web,
                        )
                        tool_results_injected = True
                # ── Force-tool fallback: si intent quimico y el modelo NO llamo
                # tools pero el user escribio un SMILES explicito, forzar
                # compute_properties con el SMILES canonico. Esto cierra el
                # bug arquitectonico de alucinaciones del 1-bit: el modelo
                # decide libremente si toolear — en MolChat, las queries
                # quimicas con SMILES en el mensaje DEBEN pasar por la tool.
                #
                # F2 (extensión determinista docking): si intent=docking
                # + hay SMILES + hay target_pdb en el mensaje del usuario,
                # forzar run_docking en lugar de compute_properties.
                # El target se detecta con regex: "contra 7E2Y", "target 6LU7".
                if not tool_calls and self._should_force_tool(intent):
                    smiles = self._extract_smiles_from_message(user_message)
                    if not smiles:
                        smiles = self._resolve_smiles_by_name(user_message)
                    if smiles:
                        target_pdb = ""
                        if intent == "docking":
                            target_pdb = self._extract_target_pdb(user_message)
                            # ── F4: target no resuelto → respuesta honesta ──
                            # El usuario pidió docking contra un nombre que no
                            # reconocemos. No ejecutar compute_properties como
                            # fallback silencioso (eso producía el error crudo
                            # "Pipeline de docking no disponible" que el LLM
                            # luego leía). Responder determinista con la lista
                            # de targets disponibles.
                            if not target_pdb:
                                try:
                                    from services.ai.target_resolver import (
                                        list_available_targets,
                                    )
                                    _avail = list_available_targets(limit=6)
                                except Exception:
                                    _avail = []
                                _target_hint = (
                                    "No reconozco el target del docking. "
                                    "Indícame el receptor por nombre común "
                                    "(ej: 'receptor de serotonina', 'CYP3A4', "
                                    "'JAK2') o por PDB ID (ej: '7E2Y')."
                                )
                                if _avail:
                                    _target_hint += "\n\nTargets disponibles:\n" + "\n".join(_avail[:6])
                                log.info("docking_target_unresolved",
                                         intent=intent, smiles=smiles[:20])
                                yield _target_hint
                                conv.add_message("assistant", _target_hint)
                                self._persist_conv(conv)
                                return
                        try:
                            # Determinismo por intent: docking → run_docking,
                            # el resto → compute_properties.
                            if intent == "docking" and target_pdb:
                                docking = tool_registry.get("run_docking")
                                if docking and docking.fn:
                                    log.info("tool_forced_docking", intent=intent,
                                             smiles=smiles, target_pdb=target_pdb)
                                    r = await docking.fn(
                                        smiles=smiles,
                                        target_pdb=target_pdb,
                                        user_id=str(user_id) if user_id else None,
                                    )
                                    results = [{"tool": "run_docking", "result": r}]
                                    result_text = format_tool_results(results)
                                    _turn_tool_text = result_text
                                    # MOLCHAT-INT-001 / D-08: la respuesta de
                                    # una evaluación lanzada es determinista y
                                    # cierra el turno. Dejar que el modelo la
                                    # reescriba es dejar que convierta «la
                                    # lancé, todavía no hay número» en un
                                    # número — exactamente lo que D-08 dice
                                    # que la herramienta existe para evitar.
                                    conv.add_message("system", result_text)
                                    yield r
                                    conv.add_message("assistant", r)
                                    self._persist_conv(conv)
                                    return
                            else:
                                # Default: compute_properties (tool, complex_chemistry, factual)
                                log.info("tool_forced_fallback", intents=intent, smiles=smiles)
                                compute = tool_registry.get("compute_properties")
                                if compute and compute.fn:
                                    r = await compute.fn(smiles=smiles)
                                    results = [{"tool": "compute_properties", "result": r}]
                                    result_text = format_tool_results(results)
                                    _turn_tool_text = result_text
                                    yield f"\n\n{result_text}"
                                    conv.add_message("assistant",
                                        "[Ejecutando compute_properties forzado por validez]")
                                    conv.add_message("system", result_text)
                                    self._persist_conv(conv)
                                    messages_for_api = self._prepare_messages_with_context(
                                        conv, user_message, context_memory, "",
                                        include_tools=False,
                                        include_engram=True,
                                        incluir_heredadas=incluir_heredadas,
                                        allow_web=allow_web,
                                    )
                                    tool_results_injected = True
                        except Exception as e:
                            log.warning("tool_forced_fallback_failed", error=str(e)[:200])
            except ImportError:
                pass
            except Exception as e:
                log.warning("native_tool_call_failed", error=str(e)[:200])

        try:
            full_response = ""
            async for token in provider.chat(messages=messages_for_api, stream=True):
                full_response += token
                yield token

            # Hallucination guard: verificar números después de la respuesta.
            # CUBRE DOS CASOS:
            #  1. El LLM dijo un valor numérico distinto del real del contexto.
            #  2. El LLM afirmó datos químicos (MW/LogP/TPSA/afinidad...) SIN haber
            #     ejecutado ninguna tool nativa en esta pasada → fabricación.
            # Fix 1: tool_was_executed ahora incluye el clasificador determinista
            # (_det_tool_executed), que ANTES solo miraba las tools nativas del
            # modelo (tool_results_injected) → falso positivo "ninguna herramienta
            # se ejecutó" cuando el clasificador SÍ ejecutó compute_properties.
            # Fix 2: pasamos el tool result del turno actual (turn_tool_text) como
            # fuente de verdad para verificar los valores de la respuesta.
            # Fix 3: history_tool_text acumula los tool results de TODA la
            # conversación — un claim que coincide con valores ya verificados en
            # turnos previos NO es fabricación (el modelo recordó datos reales).
            history_tool_text = " ".join(
                m.get("content", "")
                for m in conv.messages
                if m.get("role") == "system"
                and "Sistema: resultados de herramientas ejecutadas" in m.get("content", "")
            )
            correction = self._verify_numerical_claims(
                full_response,
                conv.molecule_context,
                tool_was_executed=(_det_tool_executed or tool_results_injected),
                turn_tool_text=_turn_tool_text,
                history_tool_text=history_tool_text,
            )
            if correction:
                yield correction
                conv.add_message("system", correction)
                self._persist_conv(conv)

            # ── F5: guard de SMILES post-LLM ───────────────────────────
            # El system prompt le dice al modelo que valide SMILES con
            # 'validate_smiles', pero un 1.5B lo ignora (inventó
            # "C(C)(S)C(C)(S)C(C)(S)C" para un péptido cíclico — sintácticamente
            # válido pero SIN amidas ni anillos, y para un "polímero infinito
            # pequeño" que es una contradicción). Este guard valida los SMILES
            # propuestos y reemplaza la respuesta con honestidad cuando no
            # cumplen el pedido.
            smiles_correction = self._verify_smiles_claims(
                user_message, full_response,
            )
            if smiles_correction:
                honest = (
                    "No puedo generar ese SMILES con precisión: lo que "
                    "propuse no cumple el pedido o es químicamente "
                    "imposible. Si me das una molécula conocida (nombre o "
                    "SMILES), puedo calcular sus propiedades, generar "
                    "análogos o buscar su bioactividad."
                )
                log.info("smiles_guard_caught", user=user_message[:40])
                yield honest
                conv.add_message("assistant", honest)
                self._persist_conv(conv)
                return

            if full_response:
                # ── Tool interceptor recursivo (max 3 LLM calls) ─────
                async for token in self._handle_tool_loop(conv, provider, full_response):
                    yield token
                return

        except Exception as e:
            log.warning("chat_provider_failed", provider=provider.id, error=str(e))
            fallback = registry.resolve_for_user("local", user_id, incluir_heredadas)
            if fallback and fallback is not provider and fallback.validate_config()[0]:
                conv.fallback_provider = "local"
                warning = f"⚠️ {provider.name} falló. Usando modo local como respaldo."
                yield f"__WARNING__:{warning}"
                async for token in fallback.chat(messages=messages_for_api, stream=True):
                    full_response += token
                    yield token
                if full_response:
                    # Guard sobre la respuesta del fallback (fix: antes se
                    # servía sin verificar — si el modelo local alucinaba
                    # valores en el fallback, nadie lo atrapaba).
                    history_tool_text = " ".join(
                        m.get("content", "")
                        for m in conv.messages
                        if m.get("role") == "system"
                        and "Sistema: resultados de herramientas ejecutadas" in m.get("content", "")
                    )
                    correction = self._verify_numerical_claims(
                        full_response,
                        conv.molecule_context,
                        tool_was_executed=(_det_tool_executed or tool_results_injected),
                        turn_tool_text=_turn_tool_text,
                        history_tool_text=history_tool_text,
                    )
                    if correction:
                        yield correction
                        conv.add_message("system", correction)
                        self._persist_conv(conv)
                    conv.add_message("assistant", full_response)
                    self._persist_conv(conv)

                # Siempre limpiar tool markers del texto visible
                try:
                    from services.ai.tool_registry import strip_tool_markers
                    cleaned = strip_tool_markers(full_response).strip()
                    if cleaned and cleaned != full_response.strip():
                        visible_text = cleaned
                except ImportError:
                    pass
            else:
                yield f"\n\nError generando respuesta: {str(e)[:200]}"

    async def _handle_tool_loop(self, conv: Conversation, provider: Any,
                                  full_response: str) -> AsyncIterator[str]:
        """Ejecutar tools en hasta 2 rondas recursivas (máx 3 LLM calls total).

        Cada respuesta generada en una ronda recursiva PASA POR EL HALLUCINATION
        GUARD (fix: antes la respuesta final del loop se servía sin verificar —
        si el modelo alucinaba valores en ronda 2-3, nadie lo atrapaba).
        """
        max_rounds = 2
        # True si el loop ejecutó al menos una ronda con tools (respuesta
        # recursiva nueva). El guard final solo corre en ese caso — si el loop
        # terminó en ronda 0 sin tools, la respuesta ya fue verificada por el
        # guard principal de chat() (fix: antes se verificaba 2 veces y la
        # corrección se duplicaba en el stream).
        _any_tool_round = False

        def _history_tool_text() -> str:
            return " ".join(
                m.get("content", "")
                for m in conv.messages
                if m.get("role") == "system"
                and "Sistema: resultados de herramientas ejecutadas" in m.get("content", "")
            )

        for round_num in range(max_rounds):
            try:
                from services.ai.tool_registry import (
                    execute_tool_step, format_tool_results,
                    strip_tool_markers, get_tool_registry,
                )
                tool_registry = get_tool_registry()
                # Gate de MolChat: lo que se ejecuta aqui lo escribio el
                # modelo, y el turno lleva dentro texto de terceros. La
                # identidad la impone la conversacion, nunca los argumentos.
                tool_results = await execute_tool_step(
                    tool_registry, full_response, identidad=conv.user_id
                )

                if not tool_results:
                    # No more tools → guardar respuesta limpia y terminar
                    clean = strip_tool_markers(full_response).strip() or full_response
                    # Guard sobre la respuesta final del loop. SOLO si esta
                    # respuesta NO fue ya verificada por el guard principal de
                    # chat() (ronda 0: la respuesta vino del provider directo
                    # y ya pasó por _verify_numerical_claims). En rondas 1+
                    # (respuestas generadas tras inyectar tool results) SÍ
                    # verificamos — es una respuesta nueva sin revisar.
                    if round_num > 0:
                        correction = self._verify_numerical_claims(
                            clean,
                            conv.molecule_context,
                            tool_was_executed=True,  # el loop ya ejecutó tools antes
                            turn_tool_text="",
                            history_tool_text=_history_tool_text(),
                        )
                        if correction:
                            yield correction
                            conv.add_message("system", correction)
                            self._persist_conv(conv)
                    conv.add_message("assistant", clean)
                    self._persist_conv(conv)
                    return

                result_text = format_tool_results(tool_results)
                _any_tool_round = True
                yield f"\n\n🔧 {result_text}"

                visible = strip_tool_markers(full_response).strip()
                conv.add_message("assistant", visible)
                conv.add_message("system", result_text)
                self._persist_conv(conv)

                messages_for_api = self._prepare_messages_with_context(
                    conv,
                    f"[Ronda {round_num + 1}: continúa con los resultados. "
                    f"Si necesitas más herramientas, úsalas. Si no, responde al usuario.]",
                    self.build_context_memory(user_id=conv.user_id), "",
                )
                full_response = ""
                async for token in provider.chat(
                    messages=messages_for_api, stream=True,
                ):
                    full_response += token
                    yield token

                # Guard sobre la respuesta de esta ronda recursiva: el modelo
                # pudo inventar valores sobre el tool result recién inyectado.
                correction = self._verify_numerical_claims(
                    full_response,
                    conv.molecule_context,
                    tool_was_executed=True,
                    turn_tool_text=result_text,
                    history_tool_text=_history_tool_text(),
                )
                if correction:
                    yield correction
                    conv.add_message("system", correction)
                    self._persist_conv(conv)
            except ImportError:
                break

        # Último turno: guardar la respuesta final. El guard final solo corre
        # si hubo rondas con tools — si no, la respuesta ya fue verificada por
        # chat() (y duplicar la corrección ensucia el stream).
        try:
            from services.ai.tool_registry import strip_tool_markers
            clean = strip_tool_markers(full_response).strip() or full_response
            if _any_tool_round:
                correction = self._verify_numerical_claims(
                    clean,
                    conv.molecule_context,
                    tool_was_executed=True,
                    turn_tool_text="",
                    history_tool_text=_history_tool_text(),
                )
                if correction:
                    yield correction
                    conv.add_message("system", correction)
                    self._persist_conv(conv)
            conv.add_message("assistant", clean)
        except ImportError:
            conv.add_message("assistant", full_response.strip())
        self._persist_conv(conv)

    # ── Hallucination Guard (Cerebelo) ──────────────────────────

    def _verify_numerical_claims(
        self,
        text: str,
        context: dict | None,
        tool_was_executed: bool = False,
        turn_tool_text: str = "",
        history_tool_text: str = "",
    ) -> str:
        """
        Verificar que los números mencionados por el LLM coincidan
        con los datos reales del contexto. Si difieren >10%, corregir.

        Además, si el LLM afirmó datos químicos (MW/LogP/TPSA/afinidad/...)
        SIN que ninguna tool nativa se haya ejecutado en esta pasada, lo
        marcamos como fabricación — PERO solo si el valor no coincide con
        ningún valor verificado en el historial de la conversación (el modelo
        puede recordar datos reales de turnos previos).

        turn_tool_text: tool result del turno ACTUAL (clasificador determinista
        o tools nativas). Fuente de verdad para verificar los valores de la
        respuesta — sin esto, el guard solo miraba conv.molecule_context (suele
        estar vacío) y dejaba pasar el caso "modelo repite valores de un turno
        anterior" (ej. paracetamol con MW del ibuprofeno).
        """
        import re as _re
        corrections = []
        if text:
            # Valores REALES del tool result del turno actual y del historial
            # acumulado de la conversación (turnos previos ya verificados).
            # Cada key mapea a una LISTA de valores (puede haber varias
            # moléculas en el historial: aspirina 180.2, ibuprofeno 206.3, ...).
            turn_values = self._parse_tool_result_values(turn_tool_text)
            history_values = self._parse_tool_result_values(history_tool_text)
            known_by_key: dict[str, list[float]] = {}
            for vals in (turn_values, history_values):
                for k, v in vals.items():
                    # v ya es una lista → extend, no append (append crearía
                    # listas anidadas y rompería la comparación).
                    known_by_key.setdefault(k, []).extend(v)

            # Fabrication detection: claims sin tool ejecutada en esta pasada.
            if not tool_was_executed:
                for pat in _FABRICATION_MARKERS:
                    for m in _re.finditer(pat, text, _re.IGNORECASE):
                        # Algunos markers no tienen grupo de captura → extraer
                        # el primer número del match para verificar vs historial.
                        try:
                            claimed = float(m.group(1))
                        except (ValueError, IndexError):
                            nums = _re.findall(r"[-+]?\d+\.?\d*", m.group(0))
                            claimed = float(nums[0]) if nums else None
                        if claimed is not None and self._value_in_history(
                            claimed, known_by_key
                        ):
                            continue  # valor real del historial → permitido
                        corrections.append(
                            "mencionaste valores químicos (MW/LogP/TPSA/afinidad) "
                            "pero ninguna herramienta se ejecutó en esta pasada "
                            "y el valor no está en los datos verificados — "
                            "esos valores no están confirmados"
                        )
                        break  # una sola corrección de fabricación basta
                    else:
                        continue
                    break

            # ── Verificación de ASIGNACIONES nombre→valor (SIEMPRE, con o sin
            # tool en esta pasada) ─────────────────────────────────────────
            # Atrapa el caso más peligroso: el modelo INVIERTE o INVENTA valores
            # POR MOLÉCULA citando el nombre ("Amlodipino: LogP 0.83" cuando el
            # real verificado es 2.66). Esto corre TAMBIÉN cuando tool_was_executed
            # es False (turnos de "cita la fuente" / "explica la discrepancia"
            # donde el modelo usa el historial para inventar con apariencia de
            # precisión). Sin esto, el fabrication guard solo verifica "¿el valor
            # existe en algún lado del historial?" — no "¿es el valor de ESTA
            # molécula?".
            named_values = self._parse_named_tool_values(
                turn_tool_text + "\n" + history_tool_text
            )
            for name, values_by_key in named_values.items():
                if not _re.search(
                    r"\b" + _re.escape(name) + r"\b", text, _re.IGNORECASE
                ):
                    continue
                for label, ctx_key, pattern in _VERIFIABLE_KEYS:
                    real_vals = values_by_key.get(ctx_key, [])
                    if not real_vals:
                        continue
                    # Claim CERCA del nombre, en AMBOS órdenes:
                    #   A) "amlodipino ... LogP ... X"   (nombre primero)
                    #   B) "LogP de amlodipino es X"     (nombre después)
                    # La ventana es CORTA (40 chars) para no cruzar a otra
                    # molécula: en "el etanol. La glucosa tiene un peso molecular
                    # de 180.2" el 180.2 es de la glucosa, NO del etanol — una
                    # ventana amplia (120) causaba falso positivo.
                    claims_found: list[float] = []
                    for m in _re.finditer(pattern, text, _re.IGNORECASE):
                        # El valor (match) — buscar si un nombre conocido está
                        # dentro de 40 chars ANTES o DESPUÉS del match.
                        match_text = m.group(0)
                        start = m.start()
                        end = m.end()
                        before = text[max(0, start - 40):start]
                        after = text[end:end + 40]
                        window = before + match_text + after
                        if _re.search(r"\b" + _re.escape(name) + r"\b", window, _re.IGNORECASE):
                            try:
                                claims_found.append(float(m.group(1)))
                            except (ValueError, IndexError):
                                nums = _re.findall(r"[-+]?\d+\.?\d*", m.group(0))
                                if nums:
                                    claims_found.append(float(nums[0]))
                    for claimed in claims_found:
                        # Igualdad exacta siempre vale (real=0: sin división por cero).
                        # Tolerancia: 1% para propiedades deterministas exactas
                        # (MW/LogP/TPSA/HBD/HBA) — el 10% dejaba pasar inversiones
                        # como "amlodipino MW=384.3" (real 422.9, diff 9.1%).
                        # Afinidad (kcal) conserva 10% porque tiene ruido de docking.
                        tolerance = 0.10 if ctx_key == "affinity_kcal" else 0.01
                        ok = False
                        for real in real_vals:
                            if claimed == real:
                                ok = True
                                break
                            if abs(real) > 0.001 and abs(claimed - real) / abs(real) <= tolerance:
                                ok = True
                                break
                        if not ok:
                            real_str = ", ".join(f"{r:g}" for r in real_vals[:3])
                            corrections.append(
                                f"dijiste que {name} tiene '{label} ≈ {claimed}' "
                                f"pero su valor verificado es {real_str}"
                            )

            # Verificación numérica: contra el tool result del turno actual
            # (prioridad) y/o contra molecule_context. Solo si hubo tool.
            # Regla clave: se verifica CADA claim contra el conjunto de valores
            # VERIFICADOS (turno actual + historial + molecule_context). En una
            # comparación legítima ("compará A con B") todos los claims coinciden
            # con valores conocidos → sin corrección. Un claim inventado ("logP
            # del paracetamol es 0.5" cuando el real es 1.35) NO coincide con
            # ninguno → corrección, haya 1 o 10 claims en el texto.
            if tool_was_executed:
                for label, ctx_key, pattern in _VERIFIABLE_KEYS:
                    real_vals = list(known_by_key.get(ctx_key, []))
                    ctx_val = (context or {}).get(ctx_key)
                    if ctx_val is not None:
                        real_vals.append(ctx_val)
                    if not real_vals:
                        continue
                    for m in _re.finditer(pattern, text, _re.IGNORECASE):
                        try:
                            claimed = float(m.group(1))
                        except ValueError:
                            continue
                        # ¿Coincide con ALGÚN valor verificado? Igualdad exacta
                        # SIEMPRE vale (incluye real=0, donde la tolerancia
                        # relativa haría división por cero — bug: HBD=0 de la
                        # cafeína marcado como incorrecto). Tolerancia: 1% para
                        # propiedades deterministas (el 10% dejaba pasar
                        # "MW=384.3" por 422.9, diff 9.1%); 10% solo afinidad.
                        tolerance = 0.10 if ctx_key == "affinity_kcal" else 0.01
                        ok = False
                        for real in real_vals:
                            if claimed == real:
                                ok = True
                                break
                            if abs(real) > 0.001 and abs(claimed - real) / abs(real) <= tolerance:
                                ok = True
                                break
                        if not ok:
                            real_str = ", ".join(f"{r:g}" for r in real_vals[:3])
                            corrections.append(
                                f"dijiste '{label} ≈ {claimed}' pero no coincide "
                                f"con ningún valor verificado ({real_str})"
                            )

            # ── CAPA 5: verificación de INVERSIONES LÓGICAS (ranking) ──
            # Atrapa el caso donde el modelo lee la tabla del ranking INVERTIDA:
            # la tabla dice "1. paracetamol: 151.2 Da, 2. aspirina: 180.2" (asc)
            # pero el modelo responde "la aspirina tiene menor peso que el
            # paracetamol" — la RELACIÓN mayor/menor está invertida. El guard
            # numérico NO la atrapa porque los valores individuales son correctos.
            rank_corrections = self._verify_ranking_logic(
                turn_tool_text, text, _re
            )
            corrections.extend(rank_corrections)
        if corrections:
            return (
                "\n\n[Sistema: detecté valores incorrectos en la respuesta. "
                + "Correcciones: " + "; ".join(corrections)
                + ". En tu próxima respuesta, usá los valores reales del contexto.]"
            )
        return ""

    @staticmethod
    def _looks_like_smiles_token(t: str) -> bool:
        """Heurística ESTRICTA: ¿el token es un SMILES plausible?

        Solo caracteres del alfabeto SMILES (elementos + símbolos de enlace),
        longitud 3-60, y al menos un átomo. Esto EXCLUYE palabras normales
        ("representa", "estructura", "SMILES", "es") que contienen letras
        no-elemento (E, M, A, T, ...) — un SMILES real solo usa átomos
        (C, c, N, n, O, o, S, s, P, p, F, I, H, B) + dígitos + símbolos.
        Cl/Br se normalizan a un solo átomo antes de verificar.
        """
        if not t or not isinstance(t, str):
            return False
        if len(t) < 3 or len(t) > 60:
            return False
        # Normalizar halógenos di-atómicos antes del check de alfabeto.
        cleaned = t.replace("Cl", "C").replace("Br", "B")
        if not cleaned:
            return False
        # Alfabeto SMILES: átomos + dígitos + símbolos de enlace/rama.
        allowed = set(
            "CcNnOoSsPpFIHB0123456789()[]=#@\\/+-.%"
        )
        if not all(ch in allowed for ch in cleaned):
            return False
        # Debe contener al menos una letra atómica.
        if not any(ch in "CcNnOoSsPpFIB" for ch in cleaned):
            return False
        return True

    @classmethod
    def _extract_smiles_candidates(cls, text: str) -> list[str]:
        """Extraer TODOS los tokens candidatos a SMILES del texto.

        Devuelve lista en orden de longitud descendente. Solo tokens que
        pasan la heurística ESTRICTA (alfabeto SMILES puro) — las palabras
        normales del texto no se consideran candidatas.
        """
        import re as _re
        tokens = _re.findall(r'[A-Za-z0-9@=\-\(\)\[\]\\/#+\.]+', text)
        candidates = [
            t for t in tokens if cls._looks_like_smiles_token(t)
        ]
        # Ordenar: más largo primero (prioriza moléculas reales sobre "C"/"O")
        return sorted(set(candidates), key=len, reverse=True)

    @classmethod
    def _verify_smiles_claims(cls, user_message: str, llm_response: str) -> str:
        """Guard F5: validar SMILES que el LLM inventó en respuestas conceptuales.

        El system prompt YA le dice al modelo que use 'validate_smiles' antes
        de mostrar un SMILES, pero un LLM 1.5B lo ignora — el usuario pidió
        "dame un SMILES de un péptido cíclico..." y el modelo respondió
        "C(C)(S)C(C)(S)C(C)(S)C". Igual que el guard numérico verifica DESPUÉS
        de la respuesta, este guard valida los SMILES propuestos.

        IMPORTANTE (hallazgo de verificación): un SMILES puede ser VÁLIDO para
        RDKit pero NO cumplir el pedido semántico. "C(C)(S)C(C)(S)C(C)(S)C"
        es sintácticamente correcto (C7H16S3, un tritiol) pero NO es un péptido
        cíclico: 0 enlaces amida, 0 anillos. Por eso el guard valida DOS niveles:

          Nivel 1 — sintaxis: los candidatos deben ser SMILES parseables.
          Nivel 2 — semántica: si el pedido exige características (péptido →
          enlaces amida; cíclico → anillos; disulfuro → enlace S-S; polímero
          → contradicción inherente), el SMILES debe tenerlas.

        Reglas:
          - Solo se activa si el USUARIO pidió generar/un SMILES (intención
            de diseño, no una query que menciona SMILES de paso).
          - Si el pedido es "polímero infinito" + "molécula pequeña" (contra-
            dicción química), corrige siempre: no existe tal molécula.
          - Sin candidatos parseables, sin intención, o cumplimiento verificado
            → no corrige (el modelo acertó).
        """
        import re as _re
        if not user_message or not llm_response:
            return ""

        lo = user_message.lower()
        # Intención de GENERACIÓN de SMILES (no mera mención).
        gen_pat = _re.compile(
            r"(?:dame|genera|generar|diseñ|disen|crea|crear|muestra|"
            r"escribe|construi|construye)\s+(?:un|el|una|la|me)?\s*"
            r"(?:smiles|mol[eé]cula|estructura|peptido|p[eé]ptido|pol[ií]mero)",
            _re.IGNORECASE,
        )
        # También "smiles de X", "SMILES para X", "SMILES que represente X"
        gen_pat2 = _re.compile(
            r"\bsmiles\s+(?:de|para|que|un|una|del|de)\b",
            _re.IGNORECASE,
        )
        # Palabras de diseño molecular explícitas
        design_words = ("peptido", "péptido", "peptido ciclico", "polimero",
                        "polímero", "puente disulfuro", "smiles")
        if not (gen_pat.search(lo) or gen_pat2.search(lo)) and not any(
            w in lo for w in design_words
        ):
            return ""

        # ── Contradicción inherente: "polímero infinito" + "molécula pequeña" ──
        # No existe una molécula que sea ambas cosas. El LLM no debe inventar
        # un SMILES para un pedido químicamente imposible: corrige siempre.
        if ("polimero" in lo or "polímero" in lo) and (
            "pequena" in lo or "pequeña" in lo or "infinita" in lo or "infinito" in lo
        ):
            return cls._SMILES_GUARD_HONEST_HINT

        candidates = cls._extract_smiles_candidates(llm_response)
        if not candidates:
            return ""

        try:
            from services.ai.tool_registry import _guard_validate_smiles
        except ImportError:
            return ""

        # Silenciar logs de parse-error de RDKit (los tokens candidatos son
        # palabras con guiones que fallan ruidosamente al intentar parsear).
        try:
            from rdkit import RDLogger
            RDLogger.DisableLog("rdApp.*")
        except ImportError:
            pass

        # Nivel 1 — sintaxis: ¿hay al menos un candidato parseable?
        valid_canons: list[str] = []
        invalid_seen: list[str] = []
        for cand in candidates:
            valid, canon, _err = _guard_validate_smiles(cand)
            if valid and canon:
                valid_canons.append(canon)
            else:
                invalid_seen.append(cand)

        if not valid_canons:
            if invalid_seen:
                sample = ", ".join(f"'{s}'" for s in invalid_seen[:3])
                return (
                    "\n\n[Sistema: el SMILES propuesto no es químicamente "
                    f"válido ({sample}). No lo muestres. Responde honestamente "
                    "que no puedes generar ese SMILES con precisión sin "
                    "herramientas de diseño molecular, y ofrece calcular "
                    "propiedades de una molécula conocida o usar "
                    "'generate_analogs' sobre un SMILES que el usuario ya "
                    "tenga.]"
                )
            return ""

        # Nivel 2 — semántica: ¿el SMILES cumple el pedido?
        try:
            from rdkit import Chem
            from rdkit.Chem import rdMolDescriptors
            mol = Chem.MolFromSmiles(valid_canons[0])
            if mol is None:
                return ""
            n_rings = rdMolDescriptors.CalcNumRings(mol)
            n_amide = len(mol.GetSubstructMatches(Chem.MolFromSmarts("C(=O)N")))
            n_disulfide = len(mol.GetSubstructMatches(
                Chem.MolFromSmarts("[SX2]-[SX2]")
            ))

            missing: list[str] = []
            if "peptido" in lo or "péptido" in lo:
                if n_amide < 1:
                    missing.append("enlaces peptídicos (amida)")
            if "ciclico" in lo or "cíclico" in lo or "ciclico" in lo:
                if n_rings < 1:
                    missing.append("anillo (estructura cíclica)")
            if "disulfuro" in lo:
                if n_disulfide < 1:
                    missing.append("puente disulfuro (enlace S-S)")
            if "polimero" in lo or "polímero" in lo:
                missing.append("un polímero no es una molécula pequeña representable")

            if missing:
                return (
                    "\n\n[Sistema: el SMILES propuesto no cumple el pedido — "
                    f"le falta: {', '.join(missing)}. El candidato "
                    f"'{valid_canons[0]}' es válido pero NO representa lo "
                    "que pidió el usuario. No lo muestres. Responde "
                    "honestamente qué representa y sugiere calcular "
                    "propiedades de una molécula conocida.]"
                )
        except ImportError:
            return ""
        except Exception:
            return ""

        return ""

    _SMILES_GUARD_HONEST_HINT = (
        "\n\n[Sistema: pedido químicamente imposible (polímero infinito + "
        "molécula pequeña). No inventes un SMILES. Responde honestamente "
        "que no existe tal molécula y ofrece ayudar con moléculas reales.]"
    )

    @staticmethod
    def _verify_ranking_logic(
        turn_tool_text: str, text: str, _re: object
    ) -> list[str]:
        """CAPA 5: verificar que la respuesta del modelo NO invierta el orden
        de una tabla de ranking determinista.

        La tool rank_session_molecules devuelve una tabla ordenada:
          "[Ranking de 3 moléculas por molecular_weight (asc)]
            1. paracetamol: 151.2 Da
            2. aspirina: 180.2 Da
            3. ibuprofeno: 206.3 Da"
        El modelo puede leerla INVERTIDA ("la aspirina tiene menor peso que el
        paracetamol" — falso). El guard numérico no lo atrapa (los valores
        individuales son correctos); esta capa verifica las RELACIONES
        mayor/menor entre pares mencionados en la respuesta.
        """
        import re as _re

        corrections: list[str] = []

        # 1. Extraer la tabla del ranking del tool result del turno.
        # Formato: "  N. nombre: valor unidad" (con nombre truncado posible)
        # También query_history: "  N. nombre | target | score=... | ..."
        ranking: list[tuple[str, float]] = []
        for line in turn_tool_text.splitlines():
            line = line.strip()
            m = _re.match(r"^\d+\.\s+(.+?):\s*(-?\d+\.?\d*)", line)
            if m:
                name, val = m.group(1).strip(), float(m.group(2))
                ranking.append((name, val))
            else:
                m2 = _re.match(r"^\d+\.\s+(.+?)\s*\|", line)
                if m2:
                    # query_history: "1. nombre | target | score=..." — extraer
                    # el score si está en la línea
                    m3 = _re.search(r"score=(-?\d+\.?\d*)", line)
                    if m3:
                        ranking.append((m2.group(1).strip(), float(m3.group(1))))

        if len(ranking) < 2:
            return []

        # Determinar el orden del ranking desde el header: "(asc)" o "(desc)".
        # En asc el primer elemento es el MENOR; en desc el primer es el MAYOR.
        rank_order = "asc"
        header_m = _re.search(r"\((\w+)\)", turn_tool_text)
        if header_m and header_m.group(1).lower() in ("desc", "descendente"):
            rank_order = "desc"

        # 2. Detectar relaciones explícitas en la respuesta: "X tiene mayor/
        #    menor ... que Y", "X es más/menos ... que Y"
        # Patrón: nombre1 (0-40 chars) mayor/menor (0-40) nombre2
        known_names = [n for n, _ in ranking]
        for n1 in known_names:
            if n1 not in text:
                continue
            # "X tiene mayor peso que Y" / "X es más lipofílica que Y"
            rel_pat = (
                r"\b" + _re.escape(n1) + r"\b.{0,40}?"
                r"(?:mayor|menor|m[áa]s|menos|mayor peso|menor peso)"
                r".{0,40}?\b(paracetamol|aspirina|ibuprofeno|cafeina|morfina|"
                r"etanol|dopamina|glucosa)\b"
            )
            for m in _re.finditer(rel_pat, text, _re.IGNORECASE):
                n2 = m.group(1).lower()
                seg = m.group(0).lower()
                # Determinar si la relación afirmada es "mayor" o "menor"
                if "menor" in seg or "menos" in seg:
                    claimed = "lt"   # n1 < n2
                elif "mayor" in seg or "más" in seg or "mas" in seg:
                    claimed = "gt"   # n1 > n2
                else:
                    continue

                # Valor real de cada uno en la tabla
                v1 = next((v for n, v in ranking if n == n1), None)
                v2 = next((v for n, v in ranking if n.lower() == n2), None)
                if v1 is None or v2 is None or abs(v1 - v2) < 0.01:
                    continue

                real = "lt" if v1 < v2 else "gt"
                if claimed != real:
                    # El modelo afirmó la relación invertida
                    if claimed == "gt":
                        corrections.append(
                            f"dijiste que {n1} es mayor que {n2}, pero según la "
                            f"tabla {n1}={v1:g} y {n2}={v2:g} — la relación está "
                            f"invertida"
                        )
                    else:
                        corrections.append(
                            f"dijiste que {n1} es menor que {n2}, pero según la "
                            f"tabla {n1}={v1:g} y {n2}={v2:g} — la relación está "
                            f"invertida"
                        )

        # 3. También verificar afirmaciones absolutas del tipo "X es la mayor/
        #    menor": la mayor debe ser la última del ranking asc / primera desc.
        for line in text.splitlines():
            m = _re.search(
                r"la mol[ée]cula (?:con )?(?:mayor|menor|m[áa]s \w+)|"
                r"es la (?:mayor|menor|m[áa]s \w+)|"
                r"la mol[ée]cula (?:con )?(?:mayor|menor|m[áa]s \w+) es",
                line, _re.IGNORECASE,
            )
            if not m:
                continue
            # Buscar el nombre que afirma como extremo en esta línea
            name_m = _re.search(
                r"\b(paracetamol|aspirina|ibuprofeno|cafeina|morfina|etanol|"
                r"dopamina|glucosa)\b",
                line, _re.IGNORECASE,
            )
            if not name_m:
                continue
            claimed_name = name_m.group(1).lower()
            claimed_extreme = "min" if "menor" in line.lower() else "max"
            # Extremo real según el orden del ranking:
            #   asc → primero = min, último = max
            #   desc → primero = max, último = min
            if rank_order == "asc":
                real_min, real_max = ranking[0], ranking[-1]
            else:
                real_max, real_min = ranking[0], ranking[-1]
            if claimed_extreme == "min":
                if claimed_name != real_min[0].lower():
                    corrections.append(
                        f"dijiste que {claimed_name} es la de menor valor, pero "
                        f"la tabla muestra que la de MENOR valor es {real_min[0]} "
                        f"({real_min[1]:g}) — la relación está invertida"
                    )
            elif claimed_extreme == "max":
                if claimed_name != real_max[0].lower():
                    corrections.append(
                        f"dijiste que {claimed_name} es la de mayor valor, pero "
                        f"la tabla muestra que la de MAYOR valor es {real_max[0]} "
                        f"({real_max[1]:g}) — la relación está invertida"
                    )

        return corrections

    @staticmethod
    def _parse_named_tool_values(tool_text: str) -> dict[str, dict[str, list[float]]]:
        """Parsear tool results que llevan NOMBRE de molécula:
        "compute_properties (paracetamol): MW: 151.2 Da, LogP: 1.35, ..."
        → {"paracetamol": {"molecular_weight": [151.2], "log_p": [1.35], ...}}.

        El clasificador inyecta el nombre cuando resuelve una molécula conocida
        o una anáfora ("y del paracetamol?"). Esto permite al guard verificar
        ASIGNACIONES nombre→valor (atrapar "paracetamol: 206.3 Da" cuando el
        real es 151.2), no solo que el número exista en algún lado.
        """
        if not tool_text:
            return {}
        result: dict[str, dict[str, list[float]]] = {}
        # El body termina en el siguiente header "tool (name):" — el `.`
        # (que matchea todo en la línea) absorbería las moléculas siguientes
        # si el historial viene concatenado: "compute_properties (amlodipino):
        # MW: 422.9 ... compute_properties (nifedipino): MW: 360.4" — sin el
        # stop, amlodipino acumularía también los valores de nifedipino y
        # felodipino (bug: el guard creía que 384.3 era de amlodipino).
        _HEADER = r"(?:[A-Za-z_]+)\s*\(([^)]+)\)\s*:"
        _BLOCK = re.compile(
            r"([A-Za-z_]+)\s*\(([^)]+)\)\s*:\s*"
            r"(.+?)(?=(?:[A-Za-z_]+)\s*\([^)]+\)\s*:|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        for block in _BLOCK.finditer(tool_text):
            name = block.group(2).strip().lower()
            body = block.group(3)
            vals = ChatService._parse_tool_result_values(body)
            if not vals:
                continue
            target = result.setdefault(name, {})
            for k, v in vals.items():
                target.setdefault(k, []).extend(v)
        return result

    @staticmethod
    def _value_in_history(claimed: float, known_by_key: dict[str, list[float]]) -> bool:
        """¿El claim coincide con algún valor verificado (turno actual o
        historial de la conversación)? Igualdad exacta SIEMPRE vale (incluye
        real=0 — la tolerancia relativa haría división por cero)."""
        for real_list in known_by_key.values():
            for real in real_list:
                if real is None:
                    continue
                if claimed == real:
                    return True
                if abs(real) > 0.001 and abs(claimed - real) / abs(real) <= 0.10:
                    return True
        return False

    @staticmethod
    def _parse_tool_result_values(tool_text: str) -> dict[str, list[float]]:
        """Extraer TODOS los valores REALES de un tool result (ej. "compute_
        properties: MW: 151.2 Da, LogP: 1.35, ..." o "Docking... Afinidad:
        -5.8 kcal/mol"). Devuelve dict key → lista de valores (puede haber
        varias moléculas en un historial concatenado).

        Clave: usa finditer para NO quedarse con el primer match — el historial
        acumulado de la conversación contiene varias moléculas (aspirina 180.2,
        ibuprofeno 206.3, paracetamol 151.2) y el guard necesita todas.
        """
        if not tool_text:
            return {}
        import re as _re
        values: dict[str, list[float]] = {}

        def _grab_all(pat: str, key: str) -> None:
            for m in _re.finditer(pat, tool_text):
                try:
                    values.setdefault(key, []).append(float(m.group(1)))
                except (ValueError, IndexError):
                    pass

        # compute_properties: "MW: 151.2 Da, LogP: 1.35, TPSA: 49.3 A^2, ..."
        _grab_all(r'MW:\s*([\d.]+)\s*Da', "molecular_weight")
        _grab_all(r'LogP:\s*(-?[\d.]+)', "log_p")
        _grab_all(r'TPSA:\s*([\d.]+)\s*A', "tpsa")
        _grab_all(r'H-?Bond [dD]onors?:\s*([\d.]+)', "hbd")
        _grab_all(r'H-?Bond [aA]cceptors?:\s*([\d.]+)', "hba")
        _grab_all(r'[rR]otatable [bB]onds?:\s*([\d.]+)', "rotatable_bonds")
        _grab_all(r'[hH]eavy [aA]toms?:\s*([\d.]+)', "heavy_atoms")
        _grab_all(r'[rR]ings?:\s*([\d.]+)', "rings")
        # run_docking: "Afinidad: -5.8 kcal/mol. Score: 87/100."
        _grab_all(r'[aA]finidad:\s*(-?[\d.]+)\s*kcal', "affinity_kcal")
        _grab_all(r'[sS]core:\s*([\d]{2,3})', "total_score")
        # check_docking_status: "afinidad=-8.40 kcal/mol | score_total=68.2/100"
        _grab_all(r'afinidad=(-?[\d.]+)\s*kcal', "affinity_kcal")
        _grab_all(r'score_total=([\d.]+)', "total_score")
        return values

    async def chat_with_info(
        self,
        messages: list[dict[str, str]],
        provider_id: str | None = None,
        molecule_context: dict[str, Any] | None = None,
        allow_web: bool = False,
        user_id: str | None = None,
        incluir_heredadas: bool = False,
        mode: str = "speed",
    ) -> tuple[str, FallbackInfo]:
        """Versión no-streaming de `chat()`. Devuelve `(content, FallbackInfo)`.

        MOLCHAT-INT-007. Antes esto era una **segunda implementación**: no
        exponía herramientas al modelo —lo decía su propia docstring—, no pasaba
        por el ruteo de intención ni por los respondedores deterministas, y
        aceptaba `allow_web` «por simetría de contrato» sin usarlo. El efecto no
        era de contrato sino del eje SCI: la misma pregunta se resolvía con una
        herramienta determinista en `stream=true` y la contestaba el modelo por
        su cuenta en `stream=false`. **Un parámetro de transporte decidía si la
        respuesta era cálculo o generación**, y el cliente no podía saberlo.

        La corrección no es copiar la lógica —dos implementaciones se
        desincronizan, que es justo lo que pasó— sino que haya una sola: aquí se
        acumula lo que produce `chat()`. El streaming pasa a ser lo que siempre
        debió ser, una forma de entregar, no una capacidad distinta.

        Aquí sólo se juntan los trozos: `chat()` siempre emite, y el llamador
        que quiere la respuesta de una pieza la acumula. El parámetro `stream`
        que antes decidía si el generador emitía o callaba se retiró en la
        auditoría SCI —era una trampa sin llamador—, así que ya no hay dos
        formas de recorrer el mismo turno.
        """
        partes: list[str] = []
        aviso = ""

        async for token in self.chat(
            messages=messages,
            provider_id=provider_id,
            molecule_context=molecule_context,
            mode=mode,
            allow_web=allow_web,
            user_id=user_id,
            incluir_heredadas=incluir_heredadas,
        ):
            if token.startswith("__WARNING__:"):
                aviso = token[len("__WARNING__:"):]
                continue
            partes.append(token)

        # `fallback_used` describe **este** turno. Se lee de la conversación
        # porque `chat()` lo marca ahí cuando cae al motor local de verdad; un
        # aviso no implica respaldo (negar un destino sin autorizar también
        # avisa, y ahí no respondió nadie).
        conv = self.get_conversation(user_id=user_id)
        fallback = bool(conv and conv.fallback_provider)

        return "".join(partes), FallbackInfo(warning=aviso, fallback_used=fallback)


_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
