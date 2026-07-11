"""
Lightweight secrets encryption for VM diagnostic credentials.

This is intentionally minimal: a single Fernet key sourced from the
environment. It exists so VM guest credentials are never stored in
plaintext in the application database.

PRODUCTION NOTE: this is not a substitute for a real secrets manager /
KMS (e.g. AWS KMS, HashiCorp Vault, GCP Secret Manager). Swap
`_get_fernet()` for a call into one of those before running this
against real infrastructure. In particular, rotating VM_CREDENTIAL_ENCRYPTION_KEY
here will make previously-stored credentials unreadable, since there is
no key-versioning.
"""
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionError(Exception):
    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = os.getenv("VM_CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise CredentialEncryptionError(
            "VM_CREDENTIAL_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it as an environment variable before storing VM credentials."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise CredentialEncryptionError(f"Invalid VM_CREDENTIAL_ENCRYPTION_KEY: {exc}") from exc


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Could not decrypt stored credential — the encryption key may have "
            "changed since it was stored."
        ) from exc
