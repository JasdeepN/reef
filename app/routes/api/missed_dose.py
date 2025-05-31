from flask import Blueprint, request, jsonify
from app import db
from modules.tank_context import ensure_tank_context
from modules.models import DSchedule
from modules.missed_dose_handler import MissedDoseHandler
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('missed_dose_api', __name__, url_prefix='/missed-dose')

@bp.route('/pending', methods=['GET'])
def get_pending_missed_doses():
    """Get pending missed dose approval requests."""
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    
    try:
        missed_dose_handler = MissedDoseHandler()
        pending_requests = missed_dose_handler.get_pending_approvals(tank_id)
        
        return jsonify({
            "success": True,
            "data": {
                "pending_requests": pending_requests,
                "count": len(pending_requests)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting pending missed dose requests: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/approve', methods=['POST'])
def approve_missed_dose():
    """Approve a missed dose request."""
    data = request.get_json()
    request_id = data.get('request_id')
    notes = data.get('notes', '')
    
    if not request_id:
        return jsonify({"success": False, "error": "Request ID is required"}), 400
    
    try:
        missed_dose_handler = MissedDoseHandler()
        success = missed_dose_handler.approve_missed_dose(
            request_id=request_id,
            approved_by="System User",
            notes=notes
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Missed dose approved and scheduled"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to approve missed dose"
            }), 400
            
    except Exception as e:
        logger.error(f"Error approving missed dose: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/reject', methods=['POST'])
def reject_missed_dose():
    """Reject a missed dose request."""
    data = request.get_json()
    request_id = data.get('request_id')
    notes = data.get('notes', '')
    
    if not request_id:
        return jsonify({"success": False, "error": "Request ID is required"}), 400
    
    try:
        missed_dose_handler = MissedDoseHandler()
        success = missed_dose_handler.reject_missed_dose(
            request_id=request_id,
            rejected_by="System User",
            notes=notes
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Missed dose rejected"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to reject missed dose"
            }), 400
            
    except Exception as e:
        logger.error(f"Error rejecting missed dose: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/config/update', methods=['POST'])
def update_missed_dose_config():
    """Update missed dose handling configuration for a schedule."""
    data = request.get_json()
    schedule_id = data.get('schedule_id')
    
    if not schedule_id:
        return jsonify({"success": False, "error": "Schedule ID is required"}), 400
    
    try:
        schedule = db.session.query(DSchedule).get(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        # Update configuration fields if provided
        if 'missed_dose_handling' in data:
            schedule.missed_dose_handling = data['missed_dose_handling']
        if 'missed_dose_grace_period_hours' in data:
            schedule.missed_dose_grace_period_hours = data['missed_dose_grace_period_hours']
        if 'missed_dose_notification_enabled' in data:
            schedule.missed_dose_notification_enabled = data['missed_dose_notification_enabled']
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Missed dose configuration updated",
            "data": {
                "schedule_id": schedule.id,
                "missed_dose_handling": schedule.missed_dose_handling.value if schedule.missed_dose_handling else None,
                "missed_dose_grace_period_hours": schedule.missed_dose_grace_period_hours,
                "missed_dose_notification_enabled": schedule.missed_dose_notification_enabled
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating missed dose configuration: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/analyze/<int:schedule_id>', methods=['GET'])
def analyze_schedule_missed_dose(schedule_id):
    """Analyze a specific schedule for missed dose status."""
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    
    try:
        schedule = db.session.query(DSchedule).get(schedule_id)
        if not schedule or schedule.tank_id != tank_id:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        missed_dose_handler = MissedDoseHandler()
        analysis = missed_dose_handler.analyze_schedule_for_missed_dose(schedule)
        
        return jsonify({
            "success": True,
            "data": {
                "schedule_id": analysis.schedule_id,
                "missed_dose_time": analysis.missed_dose_time.isoformat() if analysis.missed_dose_time else None,
                "hours_missed": analysis.hours_missed,
                "should_dose": analysis.should_dose,
                "action": analysis.action,
                "reason": analysis.reason
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing schedule for missed dose: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
