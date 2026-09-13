"""
Tests del certifier de Solana (services/blockchain/certifier.py).

Cubre:
- _build_memo() con y sin user_wallet
- _parse_memo() con formato v1 y legacy
- _extract_memo() con datos simulados
- verify() con commitment config
- certify() con error handling
- Singleton get_certifier()
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import BlockchainRecord


# ═════════════════════════════════════════════════════════════════════════════
# Tests de _build_memo
# ═════════════════════════════════════════════════════════════════════════════


def make_record(**overrides) -> BlockchainRecord:
    """Crea un BlockchainRecord con defaults."""
    defaults = {
        "smiles_hash": "a" * 64,
        "total_score": 85.5,
        "target_pdb_id": "7E2Y",
        "user_wallet": "",
        "timestamp": datetime(2026, 7, 28, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return BlockchainRecord(**defaults)


class TestBuildMemo:
    """Tests de _build_memo()."""

    def test_builds_v1_format(self):
        """El memo debe usar formato MolDesign-v1|CC0|..."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        record = make_record()
        memo = c._build_memo(record, user_wallet=None)
        assert memo.startswith("MolDesign-v1|CC0|")
        parts = memo.split("|")
        assert len(parts) == 6  # v1 + CC0 + hash + score + pdb + timestamp (sin wallet)
        assert parts[2] == "a" * 64  # smiles_hash
        assert parts[3] == "85.50"  # total_score formateado

    def test_builds_with_user_wallet(self):
        """Con user_wallet, debe agregar al final del memo."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        record = make_record()
        memo = c._build_memo(record, user_wallet="test@example.com")
        assert memo.endswith("|test@example.com")
        parts = memo.split("|")
        assert len(parts) == 7  # +1 por wallet

    def test_builds_without_user_wallet(self):
        """Sin user_wallet, el memo no debe tener wallet al final."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        record = make_record()
        memo = c._build_memo(record, user_wallet=None)
        assert "|None" not in memo
        assert memo.count("|") == 5  # 5 pipes = 6 campos

    def test_memo_contains_timestamp(self):
        """El memo debe contener el timestamp ISO."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        record = make_record()
        memo = c._build_memo(record, user_wallet=None)
        assert "2026-07-28" in memo


# ═════════════════════════════════════════════════════════════════════════════
# Tests de _parse_memo
# ═════════════════════════════════════════════════════════════════════════════


class TestParseMemo:
    """Tests de _parse_memo()."""

    def test_parses_v1_format(self):
        """Formato v1 debe parsear correctamente."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        memo = "MolDesign-v1|CC0|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa|85.50|7E2Y|2026-07-28T00:00:00+00:00"
        record = c._parse_memo(memo)
        assert record is not None
        assert record.smiles_hash == "a" * 64
        assert abs(record.total_score - 85.50) < 0.01
        assert record.target_pdb_id == "7E2Y"

    def test_parses_legacy_format(self):
        """Formato legacy MolDesign-CC0 debe seguir parseando."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        memo = "MolDesign-CC0|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa|85.50|7E2Y|2026-07-28T00:00:00+00:00|user@example.com"
        record = c._parse_memo(memo)
        assert record is not None
        assert record.smiles_hash == "a" * 64
        assert record.user_wallet == "user@example.com"

    def test_parses_with_wallet(self):
        """Memo con wallet debe extraer wallet."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        memo = "MolDesign-v1|CC0|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa|85.50|7E2Y|2026-07-28T00:00:00+00:00|test@example.com"
        record = c._parse_memo(memo)
        assert record is not None
        assert record.user_wallet == "test@example.com"

    def test_returns_none_for_invalid_memo(self):
        """Memo inválido debe retornar None."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        assert c._parse_memo("not-a-memo") is None
        assert c._parse_memo("") is None
        assert c._parse_memo("MolDesign-v1|CC0|incomplete") is None


# ═════════════════════════════════════════════════════════════════════════════
# Tests de _extract_memo
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractMemo:
    """Tests de _extract_memo()."""

    def test_extract_memo_no_discriminator_byte(self):
        """
        Verifica que NO se salta el primer byte.
        El Memo Program no usa discriminator — data ES el memo.
        """
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        c.MEMO_PROGRAM_ID_STR = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

        # Crear un mock de transacción con el memo exacto
        memo_expected = "MolDesign-v1|CC0|test_hash_here|85.50|7E2Y|2026-07-28T00:00:00+00:00"
        memo_bytes = memo_expected.encode("utf-8")

        # Mock de la instrucción
        mock_ix = MagicMock()
        mock_ix.program_id = c.MEMO_PROGRAM_ID_STR
        mock_ix.data = bytearray(memo_bytes)

        # Mock del mensaje
        mock_msg = MagicMock()
        mock_msg.instructions = [mock_ix]

        # Mock de la transacción
        mock_tx = MagicMock()
        mock_tx.transaction.message = mock_msg

        result = c._extract_memo(mock_tx)
        assert result is not None
        # El resultado DEBE empezar con 'M' (no con 'o' que sería el [1:] bug)
        assert result.startswith("MolDesign")
        assert result == memo_expected

    def test_extract_memo_no_corruption_with_bytes(self):
        """Verifica que bytes data no se corrompe (regresión del bug)."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()
        memo = "MolDesign-v1|CC0|abc123"
        memo_bytes = memo.encode("utf-8")

        mock_ix = MagicMock()
        mock_ix.program_id = c.MEMO_PROGRAM_ID_STR
        mock_ix.data = bytes(memo_bytes)  # bytes, no bytearray

        mock_msg = MagicMock()
        mock_msg.instructions = [mock_ix]

        mock_tx = MagicMock()
        mock_tx.transaction.message = mock_msg

        result = c._extract_memo(mock_tx)
        assert result == memo

    def test_extract_memo_returns_none_for_no_memo_instruction(self):
        """Sin instrucción Memo Program, debe retornar None."""
        from services.blockchain.certifier import SolanaCertifier
        c = SolanaCertifier()

        mock_ix = MagicMock()
        mock_ix.program_id = "11111111111111111111111111111111"  # System Program

        mock_msg = MagicMock()
        mock_msg.instructions = [mock_ix]

        mock_tx = MagicMock()
        mock_tx.transaction.message = mock_msg

        result = c._extract_memo(mock_tx)
        assert result is None


