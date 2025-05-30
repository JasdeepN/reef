from flask import Blueprint, request, jsonify
from app import db
from modules.tank_context import ensure_tank_context
from modules.models import DSchedule
from modules.overdue_handler import OverdueHandler
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('overdue_api', __name__, url_prefix='/overdue')

@bp.route('/pending', methods=['GET'])
def get_pending_overdue():
    """Get pending overdue dose approval requests."""
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    
    try:
        overdue_handler = OverdueHandler()
        pending_requests = overdue_handler.get_pending_approvals(tank_id)
        
        return jsonify({
            "success": True,
            "data": {
                "pending_requests": pending_requests,
                "count": len(pending_requests)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting pending overdue requests: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/approve', methods=['POST'])
def approve_overdue():
    """Approve an overdue dose request."""
    data = request.get_json()
    request_id = data.get('request_id')
    notes = data.get('notes', '')
    
    if not request_id:
        return jsonify({"success": False, "error": "Request ID is required"}), 400
    
    try:
        overdue_handler = OverdueHandler()
        success = overdue_handler.approve_overdue_dose(
            request_id=request_id,
            approved_by="System User",
            notes=notes
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Overdue dose approved and scheduled"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to approve overdue dose"
            }), 400
            
    except Exception as e:
        logger.error(f"Error approving overdue dose: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/reject', methods=['POST'])
def reject_overdue():
    """Reject an overdue dose request."""
    data = request.get_json()
    request_id = data.get('request_id')
    notes = data.get('notes', '')
    
    if not request_id:
        return jsonify({"success": False, "error": "Request ID is required"}), 400
    
    try:
        overdue_handler = OverdueHandler()
        success = overdue_handler.reject_overdue_dose(
            request_id=request_id,
            rejected_by="System User",
            notes=notes
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "Overdue dose rejected"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to reject overdue dose"
            }), 400
            
    except Exception as e:
        logger.error(f"Error rejecting overdue dose: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/config/update', methods=['POST'])
def update_overdue_config():
    """Update overdue handling configuration for a schedule."""
    data = request.get_json()
    schedule_id = data.get('schedule_id')
    
    if not schedule_id:
        return jsonify({"success": False, "error": "Schedule ID is required"}), 400
    
    try:
        schedule = db.session.query(DSchedule).get(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        # Update configuration fields if provided
        if 'auto_dose_overdue' in data:
            schedule.auto_dose_overdue = data['auto_dose_overdue']
        if 'require_approval' in data:
            schedule.require_approval = data['require_approval']
        if 'max_overdue_hours' in data:
            schedule.max_overdue_hours = data['max_overdue_hours']
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Overdue configuration updated",
            "data": {
                "schedule_id": schedule.id,
                "auto_dose_overdue": schedule.auto_dose_overdue,
                "require_approval": schedule.require_approval,
                "max_overdue_hours": schedule.max_overdue_hours
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating overdue configuration: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/analyze/<int:schedule_id>', methods=['GET'])
def analyze_schedule_overdue(schedule_id):
    """Analyze a specific schedule for overdue status."""
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    
    try:
        schedule = db.session.query(DSchedule).get(schedule_id)
        if not schedule or schedule.tank_id != tank_id:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        overdue_handler = OverdueHandler()
        analysis = overdue_handler.analyze_schedule_for_overdue(schedule)
        
        return jsonify({
            "success": True,
            "data": {
                "schedule_id": analysis.schedule_id,
                "missed_dose_time": analysis.missed_dose_time.isoformat() if analysis.missed_dose_time else None,
                "hours_overdue": analysis.hours_overdue,
                "should_dose": analysis.should_dose,
                "action": analysis.action,
                "reason": analysis.reason
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing schedule for overdue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
