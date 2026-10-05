"""Senhas dos usuários: guardadas só como hash scrypt com sal aleatório (biblioteca padrão, sem dependências)."""

import base64
import hashlib
import hmac
import secrets

MIN_LENGTH = 8
MAX_LENGTH = 128
N, R, P = 2**14, 8, 1  # custo do scrypt: ~16 MB e dezenas de milissegundos por tentativa


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Compara em tempo constante. Sem hash guardado (usuário só do Google), gasta o mesmo tempo e nega."""
    try:
        _, n, r, p, salt, digest = (stored or "").split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        hashlib.scrypt(password.encode(), salt=b"sem-senha-guardada", n=N, r=R, p=P, dklen=32)
        return False
    return hmac.compare_digest(actual, expected)
