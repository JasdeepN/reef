import logging
import json
import urllib.parse
from datetime import timedelta, time
from typing import Optional
from flask import jsonify, render_template, request, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired

from app import app, db
from modules.models import (
    Products, Tank, Doser, Dosing, 
    TestResults,
    DSchedule, ScheduleTypeEnum, MissedDoseHandlingEnum
)
from modules.utils.helper import (
    get_table_columns, generate_columns, validate_and_process_data
)
from modules.system_context import (
    get_current_system_id, get_current_system_tank_ids, 
    get_current_system_tanks, ensure_system_context
)
from modules.forms import CombinedDosingScheduleForm
from modules.timezone_utils import (
    format_time_for_display, format_time_for_html_input, 
    normalize_time_input, datetime_to_iso_format,
    parse_trigger_time_from_db
)
from datetime import datetime

# Constants for error messages and API endpoints
ERROR_NO_SYSTEM = "No system selected."
ERROR_NO_TANKS = "No tanks in selected system."
API_SCHEDULE_STATS = "/web/fn/schedule/get/stats"
API_NEXT_DOSES = "/web/fn/schedule/get/next-doses"
API_DOSE = "/api/v1/controller/dose"
API_REFILL = "/api/v1/controller/refill"
API_TOGGLE = "/api/v1/controller/toggle/schedule"
API_DELETE_SCHEDULE = "/web/fn/ops/delete/d_schedule"

logger = logging.getLogger(__name__)


