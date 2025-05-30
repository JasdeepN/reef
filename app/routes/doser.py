from datetime import timedelta
import urllib.parse
import json
from flask import jsonify, render_template, request, redirect, url_for, session, flash
from app import app
from modules.models import *  # Import your models
from modules.utils.helper import *
from modules.tank_context import get_current_tank_id, ensure_tank_context
from modules.forms import CombinedDosingScheduleForm
# import db
import enum
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired


@app.route("/doser")
def doser_main():
    """Enhanced dosing dashboard with schedule cards and control buttons"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    # API URLs for the enhanced dashboard
    api_urls = {
        "stats": "/web/fn/schedule/get/stats",
        "next_doses": "/web/fn/schedule/get/next-doses",
        "dose": "/api/v1/controller/dose",
        "refill": "/api/v1/controller/refill", 
        "toggle": "/api/v1/controller/toggle/schedule",
        "delete": "/web/fn/ops/delete/d_schedule"
    }
    
    return render_template("doser/main.html", 
                         tank_id=tank_id, api_urls=api_urls)


@app.route("/doser/db", methods=['GET'])
def db_doser():
    """Display dosing database with schedule and dosing history join"""
    from sqlalchemy import text
    
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        # Enhanced SQL query to include product information
        sql = """
            SELECT 
                dosing.id,
                dosing.trigger_time,
                dosing.amount,
                dosing.product_id,
                dosing.schedule_id,
                d_schedule.id AS schedule_id_check,
                d_schedule.trigger_interval,
                d_schedule.suspended,
                d_schedule.amount AS scheduled_amount,
                products.name AS product_name,
                products.uses AS product_uses
            FROM dosing
            JOIN d_schedule ON dosing.schedule_id = d_schedule.id
            LEFT JOIN products ON dosing.product_id = products.id
            WHERE d_schedule.tank_id = :tank_id
            ORDER BY dosing.trigger_time DESC;
        """
        
        result = db.session.execute(text(sql), {'tank_id': tank_id}).mappings()
        rows = []
        
        for row in result:
            row_dict = dict(row)
            # Convert datetime fields to string
            for k, v in row_dict.items():
                if isinstance(v, timedelta):
                    row_dict[k] = str(v)
                elif k == "trigger_time" and v:
                    row_dict[k] = v.strftime("%Y-%m-%d %H:%M:%S") if hasattr(v, 'strftime') else str(v)
                # Convert boolean/int fields to "Yes"/"No" for booleans (including 0/1)
                elif k == "suspended":
                    row_dict[k] = "Yes" if bool(v) else "No"
            rows.append(row_dict)

        # Generate columns from the first row if available, otherwise use defaults
        if rows:
            columns = generate_columns(rows[0].keys())
        else:
            # Default columns if no data
            default_cols = ['id', 'trigger_time', 'amount', 'product_name', 'suspended']
            columns = generate_columns(default_cols)

        tables = [
            {
                "id": "dosing_history_table",
                "api_url": None,
                "title": f"Dosing History for Tank {tank_id}",
                "columns": columns,
                "initial_data": rows,
                "datatable_options": {
                    "dom": "Bfrtip",
                    "buttons": [
                        {"text": "Edit", "action": "edit"},
                        {"text": "Delete", "action": "delete"}
                    ],
                    "serverSide": False,
                    "processing": False,
                    "order": [[1, "desc"]],  # Sort by trigger_time descending
                },
            }
        ]

        return render_template('doser/dosing_db.html', tables=tables)
        
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('doser_main'))


@app.route("/doser/db/test/<int:tank_id>", methods=['GET'])
def test_db_doser(tank_id):
    """Test endpoint to set tank_id and view dosing database for testing purposes"""
    from modules.tank_context import set_tank_id_for_testing
    
    # Set the tank_id for testing
    set_tank_id_for_testing(tank_id)
    
    # Call the regular db_doser function
    return db_doser()


@app.route("/doser/schedule", methods=["GET", "POST"])
def run_schedule():
    """Redirect to the new schedule manager with integrated stats"""
    # Redirect legacy route to the new schedule manager
    return redirect(url_for('schedule_new'))
    

@app.route("/doser/schedule/new", methods=["GET", "POST"])
def schedule_new():
    """Enhanced dosing schedule page with granular time controls"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected. Please select a tank before creating dosing schedules.", "warning")
        return redirect(url_for('index'))
    
    if request.method == "POST":
        data = request.get_json()
        return handle_schedule_submission(data, tank_id)
    
    # GET request - show the form
    # Fetch available products for the dropdown
    products = Products.query.all()
    products_list = [{"id": p.id, "name": p.name, "current_avail": p.current_avail} for p in products]
    
    # Fetch existing schedules for the current tank
    existing_schedules = DSchedule.query.filter_by(tank_id=tank_id).all()
    schedules_data = []
    for schedule in existing_schedules:
        schedules_data.append({
            "id": schedule.id,
            "product_name": schedule.product.name if schedule.product else "Unknown",
            "amount": schedule.amount,
            "trigger_interval": schedule.trigger_interval,
            "suspended": schedule.suspended,
            "last_refill": schedule.last_refill.isoformat() if schedule.last_refill else None
        })
    
    # Stats API URLs for the integrated cards
    stats_api_urls = {
        "GET": "/web/fn/schedule/get/stats",
        "DELETE": "/web/fn/ops/delete/d_schedule"
    }
    
    return render_template(
        "doser/schedule_new.html",
        title="Dosing Schedule Manager",
        tank_id=tank_id,
        products=products_list,
        existing_schedules=schedules_data,
        stats_api_urls=stats_api_urls
    )

