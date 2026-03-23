"""
OCR Model Manager for Learner Payment Management Application

Manages OCR models with automatic unloading to optimize memory usage.
Only loads models when needed and unloads them after a timeout period.

Features:
- Lazy model loading
- Automatic model unloading after timeout
- Memory usage monitoring
- Model caching with TTL (Time To Live)
- Background cleanup
- Resource optimization
"""

import gc
import logging
import threading
import time
import weakref
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Callable, List
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal


class ModelType(Enum):
    """Types of OCR models."""
    TESSERACT = auto()
    EASYOCR = auto()
    PADDLEOCR = auto()
    CUSTOM = auto()


@dataclass
class ModelInfo:
    """Information about a loaded model."""
    model: Any
    model_type: ModelType
    loaded_at: datetime
    last_used: datetime
    memory_usage: int = 0
    use_count: int = 0
    ttl_seconds: int = 300  # 5 minutes default


class OCRModelManager(QObject):
    """
    Manages OCR models with automatic memory optimization.
    
    Features:
    - Loads models on-demand
    - Unloads models after TTL expires
    - Monitors memory usage
    - Provides model cleanup callbacks
    """
    
    # Signals
    modelLoaded = Signal(str, ModelType)  # model_name, model_type
    modelUnloaded = Signal(str, ModelType)  # model_name, model_type
    memoryCleanup = Signal(int)  # bytes_freed
    
    def __init__(self, 
                 default_ttl: int = 300,  # 5 minutes
                 cleanup_interval: int = 60,  # 1 minute
                 max_memory_mb: int = 500):  # 500MB limit
        """
        Initialize the OCR model manager.
        
        Args:
            default_ttl: Default time-to-live for models in seconds
            cleanup_interval: How often to check for expired models in seconds
            max_memory_mb: Maximum memory usage limit in MB
        """
        super().__init__()
        
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self.max_memory_mb = max_memory_mb
        
        # Model storage
        self._models: Dict[str, ModelInfo] = {}
        self._model_lock = threading.RLock()
        
        # Model loaders registry
        self._loaders: Dict[str, Callable] = {}
        
        # Statistics
        self._stats = {
            'models_loaded': 0,
            'models_unloaded': 0,
            'total_use_count': 0,
            'memory_cleanups': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_expired_models)
        self._cleanup_timer.start(cleanup_interval * 1000)
        
        # Memory monitoring
        self._last_memory_check = time.time()
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"OCR model manager initialized (TTL: {default_ttl}s, max_memory: {max_memory_mb}MB)")
    
    def register_loader(self, model_name: str, loader_func: Callable, model_type: ModelType):
        """
        Register a model loader function.
        
        Args:
            model_name: Unique name for the model
            loader_func: Function that loads and returns the model
            model_type: Type of model
        """
        self._loaders[model_name] = (loader_func, model_type)
        self.logger.debug(f"Registered loader for model: {model_name} ({model_type.name})")
    
    def get_model(self, model_name: str, ttl_override: Optional[int] = None) -> Optional[Any]:
        """
        Get a model, loading it if necessary.
        
        Args:
            model_name: Name of the model to get
            ttl_override: Override the default TTL for this model
            
        Returns:
            The loaded model or None if loading failed
        """
        with self._model_lock:
            # Check if model is already loaded
            if model_name in self._models:
                model_info = self._models[model_name]
                model_info.last_used = datetime.now()
                model_info.use_count += 1
                self._stats['cache_hits'] += 1
                self._stats['total_use_count'] += 1
                
                self.logger.debug(f"Using cached model: {model_name}")
                return model_info.model
            
            # Load the model
            self._stats['cache_misses'] += 1
            return self._load_model(model_name, ttl_override)
    
    def _load_model(self, model_name: str, ttl_override: Optional[int] = None) -> Optional[Any]:
        """Load a model using its registered loader."""
        if model_name not in self._loaders:
            self.logger.error(f"No loader registered for model: {model_name}")
            return None
        
        loader_func, model_type = self._loaders[model_name]
        
        try:
            self.logger.info(f"Loading OCR model: {model_name}")
            start_time = time.time()
            
            # Check memory before loading
            self._check_memory_limits()
            
            # Load the model
            model = loader_func()
            
            if model is None:
                self.logger.error(f"Model loader returned None for: {model_name}")
                return None
            
            # Estimate memory usage
            memory_usage = self._estimate_model_memory(model)
            
            # Create model info
            model_info = ModelInfo(
                model=model,
                model_type=model_type,
                loaded_at=datetime.now(),
                last_used=datetime.now(),
                memory_usage=memory_usage,
                use_count=1,
                ttl_seconds=ttl_override or self.default_ttl
            )
            
            # Store the model
            self._models[model_name] = model_info
            
            load_time = time.time() - start_time
            self._stats['models_loaded'] += 1
            self._stats['total_use_count'] += 1
            
            self.logger.info(f"Model '{model_name}' loaded in {load_time:.2f}s (estimated memory: {memory_usage//1024//1024}MB)")
            self.modelLoaded.emit(model_name, model_type)
            
            return model
            
        except Exception as e:
            self.logger.error(f"Failed to load model '{model_name}': {e}", exc_info=True)
            return None
    
    def _estimate_model_memory(self, model: Any) -> int:
        """Estimate memory usage of a model in bytes."""
        try:
            import sys
            
            # Basic size estimation
            size = sys.getsizeof(model)
            
            # Try to get more accurate size for common model types
            if hasattr(model, '__dict__'):
                for attr_value in model.__dict__.values():
                    size += sys.getsizeof(attr_value)
            
            # For numpy arrays (common in ML models)
            if hasattr(model, 'nbytes'):
                size += model.nbytes
            elif hasattr(model, 'size') and hasattr(model, 'itemsize'):
                size += model.size * model.itemsize
            
            # For PyTorch models
            if hasattr(model, 'parameters'):
                try:
                    import torch
                    param_size = sum(p.numel() * p.element_size() for p in model.parameters())
                    buffer_size = sum(b.numel() * b.element_size() for b in model.buffers())
                    size += param_size + buffer_size
                except ImportError:
                    pass
            
            return max(size, 50 * 1024 * 1024)  # Minimum estimate of 50MB
            
        except Exception as e:
            self.logger.warning(f"Could not estimate model memory: {e}")
            return 100 * 1024 * 1024  # Default 100MB estimate
    
    def _check_memory_limits(self):
        """Check and enforce memory limits."""
        current_time = time.time()
        
        # Only check every 30 seconds to avoid overhead
        if current_time - self._last_memory_check < 30:
            return
        
        self._last_memory_check = current_time
        
        with self._model_lock:
            total_memory = sum(info.memory_usage for info in self._models.values())
            max_memory_bytes = self.max_memory_mb * 1024 * 1024
            
            if total_memory > max_memory_bytes:
                self.logger.warning(f"Model memory usage ({total_memory//1024//1024}MB) exceeds limit ({self.max_memory_mb}MB)")
                
                # Unload least recently used models
                models_by_usage = sorted(
                    self._models.items(),
                    key=lambda x: x[1].last_used
                )
                
                freed_memory = 0
                models_unloaded = 0
                
                for model_name, model_info in models_by_usage:
                    if total_memory - freed_memory <= max_memory_bytes * 0.8:  # 20% buffer
                        break
                    
                    freed_memory += model_info.memory_usage
                    models_unloaded += 1
                    self._unload_model(model_name, reason="memory_limit")
                
                if models_unloaded > 0:
                    self._stats['memory_cleanups'] += 1
                    self.memoryCleanup.emit(freed_memory)
                    self.logger.info(f"Memory cleanup: unloaded {models_unloaded} models, freed {freed_memory//1024//1024}MB")
    
    def _cleanup_expired_models(self):
        """Clean up models that have exceeded their TTL."""
        current_time = datetime.now()
        expired_models = []
        
        with self._model_lock:
            for model_name, model_info in self._models.items():
                time_since_use = current_time - model_info.last_used
                if time_since_use.total_seconds() > model_info.ttl_seconds:
                    expired_models.append(model_name)
        
        # Unload expired models
        for model_name in expired_models:
            self._unload_model(model_name, reason="expired")
        
        if expired_models:
            self.logger.debug(f"Cleaned up {len(expired_models)} expired models")
    
    def _unload_model(self, model_name: str, reason: str = "manual"):
        """Unload a specific model."""
        with self._model_lock:
            if model_name not in self._models:
                return
            
            model_info = self._models.pop(model_name)
            
            try:
                # Try to explicitly delete the model
                del model_info.model
                
                # Force garbage collection
                gc.collect()
                
                self._stats['models_unloaded'] += 1
                
                self.logger.debug(f"Unloaded model '{model_name}' ({reason})")
                self.modelUnloaded.emit(model_name, model_info.model_type)
                
            except Exception as e:
                self.logger.warning(f"Error unloading model '{model_name}': {e}")
    
    def unload_model(self, model_name: str):
        """Manually unload a specific model."""
        self._unload_model(model_name, reason="manual")
    
    def unload_all_models(self):
        """Unload all currently loaded models."""
        with self._model_lock:
            model_names = list(self._models.keys())
        
        for model_name in model_names:
            self._unload_model(model_name, reason="manual_all")
        
        if model_names:
            self.logger.info(f"Unloaded all {len(model_names)} models")
    
    def extend_model_ttl(self, model_name: str, additional_seconds: int):
        """Extend the TTL of a loaded model."""
        with self._model_lock:
            if model_name in self._models:
                model_info = self._models[model_name]
                model_info.ttl_seconds += additional_seconds
                self.logger.debug(f"Extended TTL for '{model_name}' by {additional_seconds}s")
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded models."""
        with self._model_lock:
            model_details = {}
            total_memory = 0
            
            for name, info in self._models.items():
                total_memory += info.memory_usage
                model_details[name] = {
                    'type': info.model_type.name,
                    'loaded_at': info.loaded_at.isoformat(),
                    'last_used': info.last_used.isoformat(),
                    'memory_mb': info.memory_usage // 1024 // 1024,
                    'use_count': info.use_count,
                    'ttl_seconds': info.ttl_seconds
                }
            
            return {
                'loaded_models': len(self._models),
                'total_memory_mb': total_memory // 1024 // 1024,
                'max_memory_mb': self.max_memory_mb,
                'model_details': model_details,
                **self._stats
            }
    
    def preload_model(self, model_name: str, ttl_override: Optional[int] = None):
        """Preload a model for better performance."""
        model = self.get_model(model_name, ttl_override)
        if model:
            self.logger.info(f"Preloaded model: {model_name}")
        else:
            self.logger.warning(f"Failed to preload model: {model_name}")
    
    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is currently loaded."""
        with self._model_lock:
            return model_name in self._models
    
    def shutdown(self):
        """Shutdown the model manager and cleanup resources."""
        self.logger.info("Shutting down OCR model manager")
        
        # Stop cleanup timer
        self._cleanup_timer.stop()
        
        # Unload all models
        self.unload_all_models()
        
        # Clear loaders
        self._loaders.clear()
        
        self.logger.info("OCR model manager shutdown complete")


