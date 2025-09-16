from .base_backend import Backend
from .selenium_backend import SeleniumBackend

# This makes the classes available for import from the 'backends' package
__all__ = ["Backend", "SeleniumBackend"]