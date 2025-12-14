import base64
import json
import os
import random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Constants from C# Reference
MODULUS = '00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7'
NONCE = b'0CoJUm6Qyw8W8jud'
PUBKEY = '010001'
IV = b'0102030405060708'

def aes_encrypt(text: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(pad(text, 16)))

def rsa_encrypt(text: bytes, pubkey: str, modulus: str) -> str:
    # RSA encryption for Netease is basically:
    # (reversed_text_as_int ^ pubkey) % modulus
    # But C# uses BigInteger.ModPow
    
    # 1. Reverse text
    text_rev = text[::-1]
    
    # 2. Convert to BigInt (hex -> int)
    # The text is ASCII string, treated as hex? 
    # Reference: BitConverter.ToString(Encoding.Default.GetBytes(srtext)).Replace("-", string.Empty)
    # So it converts text bytes to Hex String, then Parses Hex String to BigInt.
    
    hex_str = text_rev.hex()
    val = int(hex_str, 16)
    
    pub_int = int(pubkey, 16)
    mod_int = int(modulus, 16)
    
    # 3. ModPow
    rs = pow(val, pub_int, mod_int)
    
    # 4. To Hex String, Pad Left 256
    res_hex = f"{rs:x}".zfill(256)
    return res_hex


def encrypt_weapi(data: dict) -> dict:
    """
    Encrypts data dictionary for Netease WeApi.
    Returns dictionary with 'params' and 'encSecKey'.
    """
    text = json.dumps(data).encode('utf-8')
    
    # 1. Create a 16-char secret key
    # Simple fixed key for testing or random? 
    # C# generates random. Let's generate random.
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    secret = "".join(random.choice(chars) for _ in range(16)).encode('utf-8')
    
    # 2. First AES: AES(text, NONCE)
    # Note: NONCE is the key here.
    params = aes_encrypt(text, NONCE, IV)
    
    # 3. Second AES: AES(params, secret)
    # params is base64 bytes from step 2, but aes_encrypt expects bytes input to pad?
    # Wait, reference says: AESEncode(AESEncode(raw, NONCE), _secretKey)
    # AESEncode returns Base64 String.
    # So the input to second AES is the Base64 String from first AES.
    params = aes_encrypt(params, secret, IV)
    
    # 4. RSA Encrypt secret
    enc_sec_key = rsa_encrypt(secret, PUBKEY, MODULUS)
    
    return {
        "params": params.decode('utf-8'),
        "encSecKey": enc_sec_key
    }
