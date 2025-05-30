"""
Overdue dose handling system for ReefDB dosing scheduler.

This module implements configurable strategies for handling missed/overdue doses:
- Alert Only: Skip missed doses and show next scheduled dose (default)
- Grace Period: Allow dosing within configurable time window  
- Catch-up: Dose immediately if within limits
- Manual Approval: Require user confirmation for overdue doses
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

from app import db
from modules.models import DSchedule, Dosing, OverdueDoseRequest, OverdueHandlingEnum

logger = logging.getLogger(__name__)

@dataclass
class OverdueAnalysis:
    """Analysis result for an overdue dose."""
    schedule_id: int
    missed_dose_time: datetime
    hours_overdue: float
    should_dose: bool
    action: str  # 'skip', 'dose_now', 'grace_period', 'manual_approval'
    reason: str
    immediate_doses_count: int = 0
    

class OverdueHandler:
    """Handles overdue dose detection and processing based on configured strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_schedule_for_overdue(self, schedule: DSchedule, reference_time: datetime = None) -> OverdueAnalysis:
        """
        Analyze a dosing schedule to determine if it's overdue and what action to take.
        
        Args:
            schedule: DSchedule model instance
            reference_time: Time to compare against (defaults to current time)
            
        Returns:
            OverdueAnalysis with recommendation for handling the overdue dose
        """
        if reference_time is None:
            reference_time = datetime.now()
            
        # Calculate when the next dose should have been
        last_dose = self._get_last_dose_time(schedule)
        expected_dose_time = last_dose + timedelta(seconds=schedule.trigger_interval)
        
        # Check if it's actually overdue
        if expected_dose_time > reference_time:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=expected_dose_time,
                hours_overdue=0,
                should_dose=False,
                action='not_overdue',
                reason='Next dose is not yet due'
            )
        
        hours_overdue = (reference_time - expected_dose_time).total_seconds() / 3600
        
        # Determine action based on overdue handling strategy
        if schedule.overdue_handling == OverdueHandlingEnum.alert_only:
            return self._handle_alert_only(schedule, expected_dose_time, hours_overdue)
        elif schedule.overdue_handling == OverdueHandlingEnum.grace_period:
            return self._handle_grace_period(schedule, expected_dose_time, hours_overdue)
        elif schedule.overdue_handling == OverdueHandlingEnum.catch_up:
            return self._handle_catch_up(schedule, expected_dose_time, hours_overdue, reference_time)
        elif schedule.overdue_handling == OverdueHandlingEnum.manual_approval:
            return self._handle_manual_approval(schedule, expected_dose_time, hours_overdue)
        else:
            # Default to alert_only for unknown strategies
            return self._handle_alert_only(schedule, expected_dose_time, hours_overdue)
    
    def _get_last_dose_time(self, schedule: DSchedule) -> datetime:
        """Get the last dose time for a schedule."""
        last_dose = db.session.query(Dosing).filter_by(schedule_id=schedule.id).order_by(Dosing.trigger_time.desc()).first()
        if last_dose and last_dose.trigger_time:
            return last_dose.trigger_time
        
        # If no doses found, use last_refill or a default time
        if schedule.last_refill:
            return schedule.last_refill
        
        # Default to current time minus interval (will show as ready to dose)
        return datetime.now() - timedelta(seconds=schedule.trigger_interval)
    
    def _handle_alert_only(self, schedule: DSchedule, missed_dose_time: datetime, hours_overdue: float) -> OverdueAnalysis:
        """Handle alert-only strategy: skip missed doses and show next scheduled dose."""
        return OverdueAnalysis(
            schedule_id=schedule.id,
            missed_dose_time=missed_dose_time,
            hours_overdue=hours_overdue,
            should_dose=False,
            action='skip',
            reason=f'Alert-only mode: Dose missed {hours_overdue:.1f} hours ago, skipping to next scheduled dose'
        )
    
    def _handle_grace_period(self, schedule: DSchedule, missed_dose_time: datetime, hours_overdue: float) -> OverdueAnalysis:
        """Handle grace period strategy: allow dosing within configured window."""
        grace_period = schedule.grace_period_hours or 12
        
        if hours_overdue <= grace_period:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=True,
                action='grace_period',
                reason=f'Within grace period ({hours_overdue:.1f}h overdue, {grace_period}h allowed)'
            )
        else:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=False,
                action='skip',
                reason=f'Past grace period ({hours_overdue:.1f}h overdue, {grace_period}h limit)'
            )
    
    def _handle_catch_up(self, schedule: DSchedule, missed_dose_time: datetime, hours_overdue: float, reference_time: datetime) -> OverdueAnalysis:
        """Handle catch-up strategy: dose immediately if within limits."""
        max_catch_up = schedule.max_catch_up_doses or 3
        catch_up_window = schedule.catch_up_window_hours or 24
        
        if hours_overdue > catch_up_window:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=False,
                action='skip',
                reason=f'Outside catch-up window ({hours_overdue:.1f}h overdue, {catch_up_window}h limit)'
            )
        
        # Calculate how many doses we could catch up on
        interval_hours = schedule.trigger_interval / 3600
        max_catchup_doses = min(max_catch_up, int(hours_overdue / interval_hours))
        
        if max_catchup_doses > 0:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=True,
                action='catch_up',
                reason=f'Catch-up dosing: {max_catchup_doses} dose(s) within {catch_up_window}h window',
                immediate_doses_count=max_catchup_doses
            )
        else:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=False,
                action='skip',
                reason='No catch-up doses needed within limits'
            )
    
    def _handle_manual_approval(self, schedule: DSchedule, missed_dose_time: datetime, hours_overdue: float) -> OverdueAnalysis:
        """Handle manual approval strategy: require user confirmation."""
        # Check if there's already a pending request
        existing_request = db.session.query(OverdueDoseRequest).filter_by(
            schedule_id=schedule.id,
            status='pending'
        ).filter(
            OverdueDoseRequest.missed_dose_time == missed_dose_time
        ).first()
        
        if existing_request:
            return OverdueAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                should_dose=False,
                action='pending_approval',
                reason=f'Manual approval pending (request #{existing_request.id})'
            )
        
        # Create new approval request
        self._create_approval_request(schedule, missed_dose_time, hours_overdue)
        
        return OverdueAnalysis(
            schedule_id=schedule.id,
            missed_dose_time=missed_dose_time,
            hours_overdue=hours_overdue,
            should_dose=False,
            action='manual_approval',
            reason=f'Manual approval required ({hours_overdue:.1f}h overdue)'
        )
    
    def _create_approval_request(self, schedule: DSchedule, missed_dose_time: datetime, hours_overdue: float):
        """Create a new overdue dose approval request."""
        try:
            request = OverdueDoseRequest(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_overdue=hours_overdue,
                status='pending'
            )
            db.session.add(request)
            db.session.commit()
            self.logger.info(f"Created overdue approval request for schedule {schedule.id}")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create overdue approval request: {e}")
    
    def get_pending_approvals(self, tank_id: int = None) -> List[Dict]:
        """Get all pending overdue dose approval requests."""
        query = db.session.query(OverdueDoseRequest).filter_by(status='pending')
        
        if tank_id:
            query = query.join(DSchedule).filter(DSchedule.tank_id == tank_id)
        
        requests = query.order_by(OverdueDoseRequest.detected_time.asc()).all()
        return [request.to_dict() for request in requests]
    
    def approve_overdue_dose(self, request_id: int, approved_by: str = None, notes: str = None) -> bool:
        """Approve an overdue dose request and schedule the dose."""
        try:
            request = db.session.query(OverdueDoseRequest).get(request_id)
            if not request or request.status != 'pending':
                return False
            
            # Update request status
            request.status = 'approved'
            request.approved_by = approved_by
            request.approved_time = datetime.now()
            if notes:
                request.notes = notes
            
            # Schedule the dose
            dose = Dosing(
                trigger_time=datetime.now(),
                amount=request.schedule.amount,
                product_id=request.schedule.product_id,
                schedule_id=request.schedule_id
            )
            db.session.add(dose)
            db.session.commit()
            
            self.logger.info(f"Approved and scheduled overdue dose for request {request_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to approve overdue dose request {request_id}: {e}")
            return False
    
    def reject_overdue_dose(self, request_id: int, rejected_by: str = None, notes: str = None) -> bool:
        """Reject an overdue dose request."""
        try:
            request = db.session.query(OverdueDoseRequest).get(request_id)
            if not request or request.status != 'pending':
                return False
            
            request.status = 'rejected'
            request.approved_by = rejected_by
            request.approved_time = datetime.now()
            if notes:
                request.notes = notes
            
            db.session.commit()
            self.logger.info(f"Rejected overdue dose request {request_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to reject overdue dose request {request_id}: {e}")
            return False
    
    def cleanup_old_requests(self, days_old: int = 7):
        """Clean up old overdue dose requests."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            old_requests = db.session.query(OverdueDoseRequest).filter(
                OverdueDoseRequest.detected_time < cutoff_date,
                OverdueDoseRequest.status.in_(['rejected', 'expired', 'auto_dosed'])
            ).all()
            
            for request in old_requests:
                db.session.delete(request)
            
            db.session.commit()
            self.logger.info(f"Cleaned up {len(old_requests)} old overdue dose requests")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to cleanup old overdue requests: {e}")
