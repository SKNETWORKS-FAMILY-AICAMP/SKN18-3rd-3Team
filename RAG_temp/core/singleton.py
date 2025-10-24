"""Thread-safe singleton metaclass"""

import threading
from typing import Dict, Any
from abc import ABCMeta


class SingletonMeta(type):
    """
    Thread-safe singleton metaclass.
    
    Usage:
        class MyClass(metaclass=SingletonMeta):
            def __init__(self):
                # initialization code
                pass
    """
    
    _instances: Dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        """
        Create or return existing instance.
        Thread-safe implementation using double-checked locking.
        """
        # First check without lock for performance
        if cls not in cls._instances:
            with cls._lock:
                # Double-check after acquiring lock
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        
        return cls._instances[cls]
    
    @classmethod
    def clear_instances(mcs):
        """Clear all singleton instances (useful for testing)"""
        with mcs._lock:
            mcs._instances.clear()



class SingletonABCMeta(ABCMeta):
    """
    Singleton metaclass that works with ABC (Abstract Base Classes).
    
    This combines SingletonMeta with ABCMeta to allow classes to be both
    singletons and abstract base classes.
    
    Usage:
        class MyClass(ABC, metaclass=SingletonABCMeta):
            @abstractmethod
            def my_method(self):
                pass
    """
    
    _instances: Dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        """
        Create or return existing instance.
        Thread-safe implementation using double-checked locking.
        """
        # First check without lock for performance
        if cls not in cls._instances:
            with cls._lock:
                # Double-check after acquiring lock
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        
        return cls._instances[cls]
    
    @classmethod
    def clear_instances(mcs):
        """Clear all singleton instances (useful for testing)"""
        with mcs._lock:
            mcs._instances.clear()
