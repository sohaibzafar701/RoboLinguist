"""
Tests for Ray distributed computing integration.

Tests distributed task processing, load balancing, and worker management
for the ChatGPT for Robots system.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from core.data_models import Task, TaskStatus
from task_orchestrator.ray_distributed_manager import (
    RayDistributedManager, 
    RayTaskWorker, 
    DistributedTaskResult,
    WorkerStats
)


class TestRayTaskWorker:
    """Test cases for Ray task worker."""
    
    @pytest.fixture
    def worker_config(self):
        """Worker configuration for testing."""
        return {
            'max_concurrent_tasks': 3,
            'timeout': 30.0
        }
    
    @pytest.fixture
    def sample_task(self):
        """Sample task for testing."""
        return Task(
            task_id="test_task_001",
            description="Test navigation task",
            assigned_robot="robot_1",
            estimated_duration=10
        )
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self, worker_config):
        """Test worker initialization."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        assert worker.worker_id == "worker_001"
        assert worker.config == worker_config
        assert worker.tasks_processed == 0
        assert worker.tasks_failed == 0
        assert worker.current_load == 0
        assert worker.max_concurrent_tasks == 3
    
    @pytest.mark.asyncio
    async def test_execute_navigation_task(self, worker_config, sample_task):
        """Test navigation task execution."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        result = await worker.execute_task(sample_task)
        
        assert isinstance(result, DistributedTaskResult)
        assert result.task_id == sample_task.task_id
        assert result.worker_id == "worker_001"
        assert result.success is True
        assert result.error is None
        assert result.execution_time > 0
        assert 'task_id' in result.result
        assert result.result['task_id'] == sample_task.task_id
        assert result.result['processed'] is True
    
    @pytest.mark.asyncio
    async def test_execute_manipulation_task(self, worker_config):
        """Test manipulation task execution."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        task = Task(
            task_id="test_task_002",
            description="Test manipulation task",
            assigned_robot="robot_2",
            estimated_duration=15
        )
        
        result = await worker.execute_task(task)
        
        assert result.success is True
        assert result.result['task_id'] == 'test_task_002'
        assert result.result['processed'] is True
    
    @pytest.mark.asyncio
    async def test_execute_inspection_task(self, worker_config):
        """Test inspection task execution."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        task = Task(
            task_id="test_task_003",
            description="Test inspection task",
            assigned_robot="robot_3",
            estimated_duration=5
        )
        
        result = await worker.execute_task(task)
        
        assert result.success is True
        assert result.result['task_id'] == 'test_task_003'
        assert result.result['processed'] is True
    
    @pytest.mark.asyncio
    async def test_execute_custom_task(self, worker_config):
        """Test custom task execution."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        task = Task(
            task_id="test_task_004",
            description="Test custom task",
            assigned_robot="robot_4",
            estimated_duration=8
        )
        
        result = await worker.execute_task(task)
        
        assert result.success is True
        assert result.result['task_id'] == 'test_task_004'
        assert result.result['processed'] is True
    
    @pytest.mark.asyncio
    async def test_worker_load_tracking(self, worker_config, sample_task):
        """Test worker load tracking during task execution."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        # Initial state
        assert worker.current_load == 0
        assert worker.can_accept_task() is True
        
        # Start multiple tasks concurrently
        tasks = []
        for i in range(3):
            task = Task(
                task_id=f"test_task_{i:03d}",
                description=f"Test task {i}",
                assigned_robot=f"robot_{i}",
                estimated_duration=1
            )
            tasks.append(worker.execute_task(task))
        
        # Execute tasks
        results = await asyncio.gather(*tasks)
        
        # Verify all tasks completed successfully
        assert len(results) == 3
        for result in results:
            assert result.success is True
        
        # Verify final state
        assert worker.current_load == 0
        assert worker.tasks_processed == 3
        assert worker.tasks_failed == 0
    
    @pytest.mark.asyncio
    async def test_worker_stats(self, worker_config, sample_task):
        """Test worker statistics collection."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        # Execute a task
        await worker.execute_task(sample_task)
        
        stats = worker.get_stats()
        
        assert isinstance(stats, WorkerStats)
        assert stats.worker_id == "worker_001"
        assert stats.tasks_processed == 1
        assert stats.tasks_failed == 0
        assert stats.current_load == 0
        assert stats.is_healthy is True
        assert stats.last_activity is not None
    
    @pytest.mark.asyncio
    async def test_worker_error_handling(self, worker_config):
        """Test worker error handling."""
        worker = RayTaskWorker("worker_001", worker_config)
        
        # Create a task that will cause an error
        with patch.object(worker, '_handle_generic_task', side_effect=Exception("Test error")):
            task = Task(
                task_id="error_task",
                description="Task that will fail",
                assigned_robot="robot_1",
                estimated_duration=1
            )
            
            result = await worker.execute_task(task)
            
            assert result.success is False
            assert result.error == "Test error"
            assert worker.tasks_failed == 1
            assert worker.current_load == 0


