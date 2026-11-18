"""本机人脸模板加密基础设施（S4 研究支线）。

设计约束：
- 模板固定为 FaceNet 128 维 float32 向量；
- AES-GCM 提供机密性和完整性；
- AES-256 主密钥首次使用时随机生成，并由 Windows DPAPI
  LocalMachine 范围保护后落盘；
- 本模块不保存原图，不输出向量、密钥或密文到日志；
- 默认不提供跨电脑迁移接口，换电脑/重装后需重新登记。

该模块只负责密钥和模板字节格式，不连接数据库，也不改变旧识别入口。
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Union

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:  # pywin32 只在 Windows 运行时使用
    import win32crypt
except ImportError:  # pragma: no cover - Linux/非 Windows 仅用于导入测试
    win32crypt = None


KEY_SIZE = 32
VECTOR_SIZE = 128
FORMAT_VERSION = 1
_KEY_FILE_NAME = "face_templates.dpapi"
_AAD = b"yolov8-facenet-face-template:v1"


class FaceTemplateCryptoError(Exception):
    """模板加密基础设施错误。"""


def default_key_path(base_dir: Union[str, os.PathLike[str], None] = None) -> Path:
    """返回客户本机密钥文件路径，不在仓库生成密钥。"""
    if base_dir is None:
        base_dir = Path.cwd() / "data"
    return Path(base_dir) / _KEY_FILE_NAME


def _require_dpapi() -> None:
    if win32crypt is None:
        raise FaceTemplateCryptoError("Windows DPAPI 不可用；请在 Windows 环境运行")


def _protect_key(key: bytes) -> bytes:
    _require_dpapi()
    try:
        # CRYPTPROTECT_LOCAL_MACHINE：同一台电脑可用，默认不支持跨电脑迁移。
        result = win32crypt.CryptProtectData(key, "face-template-key", None, None, None, 0x4)
        # pywin32 versions differ: some return bytes, others return (description, bytes).
        protected = result[1] if isinstance(result, tuple) else result
        return bytes(protected)
    except Exception as exc:  # pragma: no cover - 依赖 Windows API
        raise FaceTemplateCryptoError(f"无法使用 Windows DPAPI 保护密钥: {exc}") from exc


def _unprotect_key(protected: bytes) -> bytes:
    _require_dpapi()
    try:
        result = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
        plaintext = result[1] if isinstance(result, tuple) else result
        return bytes(plaintext)
    except Exception as exc:  # pragma: no cover - 依赖 Windows API
        raise FaceTemplateCryptoError("无法解锁本机人脸模板密钥，可能已换电脑或重装系统") from exc


def load_or_create_key(path: Union[str, os.PathLike[str]]) -> bytes:
    """首次调用生成本机 AES-256 密钥，后续只读取 DPAPI 密文。"""
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        try:
            protected = key_path.read_bytes()
            if not protected:
                raise FaceTemplateCryptoError("本机密钥文件为空或已损坏")
            key = _unprotect_key(protected)
        except OSError as exc:
            raise FaceTemplateCryptoError(f"无法读取本机密钥文件: {exc}") from exc
        if len(key) != KEY_SIZE:
            raise FaceTemplateCryptoError("本机密钥格式无效")
        return key

    key = os.urandom(KEY_SIZE)
    protected = _protect_key(key)
    if not protected:
        raise FaceTemplateCryptoError("Windows DPAPI 返回空密钥密文")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(key_path), flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(protected)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        # 并发首次启动时，使用先创建成功的实例，避免覆盖客户密钥。
        return load_or_create_key(key_path)
    except OSError as exc:
        raise FaceTemplateCryptoError(f"无法保存本机密钥文件: {exc}") from exc
    return key


def _vector_bytes(vector: np.ndarray) -> bytes:
    array = np.asarray(vector)
    if array.shape != (VECTOR_SIZE,):
        raise ValueError(f"人脸模板必须是 128 维，收到 shape={array.shape}")
    if not np.issubdtype(array.dtype, np.floating):
        raise ValueError("人脸模板必须是浮点向量")
    array = np.asarray(array, dtype=np.float32)
    if not np.isfinite(array).all():
        raise ValueError("人脸模板包含 NaN 或无穷值")
    return array.tobytes(order="C")


def encrypt_vector(vector: np.ndarray, key: bytes) -> dict[str, object]:
    """加密一个 128 维向量，返回可序列化的模板记录。"""
    if len(key) != KEY_SIZE:
        raise ValueError("AES-GCM 密钥必须是 32 字节")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, _vector_bytes(vector), _AAD)
    return {
        "format_version": FORMAT_VERSION,
        "vector_size": VECTOR_SIZE,
        "dtype": "float32",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_vector(record: dict[str, object], key: bytes) -> np.ndarray:
    """验证并解密模板；认证失败时抛出 FaceTemplateCryptoError。"""
    if len(key) != KEY_SIZE:
        raise ValueError("AES-GCM 密钥必须是 32 字节")
    if record.get("format_version") != FORMAT_VERSION or record.get("vector_size") != VECTOR_SIZE or record.get("dtype") != "float32":
        raise FaceTemplateCryptoError("人脸模板格式或版本不受支持")
    try:
        nonce = base64.b64decode(str(record["nonce"]), validate=True)
        ciphertext = base64.b64decode(str(record["ciphertext"]), validate=True)
        raw = AESGCM(key).decrypt(nonce, ciphertext, _AAD)
    except Exception as exc:
        raise FaceTemplateCryptoError("人脸模板认证失败或密文已损坏") from exc
    if len(raw) != VECTOR_SIZE * np.dtype(np.float32).itemsize:
        raise FaceTemplateCryptoError("解密后的人脸模板长度无效")
    vector = np.frombuffer(raw, dtype=np.float32).copy()
    if not np.isfinite(vector).all():
        raise FaceTemplateCryptoError("解密后的人脸模板包含无效数值")
    return vector


def dumps_record(record: dict[str, object]) -> str:
    """以稳定 JSON 编码模板元数据；不记录原图或明文向量。"""
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def loads_record(payload: str) -> dict[str, object]:
    try:
        record = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FaceTemplateCryptoError("人脸模板 JSON 格式无效") from exc
    if not isinstance(record, dict):
        raise FaceTemplateCryptoError("人脸模板记录必须是对象")
    return record
