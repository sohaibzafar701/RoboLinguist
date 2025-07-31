"""
Unit tests for TaskManager and TaskQueue components.

Tests task distribution, tracking, and optimal robot utilization logic.
"""

import pytest
import asyncio
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from core.data_models import Task, TaskStatus, RobotState, RobotStatus
from task_orchestrator.task_manager import (
    TaskManager, TaskQueue, TaskPriority, TaskAssignment, QueuedTask
)
from task_orchestrator.robot_registry import RobotRegistry


class TestTaskQueue:
    """Test cases for TaskQueue class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.queue = TaskQueue()
        self.sample_task = Task(
            task_id="test_task_1",
            description="Move to position (1.0, 2.0)",
            estimated_duration=10
        )
    
    def test_add_task_success(self):
        """Test successful task addition."""
        result = self.queue.add_task(self.sample_task, TaskPriority.HIGH)
        assert result is True
        assert self.queue.size() == 1
        assert not self.queue.is_empty()
    
    def test_add_duplicate_task(self):
        """Test adding duplicate task fails."""
        self.queue.add_task(self.sample_task, TaskPriority.HIGH)
        result = self.queue.add_task(self.sample_task, TaskPriority.LOW)
        assert result is False
        assert self.queue.size() == 1
    
    def test_get_next_task_priority_order(self):
        """Test tasks are returned in priority order."""
        low_task = Task(task_id="low", description="Move low priority", estimated_duration=5)
        high_task = Task(task_id="high", description="Move high priority", estimated_duration=5)
        
        self.queue.add_task(low_task, TaskPriority.LOW)
        self.queue.add_task(high_task, TaskPriority.HIGH)
        
        next_task = self.queue.get_next_task()
        assert next_task.task_id == "high"
        
        next_task = self.queue.get_next_task()
        assert next_task.task_id == "low"
    
    def test_get_next_task_empty_queue(self):
        """Test getting task from empty queue."""
        result = self.queue.get_next_task()
        assert result is None
    
    def test_remove_task_success(self):
        """Test successful task removal."""
        self.queue.add_task(self.sample_task, TaskPriority.NORMAL)
        result = self.queue.remove_task("test_task_1")
        assert result is True
        assert self.queue.size() == 0
    
    def test_remove_nonexistent_task(self):
        """Test removing non-existent task."""
        result = self.queue.remove_task("nonexistent")
        assert result is False
    
    def test_mark_completed(self):
        """Test marking task as completed."""
        self.queue.add_task(self.sample_task, TaskPriority.NORMAL)
        result = self.queue.mark_completed("test_task_1")
        assert result is True
    
    def test_get_task_by_id(self):
        """Test retrieving task by ID."""
        self.queue.add_task(self.sample_task, TaskPriority.NORMAL)
        task = self.queue.get_task("test_task_1")
        assert task is not None
        assert task.task_id == "test_task_1"
    
    def test_get_pending_tasks(self):
        """Test getting all pending tasks."""
        task1 = Task(task_id="task1", description="Move task", estimated_duration=5)
        task2 = Task(task_id="task2", description="Rotate task", estimated_duration=3)
        
        self.queue.add_task(task1, TaskPriority.NORMAL)
        self.queue.add_task(task2, TaskPriority.HIGH)
        
        pending = self.queue.get_pending_tasks()
        assert len(pending) == 2
        task_ids = [t.task_id for t in pending]
        assert "task1" in task_ids
        assert "task2" in task_ids


class TestTaskAssignment:
    """Test cases for TaskAssignment class."""
    
    def test_assignment_creation(self):
        """Test task assignment creation."""
        assignment = TaskAssignment("task1", "robot1")
        assert assignment.task_id == "task1"
        assert assignment.robot_id == "robot1"
        assert assignment.assigned_at is not None
        assert assignment.started_at is None
        assert assignment.completed_at is None
    
    def test_get_duration_not_started(self):
        """Test duration calculation when task not started."""
        assignment = TaskAssignment("task1", "robot1")
        duration = assignment.get_duration()
        assert duration is None
    
    def test_get_duration_completed(self):
        """Test duration calculation for completed task."""
        assignment = TaskAssignment("task1", "robot1")
        assignment.started_at = datetime.now()
        time.sleep(0.01)  # Small delay
        assignment.completed_at = datetime.now()
        
        duration = assignment.get_duration()
        assert duration is not None
        assert duration.total_seconds() > 0
    
    def test_is_overdue_no_estimate(self):
        """Test overdue check with no estimated completion."""
        assignment = TaskAssignment("task1", "robot1")
        assert not assignment.is_overdue()
    
    def test_is_overdue_past_estimate(self):
        """Test overdue check with past estimated completion."""
        assignment = TaskAssignment("task1", "robot1")
        assignment.estimated_completion = datetime.now() - timedelta(seconds=1)
        assert assignment.is_overdue()
    
    def test_is_overdue_future_estimate(self):
        """Test overdue check with future estimated completion."""
        assignment = TaskAssignment("task1", "robot1")
        assignment.estimated_completion = datetime.now() + timedelta(seconds=10)
        assert not assignment.is_overdue()


class TestTaskManager:
    """Test cases for TaskManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_registry = Mock(spec=RobotRegistry)
        self.mock_registry.get_available_robots = Mock(return_value=["robot1", "robot2"])
        
        self.config = {
            'assignment_strategy': 'load_balanced',
            'assignment_timeout': 30.0,
            'max_retries': 3,
            'monitor_interval': 1.0
        }
        
        self.task_manager = TaskManager(self.mock_registry, self.config)
        self.sample_task = Task(
            task_id="test_task_1",
            description="Move to position (1.0, 2.0)",
            estimated_duration=10
        )
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        result = await self.task_manager.initialize()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping task manager."""
        start_result = await self.task_manager.start()
        assert start_result is True
        assert self.task_manager._monitoring_active is True
        
        stop_result = await self.task_manager.stop()
        assert stop_result is True
        assert self.task_manager._monitoring_active is False
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when healthy."""
        await self.task_manager.start()
        health = await self.task_manager.health_check()
        
        assert health['component'] == 'task_manager'
        assert health['status'] == 'healthy'
        assert health['monitoring_active'] is True
        assert 'pending_tasks' in health
        assert 'active_tasks' in health
        
        await self.task_manager.stop()
    
    @pytest.mark.asyncio
    async def test_submit_task_success(self):
        """Test successful task submission."""
        result = await self.task_manager.submit_task(self.sample_task, TaskPriority.HIGH)
        assert result is True
        assert self.task_manager.task_queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_submit_duplicate_task(self):
        """Test submitting duplicate task."""
        await self.task_manager.submit_task(self.sample_task, TaskPriority.HIGH)
        result = await self.task_manager.submit_task(self.sample_task, TaskPriority.LOW)
        assert result is False
        assert self.task_manager.task_queue.size() == 1
    
    @pytest.mark.asyncio
    async def test_assign_task_success(self):
        """Test successful task assignment."""
        result = await self.task_manager.assign_task(self.sample_task)
        assert result is True
        assert self.sample_task.assigned_robot in ["robot1", "robot2"]
        assert self.sample_task.status == TaskStatus.ASSIGNED
    
    @pytest.mark.asyncio
    async def test_assign_task_no_robots(self):
        """Test task assignment when no robots available."""
        self.mock_registry.get_available_robots.return_value = []
        result = await self.task_manager.assign_task(self.sample_task)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_task_success(self):
        """Test starting an assigned task."""
        await self.task_manager.assign_task(self.sample_task)
        result = await self.task_manager.start_task("test_task_1")
        assert result is True
        
        assignment = self.task_manager._active_tasks["test_task_1"]
        assert assignment.started_at is not None
    
    @pytest.mark.asyncio
    async def test_start_nonexistent_task(self):
        """Test starting non-existent task."""
        result = await self.task_manager.start_task("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_complete_task_success(self):
        """Test completing a task successfully."""
        await self.task_manager.assign_task(self.sample_task)
        await self.task_manager.start_task("test_task_1")
        
        result = await self.task_manager.complete_task("test_task_1", success=True)
        assert result is True
        assert "test_task_1" in self.task_manager._completed_tasks
        assert "test_task_1" not in self.task_manager._active_tasks
    
    @pytest.mark.asyncio
    async def test_complete_task_failure(self):
        """Test completing a task with failure."""
        await self.task_manager.assign_task(self.sample_task)
        await self.task_manager.start_task("test_task_1")
        
        result = await self.task_manager.complete_task("test_task_1", success=False)
        assert result is True
        assert "test_task_1" in self.task_manager._failed_tasks
        assert "test_task_1" not in self.task_manager._active_tasks
    
    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        """Test cancelling a pending task."""
        await self.task_manager.submit_task(self.sample_task)
        result = await self.task_manager.cancel_task("test_task_1")
        assert result is True
        assert self.task_manager.task_queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_cancel_active_task(self):
        """Test cancelling an active task."""
        await self.task_manager.assign_task(self.sample_task)
        result = await self.task_manager.cancel_task("test_task_1")
        assert result is True
        assert "test_task_1" in self.task_manager._failed_tasks
    
    @pytest.mark.asyncio
    async def test_get_task_status_assigned(self):
        """Test getting status of assigned task."""
        await self.task_manager.assign_task(self.sample_task)
        status = await self.task_manager.get_task_status("test_task_1")
        assert status == TaskStatus.ASSIGNED
    
    @pytest.mark.asyncio
    async def test_get_task_status_executing(self):
        """Test getting status of executing task."""
        await self.task_manager.assign_task(self.sample_task)
        await self.task_manager.start_task("test_task_1")
        status = await self.task_manager.get_task_status("test_task_1")
        assert status == TaskStatus.EXECUTING
    
    @pytest.mark.asyncio
    async def test_get_task_status_completed(self):
        """Test getting status of completed task."""
        await self.task_manager.assign_task(self.sample_task)
        await self.task_manager.start_task("test_task_1")
        await self.task_manager.complete_task("test_task_1", success=True)
        status = await self.task_manager.get_task_status("test_task_1")
        assert status == TaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_get_task_status_unknown(self):
        """Test getting status of unknown task."""
        status = await self.task_manager.get_task_status("unknown_task")
        assert status == "unknown"
    
    @pytest.mark.asyncio
    async def test_get_available_robots(self):
        """Test getting available robots."""
        robots = await self.task_manager.get_available_robots()
        assert robots == ["robot1", "robot2"]
    
    def test_get_task_statistics_empty(self):
        """Test getting statistics with no tasks."""
        stats = self.task_manager.get_task_statistics()
        assert stats['pending_tasks'] == 0
        assert stats['active_tasks'] == 0
        assert stats['completed_tasks'] == 0
        assert stats['failed_tasks'] == 0
        assert stats['success_rate'] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_task_statistics_with_tasks(self):
        """Test getting statistics with completed tasks."""
        # Complete a task
        await self.task_manager.assign_task(self.sample_task)
        await self.task_manager.start_task("test_task_1")
        await self.task_manager.complete_task("test_task_1", success=True)
        
        stats = self.task_manager.get_task_statistics()
        assert stats['completed_tasks'] == 1
        assert stats['success_rate'] == 1.0
    
    @pytest.mark.asyncio
    async def test_round_robin_assignment(self):
        """Test round robin assignment strategy."""
        self.task_manager._current_strategy = 'round_robin'
        
        task1 = Task(task_id="task1", description="Move task 1", estimated_duration=5)
        task2 = Task(task_id="task2", description="Move task 2", estimated_duration=5)
        
        robot1 = await self.task_manager._assign_round_robin(task1)
        robot2 = await self.task_manager._assign_round_robin(task2)
        
        assert robot1 in ["robot1", "robot2"]
        assert robot2 in ["robot1", "robot2"]
        # Should alternate between robots
        assert robot1 != robot2 or len(await self.task_manager.get_available_robots()) == 1
    
    @pytest.mark.asyncio
    async def test_load_balanced_assignment(self):
        """Test load balanced assignment strategy."""
        # Assign one task to create load imbalance
        await self.task_manager.assign_task(self.sample_task)
        
        # Create new task
        new_task = Task(task_id="task2", description="Move task 2", estimated_duration=5)
        robot_id = await self.task_manager._assign_load_balanced(new_task)
        
        assert robot_id in ["robot1", "robot2"]
    
    @pytest.mark.asyncio
    async def test_assignment_with_no_available_robots(self):
        """Test assignment strategies with no available robots."""
        self.mock_registry.get_available_robots.return_value = []
        
        result = await self.task_manager._assign_round_robin(self.sample_task)
        assert result is None
        
        result = await self.task_manager._assign_load_balanced(self.sample_task)
        assert result is None
    
    def test_monitoring_start_stop(self):
        """Test monitoring thread lifecycle."""
        assert not self.task_manager._monitoring_active
        
        self.task_manager._start_monitoring()
        assert self.task_manager._monitoring_active
        assert self.task_manager._monitor_thread is not None
        
        self.task_manager._stop_monitoring()
        assert not self.task_manager._monitoring_active
    
    @pytest.mark.asyncio
    async def test_task_workflow_complete(self):
        """Test complete task workflow from submission to completion."""
        # Submit task
        submit_result = await self.task_manager.submit_task(self.sample_task, TaskPriority.HIGH)
        assert submit_result is True
        
        # Assign task
        assign_result = await self.task_manager.assign_task(self.sample_task)
        assert assign_result is True
        
        # Start task
        start_result = await self.task_manager.start_task("test_task_1")
        assert start_result is True
        
        # Complete task
        complete_result = await self.task_manager.complete_task("test_task_1", success=True)
        assert complete_result is True
        
        # Verify final state
        status = await self.task_manager.get_task_status("test_task_1")
        assert status == TaskStatus.COMPLETED
        
        stats = self.task_manager.get_task_statistics()
        assert stats['completed_tasks'] == 1
        assert stats['success_rate'] == 1.0


class TestQueuedTask:
    """Test cases for QueuedTask class."""
    
    def test_queued_task_comparison_priority(self):
        """Test QueuedTask comparison by priority."""
        task1 = Task(task_id="task1", description="Move task 1", estimated_duration=5)
        task2 = Task(task_id="task2", description="Move task 2", estimated_duration=5)
        
        high_priority = QueuedTask(TaskPriority.HIGH, datetime.now(), task1)
        low_priority = QueuedTask(TaskPriority.LOW, datetime.now(), task2)
        
        # Higher priority should be "less than" (comes first in heap)
        assert high_priority < low_priority
        assert not (low_priority < high_priority)
    
    def test_queued_task_comparison_time(self):
        """Test QueuedTask comparison by creation time for same priority."""
        task1 = Task(task_id="task1", description="Move task 1", estimated_duration=5)
        task2 = Task(task_id="task2", description="Move task 2", estimated_duration=5)
        
        earlier = datetime.now()
        later = earlier + timedelta(seconds=1)
        
        earlier_task = QueuedTask(TaskPriority.NORMAL, earlier, task1)
        later_task = QueuedTask(TaskPriority.NORMAL, later, task2)
        
        # Earlier task should come first for same priority
        assert earlier_task < later_task
        assert not (later_task < earlier_task)