@app.route("/doser/schedule/edit/<int:schedule_id>", methods=["GET", "POST"])
def schedule_edit(schedule_id):
    """Edit existing dosing schedule with the same granular controls as new schedule page"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected. Please select a tank before editing dosing schedules.", "warning")
        return redirect(url_for('index'))
    
    # Get the schedule to edit
    schedule = DSchedule.query.filter_by(id=schedule_id, tank_id=tank_id).first()
    if not schedule:
        flash("Schedule not found or access denied.", "error")
        return redirect(url_for('schedule_new'))
    
    if request.method == "POST":
        data = request.get_json()
        return handle_schedule_edit_submission(data, schedule_id, tank_id)
    
    # GET request - show the form with pre-populated data
    # Fetch available products for the dropdown
    products = Products.query.all()
    products_list = [{"id": p.id, "name": p.name, "current_avail": p.current_avail} for p in products]
    
    # Fetch existing schedules for the current tank (excluding current one)
    existing_schedules = DSchedule.query.filter(DSchedule.tank_id == tank_id, DSchedule.id != schedule_id).all()
    schedules_data = []
    for s in existing_schedules:
        schedules_data.append({
            "id": s.id,
            "product_name": s.product.name if s.product else "Unknown",
            "amount": s.amount,
            "trigger_interval": s.trigger_interval,
            "suspended": s.suspended,
            "last_refill": s.last_refill.isoformat() if s.last_refill else None
        })
    
    # Convert schedule data for form pre-population
    schedule_data = {
        "id": schedule.id,
        "product_id": schedule.product_id,
        "product_name": schedule.product.name if schedule.product else "Unknown",
        "amount": schedule.amount,
        "trigger_interval": schedule.trigger_interval,
        "suspended": schedule.suspended,
        "last_refill": schedule.last_refill.isoformat() if schedule.last_refill else None
    }
    
    # Stats API URLs for the integrated cards
    stats_api_urls = {
        "GET": "/web/fn/schedule/get/stats",
        "DELETE": "/web/fn/ops/delete/d_schedule"
    }
    
    return render_template(
        "doser/schedule_edit.html",
        title="Edit Dosing Schedule",
        tank_id=tank_id,
        products=products_list,
        existing_schedules=schedules_data,
        schedule=schedule_data,
        stats_api_urls=stats_api_urls
    )

def handle_schedule_edit_submission(data, schedule_id, tank_id):
    """Handle the submission of schedule edit"""
    try:
        # Get the existing schedule
        schedule = DSchedule.query.filter_by(id=schedule_id, tank_id=tank_id).first()
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        # Extract and validate data
        product_id = data.get('product_id')
        amount = float(data.get('amount', 0))
        schedule_type = data.get('schedule_type')  # 'interval', 'daily', 'weekly', 'custom'
        suspended = data.get('suspended', False)
        
        if not product_id or amount <= 0:
            return jsonify({"success": False, "error": "Product and positive amount are required"}), 400
        
        # Calculate trigger_interval based on schedule_type and user input
        trigger_interval = calculate_trigger_interval(data, schedule_type)
        if trigger_interval is None:
            return jsonify({"success": False, "error": "Invalid schedule configuration"}), 400
        
        # Process overdue handling configuration
        overdue_strategy = data.get('overdue_strategy', 'alert_only')
        grace_period_hours = data.get('grace_period_hours')
        max_catch_up_doses = data.get('max_catch_up_doses')
        overdue_notification_enabled = data.get('overdue_notification_enabled', False)
        
        # Validate overdue strategy enum
        try:
            overdue_strategy_enum = OverdueHandlingEnum(overdue_strategy)
        except ValueError:
            overdue_strategy_enum = OverdueHandlingEnum.ALERT_ONLY
        
        # Validate grace period hours (1-72 hours)
        if grace_period_hours is not None:
            try:
                grace_period_hours = int(grace_period_hours)
                if grace_period_hours < 1 or grace_period_hours > 72:
                    grace_period_hours = None
            except (ValueError, TypeError):
                grace_period_hours = None
        
        # Validate max catch up doses (1-10 doses)
        if max_catch_up_doses is not None:
            try:
                max_catch_up_doses = int(max_catch_up_doses)
                if max_catch_up_doses < 1 or max_catch_up_doses > 10:
                    max_catch_up_doses = None
            except (ValueError, TypeError):
                max_catch_up_doses = None
        
        # Update existing schedule
        schedule.product_id = product_id
        schedule.amount = amount
        schedule.trigger_interval = trigger_interval
        schedule.suspended = suspended
        schedule.overdue_strategy = overdue_strategy_enum
        schedule.grace_period_hours = grace_period_hours
        schedule.max_catch_up_doses = max_catch_up_doses
        schedule.overdue_notification_enabled = overdue_notification_enabled
        
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Dosing schedule updated successfully",
            "schedule_id": schedule.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

def handle_schedule_submission(data, tank_id):
    """Handle the submission of a new dosing schedule"""
    try:
        # Extract and validate data
        product_id = data.get('product_id')
        amount = float(data.get('amount', 0))
        schedule_type = data.get('schedule_type')  # 'interval', 'daily', 'weekly', 'custom'
        suspended = data.get('suspended', False)
        
        if not product_id or amount <= 0:
            return jsonify({"success": False, "error": "Product and positive amount are required"}), 400
        
        # Calculate trigger_interval based on schedule_type and user input
        trigger_interval = calculate_trigger_interval(data, schedule_type)
        if trigger_interval is None:
            return jsonify({"success": False, "error": "Invalid schedule configuration"}), 400
        
        # Process overdue handling configuration
        overdue_strategy = data.get('overdue_strategy', 'alert_only')
        grace_period_hours = data.get('grace_period_hours')
        max_catch_up_doses = data.get('max_catch_up_doses')
        overdue_notification_enabled = data.get('overdue_notification_enabled', False)
        
        # Validate overdue strategy enum
        try:
            overdue_strategy_enum = OverdueHandlingEnum(overdue_strategy)
        except ValueError:
            overdue_strategy_enum = OverdueHandlingEnum.ALERT_ONLY
        
        # Validate grace period hours (1-72 hours)
        if grace_period_hours is not None:
            try:
                grace_period_hours = int(grace_period_hours)
                if grace_period_hours < 1 or grace_period_hours > 72:
                    grace_period_hours = None
            except (ValueError, TypeError):
                grace_period_hours = None
        
        # Validate max catch up doses (1-10 doses)
        if max_catch_up_doses is not None:
            try:
                max_catch_up_doses = int(max_catch_up_doses)
                if max_catch_up_doses < 1 or max_catch_up_doses > 10:
                    max_catch_up_doses = None
            except (ValueError, TypeError):
                max_catch_up_doses = None
        
        # Create new schedule
        new_schedule = DSchedule(
            trigger_interval=trigger_interval,
            suspended=suspended,
            amount=amount,
            tank_id=tank_id,
            product_id=product_id,
            overdue_strategy=overdue_strategy_enum,
            grace_period_hours=grace_period_hours,
            max_catch_up_doses=max_catch_up_doses,
            overdue_notification_enabled=overdue_notification_enabled
        )
        
        db.session.add(new_schedule)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Dosing schedule created successfully",
            "schedule_id": new_schedule.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

def calculate_trigger_interval(data, schedule_type):
    """Calculate trigger interval in seconds based on schedule type and user input"""
    try:
        if schedule_type == 'interval':
            return _calculate_interval_schedule(data)
        elif schedule_type == 'daily':
            return _calculate_daily_schedule(data)
        elif schedule_type == 'weekly':
            return _calculate_weekly_schedule(data)
        elif schedule_type == 'custom':
            return _calculate_custom_schedule(data)
    except (ValueError, TypeError):
        return None
    return None

def _calculate_interval_schedule(data):
    """Calculate interval for direct interval input"""
    interval_value = int(data.get('interval_value', 0))
    interval_unit = data.get('interval_unit', 'minutes')
    
    if interval_value <= 0:
        return None
        
    unit_multipliers = {
        'minutes': 60,
        'hours': 3600, 
        'days': 86400
    }
    return interval_value * unit_multipliers.get(interval_unit, 60)

def _calculate_daily_schedule(data):
    """Calculate interval for daily schedule"""
    times_per_day = int(data.get('times_per_day', 1))
    if times_per_day <= 0 or times_per_day > 1440:  # Max once per minute
        return None
    return 86400 // times_per_day

def _calculate_weekly_schedule(data):
    """Calculate interval for weekly schedule"""
    times_per_week = int(data.get('times_per_week', 1))
    if times_per_week <= 0 or times_per_week > 10080:  # Max once per minute for a week
        return None
    return 604800 // times_per_week  # 604800 seconds in a week

def _calculate_custom_schedule(data):
    """Calculate interval for custom schedule"""
    custom_seconds = int(data.get('custom_seconds', 0))
    if custom_seconds < 60:  # Minimum 1 minute
        return None
    return custom_seconds


@app.route("/doser/submit", methods=["POST"])
def doser_submit():
    tank_id = ensure_tank_context()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    data = request.get_json()
    form_type = data.get("form_type")
    if not form_type:
        return jsonify({"success": False, "error": "Missing form_type"}), 400

    # --- Handle new product creation if needed ---
    if data.get("product_id") == "add_new_product":
        product_fields = {"name", "total_volume", "current_avail", "dry_refill"}
        product_data = {k: v for k, v in data.items() if k in product_fields}
        from app import app as flask_app
        with flask_app.test_request_context():
            with flask_app.test_client() as client:
                resp = client.post("/web/fn/ops/new/products", json=product_data)
                prod_resp = resp.get_json()
                if not prod_resp or not prod_resp.get("success") or not prod_resp.get("id"):
                    return jsonify({"success": False, "error": "Failed to create new product"}), 400
                data["product_id"] = prod_resp["id"]

    if not data.get("product_id"):
        return jsonify({"success": False, "error": "Product ID is required"}), 400

    if "schedule_time" in data:
        data["_time"] = data["schedule_time"]
        data.pop("schedule_time", None)

    # Always set tank_id in the data dict for downstream API calls
    # data["tank_id"] = tank_id

    from app import app as flask_app
    with flask_app.test_request_context():
        with flask_app.test_client() as client:
            
            if form_type == "recurring":
                # Validation for recurring
                required_fields = ["amount", "product_id", "trigger_interval", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for recurring: {', '.join(missing)}"
                    }), 400
                # Insert only into d_schedule (not dosing)
                schedule_data = {
                    "amount": data["amount"],
                    "product_id": data["product_id"],
                    "trigger_interval": data["trigger_interval"],
                    "suspended": data.get("suspended", False),
                    "tank_id": tank_id,
                }
                sched_resp = client.post("/web/fn/ops/new/d_schedule", json=schedule_data)
                return sched_resp.get_data(), sched_resp.status_code, sched_resp.headers.items()
            elif form_type in ("single", "intermittent"):
                required_fields = ["amount", "product_id", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for {form_type}: {', '.join(missing)}"
                    }), 400
                api_url = "/web/fn/ops/new/dosing"
                dosing_data = {
                    "amount": data["amount"],
                    "product_id": data["product_id"],
                    "trigger_time": data["_time"],
                }
                resp = client.post(api_url, json=dosing_data)
                return resp.get_data(), resp.status_code, resp.headers.items()
            else:
                return jsonify({"success": False, "error": "Unknown form_type"}), 400
            

@app.route("/doser/products", methods=["GET"])
def get_products():
    urls = {
        "GET": "/web/fn/products/stats",
        "DELETE": "/web/fn/ops/delete/products",
        "POST": "/web/fn/ops/new/products",
        "PUT": "/web/fn/ops/edit/products"
    }
    return render_template("doser/products.html", title="Products", api_urls=urls)


@app.route("/doser/history")
def doser_history():
    """Display dosing history with latest dose events, amounts, times, and products"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    
    # API URLs for the history dashboard
    api_urls = {
        "history": "/web/fn/schedule/get/history",
        "stats": "/web/fn/schedule/get/stats",
        "delete": "/web/fn/ops/delete/dosing"
    }
    
    return render_template("doser/history.html", 
                         tank_id=tank_id, api_urls=api_urls)


