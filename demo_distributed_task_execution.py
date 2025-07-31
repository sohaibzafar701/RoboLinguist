#!/usr/bin/env python3
"""
Demo script for distributed task execution using Ray.

Demonstrates the integration of Ray distributed computing with the
ChatGPT for Robots task management system.
"""

import asyncio
import time
from datetime import datetime
from typing import List

from core.data_models import Task, TaskStatus
from task_orchestrator.task_manager import TaskManager
from task_orchestrator.robot_registry import RobotRegistry
from task_orchestrator.ray_distributed_manager import RayDistributedManager


async def create_sample_tasks(num_tasks: int = 10) -> List[Task]:
    """Create sample tasks for demonstration."""
    tasks = []
    
    task_descriptions = [
        "Navigate to warehouse entrance",
        "Pick up package from shelf A",
        "Inspect inventory in zone B",
        "Move to charging station",
        "Deliver package to loading dock",
        "Scan barcode on item 12345",
        "Return to home position",
        "Check battery level",
        "Navigate to maintenance area",
        "Perform system diagnostics"
    ]
    
    for i in range(num_tasks):
        task = Task(
            task_id=f"demo_task_{i:03d}",
            description=task_descriptions[i % len(task_descriptions)],
            assigned_robot=f"robot_{i % 3}",  # Distribute across 3 robots
            estimated_duration=5 + (i % 10)  # 5-14 seconds
        )
        tasks.append(task)
    
    return tasks


