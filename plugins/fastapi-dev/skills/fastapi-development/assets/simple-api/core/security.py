"""安全工具"""


def hash_password(password: str) -> str:
    """密码哈希（实际项目使用 passlib 或 bcrypt）"""
    import hashlib

    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password
