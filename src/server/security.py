import hashlib
import secrets

try:
    import bcrypt

    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


def hash_key(plain_key: str) -> str:
    """Hash the API key using bcrypt (or sha256 fallback if bcrypt not installed)."""
    if HAS_BCRYPT:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain_key.encode("utf-8"), salt).decode("utf-8")
    else:
        return f"sha256:{hashlib.sha256(plain_key.encode('utf-8')).hexdigest()}"


def verify_key(plain_key: str, hashed_key: str) -> bool:
    """Verify standard Bearer token against stored hashed API key, with fallback for unhashed keys."""
    if hashed_key.startswith("sha256:"):
        expected = f"sha256:{hashlib.sha256(plain_key.encode('utf-8')).hexdigest()}"
        return secrets.compare_digest(hashed_key, expected)
    if HAS_BCRYPT:
        try:
            return bcrypt.checkpw(plain_key.encode("utf-8"), hashed_key.encode("utf-8"))
        except Exception:
            pass
    # Fallback to direct string comparison for unhashed legacy keys
    return secrets.compare_digest(plain_key, hashed_key)
