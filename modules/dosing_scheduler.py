#!/usr/bin/env python3
"""
ReefDB Dosing Scheduler Service

This module provides automated dosing functionality by monitoring dosing schedules
and triggering doses when they're due. It integrates with the existing ReefDB Flask
application and uses APScheduler for reliable scheduling.

Key Features:
- Monitors active dosing schedules from the database
- Calculates next dose times based on trigger_interval and last_refill
- Calls existing /controller/dose API endpoint to trigger doses
- Handles product availability checks
- Logs all dosing activities
- Graceful error handling and recovery
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
import requests
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import heapq
from threading import Lock, Thread

# Flask app imports (will be imported when initialized)
db = None
current_app = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('reef_scheduler')

# Constants
EXECUTOR_SHUTDOWN_ERROR = "cannot schedule new futures after shutdown"

class DosingScheduler:
    """
    Automated dosing scheduler that monitors active schedules and triggers doses
    when they're due based on trigger_interval and last execution time.
    """
    
    def __init__(self, app=None, base_url: str = None):
        self.app = app
        self.base_url = base_url or "http://localhost:5000"
        self.scheduler = None
        self.timezone = None
        self.is_running = False
        
        # Dose queue management
        self.dose_queue = []  # Min-heap of (next_dose_time, schedule_data)
        self.queue_lock = Lock()
        self.queue_size = 5  # Number of doses to keep in queue
        self.last_queue_refresh = None
        self.queue_refresh_interval = 300  # Refresh queue every 5 minutes
        
        # Initialize missed dose handler (using lazy import to avoid circular imports)
        self.missed_dose_handler = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the scheduler with Flask app context"""
        self.app = app
        
        # Get timezone from app config
        tzname = app.config.get('TIMEZONE', 'UTC')
        self.timezone = pytz.timezone(tzname)
        
        # Configure APScheduler - use memory store for development to avoid pickle issues
        # In production, you may want to use SQLAlchemyJobStore for persistence
        from apscheduler.jobstores.memory import MemoryJobStore
        
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.timezone
        )
        
        # Add event listeners
        self.scheduler.add_listener(
            self._job_executed_listener, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        # Store reference in app
        app.dosing_scheduler = self
        
        logger.info(f"DosingScheduler initialized with timezone: {tzname}")
    
    def _get_missed_dose_handler(self):
        """Get missed dose handler with lazy initialization to avoid circular imports"""
        if self.missed_dose_handler is None:
            from modules.missed_dose_handler import MissedDoseHandler
            self.missed_dose_handler = MissedDoseHandler()
        return self.missed_dose_handler
    
    def start(self):
        """Start the dosing scheduler with queue-based dose management"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
            
        try:
            # If scheduler is in stopped state, reinitialize it
            if self.scheduler and self.scheduler.state == 2:  # STATE_STOPPED
                logger.info("Scheduler was in stopped state, reinitializing...")
                self._reinitialize_scheduler()
            
            self.scheduler.start()
            self.is_running = True
            
            # Initialize the dose queue
            self._refresh_dose_queue()
            
            # Schedule queue management - refresh queue every 5 minutes
            try:
                self.scheduler.add_job(
                    func=self._manage_dose_queue,
                    trigger="interval",
                    minutes=5,
                    id="queue_manager",
                    name="Manage Dose Queue",
                    replace_existing=True
                )
            except RuntimeError as e:
                if EXECUTOR_SHUTDOWN_ERROR in str(e):
                    logger.error("Cannot add queue management job - scheduler executor has been shut down. Reinitializing...")
                    self._reinitialize_scheduler()
                    self.scheduler.start()
                    # Retry adding the job
                    self.scheduler.add_job(
                        func=self._manage_dose_queue,
                        trigger="interval",
                        minutes=5,
                        id="queue_manager",
                        name="Manage Dose Queue",
                        replace_existing=True
                    )
                else:
                    raise
            
            # Schedule periodic check for missed doses every minute (monitoring only)
            try:
                self.scheduler.add_job(
                    func=self._check_due_doses,
                    trigger="interval",
                    minutes=1,
                    id="missed_dose_monitor",
                    name="Monitor Missed Doses (Audit Only)",
                    replace_existing=True
                )
            except RuntimeError as e:
                if EXECUTOR_SHUTDOWN_ERROR in str(e):
                    logger.error("Cannot add missed dose monitor job - scheduler executor has been shut down. This should have been handled above.")
                    # Don't retry here as we already reinitialized above
                    raise RuntimeError("Scheduler in inconsistent state after reinitialization")
                else:
                    raise
            
            # Schedule the next doses from the queue
            self._schedule_next_doses()
            
            logger.info("Dosing scheduler started successfully with queue-based management")
            
        except Exception as e:
            logger.error(f"Failed to start dosing scheduler: {e}")
            raise
    
    def stop(self):
        """Stop the dosing scheduler gracefully"""
        if not self.is_running:
            return
            
        try:
            # Set flag immediately to prevent new job submissions
            self.is_running = False
            
            if self.scheduler and self.scheduler.state != 2:  # Not STATE_STOPPED
                # Shutdown gracefully, waiting for running jobs to complete
                self.scheduler.shutdown(wait=True)
                logger.info("Dosing scheduler stopped gracefully")
            else:
                logger.info("Scheduler was already stopped")
                
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            # Force cleanup even if shutdown failed
            try:
                if self.scheduler:
                    self.scheduler.shutdown(wait=False)
            except Exception:
                pass  # Ignore errors during force cleanup
    
    def restart(self):
        """Restart the dosing scheduler with a fresh instance"""
        try:
            # Stop current scheduler if running
            if self.is_running:
                logger.info("Stopping current scheduler before restart...")
                self.stop()
            
            # Wait a moment for cleanup
            import time
            time.sleep(2)  # Increased wait time for better cleanup
            
            # Reinitialize the scheduler with fresh thread pool
            logger.info("Reinitializing scheduler with fresh thread pool...")
            self._reinitialize_scheduler()
            
            # Start the fresh scheduler
            logger.info("Starting fresh scheduler...")
            self.start()
            
            logger.info("Dosing scheduler restarted successfully")
            
        except Exception as e:
            logger.error(f"Error restarting scheduler: {e}")
            # Ensure we're in a clean state even if restart fails
            self.is_running = False
            raise
    
    def _reinitialize_scheduler(self):
        """Reinitialize the APScheduler with fresh executors and jobstores"""
        from apscheduler.jobstores.memory import MemoryJobStore
        
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.timezone
        )
        
        # Re-add event listeners
        self.scheduler.add_listener(
            self._job_executed_listener, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        logger.info("Scheduler reinitialized with fresh thread pool")
    
    def _refresh_dose_queue(self):
        """Refresh the dose queue with the next 5 scheduled doses"""
        if not self.app:
            logger.error("No Flask app context available for queue refresh")
            return
            
        with self.app.app_context():
            try:
                next_doses = self._get_next_scheduled_doses(limit=self.queue_size)
                
                with self.queue_lock:
                    self.dose_queue.clear()
                    for dose in next_doses:
                        next_dose_time = dose['next_dose_time']
                        # Convert to timestamp for heap comparison
                        timestamp = next_dose_time.timestamp()
                        heapq.heappush(self.dose_queue, (timestamp, dose))
                    
                    self.last_queue_refresh = datetime.now()
                
                logger.info(f"Dose queue refreshed with {len(next_doses)} scheduled doses")
                
                # Log the next few doses for monitoring
                for i, (timestamp, dose) in enumerate(self.dose_queue[:3]):
                    dose_time = datetime.fromtimestamp(timestamp)
                    logger.info(f"  {i+1}. {dose['product_name']} ({dose['amount']}ml) "
                               f"for tank {dose['tank_id']} at {dose_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
            except Exception as e:
                logger.error(f"Error refreshing dose queue: {e}")
    
    def _get_next_scheduled_doses(self, limit: int = 5) -> List[Dict]:
        """
        Get the next scheduled doses across all active schedules.
        Supports interval, absolute (fixed time), and relative (offset/reference) schedules.
        """
        from app import db
        from modules.models import DSchedule, Products, Dosing
        from datetime import datetime, timedelta, time as dt_time

        try:
            schedules = db.session.query(DSchedule).join(Products).filter(
                DSchedule.suspended == False,
                Products.current_avail >= DSchedule.amount
            ).all()

            scheduled_doses = []
            current_time = datetime.now()

            for schedule in schedules:
                # --- Absolute (fixed time) schedule ---
                if schedule.trigger_time:
                    # Next occurrence of trigger_time (today or tomorrow)
                    today_trigger = current_time.replace(hour=schedule.trigger_time.hour, minute=schedule.trigger_time.minute, second=0, microsecond=0)
                    if today_trigger > current_time:
                        next_dose_time = today_trigger
                    else:
                        # Already passed today, schedule for tomorrow
                        next_dose_time = today_trigger + timedelta(days=1)
                    dose_data = {
                        'schedule_id': schedule.id,
                        'tank_id': schedule.tank_id,
                        'product_id': schedule.product_id,
                        'amount': schedule.amount,
                        'trigger_interval': schedule.trigger_interval,
                        'product_name': schedule.product.name,
                        'current_avail': schedule.product.current_avail,
                        'next_dose_time': next_dose_time,
                        'missed_dose_status': 'fixed_time',
                    }
                    scheduled_doses.append(dose_data)
                    continue

                # --- Relative (offset/reference) schedule ---
                if schedule.offset_minutes and schedule.reference_schedule_id:
                    # Find the most recent dose of the reference schedule
                    ref_dose = db.session.query(Dosing).filter_by(schedule_id=schedule.reference_schedule_id).order_by(Dosing.trigger_time.desc()).first()
                    if ref_dose and ref_dose.trigger_time:
                        next_dose_time = ref_dose.trigger_time + timedelta(minutes=schedule.offset_minutes)
                        if next_dose_time < current_time:
                            # If already passed, schedule for next reference dose occurrence
                            # (This is a simple version; for more complex logic, consider recurring reference)
                            next_dose_time = current_time + timedelta(minutes=1)  # fallback: soon
                    else:
                        # No reference dose yet, schedule for now + offset
                        next_dose_time = current_time + timedelta(minutes=schedule.offset_minutes)
                    dose_data = {
                        'schedule_id': schedule.id,
                        'tank_id': schedule.tank_id,
                        'product_id': schedule.product_id,
                        'amount': schedule.amount,
                        'trigger_interval': schedule.trigger_interval,
                        'product_name': schedule.product.name,
                        'current_avail': schedule.product.current_avail,
                        'next_dose_time': next_dose_time,
                        'missed_dose_status': 'relative',
                        'reference_schedule_id': schedule.reference_schedule_id,
                        'offset_minutes': schedule.offset_minutes,
                    }
                    scheduled_doses.append(dose_data)
                    continue

                # --- Default: interval/legacy logic ---
                analysis = self._get_missed_dose_handler().analyze_schedule_for_missed_dose(schedule, current_time)
                if analysis.action == 'not_overdue':
                    dose_data = {
                        'schedule_id': schedule.id,
                        'tank_id': schedule.tank_id,
                        'product_id': schedule.product_id,
                        'amount': schedule.amount,
                        'trigger_interval': schedule.trigger_interval,
                        'product_name': schedule.product.name,
                        'current_avail': schedule.product.current_avail,
                        'next_dose_time': analysis.missed_dose_time,
                        'missed_dose_status': 'on_schedule'
                    }
                    scheduled_doses.append(dose_data)
                elif analysis.should_dose:
                    if analysis.action == 'grace_period':
                        dose_data = {
                            'schedule_id': schedule.id,
                            'tank_id': schedule.tank_id,
                            'product_id': schedule.product_id,
                            'amount': schedule.amount,
                            'trigger_interval': schedule.trigger_interval,
                            'product_name': schedule.product.name,
                            'current_avail': schedule.product.current_avail,
                            'next_dose_time': current_time,  # Dose immediately
                            'missed_dose_status': 'grace_period',
                            'hours_missed': analysis.hours_missed
                        }
                        scheduled_doses.append(dose_data)
                else:
                    # No immediate dose scheduled, but calculate next dose time for overdue alert_only schedules
                    if analysis.hours_missed > 0 and analysis.action == 'skip':
                        # For overdue alert_only schedules, calculate when the next dose should be
                        next_dose_time = analysis.missed_dose_time + timedelta(seconds=schedule.trigger_interval)
                        dose_data = {
                            'schedule_id': schedule.id,
                            'tank_id': schedule.tank_id,
                            'product_id': schedule.product_id,
                            'amount': schedule.amount,
                            'trigger_interval': schedule.trigger_interval,
                            'product_name': schedule.product.name,
                            'current_avail': schedule.product.current_avail,
                            'next_dose_time': next_dose_time,
                            'missed_dose_status': 'alert_only_overdue',
                            'hours_missed': analysis.hours_missed
                        }
                        scheduled_doses.append(dose_data)
                        logger.info(f"Schedule {schedule.id} ({schedule.product.name}): Alert-only overdue schedule added to queue for next dose at {next_dose_time}")
                    else:
                        logger.info(f"Schedule {schedule.id} requires manual approval for missed dose")
                if analysis.hours_missed > 0:
                    logger.info(f"Schedule {schedule.id} ({schedule.product.name}): "
                                f"{analysis.action} - {analysis.reason}")

            # Include all valid doses (both current and future)
            # The scheduler will handle timing appropriately
            scheduled_doses.sort(key=lambda x: x['next_dose_time'])
            return scheduled_doses[:limit]
        except Exception as e:
            logger.error(f"Database error getting next scheduled doses: {e}")
            return []
    
    def _manage_dose_queue(self):
        """
        Queue management job that runs every 5 minutes to:
        1. Check if queue needs refreshing
        2. Remove executed doses from queue
        3. Add new scheduled doses if queue is low
        """
        # Check if scheduler is still running before proceeding
        if not self.is_running or not self.scheduler or self.scheduler.state == 2:  # STATE_STOPPED
            logger.debug("Skipping queue management - scheduler is not running")
            return
            
        try:
            with self.queue_lock:
                current_time = datetime.now().timestamp()
                
                # Remove past doses from queue (in case they were missed)
                while self.dose_queue and self.dose_queue[0][0] < current_time:
                    past_dose = heapq.heappop(self.dose_queue)
                    logger.warning(f"Removed past dose from queue: {past_dose[1]['product_name']}")
                    self._log_audit_event(
                        event_type="dose_missed",
                        schedule_id=past_dose[1]['schedule_id'],
                        tank_id=past_dose[1]['tank_id'],
                        message=f"Removed past dose from queue: {past_dose[1]['product_name']} ({past_dose[1]['amount']}ml)"
                    )
                
                queue_count = len(self.dose_queue)
            
            # Refresh queue if it's getting low or it's been a while
            should_refresh = (
                queue_count < 2 or  # Queue is getting low
                not self.last_queue_refresh or
                (datetime.now() - self.last_queue_refresh).total_seconds() > self.queue_refresh_interval
            )
            
            if should_refresh:
                logger.info(f"Queue management: refreshing (current size: {queue_count})")
                self._log_audit_event(
                    event_type="queue_refresh",
                    schedule_id=0,
                    tank_id=0,
                    message=f"Refreshing dose queue (current size: {queue_count})"
                )
                self._refresh_dose_queue()
                self._schedule_next_doses()
            else:
                logger.debug(f"Queue management: queue healthy (size: {queue_count})")
                
        except Exception as e:
            logger.error(f"Error in queue management: {e}")
    
    def _schedule_next_doses(self):
        """Schedule the next doses from the queue as individual APScheduler jobs"""
        # Check if scheduler is still running before proceeding
        if not self.is_running or not self.scheduler or self.scheduler.state == 2:  # STATE_STOPPED
            logger.debug("Skipping dose scheduling - scheduler is not running")
            return
            
        try:
            with self.queue_lock:
                scheduled_count = 0
                
                for timestamp, dose_data in self.dose_queue:
                    dose_time = datetime.fromtimestamp(timestamp)
                    
                    # Only schedule future doses
                    if dose_time > datetime.now():
                        job_id = f"dose_{dose_data['schedule_id']}_{int(timestamp)}"
                        
                        # Check if job already exists
                        if not self.scheduler.get_job(job_id):
                            try:
                                self.scheduler.add_job(
                                    func=self._execute_scheduled_dose,
                                    trigger="date",
                                    run_date=dose_time,
                                    args=[dose_data],
                                    id=job_id,
                                    name=f"Dose {dose_data['product_name']} (Tank {dose_data['tank_id']})",
                                    replace_existing=True
                                )
                                scheduled_count += 1
                                self._log_audit_event(
                                    event_type="dose_scheduled",
                                    schedule_id=dose_data['schedule_id'],
                                    tank_id=dose_data['tank_id'],
                                    message=f"Scheduled dose: {dose_data['product_name']} ({dose_data['amount']}ml) at {dose_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                            except RuntimeError as e:
                                if EXECUTOR_SHUTDOWN_ERROR in str(e):
                                    logger.warning(f"Cannot schedule dose job {job_id} - scheduler executor has been shut down")
                                    break  # Stop trying to schedule more jobs
                                else:
                                    raise
                
                if scheduled_count > 0:
                    logger.info(f"Scheduled {scheduled_count} individual dose jobs")
                    
        except Exception as e:
            logger.error(f"Error scheduling doses from queue: {e}")
    
    def _execute_scheduled_dose(self, dose_data: Dict):
        """Execute a scheduled dose and refresh the queue"""
        # Check if scheduler is still running before proceeding
        if not self.is_running or not self.scheduler or self.scheduler.state == 2:  # STATE_STOPPED
            logger.debug("Skipping dose execution - scheduler is not running")
            return
            
        if not self.app:
            logger.error("No Flask app context available for dose execution")
            return
            
        with self.app.app_context():
            try:
                # Verify the dose is still valid (product availability, schedule not suspended)
                if self._validate_dose_before_execution(dose_data):
                    success = self._trigger_dose(dose_data)
                    
                    if success:
                        # Remove this dose from queue and refresh
                        self._remove_dose_from_queue(dose_data)
                        
                        # If queue is getting low, refresh it
                        with self.queue_lock:
                            if len(self.dose_queue) < 2:
                                logger.info("Queue getting low after dose execution, refreshing...")
                                self._refresh_dose_queue()
                                self._schedule_next_doses()
                else:
                    logger.warning(f"Dose validation failed for {dose_data['product_name']}, skipping")
                    self._remove_dose_from_queue(dose_data)
                    
            except Exception as e:
                logger.error(f"Error executing scheduled dose: {e}")
    
    def _validate_dose_before_execution(self, dose_data: Dict) -> bool:
        """Validate that a dose is still valid before execution"""
        try:
            from app import db
            
            # Check if schedule is still active and product has sufficient availability
            sql = """
                SELECT ds.suspended, p.current_avail
                FROM d_schedule ds
                LEFT JOIN products p ON ds.product_id = p.id
                WHERE ds.id = :schedule_id
            """
            
            result = db.session.execute(text(sql), {'schedule_id': dose_data['schedule_id']}).first()
            
            if not result:
                logger.warning(f"Schedule {dose_data['schedule_id']} no longer exists")
                return False
            
            if result.suspended:
                logger.warning(f"Schedule {dose_data['schedule_id']} is now suspended")
                return False
            
            if result.current_avail < dose_data['amount']:
                logger.warning(f"Insufficient product availability for {dose_data['product_name']}: "
                             f"{result.current_avail}ml < {dose_data['amount']}ml")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating dose: {e}")
            return False
    
    def _remove_dose_from_queue(self, dose_data: Dict):
        """Remove a specific dose from the queue"""
        try:
            with self.queue_lock:
                # Find and remove the dose from the heap
                new_queue = []
                for timestamp, queued_dose in self.dose_queue:
                    if queued_dose['schedule_id'] != dose_data['schedule_id']:
                        new_queue.append((timestamp, queued_dose))
                
                self.dose_queue = new_queue
                heapq.heapify(self.dose_queue)
                
        except Exception as e:
            logger.error(f"Error removing dose from queue: {e}")
    
    def _check_due_doses(self):
        """
        Monitoring function that checks for missed doses and logs them to audit system.
        This runs every minute to check all active schedules.
        NEVER triggers doses automatically - all dose execution is handled by the queue system.
        Overdue doses are logged as missed doses requiring manual approval.
        """
        # Check if scheduler is still running before proceeding
        if not self.is_running or not self.scheduler or self.scheduler.state == 2:  # STATE_STOPPED
            logger.debug("Skipping dose check - scheduler is not running")
            return
            
        if not self.app:
            logger.error("No Flask app context available")
            return
        
        with self.app.app_context():
            try:
                # Check for missed doses that need to be logged to audit system
                from app import db
                from modules.models import DSchedule, Products
                
                schedules = db.session.query(DSchedule).join(Products).filter(
                    DSchedule.suspended == False,
                    Products.current_avail >= DSchedule.amount
                ).all()
                
                current_time = datetime.now()
                missed_count = 0
                
                for schedule in schedules:
                    # Skip fixed-time and reference schedules for this check
                    if schedule.trigger_time or (schedule.offset_minutes and schedule.reference_schedule_id):
                        continue
                        
                    # Only check interval-based schedules for missed doses
                    analysis = self._get_missed_dose_handler().analyze_schedule_for_missed_dose(schedule, current_time)
                    
                    if analysis.hours_missed > 0:
                        # Log missed dose to audit system
                        self._log_audit_event(
                            event_type="dose_missed_detected",
                            schedule_id=schedule.id,
                            tank_id=schedule.tank_id,
                            message=f"Missed dose detected: {schedule.product.name} ({schedule.amount}ml) - {analysis.hours_missed:.1f}h overdue - strategy: {analysis.action}",
                            details={
                                'hours_missed': analysis.hours_missed,
                                'missed_dose_handling': schedule.missed_dose_handling.value if schedule.missed_dose_handling else None,
                                'action': analysis.action,
                                'reason': analysis.reason
                            }
                        )
                        
                        # Create missed dose request for manual approval or alert strategies
                        # This ensures the UI can display missed doses to users regardless of strategy
                        if analysis.action in ['manual_approval', 'skip']:
                            missed_dose_handler = self._get_missed_dose_handler()
                            # Check if missed dose request already exists to avoid duplicates
                            from modules.models import MissedDoseRequest
                            existing_request = db.session.query(MissedDoseRequest).filter_by(
                                schedule_id=schedule.id,
                                status='pending'
                            ).filter(
                                MissedDoseRequest.missed_dose_time == analysis.missed_dose_time
                            ).first()
                            
                            if not existing_request:
                                missed_dose_handler._create_approval_request(schedule, analysis.missed_dose_time, analysis.hours_missed)
                                logger.info(f"Created missed dose request for schedule {schedule.id} ({schedule.product.name}) - {analysis.hours_missed:.1f}h overdue")
                        
                        missed_count += 1
                        logger.info(f"Missed dose processed: Schedule {schedule.id} ({schedule.product.name}) - {analysis.hours_missed:.1f}h overdue")
                
                if missed_count > 0:
                    logger.info(f"Logged {missed_count} missed doses requiring manual approval")
                else:
                    logger.debug("No missed doses detected")
                    
            except Exception as e:
                logger.error(f"Error checking for missed doses: {e}")
    
    def _trigger_dose(self, schedule: Dict):
        """
        Trigger a dose by calling the existing /controller/dose API endpoint.
        
        Args:
            schedule: Dictionary containing schedule information
        """
        schedule_id = schedule['schedule_id']
        tank_id = schedule['tank_id']
        product_name = schedule['product_name']
        amount = schedule['amount']
        
        logger.info(
            f"Triggering dose: {product_name} ({amount}ml) for tank {tank_id}, "
            f"schedule {schedule_id}"
        )
        
        try:
            # Call the existing dose API endpoint
            response = requests.post(
                f"{self.base_url}/api/v1/controller/dose",
                json={
                    'schedule_id': schedule_id,
                    'tank_id': tank_id
                },
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                if data.get('success'):
                    # Update last_scheduled_time in the database to track when this dose was executed
                    self._update_schedule_last_executed(schedule_id)
                    
                    logger.info(
                        f"✅ Successfully dosed {product_name} ({amount}ml) "
                        f"for tank {tank_id}"
                    )
                    self._log_audit_event(
                        event_type="dose_executed",
                        schedule_id=schedule_id,
                        tank_id=tank_id,
                        message=f"Dosed {product_name} ({amount}ml) successfully",
                        details={"response": data}
                    )
                    return True
                else:
                    logger.error(
                        f"❌ Dose API returned success=False for {product_name}: "
                        f"{data.get('error', 'Unknown error')}"
                    )
                    self._log_audit_event(
                        event_type="dose_failed",
                        schedule_id=schedule_id,
                        tank_id=tank_id,
                        message=f"Failed to dose {product_name} ({amount}ml)",
                        details={"response": data}
                    )
            else:
                logger.error(
                    f"❌ Dose API returned status {response.status_code} "
                    f"for {product_name}: {response.text}"
                )
                self._log_audit_event(
                    event_type="dose_failed",
                    schedule_id=schedule_id,
                    tank_id=tank_id,
                    message=f"Failed to dose {product_name} ({amount}ml)",
                    details={"status_code": response.status_code, "response_text": response.text}
                )
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout dosing {product_name} for tank {tank_id}")
            self._log_audit_event(
                event_type="dose_failed",
                schedule_id=schedule_id,
                tank_id=tank_id,
                message=f"Timeout dosing {product_name} ({amount}ml)"
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 Connection error dosing {product_name} for tank {tank_id}")
            self._log_audit_event(
                event_type="dose_failed",
                schedule_id=schedule_id,
                tank_id=tank_id,
                message=f"Connection error dosing {product_name} ({amount}ml)"
            )
        except Exception as e:
            logger.error(f"💥 Unexpected error dosing {product_name}: {e}")
            self._log_audit_event(
                event_type="dose_failed",
                schedule_id=schedule_id,
                tank_id=tank_id,
                message=f"Unexpected error dosing {product_name} ({amount}ml)",
                details={"error": str(e)}
            )
        
        return False
    
    def _update_schedule_last_executed(self, schedule_id: int):
        """
        Update the last_scheduled_time field for a schedule after successful dose execution.
        This field tracks when the scheduler last processed this schedule.
        """
        try:
            from app import db
            from modules.timezone_utils import get_system_timezone
            
            # Get current time in system timezone
            current_time = datetime.now(get_system_timezone())
            
            # Update the schedule's last_scheduled_time
            update_sql = """
                UPDATE d_schedule 
                SET last_scheduled_time = :last_scheduled_time
                WHERE id = :schedule_id
            """
            
            db.session.execute(text(update_sql), {
                'schedule_id': schedule_id,
                'last_scheduled_time': current_time
            })
            db.session.commit()
            
            logger.debug(f"Updated last_scheduled_time for schedule {schedule_id} to {current_time}")
            
        except Exception as e:
            logger.error(f"Error updating last_scheduled_time for schedule {schedule_id}: {e}")
            # Don't raise the exception since the dose was successful, just log the issue
            try:
                db.session.rollback()
            except:
                pass
    
    def _log_audit_event(self, event_type: str, schedule_id: int, tank_id: int, 
                         message: str, details: Dict = None):
        """
        Log scheduler events to the audit system for tracking and monitoring.
        
        Args:
            event_type: Type of event (dose_scheduled, dose_executed, dose_failed, etc.)
            schedule_id: ID of the dosing schedule
            tank_id: ID of the tank
            message: Human-readable message
            details: Additional event details
        """
        try:
            if not self.app:
                logger.warning("No Flask app context for audit logging")
                return
                
            audit_data = {
                'event_type': event_type,
                'schedule_id': schedule_id,
                'tank_id': tank_id,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'source': 'dosing_scheduler',
                'details': details or {}
            }
            
            # Send audit event to internal API (non-blocking)
            Thread(
                target=self._send_audit_event,
                args=(audit_data,),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def _send_audit_event(self, audit_data: Dict):
        """Send audit event to internal API endpoint"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/audit/scheduler-event",
                json=audit_data,
                timeout=5
            )
            if response.status_code != 201:
                logger.warning(f"Audit API returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to send audit event: {e}")
    
    def _job_executed_listener(self, event):
        """Listen to job execution events for monitoring and logging"""
        if event.exception:
            logger.error(f"Job {event.job_id} crashed: {event.exception}")
        else:
            logger.debug(f"Job {event.job_id} executed successfully")
    
    def get_status(self) -> Dict:
        """Get scheduler status information including queue details"""
        if not self.scheduler:
            return {'status': 'not_initialized'}
        
        next_check = None
        queue_info = []
        
        if self.is_running and self.scheduler:
            # Try to get the next run time for the queue manager job
            try:
                queue_manager_job = self.scheduler.get_job('queue_manager')
                if queue_manager_job and queue_manager_job.next_run_time:
                    next_check = queue_manager_job.next_run_time.isoformat()
            except Exception:
                pass
            
            # Get queue information
            try:
                with self.queue_lock:
                    for timestamp, dose_data in self.dose_queue[:3]:  # Show next 3 doses
                        dose_time = datetime.fromtimestamp(timestamp)
                        queue_info.append({
                            'product_name': dose_data['product_name'],
                            'amount': dose_data['amount'],
                            'tank_id': dose_data['tank_id'],
                            'scheduled_time': dose_time.isoformat(),
                            'seconds_until': int(timestamp - datetime.now().timestamp())
                        })
            except Exception:
                pass
        
        return {
            'status': 'running' if self.is_running else 'stopped',
            'jobs': len(self.scheduler.get_jobs()) if self.scheduler else 0,
            'timezone': str(self.timezone),
            'next_queue_refresh': next_check,
            'queue_size': len(self.dose_queue) if hasattr(self, 'dose_queue') else 0,
            'next_doses': queue_info
        }
    
    def get_queue_status(self) -> Dict:
        """Get current queue status for monitoring (API compatibility with enhanced scheduler)"""
        if not self.scheduler:
            return {
                'queue_size': 0,
                'last_refresh': None,
                'pending_confirmations': 0,
                'precision_target_seconds': 60,  # Default precision for legacy scheduler
                'queue_data': []
            }
        
        queue_data = []
        last_refresh = None
        
        if self.is_running and hasattr(self, 'dose_queue'):
            try:
                # Get the next run time for the queue manager job as last refresh
                queue_manager_job = self.scheduler.get_job('queue_manager')
                if queue_manager_job and queue_manager_job.next_run_time:
                    # Use previous run time as last refresh
                    last_refresh = (queue_manager_job.next_run_time - timedelta(minutes=1)).isoformat()
            except Exception:
                pass
            
            # Get queue information in enhanced scheduler format
            try:
                with self.queue_lock:
                    for timestamp, dose_data in list(self.dose_queue)[:5]:  # Return next 5 doses
                        dose_time = datetime.fromtimestamp(timestamp)
                        queue_data.append({
                            'schedule_id': dose_data.get('schedule_id'),
                            'product_name': dose_data['product_name'],
                            'amount': dose_data['amount'],
                            'next_dose_time': dose_time.isoformat(),
                            'time_until_dose': (dose_time - datetime.now()).total_seconds(),
                            'precision_target': 60  # Legacy scheduler precision
                        })
            except Exception:
                pass
        
        return {
            'queue_size': len(self.dose_queue) if hasattr(self, 'dose_queue') else 0,
            'last_refresh': last_refresh,
            'pending_confirmations': 0,  # Legacy scheduler doesn't track confirmations
            'precision_target_seconds': 60,  # Legacy scheduler runs every minute
            'queue_data': queue_data
        }
    
    def force_check(self):
        """Manually refresh the dose queue and schedule next doses (for testing/debugging)"""
        if not self.is_running:
            logger.warning("Cannot force check - scheduler not running")
            return False
            
        try:
            # Check if scheduler is in a valid state
            if not self.scheduler or self.scheduler.state == 2:  # STATE_STOPPED
                logger.warning("Scheduler is stopped, cannot refresh queue")
                return False
                
            # Refresh the queue and schedule doses
            self._refresh_dose_queue()
            self._schedule_next_doses()
            
            logger.info("Manual queue refresh and dose scheduling completed")
            return True
        except Exception as e:
            logger.error(f"Error during manual queue refresh: {e}")
            return False


# Global scheduler instance
dosing_scheduler = DosingScheduler()


def init_dosing_scheduler(app, base_url: str = None):
    """
    Initialize the dosing scheduler with the Flask app.
    Call this from your Flask app factory or __init__.py
    
    Args:
        app: Flask application instance
        base_url: Base URL for API calls (defaults to localhost:5000)
    """
    global dosing_scheduler
    
    # Set base URL from app config if not provided
    if not base_url:
        base_url = app.config.get('DOSING_API_BASE_URL', 'http://localhost:5000')
    
    dosing_scheduler.init_app(app)
    dosing_scheduler.base_url = base_url
    
    # Auto-start if configured
    if app.config.get('DOSING_SCHEDULER_AUTOSTART', True):
        dosing_scheduler.start()
    
    return dosing_scheduler


def get_scheduler() -> DosingScheduler:
    """Get the global scheduler instance"""
    return dosing_scheduler
