from flask import render_template, request, flash, redirect, url_for
from modules.models import Tank
from modules.tank_context import ensure_tank_context, set_tank_id
from sqlalchemy.exc import IntegrityError
from app import app, db

# Tank management routes - handle tank CRUD operations and dashboard display

@app.route("/tanks/manage")
def tank_manage():
    """Tank management dashboard."""
    try:
        tanks = Tank.query.all()
        current_tank_id = ensure_tank_context()

        # Aggregate stats for each tank
        tank_stats = []
        from modules.models import Coral, DSchedule, MissedDoseRequest
        for tank in tanks:
            # Water volumes
            gross_vol = tank.gross_water_vol
            net_vol = tank.net_water_vol

            # Overall health: summarize coral health_status
            corals = tank.corals
            health_counts = {}
            for coral in corals:
                status = coral.health_status or "Unknown"
                health_counts[status] = health_counts.get(status, 0) + 1
            if health_counts:
                # Most common health status
                overall_health = max(health_counts, key=health_counts.get)
            else:
                overall_health = "No corals"

            # Dosing status: count active, suspended, missed doses
            schedules = tank.schedules
            dosing_total = len(schedules)
            dosing_suspended = sum(1 for s in schedules if s.suspended)
            dosing_active = dosing_total - dosing_suspended
            # Missed doses
            missed_dose_count = 0
            for sched in schedules:
                missed_dose_count += MissedDoseRequest.query.filter_by(schedule_id=sched.id, status='pending').count()

            tank_stats.append({
                'tank': tank,
                'gross_water_vol': gross_vol,
                'net_water_vol': net_vol,
                'overall_health': overall_health,
                'coral_health_counts': health_counts,
                'dosing_total': dosing_total,
                'dosing_active': dosing_active,
                'dosing_suspended': dosing_suspended,
                'dosing_missed': missed_dose_count
            })

        return render_template('tanks/manage.html', 
                             tank_stats=tank_stats, 
                             current_tank_id=current_tank_id)
    except Exception as e:
        flash(f"Error loading tanks: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route("/tanks/new", methods=['GET', 'POST'])
def tank_new():
    """Create a new tank."""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            gross_water_vol = request.form.get('gross_water_vol', 0, type=int)
            net_water_vol = request.form.get('net_water_vol', 0, type=int)
            live_rock_lbs = request.form.get('live_rock_lbs', 0, type=float)
            
            # Validate required fields
            if not name:
                flash("Tank name is required.", "error")
                return render_template('tanks/new.html')
            
            # Create new tank
            tank = Tank(
                name=name,
                gross_water_vol=gross_water_vol,
                net_water_vol=net_water_vol,
                live_rock_lbs=live_rock_lbs
            )
            
            db.session.add(tank)
            db.session.commit()
            
            flash(f'Tank "{name}" created successfully!', "success")
            
            # If this is the first tank or no tank is currently selected, set it as current
            current_tank_id = ensure_tank_context()
            if not current_tank_id:
                set_tank_id(tank.id)
                flash(f'Tank "{name}" has been set as your current tank.', "info")
            
            return redirect(url_for('tank_manage'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Tank name already exists. Please choose a different name.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating tank: {str(e)}", "error")
    
    return render_template('tanks/new.html')

@app.route("/tanks/edit/<int:tank_id>", methods=['GET', 'POST'])
def tank_edit(tank_id):
    """Edit an existing tank."""
    try:
        tank = Tank.query.get_or_404(tank_id)
    except Exception as e:
        flash(f"Tank not found: {str(e)}", "error")
        return redirect(url_for('tank_manage'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            gross_water_vol = request.form.get('gross_water_vol', 0, type=int)
            net_water_vol = request.form.get('net_water_vol', 0, type=int)
            live_rock_lbs = request.form.get('live_rock_lbs', 0, type=float)
            
            # Validate required fields
            if not name:
                flash("Tank name is required.", "error")
                return render_template('tanks/edit.html', tank=tank)
            
            # Update tank
            tank.name = name
            tank.gross_water_vol = gross_water_vol
            tank.net_water_vol = net_water_vol
            tank.live_rock_lbs = live_rock_lbs
            
            db.session.commit()
            
            flash(f'Tank "{name}" updated successfully!', "success")
            return redirect(url_for('tank_manage'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Tank name already exists. Please choose a different name.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating tank: {str(e)}", "error")
    
    return render_template('tanks/edit.html', tank=tank)

@app.route("/tanks/delete/<int:tank_id>", methods=['POST'])
def tank_delete(tank_id):
    """Delete a tank."""
    try:
        tank = Tank.query.get_or_404(tank_id)
        
        # Check if this is the current tank
        current_tank_id = ensure_tank_context()
        if current_tank_id == tank_id:
            flash("Cannot delete the currently selected tank. Please select a different tank first.", "error")
            return redirect(url_for('tank_manage'))
        
        tank_name = tank.name
        db.session.delete(tank)
        db.session.commit()
        
        flash(f'Tank "{tank_name}" deleted successfully!', "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting tank: {str(e)}", "error")
    
    return redirect(url_for('tank_manage'))