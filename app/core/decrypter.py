import base64
import zlib
from typing import Optional
from Crypto.Cipher import DES3

class DecryptionError(Exception):
    """Base class for decryption errors."""
    pass

class QQMusicDecrypt:
    """
    Decrypter for QQ Music .qrc format.
    Algorithm: 3DES (ECB) -> Zlib -> UTF-8
    """
    # Key from reference: !@#)(*$%123ZXC!@!@#)(NHL
    DEFAULT_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"

    @staticmethod
    def decrypt(encrypted_text: str, key: bytes = DEFAULT_KEY) -> str:
        """
        Decrypts a QRC encrypted string using Manual DES implementation to match reference.
        """
        try:
            from app.core.manual_des import DESHelper
            
            # 1. Hex Decode
            encrypted_bytes = bytes.fromhex(encrypted_text)
            
            # Prepare Key Schedules
            # schedule = new byte[3][][]; -> list of 3 lists of 16 lists of 6 bytes (actually handled by KeySchedule)
            # Python: 
            schedule = [[ [0]*6 for _ in range(16) ] for _ in range(3)]
            
            # Setup Key
            DESHelper.TripleDESKeySetup(key, schedule, DESHelper.DECRYPT)
            
            # Decrypt Block by Block (ECB Mode equivalent)
            decrypted_data = bytearray()
            for i in range(0, len(encrypted_bytes), 8):
                block = encrypted_bytes[i:i+8]
                if len(block) < 8:
                    # Pad? standard DES requires 8 bytes. Reference: usually aligned.
                    # QRC should be aligned.
                    break 
                
                dec_block = DESHelper.TripleDESCrypt(block, schedule)
                decrypted_data.extend(dec_block)
            
            decrypted_bytes = bytes(decrypted_data)

            # 3. Zlib Decompress
            try:
                unzipped_bytes = zlib.decompress(decrypted_bytes)
            except zlib.error:
                 # Sometimes raw deflate is used? Trying -15 just in case
                 unzipped_bytes = zlib.decompress(decrypted_bytes, -15)

            # 4. Remove BOM if present and Decode
            # UTF-8 BOM is \xef\xbb\xbf
            return unzipped_bytes.decode('utf-8-sig')  # 'utf-8-sig' handles BOM automatically
            
        except (ValueError, zlib.error) as e:
            raise DecryptionError(f"QRC Decryption failed: {str(e)}") from e
        except Exception as e:
            raise DecryptionError(f"Unexpected QRC decryption error: {str(e)}") from e


class KugouDecrypt:
    """
    Decrypter for Kugou Music .krc format.
    Algorithm: XOR -> Zlib -> UTF-8
    """
    # Key from reference: [64, 47, 126, 115, 50, 49, ...] -> converted to bytes
    # { 0x40, 0x47, 0x61, 0x77, 0x5e, 0x32, 0x74, 0x47, 0x51, 0x36, 0x31, 0x2d, 0xce, 0xd2, 0x6e, 0x69 }
    MAGIC_KEY = bytes([
        0x40, 0x47, 0x61, 0x77, 0x5e, 0x32, 0x74, 0x47, 
        0x51, 0x36, 0x31, 0x2d, 0xce, 0xd2, 0x6e, 0x69
    ])

    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """
        Decrypts a KRC encrypted string (Base64).
        
        Args:
            encrypted_text: Base64 string of the file content.
            
        Returns:
            Decrypted text.
            
        Raises:
            DecryptionError: If decryption fails.
        """
        try:
            # 1. Base64 Decode
            file_bytes = base64.b64decode(encrypted_text)
            
            # 2. Skip Header (4 bytes)
            if len(file_bytes) <= 4:
                raise DecryptionError("KRC data too short")
                
            encrypted_payload = bytearray(file_bytes[4:])
            
            # 3. XOR Decrypt
            key_len = len(KugouDecrypt.MAGIC_KEY)
            for i in range(len(encrypted_payload)):
                encrypted_payload[i] ^= KugouDecrypt.MAGIC_KEY[i % key_len]
            
            # 4. Zlib Decompress
            try:
                unzipped_bytes = zlib.decompress(encrypted_payload)
            except zlib.error:
                unzipped_bytes = zlib.decompress(encrypted_payload, -15)
                
            # 5. Decode UTF-8 and skip first character (Reference: return res[1..])
            text = unzipped_bytes.decode('utf-8')
            return text[1:] if text else ""
            
        except (ValueError, zlib.error) as e:
            raise DecryptionError(f"KRC Decryption failed: {str(e)}") from e
        except Exception as e:
            raise DecryptionError(f"Unexpected KRC decryption error: {str(e)}") from e
