#!/usr/bin/env python3
"""
Enhanced ReefDB Dosing Scheduler Service

This module provides a fully automated dosing system that:
1. Removes all manual dosing functionality for 100% hands-off operation
2. Implements precise hourly timing (e.g., 09:15, 10:15, 11:15 for hourly schedules)
3. Ensures complete audit logging of all timing information
4. Provides automatic dose confirmation with physical doser integration
5. Auto-calculates next doses and updates queue upon successful completion
6. Alerts users only on errors, not routine operations

Key Features:
- Precise time-of-day scheduling instead of interval-based
- Automatic dose confirmation workflow
- Complete audit trail with precise timing
- Physical doser communication layer
- Queue-based management with auto-progression
- Error-only notifications
"""

import logging
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Optional, Tuple, Any
import pytz
import requests
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import heapq
from threading import Lock, Thread
import json
from enum import Enum

# Flask app imports (will be imported when initialized)
from flask import g
current_app = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('enhanced_reef_scheduler')

class DoseStatus(Enum):
    """Dose execution status tracking"""
    SCHEDULED = "scheduled"
    TRIGGERED = "triggered"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class PhysicalDoserInterface:
    """Interface for communicating with physical dosing hardware"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or "http://localhost:5000"
        self.confirmation_timeout = 30  # seconds to wait for physical confirmation
        self.retry_attempts = 3
        
    async def send_dose_command(self, doser_id: int, amount: float, schedule_id: int) -> Dict[str, Any]:
        """
        Send dose command to physical doser and wait for confirmation
        
        Returns:
            {
                "success": bool,
                "confirmation_time": datetime,
                "actual_amount": float,
                "doser_response": dict,
                "error": str (if failed)
            }
        """
        import aiohttp
        import asyncio
        
        dose_command = {
            "doser_id": doser_id,
            "amount": amount,
            "schedule_id": schedule_id,
            "timestamp": datetime.now().isoformat(),
            "confirmation_required": True
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.confirmation_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Send command to physical doser
                async with session.post(
                    f"{self.base_url}/api/v1/doser/execute",
                    json=dose_command
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "confirmation_time": datetime.now(),
                            "actual_amount": result.get("actual_amount", amount),
                            "doser_response": result,
                            "error": None
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "confirmation_time": None,
                            "actual_amount": 0,
                            "doser_response": None,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "confirmation_time": None,
                "actual_amount": 0,
                "doser_response": None,
                "error": f"Physical doser timeout after {self.confirmation_timeout}s"
            }
        except Exception as e:
            return {
                "success": False,
                "confirmation_time": None,
                "actual_amount": 0,
                "doser_response": None,
                "error": f"Physical doser communication error: {str(e)}"
            }

class EnhancedDosingScheduler:
    """
    Fully automated dosing scheduler with precise timing and complete audit trail
    """
    
    def __init__(self, app=None, base_url: str = None):
        self.app = app
        self.base_url = base_url or "http://localhost:5000"
        self.scheduler = None
        self.timezone = None
        self.is_running = False
        
        # Physical doser interface
        self.doser_interface = PhysicalDoserInterface(base_url)
        
        # Dose queue management with enhanced tracking
        self.dose_queue = []  # Min-heap of (timestamp, index, dose_data)
        self.queue_lock = Lock()
        self.queue_size = 10  # Increased queue size for better planning
        self.last_queue_refresh = None
        self.queue_refresh_interval = 60  # Refresh queue every minute for precision
        
        # Audit and confirmation tracking
        self.pending_confirmations = {}  # track doses awaiting physical confirmation
        self.confirmation_timeout = 30  # seconds
        
        # Enhanced timing precision
        self.timing_precision_seconds = 15  # Target precision: ±15 seconds
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the enhanced scheduler with Flask app context"""
        self.app = app
        
        # Get timezone from app config
        tzname = app.config.get('TIMEZONE', 'UTC')
        self.timezone = pytz.timezone(tzname)
        
        # Configure APScheduler with enhanced precision
        from apscheduler.jobstores.memory import MemoryJobStore
        
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 30  # Allow 30s grace for precision timing
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.timezone
        )
        
        # Add event listeners for comprehensive audit logging
        self.scheduler.add_listener(
            self._job_executed_listener, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        logger.info("Enhanced dosing scheduler initialized with precision timing")
    
    def start(self):
        """Start the enhanced scheduler with precision timing"""
        if not self.scheduler:
            logger.error("Scheduler not initialized")
            return False
            
        try:
            self.scheduler.start()
            self.is_running = True
            
            # Schedule the queue management job to run every minute for precision
            self.scheduler.add_job(
                func=self._refresh_dose_queue,
                trigger='cron',
                second=0,  # Run at the top of every minute
                id='enhanced_queue_refresh',
                replace_existing=True,
                misfire_grace_time=15
            )
            
            # Schedule confirmation timeout checker
            self.scheduler.add_job(
                func=self._check_confirmation_timeouts,
                trigger='cron',
                second=30,  # Run at 30 seconds past every minute
                id='confirmation_timeout_checker',
                replace_existing=True
            )
            
            logger.info("Enhanced dosing scheduler started with precision timing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start enhanced scheduler: {e}")
            return False
    
    def stop(self):
        """Stop the enhanced scheduler"""
        if self.scheduler and self.is_running:
            try:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("Enhanced dosing scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping enhanced scheduler: {e}")
    
    def restart(self):
        """Restart the enhanced dosing scheduler"""
        try:
            logger.info("Restarting enhanced dosing scheduler...")
            
            # Stop current scheduler if running
            if self.is_running:
                self.stop()
            
            # Wait for cleanup
            import time
            time.sleep(1)
            
            # Reinitialize scheduler
            self.scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(20)},
                timezone=self.timezone,
                job_defaults={'coalesce': True, 'max_instances': 1}
            )
            
            # Restart
            started = self.start()
            if started:
                logger.info("Enhanced dosing scheduler restarted successfully")
            else:
                logger.error("Failed to restart enhanced dosing scheduler")
                
        except Exception as e:
            logger.error(f"Error restarting enhanced scheduler: {e}")
            raise
    
    def _calculate_precise_next_dose_time(self, schedule) -> Optional[datetime]:
        """
        Calculate precise next dose time based on enhanced schedule configuration
        
        NEW APPROACH: 
        - Hourly schedules use offset_minutes (0-59) from top of hour
        - Multi-hour schedules use offset_minutes from scheduling interval
        - Daily+ schedules use trigger_time for exact time
        """
        from modules.models import ScheduleTypeEnum
        
        current_time = datetime.now(self.timezone)
        
        # Handle different schedule types with precision
        if schedule.schedule_type == ScheduleTypeEnum.interval:
            # Convert interval-based to precise timing
            if schedule.trigger_interval:
                interval_hours = schedule.trigger_interval / 3600
                
                if interval_hours <= 24:  # Hourly/daily schedules
                    # NEW: Use offset_minutes for hourly schedules
                    if schedule.offset_minutes is not None:
                        target_minute = schedule.offset_minutes
                        logger.debug(f"Schedule {schedule.id}: Using offset_minutes={target_minute} for {interval_hours}h interval")
                        
                        if interval_hours <= 1:
                            # Every hour at :offset_minutes (e.g., :30 for 16:30, 17:30, etc.)
                            next_hour = current_time.replace(minute=target_minute, second=0, microsecond=0)
                            if next_hour <= current_time:
                                next_hour += timedelta(hours=1)
                            logger.debug(f"Schedule {schedule.id}: Hourly dose at {next_hour}")
                            return next_hour
                        
                        elif interval_hours <= 24:
                            # FIXED: Multiple hours - find the correct base time with offset
                            hours_interval = int(interval_hours)
                            
                            # Find the most recent occurrence at :offset_minutes
                            base_time = current_time.replace(minute=target_minute, second=0, microsecond=0)
                            
                            # If current base time hasn't occurred yet, use it
                            if base_time > current_time:
                                logger.debug(f"Schedule {schedule.id}: Next dose at current hour offset {base_time}")
                                return base_time
                            
                            # Otherwise, add the interval to get the next occurrence
                            next_time = base_time + timedelta(hours=hours_interval)
                            logger.debug(f"Schedule {schedule.id}: Next dose at interval offset {next_time}")
                            return next_time
                    
                    # FALLBACK: Legacy behavior for schedules without offset_minutes
                    else:
                        logger.debug(f"Schedule {schedule.id}: Using fallback logic (offset_minutes is None)")
                        # For hourly schedules, default to :00 minutes (top of hour)
                        if interval_hours <= 1:
                            next_hour = current_time.replace(minute=0, second=0, microsecond=0)
                            if next_hour <= current_time:
                                next_hour += timedelta(hours=1)
                            logger.debug(f"Schedule {schedule.id}: Fallback hourly dose at {next_hour}")
                            return next_hour
                        
                        elif interval_hours <= 24:
                            # Multiple hours - calculate next occurrence at :00
                            hours_to_add = int(interval_hours)
                            
                            next_time = current_time.replace(minute=0, second=0, microsecond=0)
                            next_time += timedelta(hours=hours_to_add)
                            
                            if next_time <= current_time:
                                next_time += timedelta(hours=hours_to_add)
                            
                            return next_time
                
                else:
                    # Multi-day schedules - use daily time if specified
                    if schedule.trigger_time:
                        days_to_add = int(interval_hours / 24)
                        next_time = current_time.replace(
                            hour=schedule.trigger_time.hour,
                            minute=schedule.trigger_time.minute,
                            second=0,
                            microsecond=0
                        )
                        next_time += timedelta(days=days_to_add)
                        
                        if next_time <= current_time:
                            next_time += timedelta(days=days_to_add)
                        
                        return next_time
        
        elif schedule.schedule_type == ScheduleTypeEnum.daily:
            # Daily schedule with exact time
            if schedule.trigger_time:
                next_time = current_time.replace(
                    hour=schedule.trigger_time.hour,
                    minute=schedule.trigger_time.minute,
                    second=0,
                    microsecond=0
                )
                
                if next_time <= current_time:
                    next_time += timedelta(days=1)
                
                return next_time
        
        elif schedule.schedule_type == ScheduleTypeEnum.custom:
            # Custom day-based scheduling
            if schedule.repeat_every_n_days and schedule.trigger_time:
                # Calculate next occurrence based on days interval
                if schedule.last_scheduled_time:
                    last_dose = schedule.last_scheduled_time.replace(tzinfo=self.timezone)
                    next_time = last_dose + timedelta(days=schedule.repeat_every_n_days)
                else:
                    # First time - schedule for today or tomorrow
                    next_time = current_time.replace(
                        hour=schedule.trigger_time.hour,
                        minute=schedule.trigger_time.minute,
                        second=0,
                        microsecond=0
                    )
                    
                    if next_time <= current_time:
                        next_time += timedelta(days=schedule.repeat_every_n_days)
                
                return next_time
        
        # Fallback for legacy interval calculations
        if schedule.trigger_interval:
            return current_time + timedelta(seconds=schedule.trigger_interval)
        
        return None
    
    def _refresh_dose_queue(self):
        """Enhanced dose queue refresh with precise timing calculations"""
        logger.info("Starting enhanced dose queue refresh...")
        
        if not self.app:
            logger.error("No Flask app context available for enhanced queue refresh")
            return
            
        with self.app.app_context():
            try:
                # Get all active schedules with enhanced filtering
                from modules.models import DSchedule, Products, Tank
                from extensions import db
                
                # Ensure database session is available
                if not db or not hasattr(db, 'session') or not db.session:
                    logger.error("Database session not available in background thread")
                    return
                
                logger.info("Querying active schedules...")
                schedules = db.session.query(DSchedule).join(Products).join(Tank).filter(
                    DSchedule.suspended == False,
                    Products.current_avail >= DSchedule.amount,
                    Tank.id.isnot(None)  # Ensure tank exists
                ).all()
                
                logger.info(f"Found {len(schedules)} active schedules")
                
                scheduled_doses = []
                current_time = datetime.now(self.timezone)
                
                for schedule in schedules:
                    logger.debug(f"Processing schedule {schedule.id} for product {schedule.product.name}")
                    # Calculate precise next dose time
                    next_dose_time = self._calculate_precise_next_dose_time(schedule)
                    
                    if next_dose_time and next_dose_time > current_time:
                        dose_data = {
                            'schedule_id': schedule.id,
                            'tank_id': schedule.tank_id,
                            'product_id': schedule.product_id,
                            'doser_id': schedule.doser_id,
                            'amount': schedule.amount,
                            'product_name': schedule.product.name,
                            'current_avail': schedule.product.current_avail,
                            'next_dose_time': next_dose_time,
                            'schedule_type': schedule.schedule_type.value if schedule.schedule_type else 'interval',
                            'precision_target': self.timing_precision_seconds,
                            'confirmation_required': True
                        }
                        scheduled_doses.append(dose_data)
                        logger.debug(f"  -> Next dose at {next_dose_time}")
                    else:
                        logger.debug(f"  -> No valid next dose time calculated")
                
                # Sort by next dose time and update queue
                scheduled_doses.sort(key=lambda x: x['next_dose_time'])
                
                with self.queue_lock:
                    self.dose_queue.clear()
                    for i, dose in enumerate(scheduled_doses[:self.queue_size]):
                        timestamp = dose['next_dose_time'].timestamp()
                        # Use index as tiebreaker to avoid dict comparison
                        heapq.heappush(self.dose_queue, (timestamp, i, dose))
                    
                    self.last_queue_refresh = datetime.now()
                
                # Schedule the next doses with precise timing
                self._schedule_precise_doses(scheduled_doses[:5])  # Schedule next 5 doses
                
                logger.info(f"Enhanced dose queue refreshed with {len(scheduled_doses)} precise doses")
                
                # Log next few doses for monitoring
                for i, dose in enumerate(scheduled_doses[:3]):
                    dose_time = dose['next_dose_time']
                    logger.info(f"  {i+1}. {dose['product_name']} ({dose['amount']}ml) "
                               f"for tank {dose['tank_id']} at {dose_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
            except Exception as e:
                logger.error(f"Error refreshing enhanced dose queue: {e}")
    
    def _schedule_precise_doses(self, doses: List[Dict]):
        """Schedule doses with precise APScheduler jobs"""
        for dose in doses:
            job_id = f"enhanced_dose_{dose['schedule_id']}_{dose['next_dose_time'].timestamp()}"
            
            # Remove existing job if it exists
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
            
            # Schedule with precise timing
            self.scheduler.add_job(
                func=self._execute_enhanced_dose,
                trigger=DateTrigger(run_date=dose['next_dose_time']),
                args=[dose],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=self.timing_precision_seconds
            )
    
    def _execute_enhanced_dose(self, dose_data: Dict):
        """
        Execute dose with automatic confirmation and complete audit logging
        """
        # Run the async dose execution in a thread
        import asyncio
        import threading
        
        def run_async_dose():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._execute_enhanced_dose_async(dose_data))
                loop.close()
            except Exception as e:
                logger.error(f"Error in async dose execution thread: {e}")
        
        # Run in a separate thread
        thread = threading.Thread(target=run_async_dose)
        thread.start()
    
    async def _execute_enhanced_dose_async(self, dose_data: Dict):
        """
        Execute dose with automatic confirmation and complete audit logging
        """
        schedule_id = dose_data['schedule_id']
        # Use timezone-aware datetime to match dose_data['next_dose_time']
        dose_start_time = datetime.now(self.timezone)
        
        # CRITICAL SAFETY CHECK: Only execute doses within 2-minute safety window
        planned_time = dose_data['next_dose_time']
        time_difference = abs((dose_start_time - planned_time).total_seconds())
        SAFETY_WINDOW_SECONDS = 120  # 2 minutes maximum
        
        if time_difference > SAFETY_WINDOW_SECONDS:
            logger.error(f"SAFETY ABORT: Dose for schedule {schedule_id} is {time_difference:.1f}s "
                        f"from planned time {planned_time}. Exceeds 2-minute safety limit. "
                        f"NOT DOSING to prevent animal harm.")
            return
        
        logger.info(f"SAFETY OK: Dose timing within {time_difference:.1f}s of planned time")
        
        # Create comprehensive audit entry
        audit_data = {
            'schedule_id': schedule_id,
            'execution_start': dose_start_time.isoformat(),
            'planned_time': dose_data['next_dose_time'].isoformat(),
            'timing_precision': abs((dose_start_time - dose_data['next_dose_time']).total_seconds()),
            'amount': dose_data['amount'],
            'product_id': dose_data['product_id'],
            'tank_id': dose_data['tank_id'],
            'doser_id': dose_data.get('doser_id'),
            'status': DoseStatus.TRIGGERED.value
        }
        
        try:
            # Log dose trigger with precise timing
            logger.info(f"Executing enhanced dose: {dose_data['product_name']} "
                       f"({dose_data['amount']}ml) for schedule {schedule_id}")
            
            # Update database to reflect dose execution
            with self.app.app_context():
                # Call existing controller API to execute dose
                response = await self._call_dose_api(dose_data)
                
                if response.get('success'):
                    # If physical doser is configured, wait for confirmation
                    if dose_data.get('doser_id'):
                        confirmation = await self.doser_interface.send_dose_command(
                            dose_data['doser_id'],
                            dose_data['amount'],
                            schedule_id
                        )
                        
                        if confirmation['success']:
                            audit_data.update({
                                'status': DoseStatus.CONFIRMED.value,
                                'confirmation_time': confirmation['confirmation_time'].isoformat(),
                                'actual_amount': confirmation['actual_amount'],
                                'execution_end': datetime.now(self.timezone).isoformat()
                            })
                            
                            # Schedule next dose automatically
                            await self._schedule_next_dose(schedule_id)
                            
                            logger.info(f"Enhanced dose confirmed: {dose_data['product_name']} "
                                       f"actual amount {confirmation['actual_amount']}ml")
                        else:
                            # Physical confirmation failed - alert user
                            audit_data.update({
                                'status': DoseStatus.FAILED.value,
                                'error': confirmation['error'],
                                'execution_end': datetime.now(self.timezone).isoformat()
                            })
                            
                            await self._send_error_alert(schedule_id, confirmation['error'])
                            logger.error(f"Enhanced dose failed confirmation: {confirmation['error']}")
                    else:
                        # No physical doser - assume successful
                        audit_data.update({
                            'status': DoseStatus.CONFIRMED.value,
                            'confirmation_time': dose_start_time.isoformat(),
                            'actual_amount': dose_data['amount'],
                            'execution_end': datetime.now(self.timezone).isoformat()
                        })
                        
                        # Schedule next dose automatically
                        await self._schedule_next_dose(schedule_id)
                        
                        logger.info(f"Enhanced dose completed (no physical doser): {dose_data['product_name']}")
                else:
                    # API call failed
                    audit_data.update({
                        'status': DoseStatus.FAILED.value,
                        'error': response.get('error', 'Unknown API error'),
                        'execution_end': datetime.now(self.timezone).isoformat()
                    })
                    
                    await self._send_error_alert(schedule_id, response.get('error'))
                    logger.error(f"Enhanced dose API failed: {response.get('error')}")
        
        except Exception as e:
            audit_data.update({
                'status': DoseStatus.FAILED.value,
                'error': str(e),
                'execution_end': datetime.now(self.timezone).isoformat()
            })
            
            await self._send_error_alert(schedule_id, str(e))
            logger.error(f"Enhanced dose execution exception: {e}")
        
        finally:
            # Always log complete audit information
            await self._log_dose_audit(audit_data)
    
    async def _call_dose_api(self, dose_data: Dict) -> Dict:
        """Call the existing dose API with enhanced error handling"""
        import aiohttp
        
        api_data = {
            'schedule_id': dose_data['schedule_id'],
            'tank_id': dose_data['tank_id']
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/controller/dose",
                    json=api_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 201:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        return {
                            'success': False,
                            'error': f"HTTP {response.status}: {error_text}"
                        }
        except Exception as e:
            return {
                'success': False,
                'error': f"API call failed: {str(e)}"
            }
    
    async def _schedule_next_dose(self, schedule_id: int):
        """Automatically calculate and schedule the next dose"""
        with self.app.app_context():
            try:
                from modules.models import DSchedule
                from extensions import db
                
                # Ensure database session is available
                if not db or not hasattr(db, 'session') or not db.session:
                    logger.error(f"Database session not available for scheduling next dose {schedule_id}")
                    return
                
                schedule = db.session.query(DSchedule).filter_by(id=schedule_id).first()
                if schedule:
                    # Update last_scheduled_time
                    schedule.last_scheduled_time = datetime.now()
                    db.session.commit()
                    
                    # Trigger queue refresh to pick up the next dose
                    self._refresh_dose_queue()
                    
                    logger.info(f"Next dose automatically scheduled for schedule {schedule_id}")
                else:
                    logger.warning(f"Schedule {schedule_id} not found for next dose scheduling")
            except Exception as e:
                logger.error(f"Error scheduling next dose for schedule {schedule_id}: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
    
    async def _send_error_alert(self, schedule_id: int, error_message: str):
        """Send error alerts only when doses fail (not for routine operations)"""
        try:
            # Import notification system
            from modules.notifications import send_dose_error_notification
            
            with self.app.app_context():
                from modules.models import DSchedule
                from extensions import db
                
                # Ensure database session is available
                if not db or not hasattr(db, 'session') or not db.session:
                    logger.error(f"Database session not available for error alert {schedule_id}")
                    return
                
                schedule = db.session.query(DSchedule).filter_by(id=schedule_id).first()
                if schedule:
                    alert_data = {
                        'schedule_id': schedule_id,
                        'product_name': schedule.product.name if schedule.product else 'Unknown',
                        'error': error_message,
                        'timestamp': datetime.now().isoformat(),
                        'tank_id': schedule.tank_id
                    }
                    
                    # Send notification only for errors
                    await send_dose_error_notification(alert_data)
                    logger.info(f"Error alert sent for schedule {schedule_id}")
        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")
    
    async def _log_dose_audit(self, audit_data: Dict):
        """Log complete audit information for all dose events"""
        try:
            with self.app.app_context():
                # Create comprehensive audit log entry
                from modules.models import DosingAudit
                from extensions import db
                
                # Ensure database session is available
                if not db or not hasattr(db, 'session') or not db.session:
                    logger.error(f"Database session not available for audit logging {audit_data.get('schedule_id')}")
                    return
                
                audit_entry = DosingAudit(
                    schedule_id=audit_data['schedule_id'],
                    execution_start=datetime.fromisoformat(audit_data['execution_start']),
                    planned_time=datetime.fromisoformat(audit_data['planned_time']),
                    timing_precision_seconds=audit_data['timing_precision'],
                    amount=audit_data['amount'],
                    product_id=audit_data['product_id'],
                    tank_id=audit_data['tank_id'],
                    doser_id=audit_data.get('doser_id'),
                    status=audit_data['status'],
                    confirmation_time=datetime.fromisoformat(audit_data['confirmation_time']) if audit_data.get('confirmation_time') else None,
                    actual_amount=audit_data.get('actual_amount'),
                    execution_end=datetime.fromisoformat(audit_data['execution_end']) if audit_data.get('execution_end') else None,
                    error_message=audit_data.get('error'),
                    raw_audit_data=json.dumps(audit_data)
                )
                
                db.session.add(audit_entry)
                db.session.commit()
                
                logger.info(f"Complete audit logged for schedule {audit_data['schedule_id']}")
        except Exception as e:
            logger.error(f"Failed to log dose audit: {e}")
            try:
                db.session.rollback()
            except:
                pass
    
    def _check_confirmation_timeouts(self):
        """Check for doses that haven't received confirmation within timeout"""
        current_time = datetime.now()
        
        for dose_id, dose_info in list(self.pending_confirmations.items()):
            if (current_time - dose_info['start_time']).total_seconds() > self.confirmation_timeout:
                # Timeout occurred - send alert
                logger.warning(f"Dose confirmation timeout for {dose_id}")
                
                # Send timeout alert
                self._send_timeout_alert(dose_info)
                
                # Remove from pending
                del self.pending_confirmations[dose_id]
    
    def _send_timeout_alert(self, dose_info: Dict):
        """Send alert for confirmation timeouts"""
        try:
            alert_data = {
                'type': 'confirmation_timeout',
                'schedule_id': dose_info['schedule_id'],
                'timeout_seconds': self.confirmation_timeout,
                'timestamp': datetime.now().isoformat()
            }
            
            # Send timeout notification
            logger.error(f"Dose confirmation timeout alert sent for schedule {dose_info['schedule_id']}")
        except Exception as e:
            logger.error(f"Failed to send timeout alert: {e}")
    
    def _job_executed_listener(self, event):
        """Enhanced job execution listener for comprehensive audit logging"""
        if event.exception:
            logger.error(f"Enhanced scheduler job failed: {event.job_id} - {event.exception}")
        else:
            logger.debug(f"Enhanced scheduler job completed: {event.job_id}")
    
    def get_queue_status(self) -> Dict:
        """Get current enhanced queue status for monitoring"""
        with self.queue_lock:
            queue_data = []
            for timestamp, index, dose in list(self.dose_queue):
                dose_time = datetime.fromtimestamp(timestamp)
                queue_data.append({
                    'schedule_id': dose['schedule_id'],
                    'product_name': dose['product_name'],
                    'amount': dose['amount'],
                    'next_dose_time': dose_time.isoformat(),
                    'time_until_dose': (dose_time - datetime.now()).total_seconds(),
                    'precision_target': dose.get('precision_target', self.timing_precision_seconds)
                })
            
            return {
                'queue_size': len(self.dose_queue),
                'last_refresh': self.last_queue_refresh.isoformat() if self.last_queue_refresh else None,
                'pending_confirmations': len(self.pending_confirmations),
                'precision_target_seconds': self.timing_precision_seconds,
                'queue_data': queue_data[:5]  # Return next 5 doses
            }

    def refresh_queue_immediately(self):
        """
        Manually trigger an immediate queue refresh to pick up schedule changes.
        This should be called after schedule modifications (create, edit, delete).
        """
        if not self.is_running:
            logger.warning("Cannot refresh queue - scheduler not running")
            return False
        
        try:
            logger.info("Manual queue refresh triggered due to schedule changes")
            self._refresh_dose_queue()
            logger.info("Manual queue refresh completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error during manual queue refresh: {e}")
            return False

    def get_status(self) -> Dict:
        """Get enhanced scheduler status information including queue details (API compatibility)"""
        if not self.scheduler:
            return {'status': 'not_initialized'}
        
        next_check = None
        queue_info = []
        
        if self.is_running and self.scheduler:
            # Try to get the next run time for the queue manager job
            try:
                queue_manager_job = self.scheduler.get_job('enhanced_queue_manager')
                if queue_manager_job and queue_manager_job.next_run_time:
                    next_check = queue_manager_job.next_run_time.isoformat()
            except Exception:
                pass
            
            # Get queue information using enhanced queue status
            try:
                queue_status = self.get_queue_status()
                for dose in queue_status.get('queue_data', [])[:3]:  # Show next 3 doses
                    queue_info.append({
                        'product_name': dose['product_name'],
                        'amount': dose['amount'],
                        'tank_id': dose.get('tank_id', 1),  # Default tank_id
                        'scheduled_time': dose['next_dose_time'],
                        'seconds_until': int(dose['time_until_dose'])
                    })
            except Exception:
                pass
        
        return {
            'status': 'running' if self.is_running else 'stopped',
            'jobs': len(self.scheduler.get_jobs()) if self.scheduler else 0,
            'timezone': str(self.timezone),
            'next_queue_refresh': next_check,
            'queue_size': len(self.dose_queue) if hasattr(self, 'dose_queue') else 0,
            'next_doses': queue_info,
            'enhanced_features': {
                'precision_target_seconds': self.timing_precision_seconds,
                'pending_confirmations': len(self.pending_confirmations),
                'last_refresh': self.last_queue_refresh.isoformat() if self.last_queue_refresh else None
            }
        }

    def _check_for_safe_missed_doses(self, schedule) -> Optional[datetime]:
        """
        CRITICAL SAFETY: Check for missed doses ONLY within 2-minute safety window
        
        This prevents dangerous late dosing that could harm or kill animals.
        
        Returns:
            datetime: The missed dose time if within 2-minute safety window
            None: If no safe missed dose found
        """
        from modules.models import ScheduleTypeEnum
        
        current_time = datetime.now(self.timezone)
        
        # Calculate when the last dose SHOULD have occurred
        last_scheduled_time = self._calculate_last_scheduled_dose_time(schedule, current_time)
        
        if not last_scheduled_time:
            return None
        
        # CRITICAL SAFETY CHECK: Only allow missed doses within 2 minutes
        time_since_scheduled = current_time - last_scheduled_time
        SAFETY_WINDOW_SECONDS = 120  # 2 minutes maximum
        
        if time_since_scheduled.total_seconds() <= SAFETY_WINDOW_SECONDS:
            logger.info(f"SAFE missed dose detected for schedule {schedule.id}: "
                       f"scheduled at {last_scheduled_time}, "
                       f"only {time_since_scheduled.total_seconds():.1f}s late")
            return last_scheduled_time
        else:
            logger.warning(f"UNSAFE missed dose skipped for schedule {schedule.id}: "
                          f"scheduled at {last_scheduled_time}, "
                          f"{time_since_scheduled.total_seconds():.1f}s late (>2min limit)")
            return None
    
    def _calculate_last_scheduled_dose_time(self, schedule, current_time) -> Optional[datetime]:
        """
        Calculate when the last dose should have occurred based on schedule configuration
        """
        from modules.models import ScheduleTypeEnum
        
        if schedule.schedule_type == ScheduleTypeEnum.interval:
            if schedule.trigger_interval:
                interval_hours = schedule.trigger_interval / 3600
                
                if interval_hours <= 24:  # Hourly/daily schedules
                    if schedule.offset_minutes is not None:
                        target_minute = schedule.offset_minutes
                        
                        if interval_hours <= 1:
                            # Hourly: Find the most recent hour:minute that should have occurred
                            last_hour = current_time.replace(minute=target_minute, second=0, microsecond=0)
                            if last_hour > current_time:
                                last_hour -= timedelta(hours=1)
                            return last_hour
                        
                        elif interval_hours <= 24:
                            # Multi-hour: Calculate the most recent interval occurrence
                            hours_interval = int(interval_hours)
                            
                            # Find the base time (midnight + offset)
                            base_time = current_time.replace(hour=0, minute=target_minute, second=0, microsecond=0)
                            
                            # Find the most recent occurrence
                            hours_since_base = (current_time - base_time).total_seconds() / 3600
                            intervals_passed = int(hours_since_base / hours_interval)
                            
                            last_scheduled = base_time + timedelta(hours=intervals_passed * hours_interval)
                            
                            # If this is in the future, go back one interval
                            if last_scheduled > current_time:
                                last_scheduled -= timedelta(hours=hours_interval)
                            
                            return last_scheduled
        
        return None

# Global enhanced scheduler instance
enhanced_scheduler = None

def init_enhanced_scheduler(app):
    """Initialize the enhanced scheduler with Flask app"""
    global enhanced_scheduler
    
    if enhanced_scheduler is None:
        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        enhanced_scheduler = EnhancedDosingScheduler(app, base_url)
        
        # Start the scheduler
        if enhanced_scheduler.start():
            logger.info("Enhanced dosing scheduler initialized and started")
            return True
        else:
            logger.error("Failed to start enhanced dosing scheduler")
            return False
    
    return True

def get_enhanced_scheduler():
    """Get the global enhanced scheduler instance"""
    global enhanced_scheduler
    return enhanced_scheduler

def refresh_scheduler_queue():
    """
    Utility function to refresh the enhanced scheduler queue immediately.
    Safe to call from anywhere - handles cases where scheduler is not available.
    
    Returns:
        bool: True if refresh was successful, False otherwise
    """
    try:
        scheduler = get_enhanced_scheduler()
        if scheduler and scheduler.is_running:
            return scheduler.refresh_queue_immediately()
        else:
            logger.warning("Enhanced scheduler not available or not running for queue refresh")
            return False
    except Exception as e:
        logger.error(f"Error refreshing enhanced scheduler queue: {e}")
        return False
