"""
Missed dose handling system for ReefDB dosing scheduler.

This module implements configurable strategies for handling missed doses:
- Alert Only: Skip missed doses and show next scheduled dose (default)
- Grace Period: Allow dosing within configurable time window  
- Manual Approval: Require user confirmation for missed doses

Note: Catch-up functionality has been removed for safety reasons to prevent
parameter swings in reef tanks.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

from app import db
from modules.models import DSchedule, Dosing, MissedDoseRequest, MissedDoseHandlingEnum

logger = logging.getLogger(__name__)

@dataclass
class MissedDoseAnalysis:
    """Analysis result for a missed dose."""
    schedule_id: int
    missed_dose_time: datetime
    hours_missed: float
    should_dose: bool
    action: str  # 'skip', 'dose_now', 'grace_period', 'manual_approval'
    reason: str
    

class MissedDoseHandler:
    """Handles missed dose detection and processing based on configured strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_schedule_for_missed_dose(self, schedule: DSchedule, reference_time: datetime = None) -> MissedDoseAnalysis:
        """
        Analyze a dosing schedule to determine if it has missed doses and what action to take.
        
        Args:
            schedule: DSchedule model instance
            reference_time: Time to compare against (defaults to current time)
            
        Returns:
            MissedDoseAnalysis with recommendation for handling the missed dose
        """
        if reference_time is None:
            reference_time = datetime.now()
            
        # Calculate when the next dose should have been
        last_dose = self._get_last_dose_time(schedule)
        expected_dose_time = last_dose + timedelta(seconds=schedule.trigger_interval)
        
        # Check if it's actually overdue
        if expected_dose_time > reference_time:
            return MissedDoseAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=expected_dose_time,
                hours_missed=0,
                should_dose=False,
                action='not_overdue',
                reason='Next dose is not yet due'
            )
        
        hours_missed = (reference_time - expected_dose_time).total_seconds() / 3600
        
        # Determine action based on missed dose handling strategy
        if schedule.missed_dose_handling == MissedDoseHandlingEnum.alert_only:
            return self._handle_alert_only(schedule, expected_dose_time, hours_missed)
        elif schedule.missed_dose_handling == MissedDoseHandlingEnum.grace_period:
            return self._handle_grace_period(schedule, expected_dose_time, hours_missed)
        elif schedule.missed_dose_handling == MissedDoseHandlingEnum.manual_approval:
            return self._handle_manual_approval(schedule, expected_dose_time, hours_missed)
        else:
            # Default to alert_only for unknown strategies
            return self._handle_alert_only(schedule, expected_dose_time, hours_missed)
    
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
    
    def _handle_alert_only(self, schedule: DSchedule, missed_dose_time: datetime, hours_missed: float) -> MissedDoseAnalysis:
        """Handle alert-only strategy: skip missed doses and show next scheduled dose."""
        return MissedDoseAnalysis(
            schedule_id=schedule.id,
            missed_dose_time=missed_dose_time,
            hours_missed=hours_missed,
            should_dose=False,
            action='skip',
            reason=f'Alert-only mode: Dose missed {hours_missed:.1f} hours ago, skipping to next scheduled dose'
        )
    
    def _handle_grace_period(self, schedule: DSchedule, missed_dose_time: datetime, hours_missed: float) -> MissedDoseAnalysis:
        """Handle grace period strategy: allow dosing within configured window."""
        grace_period = schedule.missed_dose_grace_period_hours or 12
        
        if hours_missed <= grace_period:
            return MissedDoseAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_missed=hours_missed,
                should_dose=True,
                action='grace_period',
                reason=f'Within grace period ({hours_missed:.1f}h missed, {grace_period}h allowed)'
            )
        else:
            return MissedDoseAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_missed=hours_missed,
                should_dose=False,
                action='skip',
                reason=f'Past grace period ({hours_missed:.1f}h missed, {grace_period}h limit)'
            )
    
    def _handle_manual_approval(self, schedule: DSchedule, missed_dose_time: datetime, hours_missed: float) -> MissedDoseAnalysis:
        """Handle manual approval strategy: require user confirmation."""
        # Check if there's already a pending request
        existing_request = db.session.query(MissedDoseRequest).filter_by(
            schedule_id=schedule.id,
            status='pending'
        ).filter(
            MissedDoseRequest.missed_dose_time == missed_dose_time
        ).first()
        
        if existing_request:
            return MissedDoseAnalysis(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_missed=hours_missed,
                should_dose=False,
                action='pending_approval',
                reason=f'Manual approval pending (request #{existing_request.id})'
            )
        
        # Create new approval request
        self._create_approval_request(schedule, missed_dose_time, hours_missed)
        
        return MissedDoseAnalysis(
            schedule_id=schedule.id,
            missed_dose_time=missed_dose_time,
            hours_missed=hours_missed,
            should_dose=False,
            action='manual_approval',
            reason=f'Manual approval required ({hours_missed:.1f}h missed)'
        )
    
    def _create_approval_request(self, schedule: DSchedule, missed_dose_time: datetime, hours_missed: float):
        """Create a new missed dose approval request."""
        try:
            request = MissedDoseRequest(
                schedule_id=schedule.id,
                missed_dose_time=missed_dose_time,
                hours_missed=hours_missed,
                status='pending'
            )
            db.session.add(request)
            db.session.commit()
            self.logger.info(f"Created missed dose approval request for schedule {schedule.id}")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create missed dose approval request: {e}")
    
    def get_pending_approvals(self, tank_id: int = None) -> List[Dict]:
        """Get all pending missed dose approval requests."""
        query = db.session.query(MissedDoseRequest).filter_by(status='pending')
        
        if tank_id:
            query = query.join(DSchedule).filter(DSchedule.tank_id == tank_id)
        
        requests = query.order_by(MissedDoseRequest.detected_time.asc()).all()
        return [request.to_dict() for request in requests]
    
    def approve_missed_dose(self, request_id: int, approved_by: str = None, notes: str = None) -> bool:
        """Approve a missed dose request and schedule the dose."""
        try:
            request = db.session.query(MissedDoseRequest).get(request_id)
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
            
            self.logger.info(f"Approved and scheduled missed dose for request {request_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to approve missed dose request {request_id}: {e}")
            return False
    
    def reject_missed_dose(self, request_id: int, rejected_by: str = None, notes: str = None) -> bool:
        """Reject a missed dose request."""
        try:
            request = db.session.query(MissedDoseRequest).get(request_id)
            if not request or request.status != 'pending':
                return False
            
            request.status = 'rejected'
            request.approved_by = rejected_by
            request.approved_time = datetime.now()
            if notes:
                request.notes = notes
            
            db.session.commit()
            self.logger.info(f"Rejected missed dose request {request_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to reject missed dose request {request_id}: {e}")
            return False
    
    def cleanup_old_requests(self, days_old: int = 7):
        """Clean up old missed dose requests."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            old_requests = db.session.query(MissedDoseRequest).filter(
                MissedDoseRequest.detected_time < cutoff_date,
                MissedDoseRequest.status.in_(['rejected', 'expired', 'auto_dosed'])
            ).all()
            
            for request in old_requests:
                db.session.delete(request)
            
            db.session.commit()
            self.logger.info(f"Cleaned up {len(old_requests)} old missed dose requests")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to cleanup old missed dose requests: {e}")
