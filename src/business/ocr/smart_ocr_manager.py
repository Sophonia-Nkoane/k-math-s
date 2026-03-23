"""
Smart OCR Manager with Predictive Loading and Caching Strategies

This module extends the basic OCR model manager with intelligent features to minimize
loading times when models need to be reloaded:

- Predictive preloading based on user patterns
- Smart TTL extension when usage is detected
- Background warming of frequently used models
- User activity monitoring for proactive loading
- Configurable preloading strategies
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QObject, QTimer, Signal

from utils.ocr_model_manager import get_ocr_model_manager, OCRModelContext, ModelType


class UsagePattern(Enum):
    """Different usage patterns for OCR models."""
    FREQUENT = auto()      # Used multiple times per hour
    REGULAR = auto()       # Used daily
    OCCASIONAL = auto()    # Used weekly
    RARE = auto()         # Used monthly or less


@dataclass
class UsageStats:
    """Statistics about OCR model usage."""
    total_uses: int = 0
    last_used: Optional[datetime] = None
    average_session_length: float = 0.0  # in seconds
    usage_times: deque = None  # Recent usage timestamps
    pattern: UsagePattern = UsagePattern.RARE
    
    def __post_init__(self):
        if self.usage_times is None:
            self.usage_times = deque(maxlen=50)  # Keep last 50 usage times


class SmartOCRManager(QObject):
    """
    Smart OCR manager that learns usage patterns and preloads models intelligently.
    """
    
    # Signals
    modelPreloading = Signal(str)  # model_name
    modelPreloaded = Signal(str)   # model_name
    usagePatternChanged = Signal(str, UsagePattern)  # model_name, new_pattern
    
    def __init__(self):
        super().__init__()
        
        self.ocr_manager = get_ocr_model_manager()
        if not self.ocr_manager:
            raise RuntimeError("OCR model manager must be initialized first")
        
        # Usage tracking
        self._usage_stats: Dict[str, UsageStats] = defaultdict(UsageStats)
        self._usage_lock = threading.RLock()
        
        # Preloading configuration
        self._preload_enabled = True
        self._preload_on_startup = True
        self._preload_on_activity = True
        
        # Activity monitoring
        self._last_activity = datetime.now()
        self._activity_threshold = timedelta(minutes=5)  # Consider user active if action within 5 min
        
        # Background preloading
        self._preload_timer = QTimer()
        self._preload_timer.timeout.connect(self._check_preload_opportunities)
        self._preload_timer.start(30000)  # Check every 30 seconds
        
        # Pattern analysis timer
        self._pattern_timer = QTimer()
        self._pattern_timer.timeout.connect(self._analyze_usage_patterns)
        self._pattern_timer.start(300000)  # Analyze every 5 minutes
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Smart OCR manager initialized")
        
        # Preload commonly used models if enabled
        if self._preload_on_startup:
            QTimer.singleShot(2000, self._startup_preload)  # Delay 2 seconds
    
    def get_model_with_intelligence(self, model_name: str, 
                                  expected_usage_duration: Optional[int] = None) -> Optional[any]:
        """
        Get OCR model with intelligent loading and TTL management.
        
        Args:
            model_name: Name of the model to get
            expected_usage_duration: Expected usage time in seconds (for TTL optimization)
            
        Returns:
            The loaded model or None if failed
        """
        with self._usage_lock:
            # Update activity tracking
            self._last_activity = datetime.now()
            
            # Record usage attempt
            stats = self._usage_stats[model_name]
            stats.total_uses += 1
            stats.last_used = datetime.now()
            stats.usage_times.append(datetime.now())
            
            # Calculate optimal TTL based on usage pattern and expected duration
            optimal_ttl = self._calculate_optimal_ttl(model_name, expected_usage_duration)
            
            # Get the model (this will load it if not already loaded)
            model = self.ocr_manager.get_model(model_name, ttl_override=optimal_ttl)
            
            if model:
                self.logger.debug(f"Retrieved model '{model_name}' with TTL: {optimal_ttl}s")
                
                # Preload related models if this indicates upcoming usage
                self._trigger_predictive_preload(model_name)
            
            return model
    
    def _calculate_optimal_ttl(self, model_name: str, expected_duration: Optional[int] = None) -> int:
        """Calculate optimal TTL based on usage patterns."""
        stats = self._usage_stats[model_name]
        
        # Base TTL from usage pattern
        base_ttl = {
            UsagePattern.FREQUENT: 600,    # 10 minutes
            UsagePattern.REGULAR: 300,     # 5 minutes  
            UsagePattern.OCCASIONAL: 180,  # 3 minutes
            UsagePattern.RARE: 120         # 2 minutes
        }.get(stats.pattern, 180)
        
        # Adjust based on expected usage duration
        if expected_duration:
            # Add buffer time (50% extra)
            adjusted_ttl = expected_duration + (expected_duration // 2)
            base_ttl = max(base_ttl, adjusted_ttl)
        
        # Consider recent usage frequency
        if len(stats.usage_times) >= 3:
            # If used multiple times recently, extend TTL
            recent_uses = [t for t in stats.usage_times if datetime.now() - t < timedelta(minutes=30)]
            if len(recent_uses) >= 3:
                base_ttl = int(base_ttl * 1.5)  # 50% longer TTL
        
        return min(base_ttl, 1800)  # Cap at 30 minutes
    
    def _trigger_predictive_preload(self, primary_model: str):
        """Trigger preloading of models likely to be used next."""
        if not self._preload_enabled:
            return
        
        # Define model usage correlations (models often used together)
        model_correlations = {
            'tesseract_default': ['easyocr_en'],  # If tesseract fails, might try easyocr
            'easyocr_en': ['paddleocr_en'],       # Might compare results
            'paddleocr_en': ['tesseract_default'] # Might fallback to tesseract
        }
        
        related_models = model_correlations.get(primary_model, [])
        for model_name in related_models:
            if not self.ocr_manager.is_model_loaded(model_name):
                # Check if this model has been used recently
                stats = self._usage_stats[model_name]
                if (stats.last_used and 
                    datetime.now() - stats.last_used < timedelta(hours=1)):
                    
                    self.logger.debug(f"Predictively preloading: {model_name}")
                    self._preload_model_async(model_name)
    
    def _preload_model_async(self, model_name: str):
        """Preload a model in the background."""
        def preload_worker():
            try:
                self.modelPreloading.emit(model_name)
                
                # Calculate shorter TTL for preloaded models
                stats = self._usage_stats[model_name]
                preload_ttl = 300 if stats.pattern in [UsagePattern.FREQUENT, UsagePattern.REGULAR] else 180
                
                model = self.ocr_manager.get_model(model_name, ttl_override=preload_ttl)
                
                if model:
                    self.modelPreloaded.emit(model_name)
                    self.logger.info(f"Successfully preloaded model: {model_name}")
                    
            except Exception as e:
                self.logger.error(f"Failed to preload model {model_name}: {e}")
        
        # Run in background thread to avoid blocking
        thread = threading.Thread(target=preload_worker, daemon=True)
        thread.start()
    
    def _startup_preload(self):
        """Preload frequently used models at startup."""
        try:
            # Preload the most commonly used model (usually tesseract)
            self.logger.info("Performing startup preload of common OCR models")
            
            # Preload tesseract (fast to load, commonly used)
            self._preload_model_async('tesseract_default')
            
            # Preload other models based on historical usage
            for model_name, stats in self._usage_stats.items():
                if stats.pattern == UsagePattern.FREQUENT and stats.total_uses > 10:
                    self.logger.info(f"Startup preloading frequent model: {model_name}")
                    # Delay each preload to spread the load
                    QTimer.singleShot(5000, lambda name=model_name: self._preload_model_async(name))
                    
        except Exception as e:
            self.logger.error(f"Startup preload failed: {e}")
    
    def _check_preload_opportunities(self):
        """Check for opportunities to preload models based on user activity."""
        if not self._preload_on_activity:
            return
        
        current_time = datetime.now()
        
        # If user has been active recently, preload models they might use
        if current_time - self._last_activity < self._activity_threshold:
            self._proactive_preload()
    
    def _proactive_preload(self):
        """Proactively preload models based on current time and usage patterns."""
        current_hour = datetime.now().hour
        
        # Analyze usage patterns by time of day
        for model_name, stats in self._usage_stats.items():
            if not self.ocr_manager.is_model_loaded(model_name):
                # Check if this model is typically used at this time
                if self._is_typical_usage_time(model_name, current_hour):
                    if stats.pattern in [UsagePattern.FREQUENT, UsagePattern.REGULAR]:
                        self.logger.debug(f"Proactively preloading {model_name} (typical usage time)")
                        self._preload_model_async(model_name)
    
    def _is_typical_usage_time(self, model_name: str, current_hour: int) -> bool:
        """Check if current time matches typical usage pattern for a model."""
        stats = self._usage_stats[model_name]
        
        if len(stats.usage_times) < 5:
            return False  # Not enough data
        
        # Get hours when this model was typically used
        usage_hours = [t.hour for t in stats.usage_times]
        hour_counts = defaultdict(int)
        for hour in usage_hours:
            hour_counts[hour] += 1
        
        # If current hour is in top 3 usage hours, consider it typical
        top_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        typical_hours = [hour for hour, count in top_hours]
        
        return current_hour in typical_hours
    
    def _analyze_usage_patterns(self):
        """Analyze usage patterns and update classifications."""
        current_time = datetime.now()
        
        for model_name, stats in self._usage_stats.items():
            if not stats.usage_times:
                continue
            
            # Analyze usage frequency
            recent_uses = [t for t in stats.usage_times if current_time - t < timedelta(days=7)]
            
            old_pattern = stats.pattern
            
            if len(recent_uses) >= 10:  # Used 10+ times in last week
                stats.pattern = UsagePattern.FREQUENT
            elif len(recent_uses) >= 3:  # Used 3+ times in last week
                stats.pattern = UsagePattern.REGULAR
            elif len(recent_uses) >= 1:  # Used at least once in last week
                stats.pattern = UsagePattern.OCCASIONAL
            else:
                stats.pattern = UsagePattern.RARE
            
            # Calculate average session length if we have enough data
            if len(stats.usage_times) >= 3:
                time_diffs = []
                for i in range(1, len(stats.usage_times)):
                    diff = (stats.usage_times[i] - stats.usage_times[i-1]).total_seconds()
                    if diff < 300:  # Within 5 minutes, consider same session
                        time_diffs.append(diff)
                
                if time_diffs:
                    stats.average_session_length = sum(time_diffs) / len(time_diffs)
            
            # Emit signal if pattern changed
            if old_pattern != stats.pattern:
                self.usagePatternChanged.emit(model_name, stats.pattern)
                self.logger.debug(f"Usage pattern for {model_name} changed: {old_pattern.name} -> {stats.pattern.name}")
    
    def get_usage_report(self) -> Dict[str, Dict]:
        """Get detailed usage report for all models."""
        report = {}
        
        with self._usage_lock:
            for model_name, stats in self._usage_stats.items():
                report[model_name] = {
                    'total_uses': stats.total_uses,
                    'pattern': stats.pattern.name,
                    'last_used': stats.last_used.isoformat() if stats.last_used else None,
                    'average_session_length': stats.average_session_length,
                    'recent_usage_count': len([t for t in stats.usage_times 
                                             if datetime.now() - t < timedelta(days=7)]),
                    'is_currently_loaded': self.ocr_manager.is_model_loaded(model_name)
                }
        
        return report
    
    def configure_preloading(self, 
                           enabled: bool = True,
                           startup_preload: bool = True,
                           activity_preload: bool = True):
        """Configure preloading behavior."""
        self._preload_enabled = enabled
        self._preload_on_startup = startup_preload
        self._preload_on_activity = activity_preload
        
        self.logger.info(f"Preloading configured: enabled={enabled}, startup={startup_preload}, activity={activity_preload}")
    
    def preload_for_expected_work(self, model_names: List[str], duration_minutes: int = 30):
        """Preload specific models for expected upcoming work."""
        self.logger.info(f"Preloading models for expected work: {model_names} (duration: {duration_minutes}min)")
        
        for model_name in model_names:
            # Use longer TTL for explicitly requested preloads
            extended_ttl = duration_minutes * 60
            self._preload_model_async_with_ttl(model_name, extended_ttl)
    
    def _preload_model_async_with_ttl(self, model_name: str, ttl: int):
        """Preload model with specific TTL."""
        def preload_worker():
            try:
                self.modelPreloading.emit(model_name)
                model = self.ocr_manager.get_model(model_name, ttl_override=ttl)
                if model:
                    self.modelPreloaded.emit(model_name)
                    self.logger.info(f"Preloaded {model_name} with {ttl}s TTL for expected work")
            except Exception as e:
                self.logger.error(f"Failed to preload {model_name}: {e}")
        
        threading.Thread(target=preload_worker, daemon=True).start()


# Context manager for OCR work sessions
class OCRWorkSession:
    """Context manager for OCR work sessions with smart preloading."""
    
    def __init__(self, smart_manager: SmartOCRManager, 
                 primary_model: str, 
                 backup_models: List[str] = None,
                 expected_duration: int = 300):  # 5 minutes default
        
        self.smart_manager = smart_manager
        self.primary_model = primary_model
        self.backup_models = backup_models or []
        self.expected_duration = expected_duration
        self.models = {}
    
    def __enter__(self):
        # Preload all models for the session
        all_models = [self.primary_model] + self.backup_models
        self.smart_manager.preload_for_expected_work(all_models, self.expected_duration // 60)
        
        # Get primary model immediately
        self.models[self.primary_model] = self.smart_manager.get_model_with_intelligence(
            self.primary_model, self.expected_duration
        )
        
        return self
    
    def get_model(self, model_name: str):
        """Get a model from the session."""
        if model_name not in self.models:
            self.models[model_name] = self.smart_manager.get_model_with_intelligence(
                model_name, self.expected_duration
            )
        return self.models[model_name]
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Models will be automatically cleaned up by their TTLs
        # But we could implement immediate cleanup here if needed for memory pressure
        pass


# Global smart manager instance
_smart_ocr_manager: Optional[SmartOCRManager] = None


def get_smart_ocr_manager() -> Optional[SmartOCRManager]:
    """Get the global smart OCR manager."""
    return _smart_ocr_manager


def initialize_smart_ocr_manager() -> SmartOCRManager:
    """Initialize the smart OCR manager (requires OCR model manager to be initialized first)."""
    global _smart_ocr_manager
    
    if _smart_ocr_manager:
        return _smart_ocr_manager
    
    _smart_ocr_manager = SmartOCRManager()
    return _smart_ocr_manager
