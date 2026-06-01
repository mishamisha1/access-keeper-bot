"""Secure secrets management with encryption."""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manage secrets with encryption at rest."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.secrets_file = self.db_path.parent / "encrypted_secrets.json"
        self.key_file = self.db_path.parent / ".secret_key"
        self._fernet: Optional[Fernet] = None
        self._cache: Dict[str, Any] = {}
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load encryption key
        self._init_encryption()

    def _init_encryption(self):
        """Initialize encryption key."""
        if self.key_file.exists():
            # Load existing key
            with open(self.key_file, 'rb') as f:
                key = f.read()
            self._fernet = Fernet(key)
            logger.debug("Loaded existing encryption key")
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(self.key_file, 0o600)
            self._fernet = Fernet(key)
            logger.info("Generated new encryption key")

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def save_secret(self, key: str, value: Any, encrypt: bool = True):
        """Save a secret with optional encryption."""
        # Load existing secrets
        secrets = self._load_secrets()
        
        if encrypt and self._fernet:
            # Encrypt the value
            data = json.dumps(value).encode()
            encrypted_value = self._fernet.encrypt(data)
            secrets[key] = {
                'encrypted': True,
                'value': encrypted_value.decode()
            }
        else:
            secrets[key] = {
                'encrypted': False,
                'value': value
            }
        
        # Save secrets
        self._save_secrets(secrets)
        self._cache[key] = value
        logger.debug(f"Saved secret: {key}")

    def get_secret(self, key: str, default: Any = None) -> Any:
        """Get a secret, decrypting if necessary."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        secrets = self._load_secrets()
        
        if key not in secrets:
            return default
        
        secret_data = secrets[key]
        
        if secret_data.get('encrypted', False):
            if not self._fernet:
                raise ValueError("Encryption not initialized but encrypted secret found")
            
            encrypted_value = secret_data['value'].encode()
            try:
                decrypted_data = self._fernet.decrypt(encrypted_value)
                value = json.loads(decrypted_data.decode())
            except Exception as e:
                logger.error(f"Failed to decrypt secret {key}: {e}")
                return default
        else:
            value = secret_data['value']
        
        # Cache the value
        self._cache[key] = value
        return value

    def delete_secret(self, key: str):
        """Delete a secret."""
        secrets = self._load_secrets()
        if key in secrets:
            del secrets[key]
            self._save_secrets(secrets)
            self._cache.pop(key, None)
            logger.debug(f"Deleted secret: {key}")

    def _load_secrets(self) -> Dict[str, Any]:
        """Load secrets from file."""
        if not self.secrets_file.exists():
            return {}
        
        try:
            with open(self.secrets_file, 'r') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secrets file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            return {}

    def _save_secrets(self, secrets: Dict[str, Any]):
        """Save secrets to file."""
        try:
            with open(self.secrets_file, 'w') as f:
                json.dump(secrets, f, indent=2)
            # Set restrictive permissions
            os.chmod(self.secrets_file, 0o600)
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise

    def clear_cache(self):
        """Clear the secrets cache."""
        self._cache.clear()
