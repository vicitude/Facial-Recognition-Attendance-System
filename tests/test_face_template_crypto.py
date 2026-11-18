"""S4 加密人脸模板基础契约测试。"""

import numpy as np
import pytest

import attendance.face_template_crypto as crypto


def test_encrypt_decrypt_roundtrip_without_logging_or_images():
    key = bytes(range(32))
    vector = np.linspace(-1.0, 1.0, 128, dtype=np.float32)
    record = crypto.encrypt_vector(vector, key)
    restored = crypto.decrypt_vector(record, key)
    assert restored.shape == (128,)
    assert restored.dtype == np.float32
    np.testing.assert_array_equal(restored, vector)
    payload = crypto.dumps_record(record)
    assert '"ciphertext"' in payload
    assert '"nonce"' in payload
    assert '"image"' not in payload
    assert '"plaintext"' not in payload


def test_tampered_ciphertext_is_rejected():
    key = b"k" * 32
    record = crypto.encrypt_vector(np.zeros(128, dtype=np.float32), key)
    record["ciphertext"] = record["ciphertext"][:-2] + "AA"
    with pytest.raises(crypto.FaceTemplateCryptoError, match="认证失败"):
        crypto.decrypt_vector(record, key)


def test_wrong_shape_and_nonfinite_are_rejected():
    key = b"k" * 32
    with pytest.raises(ValueError, match="128 维"):
        crypto.encrypt_vector(np.zeros(127, dtype=np.float32), key)
    vector = np.zeros(128, dtype=np.float32)
    vector[0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        crypto.encrypt_vector(vector, key)


def test_key_initialization_is_idempotent(monkeypatch, tmp_path):
    calls = []

    def fake_protect(key):
        calls.append(key)
        return b"protected:" + key

    def fake_unprotect(payload):
        assert payload.startswith(b"protected:")
        return payload[len(b"protected:"):]

    monkeypatch.setattr(crypto, "_protect_key", fake_protect)
    monkeypatch.setattr(crypto, "_unprotect_key", fake_unprotect)
    path = tmp_path / "data" / "face_templates.dpapi"
    first = crypto.load_or_create_key(path)
    second = crypto.load_or_create_key(path)
    assert first == second
    assert len(calls) == 1
    assert path.exists()