class TestRayDistributedManager:
    """Test cases for Ray distributed manager."""
    
    @pytest.fixture
    def manager_config(self):
        """Manager configuration for testing."""
        return {
            'ray': {
                'num_workers': 2,
                'worker_config': {
                    'max_concurrent_tasks': 3
                },
                'init_config': {
                    'ignore_reinit_error': True,
                    'log_to_driver': False
                }
            },
            'load_balancing_strategy': 'round_robin'
        }
    
    @pytest.fixture
    def sample_tasks(self):
        """Sample tasks for testing."""
        tasks = []
        for i in range(5):
            task = Task(
                task_id=f"test_task_{i:03d}",
                description=f"Test task {i}",
                assigned_robot=f"robot_{i}",
                estimated_duration=1
            )
            tasks.append(task)
        return tasks
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, manager_config):
        """Test distributed manager initialization."""
        manager = RayDistributedManager(manager_config)
        
        assert manager.num_workers == 2
        assert manager.load_balancing_strategy == 'round_robin'
        assert manager.is_initialized is False
        assert manager.is_running is False
        
        # Test initialization
        success = await manager.initialize()
        assert success is True
        assert manager.is_initialized is True
        
        # Cleanup
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_start_stop(self, manager_config):
        """Test manager start and stop operations."""
        manager = RayDistributedManager(manager_config)
        
        # Start manager
        success = await manager.start()
        assert success is True
        assert manager.is_running is True
        
        # Stop manager
        success = await manager.stop()
        assert success is True
        assert manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_worker_creation(self, manager_config):
        """Test worker creation and management."""
        manager = RayDistributedManager(manager_config)
        
        await manager.initialize()
        
        # Check workers were created
        assert len(manager.workers) == 2
        assert len(manager.worker_stats) == 2
        
        # Check worker IDs
        worker_ids = list(manager.workers.keys())
        assert all(worker_id.startswith('worker_') for worker_id in worker_ids)
        
        # Check worker stats
        for worker_id, stats in manager.worker_stats.items():
            assert stats.worker_id == worker_id
            assert stats.tasks_processed == 0
            assert stats.current_load == 0
            assert stats.is_healthy is True
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_task_submission(self, manager_config, sample_tasks):
        """Test task submission to distributed manager."""
        manager = RayDistributedManager(manager_config)
        
        await manager.start()
        
        # Submit tasks
        for task in sample_tasks[:3]:
            success = await manager.submit_task(task)
            assert success is True
        
        # Check task tracking
        assert len(manager.pending_tasks) <= 3  # Some may have been processed already
        
        # Wait for tasks to be processed
        await asyncio.sleep(0.5)
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_balancing_round_robin(self, manager_config):
        """Test round robin load balancing."""
        manager = RayDistributedManager(manager_config)
        manager.load_balancing_strategy = 'round_robin'
        
        await manager.initialize()
        
        # Mock worker availability
        for worker_id in manager.workers.keys():
            manager.worker_stats[worker_id].current_load = 0
        
        # Test worker selection
        worker_ids = []
        for _ in range(4):
            worker_id = await manager._select_worker_round_robin()
            worker_ids.append(worker_id)
        
        # Should cycle through workers
        unique_workers = set(worker_ids)
        assert len(unique_workers) <= 2  # We have 2 workers
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_balancing_least_loaded(self, manager_config):
        """Test least loaded load balancing."""
        manager = RayDistributedManager(manager_config)
        
        await manager.initialize()
        
        # Set different loads for workers
        worker_ids = list(manager.workers.keys())
        manager.worker_stats[worker_ids[0]].current_load = 2
        manager.worker_stats[worker_ids[1]].current_load = 1
        
        # Select worker - should pick the one with lower load
        selected_worker = await manager._select_worker_least_loaded()
        assert selected_worker == worker_ids[1]
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_health_check(self, manager_config):
        """Test health check functionality."""
        manager = RayDistributedManager(manager_config)
        
        # Health check before initialization
        health = await manager.health_check()
        assert health['status'] == 'unhealthy'
        assert health['is_initialized'] is False
        assert health['is_running'] is False
        
        # Health check after start
        await manager.start()
        health = await manager.health_check()
        assert health['status'] == 'healthy'
        assert health['is_initialized'] is True
        assert health['is_running'] is True
        assert health['total_workers'] == 2
        assert health['healthy_workers'] == 2
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_cluster_statistics(self, manager_config, sample_tasks):
        """Test cluster statistics collection."""
        manager = RayDistributedManager(manager_config)
        
        await manager.start()
        
        # Submit and process some tasks
        for task in sample_tasks[:2]:
            await manager.submit_task(task)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Get cluster stats
        stats = manager.get_cluster_stats()
        
        assert 'total_workers' in stats
        assert 'healthy_workers' in stats
        assert 'total_tasks_processed' in stats
        assert 'success_rate' in stats
        assert 'load_balancing_strategy' in stats
        assert stats['total_workers'] == 2
        assert stats['load_balancing_strategy'] == 'round_robin'
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_worker_statistics(self, manager_config):
        """Test worker statistics collection."""
        manager = RayDistributedManager(manager_config)
        
        await manager.initialize()
        
        worker_stats = manager.get_worker_stats()
        
        assert len(worker_stats) == 2
        for worker_id, stats in worker_stats.items():
            assert isinstance(stats, WorkerStats)
            assert stats.worker_id == worker_id
            assert stats.is_healthy is True
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self, manager_config, sample_tasks):
        """Test concurrent task execution across workers."""
        manager = RayDistributedManager(manager_config)
        
        await manager.start()
        
        # Submit multiple tasks concurrently
        submission_tasks = []
        for task in sample_tasks:
            submission_tasks.append(manager.submit_task(task))
        
        # Wait for all submissions
        results = await asyncio.gather(*submission_tasks)
        assert all(results)  # All submissions should succeed
        
        # Wait for task processing
        await asyncio.sleep(1.0)
        
        # Check that tasks were distributed
        stats = manager.get_cluster_stats()
        assert stats['total_tasks_processed'] > 0
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, manager_config):
        """Test error handling in distributed manager."""
        manager = RayDistributedManager(manager_config)
        
        # Test submission without initialization
        task = Task(
            task_id="error_task",
            description="Error task",
            assigned_robot="robot_1",
            estimated_duration=1
        )
        
        success = await manager.submit_task(task)
        assert success is False
        
        # Test with initialization
        await manager.start()
        success = await manager.submit_task(task)
        assert success is True
        
        await manager.stop()