# Context manager for automatic model cleanup
class OCRModelContext:
    """Context manager for automatic OCR model management."""
    
    def __init__(self, model_manager: OCRModelManager, model_name: str, ttl_override: Optional[int] = None):
        self.model_manager = model_manager
        self.model_name = model_name
        self.ttl_override = ttl_override
        self.model = None
    
    def __enter__(self):
        self.model = self.model_manager.get_model(self.model_name, self.ttl_override)
        return self.model
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Model will be automatically cleaned up by TTL
        # But we could implement immediate cleanup here if needed
        pass


# Factory functions for common OCR models
def create_tesseract_loader(config: Optional[str] = None) -> Callable:
    """Create a Tesseract loader function."""
    def load_tesseract():
        import pytesseract
        
        # Tesseract doesn't have a model object per se, but we can return a configured instance
        class TesseractModel:
            def __init__(self, config):
                self.config = config or '--oem 3 --psm 6'
            
            def extract_text(self, image):
                return pytesseract.image_to_string(image, config=self.config)
            
            def extract_data(self, image):
                return pytesseract.image_to_data(image, config=self.config, output_type=pytesseract.Output.DICT)
        
        return TesseractModel(config)
    
    return load_tesseract


def create_easyocr_loader(languages: List[str] = None) -> Callable:
    """Create an EasyOCR loader function."""
    def load_easyocr():
        try:
            import easyocr
            reader = easyocr.Reader(languages or ['en'], gpu=False)  # CPU only for memory efficiency
            return reader
        except ImportError:
            raise ImportError("EasyOCR not installed. Install with: pip install easyocr")
    
    return load_easyocr


