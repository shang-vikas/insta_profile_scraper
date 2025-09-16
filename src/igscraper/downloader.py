import requests
from pathlib import Path
from .logger import get_logger
import time

logger = get_logger(__name__)

def download_media(url: str, folder: Path, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get('content-type', '')
            if 'image/jpeg' in content_type:
                ext = '.jpg'
            elif 'image/png' in content_type:
                ext = '.png'
            elif 'video/' in content_type:
                ext = '.mp4'
            else:
                ext = '.bin'
            
            # Save file
            file_path = folder / f"media{ext}"
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return False
