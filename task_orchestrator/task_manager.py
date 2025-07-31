"""
Task Manager for distributed task assignment and execution.

Manages task distribution, tracking, and optimal robot utilization
for the ChatGPT for Robots fleet control system.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import heapq
import uuid

from core.data_models import Task, TaskStatus, RobotState, RobotStatus
from core.interfaces import ITaskManager
from core.base_component import BaseComponent
from .robot_registry import RobotRegistry, RobotCapability


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class TaskAssignment:
    """Represents a task assignment to a robot."""
    task_id: str
    robot_id: str
    assigned_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    def get_duration(self) -> Optional[timedelta]:
        """Get task execution duration if completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    def is_overdue(self) -> bool:
        """Check if task is overdue based on estimated completion."""
        if self.estimated_completion:
            return datetime.now() > self.estimated_completion
        return False


@dataclass
class QueuedTask:
    """Task wrapper for priority queue."""
    priority: int
    created_at: datetime
    task: Task
    
    def __lt__(self, other):
        """Compare tasks for priority queue (higher priority first)."""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.created_at < other.created_at  # Earlier tasks first for same priority


class TaskQueue:
    """
    Priority-based task queue with scheduling capabilities.
    
    Manages pending tasks with priority-based ordering and dependency resolution.
    """
    
    def __init__(self):
        """Initialize the task queue."""
        self._queue: List[QueuedTask] = []
        self._task_map: Dict[str, Task] = {}
        self._lock = threading.RLock()
        self._completed_tasks: Set[str] = set()
    
    def add_task(self, task: Task, priority: int = TaskPriority.NORMAL) -> bool:
        """
        Add a task to the queue.
        
        Args:
            task: Task to add
            priority: Task priority level
            
        Returns:
            True if task added successfully
        """
        try:
            with self._lock:
                if task.task_id in self._task_map:
                    return False  # Task already exists
                
                queued_task = QueuedTask(
                    priority=priority,
                    created_at=task.created_at,
                    task=task
                )
                
                heapq.heappush(self._queue, queued_task)
                self._task_map[task.task_id] = task
                return True
                
        except Exception:
            return False
    
    def get_next_task(self) -> Optional[Task]:
        """
        Get the next task that can be executed.
        
        Returns:
            Next executable task or None if no tasks available
        """
        with self._lock:
            while self._queue:
                queued_task = heapq.heappop(self._queue)
                task = queued_task.task
                
                # Check if task can start based on dependencies
                if task.can_start(list(self._completed_tasks)):
                    return task
                else:
                    # Put task back if dependencies not met
                    heapq.heappush(self._queue, queued_task)
                    break  # Avoid infinite loop
            
            return None
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.
        
        Args:
            task_id: ID of task to remove
            
        Returns:
            True if task removed successfully
        """
        with self._lock:
            if task_id not in self._task_map:
                return False
            
            # Remove from task map
            del self._task_map[task_id]
            
            # Rebuild queue without the removed task
            new_queue = [qt for qt in self._queue if qt.task.task_id != task_id]
            self._queue = new_queue
            heapq.heapify(self._queue)
            
            return True
    
    def mark_completed(self, task_id: str) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: ID of completed task
            
        Returns:
            True if task marked as completed
        """
        with self._lock:
            if task_id in self._task_map:
                self._completed_tasks.add(task_id)
                return True
            return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with self._lock:
            return self._task_map.get(task_id)
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks."""
        with self._lock:
            return [qt.task for qt in self._queue]
    
    def size(self) -> int:
        """Get number of pending tasks."""
        with self._lock:
            return len(self._queue)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._queue) == 0


class TaskManager(BaseComponent, ITaskManager):
    """
    Task manager for distributed task assignment and execution.
    
    Handles task distribution, tracking, and optimal robot utilization
    across the robot fleet.
    """
    
    def __init__(self, robot_registry: RobotRegistry, config: Optional[Dict[str, Any]] = None, distributed_manager=None):
        """
        Initialize the task manager.
        
        Args:
            robot_registry: Robot registry for fleet management
            config: Configuration dictionary
            distributed_manager: Optional distributed computing manager
        """
        super().__init__("task_manager", config or {})
        self.robot_registry = robot_registry
        self.task_queue = TaskQueue()
        
        # Distributed computing integration
        self.distributed_manager = distributed_manager
        self.use_distributed = self.config.get('use_distributed', False) and distributed_manager is not None
        
        # Task tracking
        self._active_tasks: Dict[str, TaskAssignment] = {}
        self._completed_tasks: Dict[str, TaskAssignment] = {}
        self._failed_tasks: Dict[str, TaskAssignment] = {}
        self._lock = threading.RLock()
        
        # Assignment algorithms
        self._assignment_strategies = {
            'round_robin': self._assign_round_robin,
            'load_balanced': self._assign_load_balanced,
            'capability_based': self._assign_capability_based,
            'nearest_robot': self._assign_nearest_robot
        }
        
        self._current_strategy = self.config.get('assignment_strategy', 'load_balanced')
        self._assignment_timeout = self.config.get('assignment_timeout', 30.0)
        self._max_retries = self.config.get('max_retries', 3)
        
        # Monitoring
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_interval = self.config.get('monitor_interval', 5.0)
        
        # Round robin state
        self._last_assigned_robot_index = 0
    
    async def initialize(self) -> bool:
        """Initialize the task manager."""
        try:
            self.logger.info("Initializing task manager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize task manager: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the task manager and monitoring."""
        try:
            self._start_monitoring()
            self.logger.info("Task manager started with monitoring")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start task manager: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the task manager and monitoring."""
        try:
            self._stop_monitoring()
            self.logger.info("Task manager stopped")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop task manager: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the task manager."""
        try:
            with self._lock:
                return {
                    'component': 'task_manager',
                    'status': 'healthy' if self._monitoring_active else 'unhealthy',
                    'monitoring_active': self._monitoring_active,
                    'pending_tasks': self.task_queue.size(),
                    'active_tasks': len(self._active_tasks),
                    'completed_tasks': len(self._completed_tasks),
                    'failed_tasks': len(self._failed_tasks),
                    'assignment_strategy': self._current_strategy,
                    'timestamp': datetime.now()
                }
        except Exception as e:
            return {
                'component': 'task_manager',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    async def submit_task(self, task: Task, priority: int = TaskPriority.NORMAL) -> bool:
        """
        Submit a new task for execution.
        
        Args:
            task: Task to submit
            priority: Task priority level
            
        Returns:
            True if task submitted successfully
        """
        try:
            # If distributed computing is enabled, submit to distributed manager
            if self.use_distributed and self.distributed_manager:
                success = await self.distributed_manager.submit_task(task)
                if success:
                    self.logger.info(f"Task {task.task_id} submitted to distributed manager with priority {priority}")
                    return True
                else:
                    self.logger.warning(f"Failed to submit task {task.task_id} to distributed manager, falling back to local queue")
            
            # Fall back to local task queue
            if self.task_queue.add_task(task, priority):
                self.logger.info(f"Task {task.task_id} submitted to local queue with priority {priority}")
                return True
            else:
                self.logger.warning(f"Failed to submit task {task.task_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error submitting task {task.task_id}: {e}")
            return False
    
    async def assign_task(self, task: Task) -> bool:
        """
        Assign a task to an available robot.
        
        Args:
            task: Task to assign
            
        Returns:
            True if task assigned successfully
        """
        try:
            # Get assignment strategy
            strategy = self._assignment_strategies.get(self._current_strategy)
            if not strategy:
                self.logger.error(f"Unknown assignment strategy: {self._current_strategy}")
                return False
            
            # Find suitable robot
            robot_id = await strategy(task)
            if not robot_id:
                self.logger.warning(f"No suitable robot found for task {task.task_id}")
                return False
            
            # Create assignment
            assignment = TaskAssignment(
                task_id=task.task_id,
                robot_id=robot_id,
                estimated_completion=datetime.now() + timedelta(seconds=task.estimated_duration)
            )
            
            with self._lock:
                self._active_tasks[task.task_id] = assignment
                task.assigned_robot = robot_id
                task.status = TaskStatus.ASSIGNED
            
            self.logger.info(f"Task {task.task_id} assigned to robot {robot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error assigning task {task.task_id}: {e}")
            return False
    
    async def start_task(self, task_id: str) -> bool:
        """
        Mark a task as started.
        
        Args:
            task_id: ID of task to start
            
        Returns:
            True if task started successfully
        """
        try:
            with self._lock:
                if task_id not in self._active_tasks:
                    return False
                
                assignment = self._active_tasks[task_id]
                assignment.started_at = datetime.now()
                
                # Update task status
                task = self.task_queue.get_task(task_id)
                if task:
                    task.status = TaskStatus.EXECUTING
            
            self.logger.info(f"Task {task_id} started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting task {task_id}: {e}")
            return False
    
    async def complete_task(self, task_id: str, success: bool = True) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: ID of task to complete
            success: Whether task completed successfully
            
        Returns:
            True if task completed successfully
        """
        try:
            with self._lock:
                if task_id not in self._active_tasks:
                    return False
                
                assignment = self._active_tasks[task_id]
                assignment.completed_at = datetime.now()
                
                # Move to appropriate collection
                if success:
                    self._completed_tasks[task_id] = assignment
                    self.task_queue.mark_completed(task_id)
                    status = TaskStatus.COMPLETED
                else:
                    self._failed_tasks[task_id] = assignment
                    status = TaskStatus.FAILED
                
                # Remove from active tasks
                del self._active_tasks[task_id]
                
                # Update task status
                task = self.task_queue.get_task(task_id)
                if task:
                    task.status = status
            
            self.logger.info(f"Task {task_id} completed with success={success}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error completing task {task_id}: {e}")
            return False
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.
        
        Args:
            task_id: ID of task to cancel
            
        Returns:
            True if task cancelled successfully
        """
        try:
            with self._lock:
                # Remove from queue if pending
                if self.task_queue.remove_task(task_id):
                    self.logger.info(f"Pending task {task_id} cancelled")
                    return True
                
                # Cancel active task
                if task_id in self._active_tasks:
                    assignment = self._active_tasks[task_id]
                    assignment.completed_at = datetime.now()
                    self._failed_tasks[task_id] = assignment
                    del self._active_tasks[task_id]
                    
                    self.logger.info(f"Active task {task_id} cancelled")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    async def get_task_status(self, task_id: str) -> str:
        """
        Get the current status of a task.
        
        Args:
            task_id: ID of task to query
            
        Returns:
            Task status string
        """
        try:
            # Check active tasks
            with self._lock:
                if task_id in self._active_tasks:
                    assignment = self._active_tasks[task_id]
                    if assignment.started_at:
                        return TaskStatus.EXECUTING
                    else:
                        return TaskStatus.ASSIGNED
                
                if task_id in self._completed_tasks:
                    return TaskStatus.COMPLETED
                
                if task_id in self._failed_tasks:
                    return TaskStatus.FAILED
            
            # Check pending tasks
            task = self.task_queue.get_task(task_id)
            if task:
                return task.status
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error getting task status for {task_id}: {e}")
            return "error"
    
    async def get_available_robots(self) -> List[str]:
        """
        Get list of available robot IDs.
        
        Returns:
            List of available robot IDs
        """
        return self.robot_registry.get_available_robots()
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        with self._lock:
            total_completed = len(self._completed_tasks)
            total_failed = len(self._failed_tasks)
            total_processed = total_completed + total_failed
            
            # Calculate average execution time
            avg_duration = 0.0
            if self._completed_tasks:
                durations = []
                for assignment in self._completed_tasks.values():
                    duration = assignment.get_duration()
                    if duration:
                        durations.append(duration.total_seconds())
                
                if durations:
                    avg_duration = sum(durations) / len(durations)
            
            stats = {
                'pending_tasks': self.task_queue.size(),
                'active_tasks': len(self._active_tasks),
                'completed_tasks': total_completed,
                'failed_tasks': total_failed,
                'total_processed': total_processed,
                'success_rate': total_completed / total_processed if total_processed > 0 else 0.0,
                'average_duration_seconds': avg_duration,
                'assignment_strategy': self._current_strategy,
                'use_distributed': self.use_distributed
            }
            
            # Add distributed computing statistics if available
            if self.use_distributed and self.distributed_manager:
                try:
                    distributed_stats = self.distributed_manager.get_cluster_stats()
                    stats['distributed'] = distributed_stats
                except Exception as e:
                    self.logger.error(f"Failed to get distributed stats: {e}")
                    stats['distributed'] = {'error': str(e)}
            
            return stats
    
    # Assignment strategy implementations
    
    async def _assign_round_robin(self, task: Task) -> Optional[str]:
        """Round robin assignment strategy."""
        available_robots = await self.get_available_robots()
        if not available_robots:
            return None
        
        # Use round robin to select next robot
        robot_id = available_robots[self._last_assigned_robot_index % len(available_robots)]
        self._last_assigned_robot_index += 1
        
        return robot_id
    
    async def _assign_load_balanced(self, task: Task) -> Optional[str]:
        """Load balanced assignment strategy."""
        available_robots = await self.get_available_robots()
        if not available_robots:
            return None
        
        # Count active tasks per robot
        robot_loads = {robot_id: 0 for robot_id in available_robots}
        
        with self._lock:
            for assignment in self._active_tasks.values():
                if assignment.robot_id in robot_loads:
                    robot_loads[assignment.robot_id] += 1
        
        # Select robot with minimum load
        min_load_robot = min(robot_loads.items(), key=lambda x: x[1])
        return min_load_robot[0]
    
    async def _assign_capability_based(self, task: Task) -> Optional[str]:
        """Capability-based assignment strategy."""
        # This would require task capability requirements
        # For now, fall back to load balanced
        return await self._assign_load_balanced(task)
    
    async def _assign_nearest_robot(self, task: Task) -> Optional[str]:
        """Nearest robot assignment strategy."""
        # This would require task location and robot positions
        # For now, fall back to load balanced
        return await self._assign_load_balanced(task)
    
    def _start_monitoring(self) -> None:
        """Start the task monitoring thread."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
    
    def _stop_monitoring(self) -> None:
        """Stop the task monitoring thread."""
        self._monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                self._check_overdue_tasks()
                self._process_pending_tasks()
                time.sleep(self._monitor_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def _check_overdue_tasks(self) -> None:
        """Check for overdue tasks and handle them."""
        with self._lock:
            overdue_tasks = []
            for task_id, assignment in self._active_tasks.items():
                if assignment.is_overdue():
                    overdue_tasks.append(task_id)
            
            if overdue_tasks:
                self.logger.warning(f"Overdue tasks detected: {overdue_tasks}")
    
    def _process_pending_tasks(self) -> None:
        """Process pending tasks for assignment."""
        try:
            # Get next executable task
            task = self.task_queue.get_next_task()
            if task:
                # Try to assign it
                asyncio.create_task(self.assign_task(task))
        except Exception as e:
            self.logger.error(f"Error processing pending tasks: {e}")