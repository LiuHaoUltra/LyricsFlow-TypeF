import zlib
import base64
import pytest
from Crypto.Cipher import DES3
from app.core.decrypter import QQMusicDecrypt, KugouDecrypt, DecryptionError

# --- Helper Logic to Generate Mock Mock Data ---

def encrypt_qrc(text: str, key: bytes = QQMusicDecrypt.DEFAULT_KEY) -> str:
    """Reverses QQMusicDecrypt logic to create valid test data."""
    # 1. Encode + BOM (QRC usually has BOM?) Reference says it strips it if present.
    # We will add it to be robust.
    data = b'\xef\xbb\xbf' + text.encode('utf-8')
    
    # 2. Zlib Compress
    compressed = zlib.compress(data)
    
    # 3. 3DES Encrypt (ECB)
    # Pad to 8 bytes for DES3
    pad_len = 8 - (len(compressed) % 8)
    if pad_len != 8:
        compressed += b'\x00' * pad_len # Zero padding is common for simple cases or PKCS5. 
        # Reference C# code doesn't show explicit unpadding logic in `DecryptLyrics`, 
        # but `SharpZipLib` might handle trailing zeros or the stream just stops at valid Zlib end.
        # Let's see if simple zero padding works with zlib decompression on the other side.
        # UPDATE: C# `TripleDESCrypt` loops `encryptedTextByte.Length; i += 8`.
        # C# `SharpZipLibDecompress` takes the bytes.
        # If we pad with zeros, zlib might complain about trailing garbage if not handled.
        # Let's try standard padding.
        pass
    
    cipher = DES3.new(key, DES3.MODE_ECB)
    encrypted = cipher.encrypt(compressed)
    
    # 4. Hex Encode
    return encrypted.hex().upper()


def encrypt_krc(text: str) -> str:
    """Reverses KugouDecrypt logic."""
    # 1. Prepend logic (Ref: `return res[1..]`) -> So we prepend a dummy char
    data = b'k' + text.encode('utf-8')
    
    # 2. Zlib Compress
    compressed = zlib.compress(data)
    
    # 3. XOR Encrypt
    key = KugouDecrypt.MAGIC_KEY
    key_len = len(key)
    encrypted_payload = bytearray(compressed)
    for i in range(len(encrypted_payload)):
        encrypted_payload[i] ^= key[i % key_len]
        
    # 4. Prepend Header (4 bytes)
    full_data = b'krcl' + encrypted_payload # 'krcl' is a common magic header, content doesn't matter for logic
    
    # 5. Base64 Encode
    return base64.b64encode(full_data).decode('ascii')


# --- Tests ---

def test_qrc_decrypt_success():
    original_text = "<?xml version='1.0' encoding='utf-8'?>\n<lyric>Test Lyric</lyric>"
    encrypted = encrypt_qrc(original_text)
    
    decrypted = QQMusicDecrypt.decrypt(encrypted)
    assert decrypted == original_text

def test_qrc_decrypt_invalid_key_fails():
    original_text = "test"
    # Encrypt with wrong key
    wrong_key = b'123456789012345678901234'
    encrypted = encrypt_qrc(original_text, key=wrong_key)
    
    with pytest.raises(DecryptionError):
        # Using default key should fail
        QQMusicDecrypt.decrypt(encrypted)

def test_krc_decrypt_success():
    original_text = "start_of_text\n[00:01.000]Test KRC"
    encrypted = encrypt_krc(original_text)
    
    decrypted = KugouDecrypt.decrypt(encrypted)
    assert decrypted == original_text

def test_krc_decrypt_short_header_fails():
    # Base64 of "abc" (3 bytes) -> < 4 bytes header
    short_data = base64.b64encode(b'abc').decode('ascii')
    
    with pytest.raises(DecryptionError):
        KugouDecrypt.decrypt(short_data)

def test_krc_decrypt_bad_base64():
    with pytest.raises(DecryptionError):
        KugouDecrypt.decrypt("!!!!")

