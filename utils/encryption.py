# Encryption utility for secure credential storage
from cryptography.fernet import Fernet
import os
import base64

class CredentialEncryption:
    """
    Handles encryption and decryption of sensitive credentials.
    Uses Fernet symmetric encryption from the cryptography library.
    """
    
    def __init__(self):
        """Initialize with encryption key from environment variable"""
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not found in environment variables. "
                "Please generate one using: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        
        # Convert string key to bytes if needed
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        
        try:
            self.cipher = Fernet(encryption_key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")
    
    def encrypt(self, plain_text: str) -> str:
        """
        Encrypt a plain text string.
        
        Args:
            plain_text: The plain text to encrypt
            
        Returns:
            Encrypted string (base64 encoded)
        """
        if not plain_text:
            return ""
        
        # Convert string to bytes
        plain_bytes = plain_text.encode('utf-8')
        
        # Encrypt
        encrypted_bytes = self.cipher.encrypt(plain_bytes)
        
        # Convert to string for database storage
        encrypted_string = encrypted_bytes.decode('utf-8')
        
        return encrypted_string
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            encrypted_text: The encrypted text to decrypt
            
        Returns:
            Decrypted plain text string
        """
        if not encrypted_text:
            return ""
        
        try:
            # Convert string to bytes
            encrypted_bytes = encrypted_text.encode('utf-8')
            
            # Decrypt
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            
            # Convert back to string
            plain_text = decrypted_bytes.decode('utf-8')
            
            return plain_text
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}. The data may be corrupted or the encryption key may have changed.")
    
    def is_encrypted(self, text: str) -> bool:
        """
        Check if a string appears to be encrypted (Fernet format check).
        
        Args:
            text: The text to check
            
        Returns:
            True if text appears to be encrypted, False otherwise
        """
        if not text:
            return False
        
        try:
            # Fernet encrypted strings are base64 and start with 'gAAAAA'
            # This is a basic check, not 100% accurate but good enough
            self.decrypt(text)
            return True
        except:
            return False


# Singleton instance
_encryption_instance = None

def get_encryption() -> CredentialEncryption:
    """Get or create the encryption singleton instance"""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = CredentialEncryption()
    return _encryption_instance


# Convenience functions
def encrypt_credential(plain_text: str) -> str:
    """Encrypt a credential"""
    return get_encryption().encrypt(plain_text)


def decrypt_credential(encrypted_text: str) -> str:
    """Decrypt a credential"""
    return get_encryption().decrypt(encrypted_text)