@app.route("/doser")
def doser_main():
    """Enhanced dosing dashboard with schedule cards and control buttons."""
    system_id = ensure_system_context()
    if not system_id:
        flash(ERROR_NO_SYSTEM, "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash(ERROR_NO_TANKS, "warning")
        return redirect(url_for('index'))
    
    # API URLs for the enhanced dashboard
    api_urls = {
        "stats": API_SCHEDULE_STATS,
        "next_doses": API_NEXT_DOSES,
        "dose": API_DOSE,
        "refill": API_REFILL, 
        "toggle": API_TOGGLE,
        "delete": API_DELETE_SCHEDULE
    }
    
    return render_template("doser/main.html", 
                         system_id=system_id, tank_ids=tank_ids, api_urls=api_urls)


@app.route("/doser/db", methods=['GET'])
def db_doser():
    """Display dosing database with schedule and dosing history join."""
    system_id = ensure_system_context()
    if not system_id:
        flash(ERROR_NO_SYSTEM, "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash(ERROR_NO_TANKS, "warning")
        return redirect(url_for('index'))
    
    try:
        rows = _fetch_dosing_history(tank_ids)
        columns = _generate_dosing_columns(rows)
        tables = _create_dosing_tables(rows, columns, system_id)
        
        return render_template("doser/database.html", tables=tables)
        
    except Exception as e:
        flash(f"Error loading dosing data: {str(e)}", "error")
        return redirect(url_for('doser_main'))

# ==============================================================================
# HELPER FUNCTIONS - Dosing Database Processing
# ==============================================================================

def _fetch_dosing_history(tank_ids):
    """Fetch dosing history data for given tank IDs."""
    from sqlalchemy import text
    
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
            d_schedule.tank_id,
            products.name AS product_name,
            products.uses AS product_uses
        FROM dosing
        JOIN d_schedule ON dosing.schedule_id = d_schedule.id
        LEFT JOIN products ON dosing.product_id = products.id
        WHERE d_schedule.tank_id IN :tank_ids
        ORDER BY dosing.trigger_time DESC;
    """
    
    result = db.session.execute(text(sql), {'tank_ids': tuple(tank_ids)}).mappings()
    rows = []
    
    for row in result:
        row_dict = dict(row)
        _format_dosing_row_data(row_dict)
        rows.append(row_dict)
    
    return rows

def _format_dosing_row_data(row_dict):
    """Format individual row data for display."""
    for k, v in row_dict.items():
        if isinstance(v, timedelta):
            row_dict[k] = str(v)
        elif k == "trigger_time" and v:
            row_dict[k] = datetime_to_iso_format(v) if hasattr(v, 'strftime') else str(v)
        elif k == "suspended":
            row_dict[k] = "Yes" if bool(v) else "No"

def _generate_dosing_columns(rows):
    """Generate columns for dosing history table."""
    if rows:
        return generate_columns(rows[0].keys())
    else:
        # Default columns if no data
        default_cols = ['id', 'trigger_time', 'amount', 'product_name', 'suspended']
        return generate_columns(default_cols)

def _create_dosing_tables(rows, columns, system_id):
    """Create table configuration for dosing history."""
    return [
        {
            "id": "dosing_history_table",
            "api_url": None,
            "title": f"Dosing History for System {system_id}",
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

# ==============================================================================
# MAIN DOSING ROUTES
# ==============================================================================

@app.route("/doser/db/test/<int:tank_id>", methods=['GET'])
def test_db_doser(tank_id):
    """Test endpoint to set tank_id and view dosing database for testing purposes"""
    from modules.system_context import set_tank_id_for_testing
    
    # Set the tank_id for testing (backward compatibility function)
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
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected. Please select a system before creating dosing schedules.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    if request.method == "POST":
        # Handle both JSON and form data for compatibility
        try:
            if request.is_json:
                data = request.get_json()
            else:
                # Fallback to form data
                data = request.form.to_dict()
                # Convert checkbox values to booleans
                if 'suspended' in data:
                    data['suspended'] = data['suspended'].lower() in ['true', '1', 'on']
        except Exception as e:
            return jsonify({"success": False, "error": f"Error parsing request data: {str(e)}"}), 400
        
        # Use the first tank in the system for backward compatibility
        return handle_schedule_submission(data, tank_ids[0])
    
    # GET request - show the form
    # Fetch available products for the dropdown
    products = Products.query.all()
    products_list = [{"id": p.id, "name": p.name, "current_avail": p.current_avail} for p in products]
    
    # Fetch available dosers for the current system (all tanks)
    dosers = Doser.query.filter(Doser.tank_id.in_(tank_ids), Doser.is_active == True).all()
    dosers_list = [{
        "id": d.id, 
        "doser_name": d.doser_name, 
        "doser_type": d.doser_type.value if d.doser_type else "other",
        "max_daily_volume": d.max_daily_volume
    } for d in dosers]
    
    # Fetch existing schedules for the current system (all tanks)
    existing_schedules = DSchedule.query.filter(DSchedule.tank_id.in_(tank_ids)).all()
    schedules_data = []
    for schedule in existing_schedules:
        schedules_data.append({
            "id": schedule.id,
            "product_name": schedule.product.name if schedule.product else "Unknown",
            "amount": schedule.amount,
            "trigger_interval": schedule.trigger_interval,
            "suspended": schedule.suspended,
            "last_refill": datetime_to_iso_format(schedule.last_refill) if schedule.last_refill else None
        })
    
    # Get system name for display
    from modules.models import TankSystem
    system = TankSystem.query.get(system_id)
    system_name = system.name if system else f"System {system_id}"
    
    # Get tanks for display mapping
    tanks_by_id = {tank.id: tank for tank in get_current_system_tanks()}
    
    # Stats API URLs for the integrated cards
    stats_api_urls = {
        "GET": "/web/fn/schedule/get/stats",
        "DELETE": "/web/fn/ops/delete/d_schedule"
    }
    
    return render_template(
        "doser/schedule_new.html",
        title="Dosing Schedule Manager",
        system_id=system_id,
        system_name=system_name,
        tank_ids=tank_ids,
        tanks_by_id=tanks_by_id,
        products=products_list,
        dosers=dosers_list,
        existing_schedules=schedules_data,
        stats_api_urls=stats_api_urls
    )

@app.route("/doser/schedule/edit/<int:schedule_id>", methods=["GET", "POST"])
def schedule_edit(schedule_id):
    """Edit existing dosing schedule with the same granular controls as new schedule page"""
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected. Please select a system before editing dosing schedules.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    # Get the schedule to edit
    schedule = DSchedule.query.filter(
        DSchedule.id == schedule_id,
        DSchedule.tank_id.in_(tank_ids)
    ).first()
    if not schedule:
        flash("Schedule not found or access denied.", "error")
        return redirect(url_for('schedule_new'))
    
    if request.method == "POST":
        # Handle both JSON and form data for compatibility
        try:
            if request.is_json:
                data = request.get_json()
            else:
                # Fallback to form data
                data = request.form.to_dict()
                # Convert checkbox values to booleans
                if 'suspended' in data:
                    data['suspended'] = data['suspended'].lower() in ['true', '1', 'on']
                else:
                    # If checkbox not present in form data, it means unchecked
                    data['suspended'] = False
                
                # Ensure schedule_type is set for form submissions
                if 'schedule_type' not in data:
                    data['schedule_type'] = 'interval'  # Default for compatibility
        except Exception as e:
            return jsonify({"success": False, "error": f"Error parsing request data: {str(e)}"}), 400
        
        return handle_schedule_edit_submission(data, schedule_id, tank_ids[0])
    
    # GET request - show the form with pre-populated data
    # Fetch available products for the dropdown
    products = Products.query.all()
    products_list = [{"id": p.id, "name": p.name, "current_avail": p.current_avail} for p in products]
    
    # Fetch active dosers for the current system tanks
    dosers = Doser.query.filter(Doser.tank_id.in_(tank_ids), Doser.is_active == True).all()
    
    # Fetch existing schedules for the current system tanks (excluding current one)
    existing_schedules = DSchedule.query.filter(
        DSchedule.tank_id.in_(tank_ids), 
        DSchedule.id != schedule_id
    ).all()
    schedules_data = []
    for s in existing_schedules:
        schedules_data.append({
            "id": s.id,
            "product_name": s.product.name if s.product else "Unknown",
            "amount": s.amount,
            "trigger_interval": s.trigger_interval,
            "suspended": s.suspended,
            "last_refill": datetime_to_iso_format(s.last_refill) if s.last_refill else None
        })
    
    # Convert trigger_interval to enhanced form fields (interval_value and interval_unit)
    interval_value = 8  # Default
    interval_unit = 'hours'  # Default
    
    if schedule.trigger_interval:
        # Convert seconds to appropriate unit and value
        seconds = schedule.trigger_interval
        
        # Check for perfect day intervals first
        if seconds % 86400 == 0:
            interval_value = seconds // 86400
            interval_unit = 'days'
        # Check for perfect hour intervals
        elif seconds % 3600 == 0:
            interval_value = seconds // 3600
            interval_unit = 'hours'
        # Check for perfect minute intervals
        elif seconds % 60 == 0:
            interval_value = seconds // 60
            interval_unit = 'minutes'
        else:
            # Default to hours with decimal (round to nearest)
            interval_value = round(seconds / 3600)
            interval_unit = 'hours'
    
    # Convert schedule data for form pre-population
    schedule_data = {
        "id": schedule.id,
        "product_id": schedule.product_id,
        "product_name": schedule.product.name if schedule.product else "Unknown",
        "amount": schedule.amount,
        "trigger_interval": schedule.trigger_interval,
        "interval_value": interval_value,  # Enhanced field for form
        "interval_unit": interval_unit,    # Enhanced field for form
        "suspended": schedule.suspended,
        "last_refill": datetime_to_iso_format(schedule.last_refill) if schedule.last_refill else None,
        "start_time": format_time_for_html_input(schedule.trigger_time) if schedule.trigger_time else None,
        "offset_minutes": schedule.offset_minutes,
        "hour_offset": schedule.offset_minutes if schedule.offset_minutes is not None else 0,  # Convenience field for form
        "doser_id": schedule.doser_id,
        "doser_name": schedule.doser_name,
        "repeat_every_n_days": schedule.repeat_every_n_days,
        "days_of_week": schedule.days_of_week,
        "missed_dose_handling": schedule.missed_dose_handling.value if schedule.missed_dose_handling else 'alert_only',
        "missed_dose_grace_period_hours": schedule.missed_dose_grace_period_hours,
        "missed_dose_notification_enabled": schedule.missed_dose_notification_enabled
    }
    
    # Stats API URLs for the integrated cards
    stats_api_urls = {
        "GET": "/web/fn/schedule/get/stats",
        "DELETE": "/web/fn/ops/delete/d_schedule"
    }
    
    # Get tanks for display mapping
    tanks_by_id = {tank.id: tank for tank in get_current_system_tanks()}
    
    return render_template(
        "doser/schedule_edit.html",
        title="Edit Dosing Schedule",
        system_id=system_id,
        tank_ids=tank_ids,
        tanks_by_id=tanks_by_id,
        products=products_list,
        dosers=dosers,
        existing_schedules=schedules_data,
        schedule=schedule_data,
        stats_api_urls=stats_api_urls
    )

def handle_schedule_edit_submission(data, schedule_id, tank_id):
    """Handle the submission of schedule edit with enhanced validation"""
    try:
        # Enhanced debugging for the "Invalid schedule configuration" error
        print("DEBUG: handle_schedule_edit_submission called")
        print("  schedule_id:", schedule_id)
        print("  tank_id:", tank_id)
        print("  data:", data)
        print("  data keys:", list(data.keys()))
        print("  data types:", [(k, type(v)) for k, v in data.items()])
        
        # CRITICAL DEBUG: Check all form fields that should be present
        start_time_value = data.get('start_time')
        interval_value = data.get('interval_value')
        interval_unit = data.get('interval_unit')
        print("  CRITICAL ANALYSIS:")
        print("    start_time =", start_time_value, "(type:", type(start_time_value), ")")
        print("    interval_value =", interval_value, "(type:", type(interval_value), ")")
        print("    interval_unit =", interval_unit, "(type:", type(interval_unit), ")")
        print("  BUG ANALYSIS: _calculate_interval_schedule needs interval_value and interval_unit, but we got:")
        
        # Determine response format based on request type
        is_json_request = request.is_json or request.headers.get('Content-Type') == 'application/json'
        
        # Get the existing schedule
        schedule = DSchedule.query.filter_by(id=schedule_id, tank_id=tank_id).first()
        if not schedule:
            print("DEBUG: Schedule not found - id=", schedule_id, ", tank_id=", tank_id)
            if is_json_request:
                return jsonify({"success": False, "error": "Schedule not found"}), 404
            else:
                flash("Schedule not found", "error")
                return redirect(url_for('doser_main'))
        
        print("DEBUG: Found existing schedule:", schedule.id)
        
        # Basic validation
        validation_result = _validate_schedule_data(data)
        if not validation_result['valid']:
            print("DEBUG: Basic validation failed:", validation_result)
            if is_json_request:
                return jsonify({"success": False, "error": validation_result['error']}), 400
            else:
                flash(f"Validation error: {validation_result['error']}", "error")
                return redirect(url_for('schedule_edit', schedule_id=schedule_id))
        
        print("DEBUG: Basic validation passed")
        
        # CRITICAL FIX: If interval_value/interval_unit are missing for interval schedule,
        # reconstruct them from the existing schedule's trigger_interval BEFORE calculating
        schedule_type = data.get('schedule_type')
        print(f"DEBUG: CONDITION CHECK - schedule_type={schedule_type}, interval_value={data.get('interval_value')}")
        print(f"DEBUG: CONDITION PARTS - (schedule_type == 'interval')={schedule_type == 'interval'}, (not data.get('interval_value'))={not data.get('interval_value')}")
        
        if schedule_type == 'interval' and not data.get('interval_value'):
            print(f"DEBUG: CONDITION MET - entering reconstruction logic")
            existing_trigger_interval = schedule.trigger_interval
            print(f"DEBUG: existing_trigger_interval from schedule = {existing_trigger_interval}")
            
            if existing_trigger_interval:
                print(f"DEBUG: CRITICAL FIX APPLIED - reconstructing interval fields from existing trigger_interval={existing_trigger_interval}")
                
                # Convert seconds to appropriate unit and value (same logic as in GET route)
                seconds = existing_trigger_interval
                if seconds % 86400 == 0:
                    data['interval_value'] = str(seconds // 86400)
                    data['interval_unit'] = 'days'
                elif seconds % 3600 == 0:
                    data['interval_value'] = str(seconds // 3600)
                    data['interval_unit'] = 'hours'
                elif seconds % 60 == 0:
                    data['interval_value'] = str(seconds // 60)
                    data['interval_unit'] = 'minutes'
                else:
                    # Default to hours with decimal (round to nearest)
                    data['interval_value'] = str(round(seconds / 3600))
                    data['interval_unit'] = 'hours'
                
                print(f"DEBUG: RECONSTRUCTED interval_value={data['interval_value']}, interval_unit={data['interval_unit']}")
            else:
                print(f"DEBUG: RECONSTRUCTION FAILED - existing_trigger_interval is None or 0")
        else:
            print(f"DEBUG: CONDITION NOT MET - skipping reconstruction logic")
        
        # CRITICAL: Calculate trigger_interval AFTER fixing missing fields
        print(f"DEBUG: About to calculate trigger_interval with schedule_type={schedule_type}")
        trigger_interval = calculate_trigger_interval(data, schedule_type)
        print(f"DEBUG: calculate_trigger_interval returned: {trigger_interval}")
        
        if trigger_interval is None:
            print(f"DEBUG: CRITICAL ERROR - calculate_trigger_interval returned None!")
            print(f"  This is what causes 'Invalid schedule configuration' error")
            print(f"  schedule_type: {schedule_type}")
            print(f"  interval_value: {data.get('interval_value')} (type: {type(data.get('interval_value'))})")
            print(f"  interval_unit: {data.get('interval_unit')} (type: {type(data.get('interval_unit'))})")
            
            # Provide more specific error messages based on the actual problem
            interval_value = data.get('interval_value')
            interval_unit = data.get('interval_unit')
            
            error_message = ""
            if not interval_value:
                error_message = "Interval value is required"
            elif not interval_unit:
                error_message = "Interval unit (minutes/hours/days) is required"
            else:
                # Try to convert interval_value to check what's wrong
                try:
                    interval_val_int = int(interval_value)
                    if interval_val_int <= 0:
                        error_message = f"Interval value must be greater than 0, got {interval_val_int}"
                    elif interval_unit not in ['minutes', 'hours', 'days']:
                        error_message = f"Invalid interval unit '{interval_unit}'. Must be 'minutes', 'hours', or 'days'"
                    else:
                        error_message = f"Invalid interval configuration: {interval_val_int} {interval_unit}"
                except (ValueError, TypeError):
                    error_message = f"Interval value must be a number, got '{interval_value}'"
            
            if is_json_request:
                return jsonify({"success": False, "error": error_message}), 400
            else:
                flash(f"Configuration error: {error_message}", "error")
                return redirect(url_for('schedule_edit', schedule_id=schedule_id))
        
        # Add calculated trigger_interval to data for validation
        data['trigger_interval'] = trigger_interval
        
        # CRITICAL: Add schedule configuration validation to prevent conflicts
        from modules.schedule_validator import validate_and_fix_schedule
        
        # Extract schedule configuration for validation
        schedule_config = _clean_schedule_config_for_validation(data)
        
        # Validate and auto-fix conflicting configurations
        fixed_config, remaining_errors = validate_and_fix_schedule(schedule_config)
        
        if remaining_errors:
            error_message = f"Schedule configuration errors: {'; '.join(remaining_errors)}"
            if is_json_request:
                return jsonify({"success": False, "error": error_message}), 400
            else:
                flash(error_message, "error")
                return redirect(url_for('schedule_edit', schedule_id=schedule_id))
        
        # Use the fixed configuration
        data.update(fixed_config)
        
        # Extract and process data
        schedule_data = _process_schedule_data(data, tank_id)
        
        # CRITICAL DEBUG: Check what's in schedule_data
        print(f"DEBUG: schedule_data keys: {list(schedule_data.keys())}")
        print(f"DEBUG: schedule_data: {schedule_data}")
        print(f"DEBUG: offset_minutes in schedule_data: {'offset_minutes' in schedule_data}")
        if 'offset_minutes' in schedule_data:
            print(f"DEBUG: offset_minutes value: {schedule_data['offset_minutes']}")
        
        # Update existing schedule
        for key, value in schedule_data.items():
            if key != 'tank_id':  # Don't update tank_id
                print(f"DEBUG: Setting {key} = {value}")
                setattr(schedule, key, value)
        
        db.session.commit()
        
        # CRITICAL: Immediately refresh the enhanced scheduler queue to pick up changes
        try:
            from modules.enhanced_dosing_scheduler import refresh_scheduler_queue
            refresh_success = refresh_scheduler_queue()
            logger.info(f"Enhanced scheduler queue refresh after edit: {'successful' if refresh_success else 'failed'}")
        except Exception as refresh_error:
            logger.warning(f"Failed to refresh enhanced scheduler queue after edit: {refresh_error}")
        
        # Success response
        if is_json_request:
            return jsonify({
                "success": True, 
                "message": "Dosing schedule updated successfully",
                "schedule_id": schedule.id,
                "auto_fixed": len(fixed_config) > len(schedule_config)  # Indicate if auto-fixes were applied
            })
        else:
            # Traditional form submission - flash message and redirect
            flash("Dosing schedule updated successfully!", "success")
            return redirect(url_for('doser_main'))
        
    except Exception as e:
        db.session.rollback()
        error_message = str(e)
        if is_json_request:
            return jsonify({"success": False, "error": error_message}), 500
        else:
            flash(f"Error updating schedule: {error_message}", "error")
            return redirect(url_for('schedule_edit', schedule_id=schedule_id))

def handle_schedule_submission(data, tank_id):
    """Handle the submission of a new dosing schedule with enhanced validation"""
    try:
        # Basic validation
        validation_result = _validate_schedule_data(data)
        if not validation_result['valid']:
            return jsonify({"success": False, "error": validation_result['error']}), 400
        
        # CRITICAL: Calculate trigger_interval BEFORE validation
        schedule_type = data.get('schedule_type')
        trigger_interval = calculate_trigger_interval(data, schedule_type)
        if trigger_interval is None:
            # Provide more specific error messages based on the actual problem
            interval_value = data.get('interval_value')
            interval_unit = data.get('interval_unit')
            
            if not interval_value:
                return jsonify({"success": False, "error": "Interval value is required"}), 400
            elif not interval_unit:
                return jsonify({"success": False, "error": "Interval unit (minutes/hours/days) is required"}), 400
            else:
                # Try to convert interval_value to check what's wrong
                try:
                    interval_val_int = int(interval_value)
                    if interval_val_int <= 0:
                        return jsonify({"success": False, "error": f"Interval value must be greater than 0, got {interval_val_int}"}), 400
                    elif interval_unit not in ['minutes', 'hours', 'days']:
                        return jsonify({"success": False, "error": f"Invalid interval unit '{interval_unit}'. Must be 'minutes', 'hours', or 'days'"}), 400
                    else:
                        return jsonify({"success": False, "error": f"Invalid interval configuration: {interval_val_int} {interval_unit}"}), 400
                except (ValueError, TypeError):
                    return jsonify({"success": False, "error": f"Interval value must be a number, got '{interval_value}'"}), 400
        
        # Add calculated trigger_interval to data for validation
        data['trigger_interval'] = trigger_interval
        
        # CRITICAL: Add schedule configuration validation to prevent conflicts
        from modules.schedule_validator import validate_and_fix_schedule
        
        # Extract schedule configuration for validation
        schedule_config = _clean_schedule_config_for_validation(data)
        
        # Validate and auto-fix conflicting configurations
        fixed_config, remaining_errors = validate_and_fix_schedule(schedule_config)
        
        if remaining_errors:
            return jsonify({
                "success": False, 
                "error": f"Schedule configuration errors: {'; '.join(remaining_errors)}"
            }), 400
        
        # Use the fixed configuration
        data.update(fixed_config)
        
        # Extract and process data
        schedule_data = _process_schedule_data(data, tank_id)
        
        # Create new schedule
        new_schedule = DSchedule(**schedule_data)
        
        db.session.add(new_schedule)
        db.session.commit()
        
        # CRITICAL: Immediately refresh the enhanced scheduler queue to pick up new schedule
        try:
            from modules.enhanced_dosing_scheduler import refresh_scheduler_queue
            refresh_success = refresh_scheduler_queue()
            logger.info(f"Enhanced scheduler queue refresh after creation: {'successful' if refresh_success else 'failed'}")
        except Exception as refresh_error:
            logger.warning(f"Failed to refresh enhanced scheduler queue after creation: {refresh_error}")
        
        return jsonify({
            "success": True, 
            "message": "Dosing schedule created successfully",
            "schedule_id": new_schedule.id,
            "auto_fixed": len(fixed_config) > len(schedule_config)  # Indicate if auto-fixes were applied
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

def _validate_schedule_data(data):
    """Validate basic schedule data"""
    product_id = data.get('product_id')
    amount = data.get('amount', 0)
    
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return {'valid': False, 'error': 'Invalid amount value'}
    
    if not product_id or amount <= 0:
        return {'valid': False, 'error': 'Product and positive amount are required'}
    
    return {'valid': True}

def _process_schedule_data(data, tank_id):
    """Process and normalize schedule data"""
    # Basic fields with proper type conversion
    product_id = int(data.get('product_id')) if data.get('product_id') else None
    amount = float(data.get('amount', 0))
    schedule_type = data.get('schedule_type')
    suspended = data.get('suspended', False)
    
    # Calculate trigger_interval
    trigger_interval = calculate_trigger_interval(data, schedule_type)
    if trigger_interval is None:
        raise ValueError(f"Invalid interval configuration: {data.get('interval_value')} {data.get('interval_unit')}")
    
    # Process enhanced scheduling fields
    doser_data = _process_doser_data(data, trigger_interval)
    
    # Force missed dose handling to alert_only (simplified system)
    missed_dose_data = {
        'missed_dose_handling': MissedDoseHandlingEnum.alert_only,
        'missed_dose_grace_period_hours': None,
        'missed_dose_notification_enabled': True  # Keep notifications enabled
    }
    
    # Validate schedule type enum
    try:
        schedule_type_enum = ScheduleTypeEnum(schedule_type)
    except ValueError:
        schedule_type_enum = ScheduleTypeEnum.interval
    
    # Return combined data
    return {
        'trigger_interval': trigger_interval,
        'suspended': suspended,
        'amount': amount,
        'tank_id': tank_id,
        'product_id': product_id,
        'schedule_type': schedule_type_enum,
        **doser_data,
        **missed_dose_data
    }

def _process_doser_data(data, trigger_interval=None):
    """Process doser-related fields with enhanced hourly offset support"""
    print(f"DEBUG _process_doser_data: ENTRY POINT - VERSION WITH HOUR_OFFSET SUPPORT")
    print(f"DEBUG _process_doser_data: trigger_interval parameter = {trigger_interval}")
    
    # CRITICAL DEBUG: Log the start_time processing
    start_time_input = (data.get('start_time') or '').strip()
    print(f"DEBUG _process_doser_data: start_time input = '{start_time_input}'")
    
    doser_id = _validate_doser_id(data.get('doser_id'))
    doser_name = (data.get('doser_name') or '').strip()
    days_of_week = (data.get('days_of_week') or '').strip()
    repeat_every_n_days = _validate_repeat_days(data.get('repeat_every_n_days'))
    
    # Enhanced time handling - convert time to offset for hourly schedules
    trigger_time = _validate_start_time(start_time_input)
    offset_minutes = _validate_offset_minutes(data.get('offset_minutes'))
    
    # NEW: Handle hour_offset input field (frontend convenience field)
    try:
        hour_offset = data.get('hour_offset')
        print(f"DEBUG: hour_offset from form = {hour_offset} (type: {type(hour_offset)})")
        print(f"DEBUG: existing offset_minutes = {offset_minutes}")
        print(f"DEBUG: condition check: hour_offset is not None = {hour_offset is not None}, offset_minutes is None = {offset_minutes is None}")
        
        if hour_offset is not None and offset_minutes is None:
            try:
                offset_minutes = int(hour_offset)
                print(f"DEBUG: Converted hour_offset {hour_offset} to int: {offset_minutes}")
                if 0 <= offset_minutes <= 59:
                    print(f"DEBUG: Using hour_offset {hour_offset} as offset_minutes")
                else:
                    print(f"DEBUG: hour_offset {offset_minutes} out of range (0-59), setting to None")
                    offset_minutes = None
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error converting hour_offset {hour_offset}: {e}")
                pass
    except Exception as e:
        print(f"CRITICAL ERROR in hour_offset processing: {e}")
        import traceback
        traceback.print_exc()
    
    # NEW: Convert trigger_time to offset_minutes for hourly schedules
    schedule_type = data.get('schedule_type', 'interval')
    
    if schedule_type == 'interval' and trigger_interval and int(trigger_interval) == 3600:
        # This is an hourly schedule - convert trigger_time to offset_minutes
        if trigger_time and not offset_minutes:
            try:
                # Extract minute from trigger_time (e.g., "16:30:00" -> 30)
                if isinstance(trigger_time, str):
                    time_parts = trigger_time.split(':')
                    if len(time_parts) >= 2:
                        offset_minutes = int(time_parts[1])
                        print(f"DEBUG: Converted trigger_time {trigger_time} to offset_minutes {offset_minutes}")
                        # Clear trigger_time for hourly schedules
                        trigger_time = None
                elif hasattr(trigger_time, 'minute'):
                    offset_minutes = trigger_time.minute
                    print(f"DEBUG: Converted time object {trigger_time} to offset_minutes {offset_minutes}")
                    trigger_time = None
            except (ValueError, AttributeError) as e:
                print(f"WARNING: Could not convert trigger_time to offset_minutes: {e}")
    
    print(f"DEBUG _process_doser_data: processed trigger_time = {trigger_time}, offset_minutes = {offset_minutes}")
    
    return {
        'doser_name': doser_name if doser_name else None,
        'days_of_week': days_of_week if days_of_week else None,
        'repeat_every_n_days': repeat_every_n_days,
        'doser_id': doser_id,
        'trigger_time': trigger_time,
        'offset_minutes': offset_minutes
    }

def _validate_doser_id(doser_id):
    """Validate doser ID"""
    if doser_id:
        try:
            return int(doser_id)
        except (ValueError, TypeError):
            return None
    return None

def _validate_repeat_days(repeat_every_n_days):
    """Validate repeat every n days"""
    if repeat_every_n_days:
        try:
            repeat_every_n_days = int(repeat_every_n_days)
            if 1 <= repeat_every_n_days <= 365:
                return repeat_every_n_days
        except (ValueError, TypeError):
            pass
    return None

def _validate_start_time(start_time):
    """Validate and convert start_time"""
    if start_time:
        try:
            # Parse time string (format: HH:MM)
            hour, minute = map(int, start_time.split(':'))
            return time(hour, minute)
        except (ValueError, TypeError):
            pass
    return None

def _validate_offset_minutes(offset_minutes):
    """Validate offset_minutes"""
    if offset_minutes is not None:
        try:
            offset_minutes = int(offset_minutes)
            if -1440 <= offset_minutes <= 1440:
                return offset_minutes
        except (ValueError, TypeError):
            pass
    return None

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
    """Calculate interval for direct interval input with enhanced fallback support"""
    interval_value = data.get('interval_value', 0)
    interval_unit = data.get('interval_unit', 'minutes')
    
    # NEW: Handle missing interval fields in edit forms
    if not interval_value or interval_value == 0:
        # Try to reconstruct from existing trigger_interval (edit mode)
        existing_trigger_interval = data.get('trigger_interval')
        if existing_trigger_interval:
            try:
                seconds = int(existing_trigger_interval)
                # Convert back to interval_value and interval_unit
                if seconds % 3600 == 0:  # Hours
                    interval_value = seconds // 3600
                    interval_unit = 'hours'
                elif seconds % 60 == 0:  # Minutes  
                    interval_value = seconds // 60
                    interval_unit = 'minutes'
                else:  # Days
                    interval_value = seconds // 86400
                    interval_unit = 'days'
                print(f"DEBUG: Reconstructed interval_value={interval_value}, interval_unit={interval_unit}")
            except (ValueError, TypeError) as e:
                print(f"WARNING: Could not reconstruct interval from trigger_interval: {e}")
                return None
    
    try:
        interval_value_int = int(interval_value)
    except (ValueError, TypeError):
        return None
    
    if interval_value_int <= 0:
        return None
    
    # Validate interval_unit before using it
    valid_units = ['minutes', 'hours', 'days']
    if interval_unit not in valid_units:
        return None
        
    unit_multipliers = {
        'minutes': 60,
        'hours': 3600, 
        'days': 86400
    }
    
    multiplier = unit_multipliers[interval_unit]  # Now safe to use direct access
    result = interval_value_int * multiplier
    return result

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
    # Handle day-based custom schedule (repeat_every_n_days + custom_time)
    repeat_every_n_days = data.get('repeat_every_n_days')
    custom_time = data.get('custom_time')
    
    if repeat_every_n_days and custom_time:
        # Convert days to seconds for trigger_interval
        days = int(repeat_every_n_days)
        if days < 1 or days > 365:
            return None
        return days * 24 * 3600  # Convert days to seconds
    
    # Handle exact second intervals (legacy/advanced mode)
    custom_seconds = data.get('custom_seconds')
    if custom_seconds:
        seconds = int(custom_seconds)
        if seconds < 60:  # Minimum 1 minute
            return None
        return seconds
    
    # No valid custom schedule configuration provided
    return None


def _clean_schedule_config_for_validation(data):
    """Clean schedule configuration data to remove inappropriate fields for validation"""
    schedule_type = data.get('schedule_type', 'interval')
    
    # Base configuration
    schedule_config = {
        'schedule_type': schedule_type,
        'trigger_interval': data.get('trigger_interval'),
        'trigger_time': data.get('custom_time') or data.get('daily_time'),  # Handle both field names
        'days_of_week': data.get('days_of_week')
    }
    
    # Only include repeat_every_n_days for custom schedules
    if schedule_type == 'custom':
        schedule_config['repeat_every_n_days'] = data.get('repeat_every_n_days')
    
    return schedule_config


@app.route("/doser/submit", methods=["POST"])
def doser_submit():
    system_id = ensure_system_context()
    if not system_id:
        return jsonify({"success": False, "error": "No system selected"}), 400
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        return jsonify({"success": False, "error": "No tanks in selected system"}), 400
    
    # Use the first tank for backward compatibility
    tank_id = tank_ids[0]
    
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
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    # API URLs for the history dashboard
    api_urls = {
        "history": "/web/fn/schedule/get/history",
        "stats": "/web/fn/schedule/get/stats",
        "delete": "/web/fn/ops/delete/dosing"
    }
    
    return render_template("doser/history.html", 
                         system_id=system_id, tank_ids=tank_ids, api_urls=api_urls)


@app.route("/doser/audit")
def doser_audit():
    """Audit log dashboard for dose tracking and activity monitoring"""
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    # API URLs for the audit dashboard
    api_urls = {
        "dose_events": "/api/v1/audit/dose-events",
        "dose_events_recent": "/api/v1/audit/dose-events/recent",
        "schedule_changes": "/api/v1/audit/schedule-changes",
        "stats": "/web/fn/schedule/get/stats",
        "calendar_monthly": "/api/v1/audit-calendar/calendar/monthly-summary",
        "calendar_day_details": "/api/v1/audit-calendar/calendar/day-details"
    }
    
    return render_template("doser/audit_log.html", 
                         system_id=system_id, tank_ids=tank_ids, api_urls=api_urls)


@app.route("/doser/audit/calendar")
def doser_audit_calendar():
    """Calendar-based audit log interface for visual dose tracking"""
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    # API URLs for the calendar audit dashboard
    api_urls = {
        "calendar_monthly": "/api/v1/audit-calendar/calendar/monthly-summary",
        "calendar_day_details": "/api/v1/audit-calendar/calendar/day-details",
        "calendar_date_range": "/api/v1/audit-calendar/calendar/date-range-summary",
        "dose_events": "/api/v1/audit/dose-events",
        "stats": "/web/fn/schedule/get/stats"
    }
    
    return render_template("doser/audit_calendar.html", 
                         system_id=system_id, tank_ids=tank_ids, api_urls=api_urls)


# Removed separate calendar day route - functionality moved to modal in audit_calendar.html
# Use the enhanced modal in /doser/audit/calendar instead


def _calculate_next_dose_time(schedule) -> Optional[datetime]:
    """
    Calculate next dose time using enhanced scheduler logic
    
    This matches the logic in the enhanced dosing scheduler for consistent timing
    """
    from modules.models import ScheduleTypeEnum
    
    # Use current time for calculations
    current_time = datetime.now()
    
    # Handle different schedule types with precision
    if schedule.schedule_type == ScheduleTypeEnum.interval:
        # Convert interval-based to precise timing
        if schedule.trigger_interval:
            interval_hours = schedule.trigger_interval / 3600
            
            if interval_hours <= 24:  # Hourly/daily schedules
                # Use offset_minutes for hourly schedules
                if schedule.offset_minutes is not None:
                    target_minute = schedule.offset_minutes
                    
                    if interval_hours <= 1:
                        # Every hour at :offset_minutes (e.g., :30 for 16:30, 17:30, etc.)
                        next_hour = current_time.replace(minute=target_minute, second=0, microsecond=0)
                        if next_hour <= current_time:
                            next_hour += timedelta(hours=1)
                        return next_hour
                    
                    elif interval_hours <= 24:
                        # Multiple hours - find the correct base time with offset
                        hours_interval = int(interval_hours)
                        
                        # Find the most recent occurrence at :offset_minutes
                        base_time = current_time.replace(minute=target_minute, second=0, microsecond=0)
                        
                        # If current base time hasn't occurred yet, use it
                        if base_time > current_time:
                            return base_time
                        
                        # Otherwise, add the interval to get the next occurrence
                        next_time = base_time + timedelta(hours=hours_interval)
                        return next_time
                
                # FALLBACK: Legacy behavior for schedules without offset_minutes
                else:
                    # For hourly schedules, default to :00 minutes (top of hour)
                    if interval_hours <= 1:
                        next_hour = current_time.replace(minute=0, second=0, microsecond=0)
                        if next_hour <= current_time:
                            next_hour += timedelta(hours=1)
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
                last_dose = schedule.last_scheduled_time
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


@app.route("/doser/schedule/view")
def schedule_view():
    """Simple schedule overview page showing all schedules (active and suspended)"""
    system_id = ensure_system_context()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        flash("No tanks in selected system.", "warning")
        return redirect(url_for('index'))
    
    # Get all schedules for tanks in the current system (both active and suspended)
    schedules = db.session.query(DSchedule).filter(
        DSchedule.tank_id.in_(tank_ids)
    ).join(Products).all()
    
    # Get tanks for display mapping
    tanks_by_id = {tank.id: tank for tank in get_current_system_tanks()}
    
    schedules_data = []
    for schedule in schedules:
        # Calculate interval display string
        if schedule.trigger_interval:
            interval_str = f"Every {schedule.trigger_interval // 3600}h {(schedule.trigger_interval % 3600) // 60}m"
            if schedule.trigger_interval < 3600:
                interval_str = f"Every {schedule.trigger_interval}s"
        else:
            interval_str = "Unknown"
        
        # Calculate next dose time for non-suspended schedules
        next_dose_time = None
        next_dose_display = None
        if not schedule.suspended:
            try:
                next_dose_time = _calculate_next_dose_time(schedule)
                if next_dose_time:
                    # Format as relative time (e.g., "in 2h 30m", "in 45m", "Due now")
                    current_time = datetime.now()
                    time_diff = next_dose_time - current_time
                    
                    if time_diff.total_seconds() <= 0:
                        next_dose_display = "Due now"
                    else:
                        total_minutes = int(time_diff.total_seconds() / 60)
                        hours = total_minutes // 60
                        minutes = total_minutes % 60
                        
                        if hours > 0:
                            if minutes > 0:
                                next_dose_display = f"in {hours}h {minutes}m"
                            else:
                                next_dose_display = f"in {hours}h"
                        else:
                            next_dose_display = f"in {minutes}m"
            except Exception as e:
                logger.warning(f"Error calculating next dose time for schedule {schedule.id}: {e}")
                next_dose_display = "Error"
            
        schedules_data.append({
            "id": schedule.id,
            "tank_id": schedule.tank_id,
            "tank_name": tanks_by_id.get(schedule.tank_id, {}).name if schedule.tank_id in tanks_by_id else "Unknown Tank",
            "product_name": schedule.product.name if schedule.product else "Unknown",
            "amount": schedule.amount,
            "schedule_type": schedule.schedule_type,
            "trigger_interval": schedule.trigger_interval,
            "interval_display": interval_str,
            "trigger_time": format_time_for_display(schedule.trigger_time) if schedule.trigger_time else None,
            "doser_name": schedule.doser.doser_name if schedule.doser else "Default",
            "last_scheduled": datetime_to_iso_format(schedule.last_scheduled_time) if schedule.last_scheduled_time else None,
            "next_dose_time": next_dose_time.isoformat() if next_dose_time else None,
            "next_dose_display": next_dose_display,
            "suspended": schedule.suspended
        })
    
    return render_template("doser/schedule_view.html", 
                         schedules=schedules_data,
                         system_id=system_id,
                         tank_ids=tank_ids,
                         tanks_by_id=tanks_by_id)


