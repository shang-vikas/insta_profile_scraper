from abc import ABC, abstractmethod
from typing import Iterator, Any, List, Dict

class Backend(ABC):
    @abstractmethod
    def start(self):
        """Initialize backend resources"""
        pass

    @abstractmethod
    def stop(self):
        """Clean up resources"""
        pass

    @abstractmethod
    def open_profile(self, profile_handle: str) -> None:
        """Navigate to profile page"""
        pass

    @abstractmethod
    def get_post_elements(self, limit: int) -> Iterator[Any]:
        """Get post elements/objects"""
        pass

    @abstractmethod
    def extract_post_metadata(self, post_element: Any) -> Dict:
        """Extract metadata from post element"""
        pass
