"""Privacy and identity contract for public Solana memos."""

from types import SimpleNamespace
from uuid import UUID

from api.routers.blockchain import _is_solana_wallet, _public_author_reference


def test_institutional_author_reference_never_publishes_email():
    user = SimpleNamespace(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        email="researcher@example.org",
        solana_wallet_address="researcher@example.org",  # legacy bad value
    )

    reference = _public_author_reference(user, None)

    assert reference.startswith("account:")
    assert "@" not in reference
    assert user.email not in reference


def test_explicit_valid_wallet_is_preserved():
    wallet = "11111111111111111111111111111111"
    user = SimpleNamespace(id=UUID(int=1), solana_wallet_address=None)

    assert _is_solana_wallet(wallet)
    assert _public_author_reference(user, wallet) == wallet


def test_arbitrary_author_identifier_is_rejected_as_wallet():
    assert not _is_solana_wallet("someone@example.org")
    assert not _is_solana_wallet("not-a-wallet")
