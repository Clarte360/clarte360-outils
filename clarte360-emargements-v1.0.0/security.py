import os, hashlib, hmac, base64

def hash_password(password: str) -> str:
    salt=os.urandom(16)
    dk=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,240000)
    return 'pbkdf2_sha256$240000$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(dk).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        alg,it,salt_b64,dk_b64=hashed.split('$',3)
        if alg!='pbkdf2_sha256': return False
        salt=base64.urlsafe_b64decode(salt_b64.encode());expected=base64.urlsafe_b64decode(dk_b64.encode())
        actual=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,int(it))
        return hmac.compare_digest(actual,expected)
    except Exception:
        return False


def _secret_key_material(secret: str | None = None) -> bytes:
    raw=(secret or os.getenv("CLARTE360_PIN_KEY") or "").encode("utf-8")
    if not raw:
        raise ValueError("Clé de protection des codes personnels absente.")
    return hashlib.sha256(raw).digest()

def seal_short_secret(value: str, secret: str | None = None) -> str:
    """Protect a short recoverable value with a keyed stream + HMAC (stdlib only).

    The application stores the participant PIN hash for authentication and this sealed
    copy only to satisfy authorised recovery/display workflows.
    """
    key=_secret_key_material(secret); nonce=os.urandom(16); data=value.encode("utf-8")
    stream=hashlib.sha256(key+nonce).digest()
    enc=bytes(b ^ stream[i % len(stream)] for i,b in enumerate(data))
    mac=hmac.new(key,nonce+enc,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce+enc+mac).decode("ascii")

def open_short_secret(token: str | None, secret: str | None = None) -> str | None:
    if not token: return None
    try:
        key=_secret_key_material(secret); raw=base64.urlsafe_b64decode(token.encode("ascii"))
        nonce,body=raw[:16],raw[16:]; enc,mac=body[:-32],body[-32:]
        if not hmac.compare_digest(mac,hmac.new(key,nonce+enc,hashlib.sha256).digest()): return None
        stream=hashlib.sha256(key+nonce).digest()
        return bytes(b ^ stream[i % len(stream)] for i,b in enumerate(enc)).decode("utf-8")
    except Exception:
        return None
