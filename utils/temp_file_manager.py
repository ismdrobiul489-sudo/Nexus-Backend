import os
import base64
import httpx
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TempFileManager:
    BASE_DIR = "server_backup/temp_uploads"

    @classmethod
    def _ensure_dir(cls):
        if not os.path.exists(cls.BASE_DIR):
            os.makedirs(cls.BASE_DIR)

    @classmethod
    def save_to_device(cls, data: str, file_name: str) -> str:
        """
        Save a Base64 string to a local file.
        Returns the relative path or URI of the saved file.
        Clones tempFileManager.saveToDevice
        """
        cls._ensure_dir()
        
        # Clean Base64 (Remove header if present)
        if "," in data:
            data = data.split(",")[1]
            
        clean_data = data.replace("\n", "").replace("\r", "").strip()
        
        # Determine Path (Mirroring TS logic: default to temp_uploads)
        if not file_name.startswith("FacebookAutomation/") and "/" not in file_name:
             final_path = os.path.join(cls.BASE_DIR, file_name)
        else:
             # If caller provided a path, we try to respect it relative to root or handle it
             # For backend safety, we flatten or just use BASE_DIR for now to avoid traversal
             safe_name = os.path.basename(file_name)
             final_path = os.path.join(cls.BASE_DIR, safe_name)
             
        # Decode and Write
        try:
            file_bytes = base64.b64decode(clean_data)
            with open(final_path, "wb") as f:
                f.write(file_bytes)
            
            logger.info(f"[TempFile] Saved {len(clean_data)} chars to {final_path}")
            return final_path
        except Exception as e:
            logger.error(f"TempFileManager Save Error: {e}")
            raise e

    @classmethod
    def read_as_bytes(cls, file_path: str) -> bytes:
        """
        Read a local file and return it as Bytes.
        Clones tempFileManager.readAsBlob
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"TempFileManager Read Error: {e}")
            raise e

    @classmethod
    def delete_file(cls, path: str):
        """Deletes a temp file"""
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"[TempFile] Deleted: {path}")
        except Exception as e:
             logger.warning(f"Failed to delete temp file {path}: {e}")

    @classmethod
    async def download_file(cls, url: str, file_name: str, headers: Optional[dict] = None) -> str:
        """
        Downloads a file from a URL to the local temp directory.
        Returns the local file path.
        Clones tempFileManager.downloadFile
        """
        cls._ensure_dir()
        final_path = os.path.join(cls.BASE_DIR, file_name)
        
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    raise Exception(f"Download failed: {resp.status_code}")
                
                with open(final_path, "wb") as f:
                    f.write(resp.content)
            
            return final_path
        except Exception as e:
            logger.error(f"TempFileManager Download Error: {e}")
            raise e
