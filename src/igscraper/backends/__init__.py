from .base_backend import Backend
from .selenium_backend import SeleniumBackend
from .instaloader_backend import InstaloaderBackend

# This makes the classes available for import from the 'backends' package
__all__ = ["Backend", "SeleniumBackend", "InstaloaderBackend"]