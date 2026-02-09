import base64
from typing import Optional

class AesCryptoService:
    @staticmethod
    def encrypt(data: str, key: str) -> str:
        if not key or len(key) < 10:
            return "ERROR: KEY TOO SHORT"
        
        try:
            # Match btoa(unescape(encodeURIComponent(data)))
            # UTF-8 encoded string -> Base64
            data_bytes = data.encode('utf-8')
            base64_data = base64.b64encode(data_bytes).decode('utf-8')
            
            hash_suffix = key[:8]
            # Match MAGIC_PREFIX + hash + reversed base64
            reversed_base64 = base64_data[::-1]
            return f"AUTOSECURE{hash_suffix}:{reversed_base64}"
        except Exception as e:
            print(f"Encryption failed: {e}")
            return ""

    @staticmethod
    def decrypt(encrypted_data: str, key: str) -> Optional[str]:
        hash_prefix = key[:8]
        magic = f"AUTOSECURE{hash_prefix}:"
        
        if not encrypted_data.startswith(magic):
            print("Invalid magic prefix or key mismatch.")
            return None
        
        try:
            # Extract reversed base64
            base64_content = encrypted_data.split(':', 1)[1]
            # Reverse it back
            original_base64 = base64_content[::-1]
            # Decode Base64 -> UTF-8 String
            data_bytes = base64.b64decode(original_base64)
            return data_bytes.decode('utf-8')
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None
