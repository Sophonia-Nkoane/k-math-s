"""
Background Task Manager for Learner Payment Management Application

Handles heavy operations like OCR processing, database operations, and other
tasks that should not block the main UI thread.

Features:
- Thread pool for concurrent task execution
- Task queuing and prioritization
- Progress tracking and callbacks
- Error handling and retry logic
- Resource management
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from queue import PriorityQueue, Empty
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps
import weakref


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    RETRYING = auto()


@dataclass
class TaskResult:
    """Result of a background task execution."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    retry_count: int = 0
    completed_at: Optional[datetime] = None


@dataclass
class BackgroundTask:
    """Represents a background task to be executed."""
    task_id: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    timeout: Optional[float] = None
    progress_callback: Optional[Callable[[str, float], None]] = None
    success_callback: Optional[Callable[[TaskResult], None]] = None
    error_callback: Optional[Callable[[TaskResult], None]] = None
    created_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    
    def __lt__(self, other):
        """For priority queue ordering."""
        if not isinstance(other, BackgroundTask):
            return NotImplemented
        return self.priority.value < other.priority.value


class BackgroundTaskManager:
    """
    Manages background task execution with threading and progress tracking.
    
    Features:
    - Thread pool management
    - Task queuing with priorities
    - Progress tracking
    - Automatic retries
    - Resource cleanup
    - Performance monitoring
    """
    
    def __init__(self, max_workers: int = 4, max_queue_size: int = 100):
        """
        Initialize the background task manager.
        
        Args:
            max_workers: Maximum number of worker threads
            max_queue_size: Maximum number of tasks in queue
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        # Thread pool and task management
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="BgTask")
        self._task_queue = PriorityQueue(maxsize=max_queue_size)
        self._running_tasks: Dict[str, Future] = {}
        self._task_results: Dict[str, TaskResult] = {}
        self._task_history: List[TaskResult] = []
        
        # Control and monitoring
        self._shutdown_event = threading.Event()
        self._worker_thread = None
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0,
            'average_execution_time': 0.0,
            'peak_concurrent_tasks': 0
        }
        
        # Weak references to avoid circular references
        self._progress_callbacks: Dict[str, weakref.ReferenceType] = {}
        
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Start the worker thread
        self._start_worker()
        
        self._logger.info(f"Background task manager initialized with {max_workers} workers")
    
    def _start_worker(self):
        """Start the background worker thread."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="BackgroundTaskWorker",
            daemon=True
        )
        self._worker_thread.start()
    
    def _worker_loop(self):
        """Main worker loop that processes tasks from the queue."""
        while not self._shutdown_event.is_set():
            try:
                # Get next task from queue with timeout
                task = self._task_queue.get(timeout=1.0)
                
                if task is None:  # Poison pill
                    break
                
                # Execute the task
                self._execute_task(task)
                
                self._task_queue.task_done()
                
            except Empty:
                continue  # Timeout, check shutdown event
            except Exception as e:
                self._logger.error(f"Error in worker loop: {e}", exc_info=True)
    
    def submit_task(self, 
                   task_id: str,
                   function: Callable,
                   *args,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   max_retries: int = 3,
                   timeout: Optional[float] = None,
                   progress_callback: Optional[Callable[[str, float], None]] = None,
                   success_callback: Optional[Callable[[TaskResult], None]] = None,
                   error_callback: Optional[Callable[[TaskResult], None]] = None,
                   **kwargs) -> str:
        """
        Submit a task for background execution.
        
        Args:
            task_id: Unique identifier for the task
            function: Function to execute
            *args: Positional arguments for the function
            priority: Task priority
            max_retries: Maximum number of retry attempts
            timeout: Execution timeout in seconds
            progress_callback: Callback for progress updates
            success_callback: Callback for successful completion
            error_callback: Callback for errors
            **kwargs: Keyword arguments for the function
            
        Returns:
            Task ID for tracking
            
        Raises:
            ValueError: If task_id already exists or queue is full
        """
        if task_id in self._running_tasks or task_id in self._task_results:
            raise ValueError(f"Task with ID '{task_id}' already exists")
        
        if self._task_queue.qsize() >= self.max_queue_size:
            raise ValueError("Task queue is full")
        
        task = BackgroundTask(
            task_id=task_id,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
            progress_callback=progress_callback,
            success_callback=success_callback,
            error_callback=error_callback
        )
        
        # Store weak reference to progress callback to avoid memory leaks
        if progress_callback:
            self._progress_callbacks[task_id] = weakref.ref(progress_callback)
        
        self._task_queue.put(task)
        self._stats['total_tasks'] += 1
        
        self._logger.info(f"Task '{task_id}' submitted with priority {priority.name}")
        return task_id
    
    def _execute_task(self, task: BackgroundTask):
        """Execute a single task."""
        start_time = time.time()
        
        # Create task result
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.RUNNING
        )
        
        self._task_results[task.task_id] = result
        
        try:
            self._logger.debug(f"Executing task '{task.task_id}'")
            
            # Submit to thread pool
            future = self._executor.submit(
                self._run_task_with_monitoring,
                task
            )
            
            self._running_tasks[task.task_id] = future
            
            # Update peak concurrent tasks
            current_concurrent = len(self._running_tasks)
            if current_concurrent > self._stats['peak_concurrent_tasks']:
                self._stats['peak_concurrent_tasks'] = current_concurrent
            
            # Wait for completion with timeout
            try:
                task_result = future.result(timeout=task.timeout)
                
                # Update result
                result.status = TaskStatus.COMPLETED
                result.result = task_result
                result.execution_time = time.time() - start_time
                result.completed_at = datetime.now()
                
                # Call success callback
                if task.success_callback:
                    try:
                        task.success_callback(result)
                    except Exception as e:
                        self._logger.error(f"Error in success callback for task '{task.task_id}': {e}")
                
                self._stats['completed_tasks'] += 1
                self._logger.info(f"Task '{task.task_id}' completed successfully in {result.execution_time:.2f}s")
                
            except Exception as e:
                # Task failed
                result.status = TaskStatus.FAILED
                result.error = e
                result.execution_time = time.time() - start_time
                result.completed_at = datetime.now()
                result.retry_count = task.retry_count
                
                # Check if we should retry
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    result.status = TaskStatus.RETRYING
                    
                    self._logger.warning(f"Task '{task.task_id}' failed, retrying ({task.retry_count}/{task.max_retries}): {e}")
                    
                    # Re-queue the task with a delay
                    retry_delay = min(2 ** task.retry_count, 30)  # Exponential backoff, max 30s
                    threading.Timer(retry_delay, lambda: self._task_queue.put(task)).start()
                    
                    return  # Don't finalize yet
                else:
                    self._logger.error(f"Task '{task.task_id}' failed after {task.max_retries} retries: {e}")
                    
                    # Call error callback
                    if task.error_callback:
                        try:
                            task.error_callback(result)
                        except Exception as cb_error:
                            self._logger.error(f"Error in error callback for task '{task.task_id}': {cb_error}")
                    
                    self._stats['failed_tasks'] += 1
            
        finally:
            # Cleanup
            self._running_tasks.pop(task.task_id, None)
            self._task_history.append(result)
            self._update_average_execution_time(result.execution_time)
            self._logger.debug(f"Task '{task.task_id}' finalized with status {result.status.name}")