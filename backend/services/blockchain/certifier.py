"""Experimental Solana devnet integrity records for MolDesign.

The browser signs with the researcher's wallet. The desktop proof of concept
signs with an ephemeral key created in the WebView and funded only with devnet
SOL. Python only prepares and verifies Memo Program payloads through JSON-RPC;
it intentionally contains no Solana signing SDK or private key.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

from core.config import get_settings
from core.exceptions import TransactionFailedError
from core.models import BlockchainRecord
from utils.logger import get_logger

log = get_logger(__name__)

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
DEVNET_HOST = "api.devnet.solana.com"


def _decode_base58(value: str) -> bytes:
    """Decode base58 without introducing another runtime dependency."""
    number = 0
    for char in value:
        try:
            digit = BASE58_ALPHABET.index(char)
        except ValueError as exc:
            raise ValueError("invalid base58 payload") from exc
        number = number * 58 + digit
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return (b"\x00" * (len(value) - len(value.lstrip("1")))) + body


def is_solana_public_key(value: Optional[str]) -> bool:
    """Return whether value is a canonical 32-byte Solana public key."""
    if not value:
        return False
    candidate = value.strip()
    if candidate != value or not 32 <= len(candidate) <= 44:
        return False
    try:
        return len(_decode_base58(candidate)) == 32
    except ValueError:
        return False


def is_solana_signature(value: str) -> bool:
    """Validate the shape of an Ed25519 transaction signature."""
    if not value or not 64 <= len(value) <= 88:
        return False
    try:
        return len(_decode_base58(value)) == 64
    except ValueError:
        return False


class SolanaCertifier:
    """Prepare and verify MolDesign memos on Solana devnet only."""

    MEMO_PROGRAM_ID_STR = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

    def __init__(self, rpc_url: Optional[str] = None):
        self._rpc_url = rpc_url
        self._request_id = 0

    @property
    def rpc_url(self) -> str:
        return self._rpc_url or get_settings().solana_rpc_url

    @property
    def is_devnet(self) -> bool:
        return DEVNET_HOST in self.rpc_url.lower()

    @property
    def is_available(self) -> bool:
        """Client-side signing is enabled only for the configured devnet."""
        return self.is_devnet

    async def _rpc(self, method: str, params: Optional[list[Any]] = None) -> Any:
        """Call Solana JSON-RPC using only the Python standard library."""
        if not self.is_devnet:
            raise RuntimeError("MolDesign alpha only permits Solana devnet")
        self._request_id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or []}
        ).encode("utf-8")

        def send() -> Any:
            req = urlrequest.Request(
                self.rpc_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "MolDesign/1.0-devnet-poc",
                },
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=10) as response:
                document = json.loads(response.read().decode("utf-8"))
            if document.get("error"):
                raise RuntimeError(f"Solana RPC error: {document['error']}")
            return document.get("result")

        return await asyncio.to_thread(send)

    async def health(self) -> dict[str, Any]:
        """Probe devnet without a wallet or a state-changing operation."""
        base = {
            "available": False,
            "rpc_reachable": False,
            "network": "devnet" if self.is_devnet else "unsupported",
            "experimental": True,
            "official_validity": False,
            "signing_mode": "client_wallet_or_ephemeral_devnet",
        }
        if not self.is_devnet:
            return {**base, "reason": "Esta versión experimental sólo permite Solana devnet."}
        try:
            reachable = await self._rpc("getHealth") == "ok"
            return {
                **base,
                "available": reachable,
                "rpc_reachable": reachable,
                "reason": None if reachable else "Solana devnet respondió sin estado saludable.",
            }
        except (OSError, RuntimeError, ValueError, urlerror.URLError) as exc:
            log.warning("solana_devnet_health_failed", error=str(exc))
            return {**base, "reason": "No se pudo conectar con Solana devnet."}

    async def certify(self, record: BlockchainRecord, user_wallet: Optional[str] = None) -> str:
        """Refuse server-side signing; private keys live only in the client."""
        raise TransactionFailedError(
            smiles_hash=record.smiles_hash,
            reason=(
                "La firma institucional fue retirada. Usa el flujo experimental "
                "de wallet o la identidad efímera de Solana devnet."
            ),
            detail="ClientWalletRequired",
        )

    async def verify(self, signature: str) -> Optional[BlockchainRecord]:
        """Verify a confirmed devnet transaction and parse its MolDesign memo."""
        if not is_solana_signature(signature):
            return None
        try:
            transaction = None
            for attempt in range(3):
                transaction = await self._rpc(
                    "getTransaction",
                    [
                        signature,
                        {
                            "encoding": "jsonParsed",
                            "commitment": "confirmed",
                            "maxSupportedTransactionVersion": 0,
                        },
                    ],
                )
                if transaction is not None:
                    break
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
            if not transaction or (transaction.get("meta") or {}).get("err") is not None:
                return None
            memo = self._extract_memo(transaction)
            return self._parse_memo(memo) if memo else None
        except (OSError, RuntimeError, ValueError, TypeError, urlerror.URLError) as exc:
            log.warning("solana_verify_failed", signature=signature[:16], error=str(exc))
            return None

    async def close(self):
        """Compatibility no-op: stdlib HTTP calls do not keep a client open."""

    def _build_memo(self, record: BlockchainRecord, user_wallet: Optional[str]) -> str:
        ts = record.timestamp.isoformat()
        memo = (
            f"MolDesign-v1|CC0|{record.smiles_hash}|"
            f"{record.total_score:.2f}|{record.target_pdb_id}|{ts}"
        )
        if user_wallet:
            memo += f"|{user_wallet}"
        return memo

    def _extract_memo(self, tx: Any) -> Optional[str]:
        """Extract a Memo Program instruction from JSON-RPC or legacy doubles."""
        try:
            if isinstance(tx, dict):
                message = tx["transaction"]["message"]
                account_keys = message.get("accountKeys", [])
                for instruction in message.get("instructions", []):
                    program_id = instruction.get("programId")
                    if not program_id and "programIdIndex" in instruction:
                        key = account_keys[instruction["programIdIndex"]]
                        program_id = key.get("pubkey") if isinstance(key, dict) else key
                    if program_id != self.MEMO_PROGRAM_ID_STR:
                        continue
                    parsed = instruction.get("parsed")
                    if isinstance(parsed, str):
                        return parsed
                    if isinstance(parsed, dict):
                        parsed_value = parsed.get("memo") or parsed.get("info")
                        if isinstance(parsed_value, str):
                            return parsed_value
                    data = instruction.get("data")
                    if isinstance(data, str):
                        return _decode_base58(data).decode("utf-8", errors="replace")
                return None

            encoded = tx.transaction
            try:
                message = encoded.message
            except AttributeError:
                message = encoded.transaction.message
            for instruction in message.instructions:
                if hasattr(instruction, "program_id"):
                    program_id = str(instruction.program_id)
                else:
                    program_id = str(message.account_keys[instruction.program_id_index])
                if program_id != self.MEMO_PROGRAM_ID_STR:
                    continue
                data = instruction.data
                if data is None:
                    continue
                memo_bytes = _decode_base58(data) if isinstance(data, str) else bytes(data)
                return memo_bytes.decode("utf-8", errors="replace")
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            log.debug("memo_extraction_failed", error=str(exc))
        return None

    def _parse_memo(self, memo: str) -> Optional[BlockchainRecord]:
        try:
            parts = memo.split("|")
            if len(parts) < 6 or not parts[0].startswith("MolDesign"):
                return None
            offset = 1 if len(parts) > 1 and parts[1] == "CC0" else 0
            return BlockchainRecord(
                smiles_hash=parts[1 + offset],
                total_score=float(parts[2 + offset]),
                target_pdb_id=parts[3 + offset],
                user_wallet=parts[5 + offset] if len(parts) > 5 + offset else "",
                timestamp=_parse_timestamp(parts[4 + offset]),
            )
        except (ValueError, IndexError) as exc:
            log.debug("memo_parse_failed", memo=memo[:60], error=str(exc))
            return None


def _parse_timestamp(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        pass
    try:
        from dateutil.parser import parse as dateparse
        dt = dateparse(ts)
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


_certifier: Optional[SolanaCertifier] = None
_lock = asyncio.Lock()


async def get_certifier() -> SolanaCertifier:
    global _certifier
    if _certifier is None:
        async with _lock:
            if _certifier is None:
                _certifier = SolanaCertifier()
    return _certifier


async def certify_molecule(record: BlockchainRecord, user_wallet: Optional[str] = None) -> str:
    return await (await get_certifier()).certify(record, user_wallet)


async def verify_certification(signature: str) -> Optional[BlockchainRecord]:
    return await (await get_certifier()).verify(signature)


async def close_certifier():
    global _certifier
    if _certifier:
        await _certifier.close()
        _certifier = None