# ═════════════════════════════════════════════════════════════════════════════
# Tests de verify() y health()
# ═════════════════════════════════════════════════════════════════════════════


class TestVerify:
    """Tests de verificación por JSON-RPC, sin SDK de Solana."""

    @pytest.mark.asyncio
    async def test_verify_uses_devnet_rpc_and_extracts_memo(self):
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier("https://api.devnet.solana.com")
        memo = (
            "MolDesign-v1|CC0|"
            + ("a" * 64)
            + "|85.50|7E2Y|2026-07-28T00:00:00+00:00|"
            + ("1" * 32)
        )
        c._rpc = AsyncMock(
            return_value={
                "meta": {"err": None},
                "transaction": {
                    "message": {
                        "accountKeys": [],
                        "instructions": [
                            {
                                "programId": c.MEMO_PROGRAM_ID_STR,
                                "parsed": memo,
                            }
                        ],
                    }
                },
            }
        )

        record = await c.verify("1" * 64)

        assert record is not None
        assert record.smiles_hash == "a" * 64
        method, params = c._rpc.await_args.args
        assert method == "getTransaction"
        assert params[1]["encoding"] == "jsonParsed"
        assert params[1]["commitment"] == "confirmed"
        assert params[1]["maxSupportedTransactionVersion"] == 0

    @pytest.mark.asyncio
    async def test_verify_rejects_malformed_signature_without_rpc(self):
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier("https://api.devnet.solana.com")
        c._rpc = AsyncMock()
        assert await c.verify("not-a-signature") is None
        c._rpc.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verify_returns_none_on_rpc_failure(self):
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier("https://api.devnet.solana.com")
        c._rpc = AsyncMock(side_effect=RuntimeError("RPC failed"))
        assert await c.verify("1" * 64) is None

    @pytest.mark.asyncio
    async def test_health_is_read_only_and_explicitly_experimental(self):
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier("https://api.devnet.solana.com")
        c._rpc = AsyncMock(return_value="ok")

        health = await c.health()

        assert health["available"] is True
        assert health["network"] == "devnet"
        assert health["experimental"] is True
        assert health["official_validity"] is False
        c._rpc.assert_awaited_once_with("getHealth")

    @pytest.mark.asyncio
    async def test_non_devnet_configuration_is_refused_without_rpc(self):
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier("https://api.mainnet-beta.solana.com")
        c._rpc = AsyncMock()

        health = await c.health()

        assert health["available"] is False
        assert health["network"] == "unsupported"
        c._rpc.assert_not_awaited()

# ═════════════════════════════════════════════════════════════════════════════
# Tests de certify()
# ═════════════════════════════════════════════════════════════════════════════


class TestCertify:
    """Tests de certify()."""

    @pytest.mark.asyncio
    async def test_certify_requires_keypair(self):
        """El backend nunca debe firmar: exige el flujo cliente experimental."""
        from core.exceptions import TransactionFailedError
        from services.blockchain.certifier import SolanaCertifier

        c = SolanaCertifier()
        c._keypair = None
        c._initialized = True

        record = make_record()
        with pytest.raises(TransactionFailedError):
            await c.certify(record)


# ═════════════════════════════════════════════════════════════════════════════
# Tests de singleton
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_certifier_returns_same_instance():
    """get_certifier() debe retornar el mismo singleton."""
    from services.blockchain.certifier import get_certifier
    c1 = await get_certifier()
    c2 = await get_certifier()
    assert c1 is c2
