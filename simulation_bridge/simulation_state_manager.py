"""
Simulation State Manager

Manages synchronization between real system state and simulation state.
Ensures consistency between the real robot system and Webots simulation.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SimulationStateManager:
    """Manages state synchronization between real system and simulation."""
    
    def __init__(self, bridge_config):
        self.bridge_config = bridge_config
        self.real_states = {}  # Real system robot states
        self.sim_states = {}   # Simulation robot states
        self.sync_tasks = {}   # Background sync tasks
        self.running = False
        self.sync_interval = 1.0 / bridge_config.update_rate_hz  # Update rate
        
        logger.info("Simulation State Manager initialized")
    
    async def initialize(self):
        """Initialize the state manager."""
        logger.info("Initializing Simulation State Manager...")
        
        try:
            self.running = True
            
            # Start background sync task
            self.sync_task = asyncio.create_task(self._sync_loop())
            
            logger.info("Simulation State Manager ready")
            
        except Exception as e:
            logger.error(f"State manager initialization failed: {e}")
            raise
    
    async def _sync_loop(self):
        """Background loop to synchronize states."""
        while self.running:
            try:
                await self._sync_states()
                await asyncio.sleep(self.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(1.0)  # Wait before retrying
    
    async def _sync_states(self):
        """Synchronize real and simulation states."""
        try:
            # Check for state differences and sync if needed
            for robot_id in self.real_states.keys():
                if robot_id in self.sim_states:
                    await self._sync_robot_state(robot_id)
            
        except Exception as e:
            logger.error(f"State sync failed: {e}")
    
    async def _sync_robot_state(self, robot_id: str):
        """Sync state for a specific robot."""
        try:
            real_state = self.real_states.get(robot_id)
            sim_state = self.sim_states.get(robot_id)
            
            if not real_state or not sim_state:
                return
            
            # Check if states are significantly different
            if self._states_differ(real_state, sim_state):
                # Update simulation to match real state
                await self._update_simulation_state(robot_id, real_state)
                
                # Log the sync
                logger.debug(f"Synced state for robot {robot_id}")
                
        except Exception as e:
            logger.error(f"Robot state sync failed for {robot_id}: {e}")
    
    def _states_differ(self, real_state: Dict[str, Any], sim_state: Dict[str, Any]) -> bool:
        """Check if real and simulation states differ significantly."""
        try:
            # Compare positions (with tolerance)
            real_pos = real_state.get('position', (0, 0, 0))
            sim_pos = sim_state.get('position', (0, 0, 0))
            
            position_diff = sum((r - s) ** 2 for r, s in zip(real_pos, sim_pos)) ** 0.5
            
            # Compare status
            status_diff = real_state.get('status') != sim_state.get('status')
            
            # Return true if significant difference
            return position_diff > 0.1 or status_diff
            
        except Exception as e:
            logger.error(f"State comparison failed: {e}")
            return False
    
    async def _update_simulation_state(self, robot_id: str, real_state: Dict[str, Any]):
        """Update simulation to match real state."""
        try:
            # Update simulation state
            self.sim_states[robot_id] = real_state.copy()
            self.sim_states[robot_id]['last_sync'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Simulation state update failed for {robot_id}: {e}")
    
    async def register_robot(self, robot_id: str, initial_state: Dict[str, Any]):
        """Register a robot for state management."""
        try:
            self.real_states[robot_id] = initial_state.copy()
            self.sim_states[robot_id] = initial_state.copy()
            
            logger.info(f"Registered robot {robot_id} for state management")
            
        except Exception as e:
            logger.error(f"Robot registration failed for {robot_id}: {e}")
    
    async def update_real_state(self, robot_id: str, state: Dict[str, Any]):
        """Update real system state for a robot."""
        try:
            if robot_id in self.real_states:
                self.real_states[robot_id].update(state)
                self.real_states[robot_id]['last_update'] = datetime.now()
                
        except Exception as e:
            logger.error(f"Real state update failed for {robot_id}: {e}")
    
    async def update_sim_state(self, robot_id: str, state: Dict[str, Any]):
        """Update simulation state for a robot."""
        try:
            if robot_id in self.sim_states:
                self.sim_states[robot_id].update(state)
                self.sim_states[robot_id]['last_update'] = datetime.now()
                
        except Exception as e:
            logger.error(f"Simulation state update failed for {robot_id}: {e}")
    
    async def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of state synchronization."""
        try:
            total_robots = len(self.real_states)
            synced_robots = 0
            out_of_sync_robots = []
            
            for robot_id in self.real_states.keys():
                if robot_id in self.sim_states:
                    if not self._states_differ(self.real_states[robot_id], self.sim_states[robot_id]):
                        synced_robots += 1
                    else:
                        out_of_sync_robots.append(robot_id)
            
            return {
                'total_robots': total_robots,
                'synced_robots': synced_robots,
                'out_of_sync_robots': out_of_sync_robots,
                'sync_rate_hz': 1.0 / self.sync_interval,
                'running': self.running
            }
            
        except Exception as e:
            logger.error(f"State summary failed: {e}")
            return {'error': str(e)}
    
    async def shutdown(self):
        """Shutdown the state manager."""
        logger.info("Shutting down Simulation State Manager...")
        
        self.running = False
        
        # Cancel sync task
        if hasattr(self, 'sync_task'):
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        # Clear states
        self.real_states.clear()
        self.sim_states.clear()
        self.sync_tasks.clear()
        
        logger.info("Simulation State Manager shutdown complete")
            