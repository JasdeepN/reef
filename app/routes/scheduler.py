"""
Routes for the dosing scheduler dashboard and management interface.
"""

from flask import render_template, redirect, url_for, flash, jsonify, request
from app import app
from modules.tank_context import get_current_tank_id, ensure_tank_context
import requests

@app.route("/scheduler")
def scheduler_dashboard():
    """Scheduler monitoring and control dashboard"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    # Import models locally to avoid circular imports
    from modules.models import DSchedule, Products, Dosing
    from modules.models import db
    
    # Get scheduler status from API
    try:
        response = requests.get('http://localhost:5000/api/v1/scheduler/status')
        scheduler_status = response.json() if response.status_code == 200 else {}
    except Exception:
        scheduler_status = {"running": False, "error": "Could not connect to scheduler"}
    
    # Get active schedules for this tank
    active_schedules = DSchedule.query.filter_by(
        tank_id=tank_id, 
        suspended=False
    ).join(Products).all()
    
    # Get suspended schedules
    suspended_schedules = DSchedule.query.filter_by(
        tank_id=tank_id, 
        suspended=True
    ).count()
    
    # Prepare schedule data for dashboard
    schedules_data = []
    for schedule in active_schedules:
        # Get the most recent dose for this schedule
        last_dosing = db.session.query(Dosing).filter_by(schedule_id=schedule.id).order_by(Dosing.trigger_time.desc()).first()
        
        schedules_data.append({
            "id": schedule.id,
            "product_name": schedule.product.name if schedule.product else "Unknown",
            "amount": schedule.amount,
            "trigger_interval": schedule.trigger_interval,
            "last_dose": last_dosing.trigger_time.isoformat() if last_dosing and last_dosing.trigger_time else None
        })
    
    # API URLs for the dashboard
    api_urls = {
        "status": "/api/v1/scheduler/status",
        "start": "/api/v1/scheduler/start",
        "stop": "/api/v1/scheduler/stop",
        "restart": "/api/v1/scheduler/restart",
        "check": "/api/v1/scheduler/check",
        "due": "/api/v1/scheduler/due",
        "schedules": f"/web/fn/schedule/test/stats/{tank_id}",
        "control": "/scheduler/control"
    }
    
    return render_template("scheduler/dashboard.html", 
                         tank_id=tank_id, 
                         api_urls=api_urls,
                         scheduler_status=scheduler_status,
                         active_schedules_count=len(active_schedules),
                         suspended_schedules_count=suspended_schedules,
                         schedules_data=schedules_data)

@app.route("/scheduler/control", methods=["POST"])
def scheduler_control():
    """
    Handle scheduler control actions (start/stop/check).
    """
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    
    action = request.form.get('action')
    
    if action not in ['start', 'stop', 'check', 'restart']:
        return jsonify({"success": False, "error": "Invalid action"}), 400
    
    try:
        response = requests.post(f'http://localhost:5000/api/v1/scheduler/{action}')
        
        if response.status_code == 200:
            result = response.json()
            flash(f"Scheduler {action} successful: {result.get('message', '')}", "success")
            return jsonify({"success": True, "data": result})
        else:
            error_msg = f"Scheduler {action} failed"
            flash(error_msg, "danger")
            return jsonify({"success": False, "error": error_msg}), response.status_code
            
    except Exception as e:
        error_msg = f"Error executing {action}: {str(e)}"
        flash(error_msg, "danger")
        return jsonify({"success": False, "error": error_msg}), 500