async def demo_local_task_execution():
    """Demonstrate local (non-distributed) task execution."""
    print("=" * 60)
    print("DEMO: Local Task Execution")
    print("=" * 60)
    
    # Create robot registry and task manager
    robot_registry = RobotRegistry()
    task_manager = TaskManager(robot_registry)
    
    # Initialize and start
    await task_manager.initialize()
    await task_manager.start()
    
    # Create and submit tasks
    tasks = await create_sample_tasks(5)
    
    print(f"Submitting {len(tasks)} tasks for local execution...")
    start_time = time.time()
    
    for task in tasks:
        success = await task_manager.submit_task(task)
        print(f"  Task {task.task_id}: {'✓' if success else '✗'}")
    
    # Wait a bit for processing
    await asyncio.sleep(2.0)
    
    # Get statistics
    stats = task_manager.get_task_statistics()
    execution_time = time.time() - start_time
    
    print(f"\nLocal Execution Results:")
    print(f"  Execution time: {execution_time:.2f}s")
    print(f"  Pending tasks: {stats['pending_tasks']}")
    print(f"  Active tasks: {stats['active_tasks']}")
    print(f"  Completed tasks: {stats['completed_tasks']}")
    print(f"  Failed tasks: {stats['failed_tasks']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    
    await task_manager.stop()


async def demo_distributed_task_execution():
    """Demonstrate distributed task execution with Ray."""
    print("\n" + "=" * 60)
    print("DEMO: Distributed Task Execution")
    print("=" * 60)
    
    # Create distributed manager
    distributed_config = {
        'ray': {
            'num_workers': 4,
            'worker_config': {
                'max_concurrent_tasks': 3
            }
        },
        'load_balancing_strategy': 'least_loaded'
    }
    
    distributed_manager = RayDistributedManager(distributed_config)
    
    # Create robot registry and task manager with distributed support
    robot_registry = RobotRegistry()
    task_manager_config = {
        'use_distributed': True,
        'assignment_strategy': 'load_balanced'
    }
    
    task_manager = TaskManager(
        robot_registry, 
        task_manager_config, 
        distributed_manager
    )
    
    # Initialize and start
    await distributed_manager.initialize()
    await distributed_manager.start()
    await task_manager.initialize()
    await task_manager.start()
    
    # Create and submit tasks
    tasks = await create_sample_tasks(12)
    
    print(f"Submitting {len(tasks)} tasks for distributed execution...")
    start_time = time.time()
    
    # Submit tasks concurrently
    submission_tasks = []
    for task in tasks:
        submission_tasks.append(task_manager.submit_task(task))
    
    results = await asyncio.gather(*submission_tasks)
    successful_submissions = sum(1 for r in results if r)
    
    print(f"  Successfully submitted: {successful_submissions}/{len(tasks)} tasks")
    
    # Wait for processing
    print("  Processing tasks...")
    await asyncio.sleep(3.0)
    
    # Get statistics
    stats = task_manager.get_task_statistics()
    cluster_stats = distributed_manager.get_cluster_stats()
    worker_stats = distributed_manager.get_worker_stats()
    execution_time = time.time() - start_time
    
    print(f"\nDistributed Execution Results:")
    print(f"  Execution time: {execution_time:.2f}s")
    print(f"  Task Manager Stats:")
    print(f"    Pending tasks: {stats['pending_tasks']}")
    print(f"    Active tasks: {stats['active_tasks']}")
    print(f"    Completed tasks: {stats['completed_tasks']}")
    print(f"    Success rate: {stats['success_rate']:.1%}")
    
    print(f"  Distributed Cluster Stats:")
    print(f"    Total workers: {cluster_stats['total_workers']}")
    print(f"    Healthy workers: {cluster_stats['healthy_workers']}")
    print(f"    Tasks processed: {cluster_stats['total_tasks_processed']}")
    print(f"    Cluster success rate: {cluster_stats['success_rate']:.1%}")
    print(f"    Load balancing: {cluster_stats['load_balancing_strategy']}")
    
    print(f"  Worker Performance:")
    for worker_id, worker_stat in worker_stats.items():
        print(f"    {worker_id}: {worker_stat.tasks_processed} tasks, "
              f"load: {worker_stat.current_load}, "
              f"healthy: {'✓' if worker_stat.is_healthy else '✗'}")
    
    await task_manager.stop()
    await distributed_manager.stop()


async def demo_performance_comparison():
    """Compare performance between local and distributed execution."""
    print("\n" + "=" * 60)
    print("DEMO: Performance Comparison")
    print("=" * 60)
    
    num_tasks = 20
    
    # Test local execution
    print(f"Testing local execution with {num_tasks} tasks...")
    robot_registry = RobotRegistry()
    local_manager = TaskManager(robot_registry)
    
    await local_manager.initialize()
    await local_manager.start()
    
    local_tasks = await create_sample_tasks(num_tasks)
    local_start = time.time()
    
    for task in local_tasks:
        await local_manager.submit_task(task)
    
    await asyncio.sleep(1.0)  # Wait for processing
    local_time = time.time() - local_start
    local_stats = local_manager.get_task_statistics()
    
    await local_manager.stop()
    
    # Test distributed execution
    print(f"Testing distributed execution with {num_tasks} tasks...")
    distributed_config = {
        'ray': {
            'num_workers': 6,
            'worker_config': {'max_concurrent_tasks': 4}
        },
        'load_balancing_strategy': 'round_robin'
    }
    
    distributed_manager = RayDistributedManager(distributed_config)
    robot_registry = RobotRegistry()
    distributed_task_manager = TaskManager(
        robot_registry, 
        {'use_distributed': True}, 
        distributed_manager
    )
    
    await distributed_manager.initialize()
    await distributed_manager.start()
    await distributed_task_manager.initialize()
    await distributed_task_manager.start()
    
    distributed_tasks = await create_sample_tasks(num_tasks)
    distributed_start = time.time()
    
    # Submit all tasks concurrently
    submission_tasks = [
        distributed_task_manager.submit_task(task) 
        for task in distributed_tasks
    ]
    await asyncio.gather(*submission_tasks)
    
    await asyncio.sleep(1.0)  # Wait for processing
    distributed_time = time.time() - distributed_start
    distributed_stats = distributed_task_manager.get_task_statistics()
    cluster_stats = distributed_manager.get_cluster_stats()
    
    await distributed_task_manager.stop()
    await distributed_manager.stop()
    
    # Compare results
    print(f"\nPerformance Comparison Results:")
    print(f"  Local Execution:")
    print(f"    Time: {local_time:.2f}s")
    print(f"    Tasks processed: {local_stats['completed_tasks']}")
    print(f"    Throughput: {local_stats['completed_tasks']/local_time:.1f} tasks/sec")
    
    print(f"  Distributed Execution:")
    print(f"    Time: {distributed_time:.2f}s")
    print(f"    Tasks processed: {cluster_stats['total_tasks_processed']}")
    print(f"    Throughput: {cluster_stats['total_tasks_processed']/distributed_time:.1f} tasks/sec")
    print(f"    Workers used: {cluster_stats['total_workers']}")
    
    speedup = local_time / distributed_time if distributed_time > 0 else 0
    print(f"    Speedup: {speedup:.1f}x")


async def main():
    """Run all demonstrations."""
    print("ChatGPT for Robots - Distributed Task Execution Demo")
    print("=" * 60)
    print(f"Demo started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run demonstrations
        await demo_local_task_execution()
        await demo_distributed_task_execution()
        await demo_performance_comparison()
        
        print("\n" + "=" * 60)
        print("All demonstrations completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())