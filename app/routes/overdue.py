"""
Overdue dose management routes for configuring and approving overdue doses.
"""

from flask import request, jsonify, render_template, flash, redirect, url_for
from app import app, db
from modules.tank_context import get_current_tank_id, ensure_tank_context
from modules.models import DSchedule, OverdueDoseRequest, OverdueHandlingEnum
from modules.overdue_handler import OverdueHandler
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@app.route("/overdue")
def overdue_redirect():
    """Redirect /overdue to /overdue/dashboard for convenience."""
    return redirect(url_for('overdue_dashboard'))

@app.route("/overdue/dashboard")
def overdue_dashboard():
    """Dashboard for managing overdue doses and configuration."""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        # Get pending approval requests
        overdue_handler = OverdueHandler()
        pending_requests = overdue_handler.get_pending_approvals(tank_id)
        
        # Get schedules with overdue handling configuration
        schedules = db.session.query(DSchedule).filter_by(tank_id=tank_id).all()
        
        # Build schedules data with overdue configuration
        schedules_data = []
        for schedule in schedules:
            schedules_data.append({
                "id": schedule.id,
                "product_name": schedule.product.name if schedule.product else "Unknown",
                "amount": schedule.amount,
                "trigger_interval": schedule.trigger_interval,
                "overdue_handling": schedule.overdue_handling.value if schedule.overdue_handling else 'alert_only',
                "grace_period_hours": schedule.grace_period_hours,
                "max_catch_up_doses": schedule.max_catch_up_doses,
                "catch_up_window_hours": schedule.catch_up_window_hours,
                "overdue_notification_enabled": schedule.overdue_notification_enabled,
                "suspended": schedule.suspended
            })
        
        # API URLs for frontend with correct v1 prefix
        api_urls = {
            "get_pending": "/api/v1/overdue/pending",
            "approve": "/api/v1/overdue/approve", 
            "reject": "/api/v1/overdue/reject",
            "update_config": "/api/v1/overdue/config/update",
            "analyze": "/api/v1/overdue/analyze"
        }
        
        return render_template(
            "overdue/dashboard.html",
            schedules=schedules_data,
            pending_requests=pending_requests,
            api_urls=api_urls,
            overdue_handling_options=[
                {"value": "alert_only", "label": "Alert Only (Skip missed doses)"},
                {"value": "grace_period", "label": "Grace Period (Allow within time window)"},
                {"value": "catch_up", "label": "Catch-up (Dose immediately if within limits)"},
                {"value": "manual_approval", "label": "Manual Approval Required"}
            ]
        )
        
    except Exception as e:
        logger.error(f"Error loading overdue dashboard: {e}")
        flash("Error loading overdue configuration.", "error")
        return redirect(url_for('index'))