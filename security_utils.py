from werkzeug.security import generate_password_hash as _gph

def safe_generate_password_hash(password: str) -> str:
    try:
        return _gph(password, method='scrypt')
    except Exception:
        return _gph(password, method='pbkdf2:sha256', salt_length=16)