def create_paddleocr_loader(lang: str = 'en') -> Callable:
    """Create a PaddleOCR loader function."""
    def load_paddleocr():
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=False)  # CPU only
            return ocr
        except ImportError:
            raise ImportError("PaddleOCR not installed. Install with: pip install paddlepaddle paddleocr")
    
    return load_paddleocr


# Global model manager instance
_ocr_model_manager: Optional[OCRModelManager] = None


def get_ocr_model_manager() -> Optional[OCRModelManager]:
    """Get the global OCR model manager instance."""
    return _ocr_model_manager


def initialize_ocr_model_manager(**kwargs) -> OCRModelManager:
    """Initialize the global OCR model manager."""
    global _ocr_model_manager
    
    if _ocr_model_manager:
        _ocr_model_manager.shutdown()
    
    _ocr_model_manager = OCRModelManager(**kwargs)
    
    # Register default loaders
    _ocr_model_manager.register_loader(
        "tesseract_default",
        create_tesseract_loader(),
        ModelType.TESSERACT
    )
    
    try:
        _ocr_model_manager.register_loader(
            "easyocr_en",
            create_easyocr_loader(['en']),
            ModelType.EASYOCR
        )
    except ImportError:
        pass  # EasyOCR not available
    
    try:
        _ocr_model_manager.register_loader(
            "paddleocr_en",
            create_paddleocr_loader('en'),
            ModelType.PADDLEOCR
        )
    except ImportError:
        pass  # PaddleOCR not available
    
    return _ocr_model_manager


def shutdown_ocr_model_manager():
    """Shutdown the global OCR model manager."""
    global _ocr_model_manager
    
    if _ocr_model_manager:
        _ocr_model_manager.shutdown()
        _ocr_model_manager = None
