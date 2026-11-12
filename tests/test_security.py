from __future__ import annotations

from _2001.core.security import ALGORITHM, hash_password, verify_password


def test_hash_roundtrip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith(f"{ALGORITHM}$210000$")
    assert verify_password("correct horse battery staple", encoded) is True


def test_hash_rejects_wrong_password() -> None:
    encoded = hash_password("s3cret-value")

    assert verify_password("s3cret-valuE", encoded) is False


def test_hash_is_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_verify_tolerates_garbage() -> None:
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "md5$1$aa$bb") is False
