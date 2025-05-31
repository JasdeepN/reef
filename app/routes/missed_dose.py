"""
Missed dose management routes for configuring and approving missed doses.
"""

from flask import request, jsonify, render_template, flash, redirect, url_for
from app import app, db
from modules.tank_context import get_current_tank_id, ensure_tank_context
from modules.models import DSchedule, MissedDoseRequest, MissedDoseHandlingEnum
from modules.missed_dose_handler import MissedDoseHandler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@app.route("/missed-dose")
def missed_dose_redirect():
    """Redirect /missed-dose to /missed-dose/dashboard for convenience."""
    return redirect(url_for('missed_dose_dashboard'))

@app.route("/missed-dose/dashboard")
def missed_dose_dashboard():
    """Dashboard for managing missed doses and configuration."""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        # Get pending approval requests
        missed_dose_handler = MissedDoseHandler()
        pending_requests = missed_dose_handler.get_pending_approvals(tank_id)
        
        # Get schedules with missed dose handling configuration
        schedules = db.session.query(DSchedule).filter_by(tank_id=tank_id).all()
        
        # Build schedules data with missed dose configuration
        schedules_data = []
        for schedule in schedules:
            schedules_data.append({
                "id": schedule.id,
                "product_name": schedule.product.name if schedule.product else "Unknown",
                "amount": schedule.amount,
                "trigger_interval": schedule.trigger_interval,
                "missed_dose_handling": schedule.missed_dose_handling.value if schedule.missed_dose_handling else 'alert_only',
                "missed_dose_grace_period_hours": schedule.missed_dose_grace_period_hours,
                "missed_dose_notification_enabled": schedule.missed_dose_notification_enabled,
                "suspended": schedule.suspended
            })
        
        # API URLs for frontend with correct v1 prefix
        api_urls = {
            "get_pending": "/api/v1/missed-dose/pending",
            "approve": "/api/v1/missed-dose/approve", 
            "reject": "/api/v1/missed-dose/reject",
            "update_config": "/api/v1/missed-dose/config/update",
            "analyze": "/api/v1/missed-dose/analyze"
        }
        
        return render_template(
            "missed-dose/dashboard.html",
            schedules=schedules_data,
            pending_requests=pending_requests,
            api_urls=api_urls,
            missed_dose_handling_options=[
                {"value": "alert_only", "label": "Alert Only (Skip missed doses)"},
                {"value": "grace_period", "label": "Grace Period (Allow within time window)"},
                {"value": "manual_approval", "label": "Manual Approval Required"}
            ]
        )
        
    except Exception as e:
        logger.error(f"Error loading missed dose dashboard: {e}")
        flash("Error loading missed dose configuration.", "error")
        return redirect(url_for('index'))