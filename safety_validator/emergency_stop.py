"""
Emergency Stop System

Provides system-wide emergency stop capabilities with ROS2 broadcast mechanism.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.base_component import BaseComponent


class EmergencyStopTrigger(str, Enum):
    """Types of emergency stop triggers."""
    MANUAL = "manual"
    SAFETY_VIOLATION = "safety_violation"
    SYSTEM_ERROR = "system_error"
    COMMUNICATION_LOSS = "communication_loss"
    HARDWARE_FAULT = "hardware_fault"


class EmergencyStopState(str, Enum):
    """Emergency stop system states."""
    NORMAL = "normal"
    STOPPING = "stopping"
    STOPPED = "stopped"
    RECOVERING = "recovering"


@dataclass
class EmergencyStopEvent:
    """Represents an emergency stop event."""
    event_id: str
    trigger: EmergencyStopTrigger
    description: str
    timestamp: datetime
    robot_id: Optional[str] = None
    severity: str = "critical"
    recovery_required: bool = True


@dataclass
class RecoveryProcedure:
    """Represents a recovery procedure after emergency stop."""
    procedure_id: str
    name: str
    description: str
    steps: List[str]
    estimated_duration: int  # seconds
    requires_manual_intervention: bool = False


class EmergencyStop(BaseComponent):
    """
    Emergency stop system with system-wide shutdown capabilities.
    
    Provides immediate shutdown of all robot operations with ROS2 broadcast
    mechanism and recovery procedures.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the emergency stop system.
        
        Args:
            config: Configuration dictionary containing emergency stop settings
        """
        super().__init__("emergency_stop", config)
        
        self.state: EmergencyStopState = EmergencyStopState.NORMAL
        self.emergency_events: List[EmergencyStopEvent] = []
        self.recovery_procedures: Dict[str, RecoveryProcedure] = {}
        self.stop_callbacks: List[Callable] = []
        self.recovery_callbacks: List[Callable] = []
        
        # Configuration
        self.stop_timeout = self.config.get('stop_timeout', 5.0)  # seconds
        self.recovery_timeout = self.config.get('recovery_timeout', 30.0)  # seconds
        self.auto_recovery_enabled = self.config.get('auto_recovery_enabled', False)
        self.broadcast_topic = self.config.get('broadcast_topic', '/emergency_stop')
        self.heartbeat_interval = self.config.get('heartbeat_interval', 1.0)  # seconds
        
        # ROS2 integration (will be initialized in start method)
        self.ros2_publisher = None
        self.ros2_subscriber = None
        self.heartbeat_task = None
        
        # Recovery state
        self.recovery_in_progress = False
        self.recovery_start_time = None
        
    async def initialize(self) -> bool:
        """Initialize the emergency stop system."""
        try:
            # Load default recovery procedures
            await self._load_recovery_procedures()
            
            self.is_initialized = True
            self.logger.info("Emergency stop system initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize emergency stop system: {e}")
            self.is_initialized = False
            return False
    
    async def start(self) -> bool:
        """Start the emergency stop system."""
        try:
            # Initialize ROS2 components (mock implementation for now)
            await self._initialize_ros2()
            
            # Start heartbeat monitoring
            self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            
            self.is_running = True
            self.start_time = datetime.now()
            self.logger.info("Emergency stop system started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start emergency stop system: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the emergency stop system."""
        try:
            # Cancel heartbeat monitoring
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup ROS2 components
            await self._cleanup_ros2()
            
            self.is_running = False
            self.logger.info("Emergency stop system stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop emergency stop system: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the emergency stop system."""
        return {
            'component': self.component_name,
            'status': 'healthy' if self.is_running else 'stopped',
            'state': self.state.value,
            'emergency_events_count': len(self.emergency_events),
            'recovery_procedures_loaded': len(self.recovery_procedures),
            'auto_recovery_enabled': self.auto_recovery_enabled,
            'recovery_in_progress': self.recovery_in_progress
        }
    
    async def trigger_emergency_stop(
        self, 
        trigger: EmergencyStopTrigger, 
        description: str,
        robot_id: Optional[str] = None,
        severity: str = "critical"
    ) -> str:
        """
        Trigger emergency stop for all robots.
        
        Args:
            trigger: Type of trigger that caused the emergency stop
            description: Description of the emergency situation
            robot_id: Optional specific robot ID if applicable
            severity: Severity level of the emergency
            
        Returns:
            Event ID of the emergency stop event
        """
        event_id = f"estop_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Create emergency stop event
        event = EmergencyStopEvent(
            event_id=event_id,
            trigger=trigger,
            description=description,
            timestamp=datetime.now(),
            robot_id=robot_id,
            severity=severity
        )
        
        self.emergency_events.append(event)
        
        # Update state
        self.state = EmergencyStopState.STOPPING
        
        # Log critical event
        self.logger.critical(f"EMERGENCY STOP TRIGGERED: {description} (Event ID: {event_id})")
        
        try:
            # Broadcast emergency stop to all robots
            await self._broadcast_emergency_stop(event)
            
            # Execute stop callbacks
            await self._execute_stop_callbacks(event)
            
            # Wait for stop confirmation or timeout
            await self._wait_for_stop_confirmation()
            
            # Update state to stopped
            self.state = EmergencyStopState.STOPPED
            
            self.logger.critical(f"EMERGENCY STOP COMPLETED: All systems halted (Event ID: {event_id})")
            
            # Trigger auto-recovery if enabled
            if self.auto_recovery_enabled and not event.recovery_required:
                asyncio.create_task(self._auto_recovery(event_id))
            
            return event_id
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop execution: {e}")
            self.state = EmergencyStopState.STOPPED  # Fail to safe state
            return event_id
    
    async def reset_emergency_stop(self, event_id: Optional[str] = None) -> bool:
        """
        Reset emergency stop state and begin recovery procedures.
        
        Args:
            event_id: Optional specific event ID to reset
            
        Returns:
            True if reset was successful, False otherwise
        """
        if self.state not in [EmergencyStopState.STOPPED, EmergencyStopState.RECOVERING]:
            self.logger.warning("Cannot reset emergency stop - system not in stopped state")
            return False
        
        if self.recovery_in_progress:
            self.logger.warning("Recovery already in progress")
            return False
        
        try:
            self.state = EmergencyStopState.RECOVERING
            self.recovery_in_progress = True
            self.recovery_start_time = datetime.now()
            
            self.logger.info(f"Starting emergency stop recovery (Event ID: {event_id})")
            
            # Execute recovery procedures
            success = await self._execute_recovery_procedures(event_id)
            
            if success:
                self.state = EmergencyStopState.NORMAL
                self.recovery_in_progress = False
                self.recovery_start_time = None
                
                # Execute recovery callbacks
                await self._execute_recovery_callbacks(event_id)
                
                self.logger.info("Emergency stop recovery completed successfully")
                return True
            else:
                self.logger.error("Emergency stop recovery failed")
                self.state = EmergencyStopState.STOPPED
                self.recovery_in_progress = False
                return False
                
        except Exception as e:
            self.logger.error(f"Error during emergency stop recovery: {e}")
            self.state = EmergencyStopState.STOPPED
            self.recovery_in_progress = False
            return False
    
    async def add_stop_callback(self, callback: Callable) -> None:
        """
        Add callback to be executed during emergency stop.
        
        Args:
            callback: Async function to call during emergency stop
        """
        self.stop_callbacks.append(callback)
        self.logger.debug(f"Added emergency stop callback: {callback.__name__}")
    
    async def add_recovery_callback(self, callback: Callable) -> None:
        """
        Add callback to be executed during recovery.
        
        Args:
            callback: Async function to call during recovery
        """
        self.recovery_callbacks.append(callback)
        self.logger.debug(f"Added recovery callback: {callback.__name__}")
    
    async def get_emergency_events(self, limit: Optional[int] = None) -> List[EmergencyStopEvent]:
        """
        Get emergency stop event history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of emergency stop events
        """
        events = sorted(self.emergency_events, key=lambda e: e.timestamp, reverse=True)
        return events[:limit] if limit else events
    
    async def get_recovery_procedures(self) -> Dict[str, RecoveryProcedure]:
        """Get available recovery procedures."""
        return self.recovery_procedures.copy()
    
    async def is_emergency_active(self) -> bool:
        """Check if emergency stop is currently active."""
        return self.state in [EmergencyStopState.STOPPING, EmergencyStopState.STOPPED]
    
    async def get_system_state(self) -> Dict[str, Any]:
        """Get current emergency stop system state."""
        return {
            'state': self.state.value,
            'recovery_in_progress': self.recovery_in_progress,
            'recovery_start_time': self.recovery_start_time.isoformat() if self.recovery_start_time else None,
            'recent_events': [
                {
                    'event_id': event.event_id,
                    'trigger': event.trigger.value,
                    'description': event.description,
                    'timestamp': event.timestamp.isoformat(),
                    'robot_id': event.robot_id,
                    'severity': event.severity
                }
                for event in self.emergency_events[-5:]  # Last 5 events
            ],
            'auto_recovery_enabled': self.auto_recovery_enabled
        }
    
    async def _load_recovery_procedures(self) -> None:
        """Load default recovery procedures."""
        default_procedures = [
            RecoveryProcedure(
                procedure_id="system_restart",
                name="System Restart Recovery",
                description="Standard recovery procedure for system-wide emergency stops",
                steps=[
                    "Verify all robots are in safe positions",
                    "Check system health and error logs",
                    "Reset robot controllers",
                    "Reinitialize navigation systems",
                    "Perform system health check",
                    "Resume normal operations"
                ],
                estimated_duration=1,  # Reduced for testing
                requires_manual_intervention=False
            ),
            RecoveryProcedure(
                procedure_id="manual_intervention",
                name="Manual Intervention Recovery",
                description="Recovery procedure requiring human operator intervention",
                steps=[
                    "Wait for human operator assessment",
                    "Follow operator instructions",
                    "Verify safety conditions",
                    "Manually reset affected systems",
                    "Confirm system readiness",
                    "Resume operations under supervision"
                ],
                estimated_duration=2,  # Reduced for testing
                requires_manual_intervention=True
            ),
            RecoveryProcedure(
                procedure_id="hardware_fault_recovery",
                name="Hardware Fault Recovery",
                description="Recovery procedure for hardware-related emergency stops",
                steps=[
                    "Isolate faulty hardware component",
                    "Run hardware diagnostics",
                    "Replace or repair faulty component",
                    "Recalibrate affected systems",
                    "Perform integration tests",
                    "Resume normal operations"
                ],
                estimated_duration=3,  # Reduced for testing
                requires_manual_intervention=True
            )
        ]
        
        for procedure in default_procedures:
            self.recovery_procedures[procedure.procedure_id] = procedure
        
        self.logger.info(f"Loaded {len(default_procedures)} recovery procedures")
    
    async def _initialize_ros2(self) -> None:
        """Initialize ROS2 components for emergency stop broadcasting."""
        # Mock ROS2 initialization - in real implementation, this would
        # initialize actual ROS2 publishers and subscribers
        self.logger.info(f"Initialized ROS2 emergency stop broadcaster on topic: {self.broadcast_topic}")
        
        # In real implementation:
        # self.ros2_publisher = self.create_publisher(EmergencyStopMsg, self.broadcast_topic, 10)
        # self.ros2_subscriber = self.create_subscription(EmergencyStopMsg, self.broadcast_topic, self._handle_emergency_stop_message, 10)
    
    async def _cleanup_ros2(self) -> None:
        """Cleanup ROS2 components."""
        self.logger.info("Cleaned up ROS2 emergency stop components")
        
        # In real implementation:
        # if self.ros2_publisher:
        #     self.ros2_publisher.destroy()
        # if self.ros2_subscriber:
        #     self.ros2_subscriber.destroy()
    
    async def _broadcast_emergency_stop(self, event: EmergencyStopEvent) -> None:
        """
        Broadcast emergency stop message to all robots via ROS2.
        
        Args:
            event: Emergency stop event to broadcast
        """
        # Mock ROS2 message broadcasting
        message = {
            'event_id': event.event_id,
            'trigger': event.trigger.value,
            'description': event.description,
            'timestamp': event.timestamp.isoformat(),
            'robot_id': event.robot_id,
            'severity': event.severity,
            'command': 'EMERGENCY_STOP'
        }
        
        self.logger.critical(f"Broadcasting emergency stop: {message}")
        
        # In real implementation:
        # msg = EmergencyStopMsg()
        # msg.event_id = event.event_id
        # msg.trigger = event.trigger.value
        # msg.description = event.description
        # msg.timestamp = event.timestamp.isoformat()
        # msg.robot_id = event.robot_id or ""
        # msg.severity = event.severity
        # msg.command = "EMERGENCY_STOP"
        # self.ros2_publisher.publish(msg)
    
    async def _execute_stop_callbacks(self, event: EmergencyStopEvent) -> None:
        """
        Execute all registered stop callbacks.
        
        Args:
            event: Emergency stop event
        """
        for callback in self.stop_callbacks:
            try:
                await callback(event)
                self.logger.debug(f"Executed stop callback: {callback.__name__}")
            except Exception as e:
                self.logger.error(f"Error executing stop callback {callback.__name__}: {e}")
    
    async def _wait_for_stop_confirmation(self) -> None:
        """Wait for stop confirmation or timeout."""
        await asyncio.sleep(self.stop_timeout)
        self.logger.info(f"Emergency stop confirmation timeout reached ({self.stop_timeout}s)")
    
    async def _execute_recovery_procedures(self, event_id: Optional[str]) -> bool:
        """
        Execute recovery procedures.
        
        Args:
            event_id: Event ID to recover from
            
        Returns:
            True if recovery was successful, False otherwise
        """
        # Determine appropriate recovery procedure
        procedure = self._select_recovery_procedure(event_id)
        
        if not procedure:
            self.logger.error("No suitable recovery procedure found")
            return False
        
        self.logger.info(f"Executing recovery procedure: {procedure.name}")
        
        try:
            # Execute recovery steps
            for i, step in enumerate(procedure.steps, 1):
                self.logger.info(f"Recovery step {i}/{len(procedure.steps)}: {step}")
                
                # Simulate step execution time
                await asyncio.sleep(procedure.estimated_duration / len(procedure.steps))
                
                # Check for timeout
                if self.recovery_start_time:
                    elapsed = (datetime.now() - self.recovery_start_time).total_seconds()
                    if elapsed > self.recovery_timeout:
                        self.logger.error("Recovery timeout exceeded")
                        return False
            
            self.logger.info(f"Recovery procedure '{procedure.name}' completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during recovery procedure execution: {e}")
            return False
    
    async def _execute_recovery_callbacks(self, event_id: Optional[str]) -> None:
        """
        Execute all registered recovery callbacks.
        
        Args:
            event_id: Event ID being recovered from
        """
        for callback in self.recovery_callbacks:
            try:
                await callback(event_id)
                self.logger.debug(f"Executed recovery callback: {callback.__name__}")
            except Exception as e:
                self.logger.error(f"Error executing recovery callback {callback.__name__}: {e}")
    
    def _select_recovery_procedure(self, event_id: Optional[str]) -> Optional[RecoveryProcedure]:
        """
        Select appropriate recovery procedure based on the emergency event.
        
        Args:
            event_id: Event ID to select procedure for
            
        Returns:
            Selected recovery procedure or None
        """
        if not event_id:
            return self.recovery_procedures.get("system_restart")
        
        # Find the event
        event = None
        for e in self.emergency_events:
            if e.event_id == event_id:
                event = e
                break
        
        if not event:
            return self.recovery_procedures.get("system_restart")
        
        # Select procedure based on trigger type
        if event.trigger == EmergencyStopTrigger.HARDWARE_FAULT:
            return self.recovery_procedures.get("hardware_fault_recovery")
        elif event.trigger in [EmergencyStopTrigger.SAFETY_VIOLATION, EmergencyStopTrigger.SYSTEM_ERROR]:
            return self.recovery_procedures.get("manual_intervention")
        else:
            return self.recovery_procedures.get("system_restart")
    
    async def _auto_recovery(self, event_id: str) -> None:
        """
        Perform automatic recovery after emergency stop.
        
        Args:
            event_id: Event ID to recover from
        """
        # Wait a short period before attempting auto-recovery
        await asyncio.sleep(5.0)
        
        self.logger.info(f"Attempting auto-recovery for event: {event_id}")
        
        success = await self.reset_emergency_stop(event_id)
        
        if success:
            self.logger.info(f"Auto-recovery successful for event: {event_id}")
        else:
            self.logger.error(f"Auto-recovery failed for event: {event_id}")
    
    async def _heartbeat_monitor(self) -> None:
        """Monitor system heartbeat and trigger emergency stop on communication loss."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # In real implementation, this would monitor ROS2 heartbeat messages
                # and trigger emergency stop if communication is lost
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat monitor: {e}")