"""安全工具

依赖安装: uv add "pwdlib[argon2]"
"""

from pwdlib import PasswordHash

# 使用推荐的 Argon2 算法
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """密码哈希"""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return password_hash.verify(hashed_password, plain_password)
