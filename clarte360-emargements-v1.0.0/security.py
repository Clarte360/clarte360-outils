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
