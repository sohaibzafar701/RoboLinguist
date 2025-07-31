"""
Ray-based distributed computing integration for task processing.

Provides distributed task execution using Ray framework with load balancing
and parallel robot command execution capabilities.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import uuid

try:
    import ray
    from ray.util.queue import Queue as RayQueue
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    # Mock Ray classes for when Ray is not available
    class ray:
        @staticmethod
        def init(*args, **kwargs):
            pass
        
        @staticmethod
        def shutdown():
            pass
        
        @staticmethod
        def remote(func):
            return func
        
        @staticmethod
        def get(obj):
            return obj
        
        @staticmethod
        def put(obj):
            return obj
    
    class RayQueue:
        def __init__(self, *args, **kwargs):
            self._queue = []
        
        def put(self, item):
            self._queue.append(item)
        
        def get(self, timeout=None):
            if self._queue:
                return self._queue.pop(0)
            return None
        
        def size(self):
            return len(self._queue)

from core.data_models import Task, RobotCommand, TaskStatus
from core.interfaces import ITaskManager
from core.base_component import BaseComponent


@dataclass
class WorkerStats:
    """Statistics for a Ray worker."""
    worker_id: str
    tasks_processed: int = 0
    tasks_failed: int = 0
    last_activity: Optional[datetime] = None
    current_load: int = 0
    is_healthy: bool = True


@dataclass
class DistributedTaskResult:
    """Result from distributed task execution."""
    task_id: str
    worker_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@ray.remote
class RayTaskWorker:
    """
    Ray worker for executing robot tasks in parallel.
    
    Each worker can process robot commands independently and report results
    back to the distributed manager.
    """
    
    def __init__(self, worker_id: str, config: Dict[str, Any] = None):
        """
        Initialize the Ray worker.
        
        Args:
            worker_id: Unique identifier for this worker
            config: Worker configuration
        """
        self.worker_id = worker_id
        self.config = config or {}
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.current_load = 0
        self.max_concurrent_tasks = self.config.get('max_concurrent_tasks', 5)
        self.logger = logging.getLogger(f"ray_worker_{worker_id}")
        
        # Task execution handlers - simplified for current Task model
        self._task_handlers: Dict[str, Callable] = {
            'generic': self._handle_generic_task
        }
    
    async def execute_task(self, task: Task) -> DistributedTaskResult:
        """
        Execute a task on this worker.
        
        Args:
            task: Task to execute
            
        Returns:
            Task execution result
        """
        start_time = time.time()
        self.current_load += 1
        
        try:
            self.logger.info(f"Worker {self.worker_id} executing task {task.task_id}")
            
            # For now, all tasks are handled as generic tasks since Task model doesn't have action_type
            # In a real implementation, this would be determined by task parameters or description
            result = await self._handle_generic_task(task)
            
            execution_time = time.time() - start_time
            self.tasks_processed += 1
            
            return DistributedTaskResult(
                task_id=task.task_id,
                worker_id=self.worker_id,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.tasks_failed += 1
            self.logger.error(f"Worker {self.worker_id} failed to execute task {task.task_id}: {e}")
            
            return DistributedTaskResult(
                task_id=task.task_id,
                worker_id=self.worker_id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
        
        finally:
            self.current_load -= 1
    
    async def _handle_generic_task(self, task: Task) -> Dict[str, Any]:
        """Handle generic task execution."""
        # Simulate task processing time based on estimated duration
        processing_time = min(task.estimated_duration * 0.1, 0.5)  # Cap at 0.5 seconds for testing
        await asyncio.sleep(processing_time)
        
        return {
            'task_id': task.task_id,
            'description': task.description,
            'robot_id': task.assigned_robot,
            'estimated_duration': task.estimated_duration,
            'processed': True,
            'processing_time': processing_time
        }
    
    def get_stats(self) -> WorkerStats:
        """Get worker statistics."""
        return WorkerStats(
            worker_id=self.worker_id,
            tasks_processed=self.tasks_processed,
            tasks_failed=self.tasks_failed,
            last_activity=datetime.now(),
            current_load=self.current_load,
            is_healthy=True
        )
    
    def can_accept_task(self) -> bool:
        """Check if worker can accept more tasks."""
        return self.current_load < self.max_concurrent_tasks


class RayDistributedManager(BaseComponent):
    """
    Ray-based distributed task processing manager.
    
    Manages Ray cluster, workers, and distributed task execution with
    load balancing and fault tolerance.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the distributed manager.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__("ray_distributed_manager", config or {})
        
        if not RAY_AVAILABLE:
            self.logger.warning("Ray not available, running in mock mode")
        
        # Ray configuration
        self.ray_config = self.config.get('ray', {})
        self.num_workers = self.ray_config.get('num_workers', 4)
        self.worker_config = self.ray_config.get('worker_config', {})
        
        # Worker management
        self.workers: Dict[str, Any] = {}  # worker_id -> Ray actor reference
        self.worker_stats: Dict[str, WorkerStats] = {}
        self.task_queue: Optional[RayQueue] = None
        self.result_queue: Optional[RayQueue] = None
        
        # Load balancing
        self.load_balancing_strategy = self.config.get('load_balancing_strategy', 'round_robin')
        self.current_worker_index = 0
        
        # Monitoring
        self.is_initialized = False
        self.is_running = False
        
        # Task tracking
        self.pending_tasks: Dict[str, Task] = {}
        self.executing_tasks: Dict[str, str] = {}  # task_id -> worker_id
    
    async def initialize(self) -> bool:
        """Initialize Ray cluster and workers."""
        try:
            if not RAY_AVAILABLE:
                self.logger.warning("Ray not available, running in mock mode")
                # Create mock workers for testing
                await self._create_workers()
                self.is_initialized = True
                return True
            
            self.logger.info("Initializing Ray distributed manager")
            
            # Initialize Ray
            ray_init_config = {
                'ignore_reinit_error': True,
                'log_to_driver': False,
                **self.ray_config.get('init_config', {})
            }
            
            ray.init(**ray_init_config)
            
            # Create task and result queues
            self.task_queue = RayQueue(maxsize=1000)
            self.result_queue = RayQueue(maxsize=1000)
            
            # Create workers
            await self._create_workers()
            
            self.is_initialized = True
            self.logger.info(f"Ray distributed manager initialized with {len(self.workers)} workers")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Ray distributed manager: {e}")
            return False
    
    async def start(self) -> bool:
        """Start distributed task processing."""
        try:
            if not self.is_initialized:
                if not await self.initialize():
                    return False
            
            self.is_running = True
            
            # Start result processing
            asyncio.create_task(self._process_results())
            
            self.logger.info("Ray distributed manager started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Ray distributed manager: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop distributed task processing and shutdown Ray."""
        try:
            self.is_running = False
            
            if RAY_AVAILABLE:
                # Shutdown Ray
                ray.shutdown()
            
            self.logger.info("Ray distributed manager stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop Ray distributed manager: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the distributed manager."""
        try:
            healthy_workers = sum(1 for stats in self.worker_stats.values() if stats.is_healthy)
            
            return {
                'component': 'ray_distributed_manager',
                'status': 'healthy' if self.is_running and healthy_workers > 0 else 'unhealthy',
                'ray_available': RAY_AVAILABLE,
                'is_initialized': self.is_initialized,
                'is_running': self.is_running,
                'total_workers': len(self.workers),
                'healthy_workers': healthy_workers,
                'pending_tasks': len(self.pending_tasks),
                'executing_tasks': len(self.executing_tasks),
                'load_balancing_strategy': self.load_balancing_strategy,
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {
                'component': 'ray_distributed_manager',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    async def submit_task(self, task: Task) -> bool:
        """
        Submit a task for distributed execution.
        
        Args:
            task: Task to execute
            
        Returns:
            True if task submitted successfully
        """
        try:
            if not self.is_running:
                self.logger.error("Distributed manager not running")
                return False
            
            # Add to pending tasks
            self.pending_tasks[task.task_id] = task
            
            # Submit to task queue
            if self.task_queue:
                self.task_queue.put(task)
            
            # Assign to worker
            await self._assign_task_to_worker(task)
            
            self.logger.info(f"Task {task.task_id} submitted for distributed execution")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to submit task {task.task_id}: {e}")
            return False
    
    async def _create_workers(self) -> None:
        """Create Ray workers."""
        for i in range(self.num_workers):
            worker_id = f"worker_{i}_{uuid.uuid4().hex[:8]}"
            
            if RAY_AVAILABLE:
                worker = RayTaskWorker.remote(worker_id, self.worker_config)
            else:
                # Mock worker for testing
                worker = RayTaskWorker(worker_id, self.worker_config)
            
            self.workers[worker_id] = worker
            self.worker_stats[worker_id] = WorkerStats(worker_id=worker_id)
            
            self.logger.info(f"Created worker {worker_id}")
    
    async def _assign_task_to_worker(self, task: Task) -> bool:
        """
        Assign a task to an available worker using load balancing.
        
        Args:
            task: Task to assign
            
        Returns:
            True if task assigned successfully
        """
        try:
            # Select worker based on load balancing strategy
            worker_id = await self._select_worker(task)
            if not worker_id:
                self.logger.warning(f"No available worker for task {task.task_id}")
                return False
            
            worker = self.workers[worker_id]
            
            # Execute task on worker
            if RAY_AVAILABLE:
                future = worker.execute_task.remote(task)
                # Store the future for result processing
                asyncio.create_task(self._handle_task_execution(task.task_id, worker_id, future))
            else:
                # Mock execution
                result = await worker.execute_task(task)
                await self._handle_task_result(result)
            
            # Track executing task
            self.executing_tasks[task.task_id] = worker_id
            
            # Remove from pending
            if task.task_id in self.pending_tasks:
                del self.pending_tasks[task.task_id]
            
            self.logger.info(f"Task {task.task_id} assigned to worker {worker_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign task {task.task_id}: {e}")
            return False
    
    async def _select_worker(self, task: Task) -> Optional[str]:
        """
        Select a worker based on load balancing strategy.
        
        Args:
            task: Task to assign
            
        Returns:
            Selected worker ID or None if no workers available
        """
        if not self.workers:
            return None
        
        if self.load_balancing_strategy == 'round_robin':
            return await self._select_worker_round_robin()
        elif self.load_balancing_strategy == 'least_loaded':
            return await self._select_worker_least_loaded()
        elif self.load_balancing_strategy == 'random':
            return await self._select_worker_random()
        else:
            # Default to round robin
            return await self._select_worker_round_robin()
    
    async def _select_worker_round_robin(self) -> Optional[str]:
        """Select worker using round robin strategy."""
        worker_ids = list(self.workers.keys())
        if not worker_ids:
            return None
        
        # Check if current worker can accept tasks
        for _ in range(len(worker_ids)):
            worker_id = worker_ids[self.current_worker_index % len(worker_ids)]
            self.current_worker_index += 1
            
            if await self._can_worker_accept_task(worker_id):
                return worker_id
        
        return None
    
    async def _select_worker_least_loaded(self) -> Optional[str]:
        """Select worker with least load."""
        available_workers = []
        
        for worker_id in self.workers.keys():
            if await self._can_worker_accept_task(worker_id):
                load = self.worker_stats[worker_id].current_load
                available_workers.append((worker_id, load))
        
        if not available_workers:
            return None
        
        # Sort by load and return least loaded
        available_workers.sort(key=lambda x: x[1])
        return available_workers[0][0]
    
    async def _select_worker_random(self) -> Optional[str]:
        """Select worker randomly."""
        import random
        
        available_workers = []
        for worker_id in self.workers.keys():
            if await self._can_worker_accept_task(worker_id):
                available_workers.append(worker_id)
        
        if not available_workers:
            return None
        
        return random.choice(available_workers)
    
    async def _can_worker_accept_task(self, worker_id: str) -> bool:
        """Check if worker can accept more tasks."""
        if worker_id not in self.workers:
            return False
        
        stats = self.worker_stats.get(worker_id)
        if not stats or not stats.is_healthy:
            return False
        
        # Check current load
        max_load = self.worker_config.get('max_concurrent_tasks', 5)
        return stats.current_load < max_load
    
    async def _handle_task_execution(self, task_id: str, worker_id: str, future) -> None:
        """Handle task execution and result processing."""
        try:
            if RAY_AVAILABLE:
                result = ray.get(future)
            else:
                result = future
            
            await self._handle_task_result(result)
            
        except Exception as e:
            self.logger.error(f"Task {task_id} execution failed on worker {worker_id}: {e}")
            
            # Create error result
            error_result = DistributedTaskResult(
                task_id=task_id,
                worker_id=worker_id,
                success=False,
                error=str(e)
            )
            await self._handle_task_result(error_result)
    
    async def _handle_task_result(self, result: DistributedTaskResult) -> None:
        """Handle task execution result."""
        try:
            # Update worker stats
            if result.worker_id in self.worker_stats:
                stats = self.worker_stats[result.worker_id]
                stats.last_activity = datetime.now()
                stats.current_load = max(0, stats.current_load - 1)
                
                if result.success:
                    stats.tasks_processed += 1
                else:
                    stats.tasks_failed += 1
            
            # Remove from executing tasks
            if result.task_id in self.executing_tasks:
                del self.executing_tasks[result.task_id]
            
            # Add to result queue for external processing
            if self.result_queue:
                self.result_queue.put(result)
            
            self.logger.info(f"Task {result.task_id} completed on worker {result.worker_id} "
                           f"(success={result.success}, time={result.execution_time:.2f}s)")
            
        except Exception as e:
            self.logger.error(f"Failed to handle task result for {result.task_id}: {e}")
    
    async def _process_results(self) -> None:
        """Process task results from the result queue."""
        while self.is_running:
            try:
                if self.result_queue and self.result_queue.size() > 0:
                    result = self.result_queue.get(timeout=1.0)
                    if result:
                        # Results are already processed in _handle_task_result
                        # This is for additional result processing if needed
                        pass
                else:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error processing results: {e}")
                await asyncio.sleep(1.0)
    
    def get_worker_stats(self) -> Dict[str, WorkerStats]:
        """Get statistics for all workers."""
        return self.worker_stats.copy()
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get overall cluster statistics."""
        total_processed = sum(stats.tasks_processed for stats in self.worker_stats.values())
        total_failed = sum(stats.tasks_failed for stats in self.worker_stats.values())
        total_load = sum(stats.current_load for stats in self.worker_stats.values())
        healthy_workers = sum(1 for stats in self.worker_stats.values() if stats.is_healthy)
        
        return {
            'total_workers': len(self.workers),
            'healthy_workers': healthy_workers,
            'total_tasks_processed': total_processed,
            'total_tasks_failed': total_failed,
            'current_total_load': total_load,
            'pending_tasks': len(self.pending_tasks),
            'executing_tasks': len(self.executing_tasks),
            'success_rate': total_processed / (total_processed + total_failed) if (total_processed + total_failed) > 0 else 0.0,
            'load_balancing_strategy': self.load_balancing_strategy
        }