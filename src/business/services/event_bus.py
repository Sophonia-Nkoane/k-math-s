"""
Event Bus System for Decoupled Service Communication

This module provides a simple event bus implementation for decoupled
communication between different services in the application.
"""

import logging
from typing import Dict, List, Callable, Any, Optional
from threading import Lock
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Represents an event in the event bus."""
    name: str
    data: Dict[str, Any]
    timestamp: datetime
    source: Optional[str] = None


class EventBus:
    """
    A simple event bus for decoupled service communication.
    
    Features:
    - Subscribe/unsubscribe to events
    - Emit events with data
    - Thread-safe operations
    - Event filtering by name
    """
    
    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
    
    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Name of the event to subscribe to
            callback: Function to call when event is emitted
        """
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
                self.logger.debug(f"Subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Name of the event to unsubscribe from
            callback: Function to remove from subscribers
        """
        with self._lock:
            if event_name in self._subscribers:
                if callback in self._subscribers[event_name]:
                    self._subscribers[event_name].remove(callback)
                    self.logger.debug(f"Unsubscribed from event: {event_name}")
                    
                    # Clean up empty subscriber lists
                    if not self._subscribers[event_name]:
                        del self._subscribers[event_name]
    
    def emit(self, event_name: str, data: Dict[str, Any] = None, source: str = None) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event_name: Name of the event
            data: Optional data to pass with the event
            source: Optional source identifier
        """
        event = Event(
            name=event_name,
            data=data or {},
            timestamp=datetime.now(),
            source=source
        )
        
        with self._lock:
            subscribers = self._subscribers.get(event_name, [])
            
            # Create a copy to avoid modification during iteration
            subscribers_copy = subscribers.copy()
        
        # Call subscribers outside the lock to avoid deadlocks
        for callback in subscribers_copy:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Error in event subscriber for {event_name}: {e}")
    
    def get_subscribers(self, event_name: str) -> List[Callable]:
        """
        Get all subscribers for an event.
        
        Args:
            event_name: Name of the event
            
        Returns:
            List of subscriber callbacks
        """
        with self._lock:
            return self._subscribers.get(event_name, [])
    
    def get_all_events(self) -> List[str]:
        """Get all registered event names."""
        with self._lock:
            return list(self._subscribers.keys())
    
    def clear_subscribers(self, event_name: str = None) -> None:
        """
        Clear subscribers for an event or all events.
        
        Args:
            event_name: Specific event to clear, or None for all events
        """
        with self._lock:
            if event_name:
                if event_name in self._subscribers:
                    del self._subscribers[event_name]
                    self.logger.debug(f"Cleared subscribers for event: {event_name}")
            else:
                self._subscribers.clear()
                self.logger.debug("Cleared all event subscribers")


# Global event bus instance
event_bus = EventBus()


# Convenience functions for common operations
def subscribe(event_name: str, callback: Callable) -> None:
    """Subscribe to an event using the global event bus."""
    event_bus.subscribe(event_name, callback)


def unsubscribe(event_name: str, callback: Callable) -> None:
    """Unsubscribe from an event using the global event bus."""
    event_bus.unsubscribe(event_name, callback)


def emit(event_name: str, data: Dict[str, Any] = None, source: str = None) -> None:
    """Emit an event using the global event bus."""
    event_bus.emit(event_name, data, source)


def get_subscribers(event_name: str) -> List[Callable]:
    """Get subscribers for an event using the global event bus."""
    return event_bus.get_subscribers(event_name)


def get_all_events() -> List[str]:
    """Get all registered events using the global event bus."""
    return event_bus.get_all_events()


def clear_subscribers(event_name: str = None) -> None:
    """Clear subscribers using the global event bus."""
    event_bus.clear_subscribers(event_name)