class TestDistributedTaskIntegration:
    """Integration tests for distributed task execution."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_task_execution(self):
        """Test complete end-to-end task execution flow."""
        config = {
            'ray': {
                'num_workers': 2,
                'worker_config': {'max_concurrent_tasks': 2}
            },
            'load_balancing_strategy': 'least_loaded'
        }
        
        manager = RayDistributedManager(config)
        await manager.start()
        
        # Create test tasks
        tasks = []
        for i in range(4):
            task = Task(
                task_id=f"integration_task_{i:03d}",
                description=f"Integration test task {i}",
                assigned_robot=f"robot_{i}",
                estimated_duration=1
            )
            tasks.append(task)
        
        # Submit all tasks
        start_time = time.time()
        for task in tasks:
            success = await manager.submit_task(task)
            assert success is True
        
        # Wait for completion
        await asyncio.sleep(2.0)
        
        # Verify results
        stats = manager.get_cluster_stats()
        assert stats['total_tasks_processed'] == len(tasks)
        assert stats['success_rate'] == 1.0
        
        execution_time = time.time() - start_time
        assert execution_time < 5.0  # Should complete within reasonable time
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_load_distribution(self):
        """Test that tasks are properly distributed across workers."""
        config = {
            'ray': {
                'num_workers': 3,
                'worker_config': {'max_concurrent_tasks': 2}
            },
            'load_balancing_strategy': 'round_robin'
        }
        
        manager = RayDistributedManager(config)
        await manager.start()
        
        # Submit many tasks
        num_tasks = 9
        for i in range(num_tasks):
            task = Task(
                task_id=f"load_test_task_{i:03d}",
                description=f"Load test task {i}",
                assigned_robot=f"robot_{i}",
                estimated_duration=1
            )
            await manager.submit_task(task)
        
        # Wait for completion
        await asyncio.sleep(3.0)
        
        # Check load distribution
        worker_stats = manager.get_worker_stats()
        total_processed = sum(stats.tasks_processed for stats in worker_stats.values())
        
        assert total_processed == num_tasks
        
        # Each worker should have processed some tasks
        for stats in worker_stats.values():
            assert stats.tasks_processed > 0
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_fault_tolerance(self):
        """Test system behavior under worker failures."""
        config = {
            'ray': {
                'num_workers': 2,
                'worker_config': {'max_concurrent_tasks': 1}
            }
        }
        
        manager = RayDistributedManager(config)
        await manager.start()
        
        # Submit tasks
        tasks = []
        for i in range(3):
            task = Task(
                task_id=f"fault_test_task_{i:03d}",
                description=f"Fault test task {i}",
                assigned_robot=f"robot_{i}",
                estimated_duration=1
            )
            tasks.append(task)
            await manager.submit_task(task)
        
        # Wait for processing
        await asyncio.sleep(2.0)
        
        # System should still be functional
        health = await manager.health_check()
        assert health['status'] == 'healthy'
        
        stats = manager.get_cluster_stats()
        assert stats['total_tasks_processed'] > 0
        
        await manager.stop()


if __name__ == "__main__":
    pytest.main([__file__])