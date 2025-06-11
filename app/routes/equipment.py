from flask import render_template, request, flash, redirect, url_for, jsonify
from modules.models import Tank, Equipment, EquipmentTypeEnum, TankSystem
from modules.system_context import get_current_system_id, get_current_system_tank_ids, get_current_system_tanks
from sqlalchemy.exc import IntegrityError
from flask import render_template, request, redirect, url_for, flash
from app import app, db

# Equipment management routes - handle equipment CRUD operations for tanks in current system

@app.route("/equipment")
def equipment_manage():
    """Equipment management for tanks in current system."""
    system_id = get_current_system_id()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        # Get system info
        tank_system = TankSystem.query.get_or_404(system_id)
        tanks = get_current_system_tanks()
        
        # Get all equipment for tanks in system
        tank_ids = [tank.id for tank in tanks]
        equipment = Equipment.query.filter(Equipment.tank_id.in_(tank_ids)).order_by(Equipment.equipment_name).all()
        
        # Calculate total power consumption across all tanks
        active_equipment = [eq for eq in equipment if eq.is_active and eq.power_watts]
        total_watts = sum(eq.power_watts for eq in active_equipment)
        
        # Calculate total monthly kWh for all tanks
        total_monthly_kwh = sum(tank.calculate_monthly_kwh() for tank in tanks)
        
        return render_template('equipment/manage.html', 
                             tanks=tanks,
                             equipment=equipment,
                             total_watts=total_watts,
                             total_monthly_kwh=total_monthly_kwh,
                             equipment_types=list(EquipmentTypeEnum),
                             system_name=tank_system.name,
                             system_id=system_id)
    except Exception as e:
        flash(f"Error loading equipment: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route("/equipment/new", methods=['GET', 'POST'])
def equipment_new():
    """Create new equipment for a tank in the current system."""
    system_id = get_current_system_id()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        tanks = get_current_system_tanks()
    except Exception as e:
        flash(f"System not found: {str(e)}", "error")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            equipment_name = (request.form.get('equipment_name') or '').strip()
            equipment_type = request.form.get('equipment_type')
            tank_id = request.form.get('tank_id', type=int)
            power_watts = request.form.get('power_watts', type=int)
            brand = (request.form.get('brand') or '').strip() or None
            model = (request.form.get('model') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            is_active = request.form.get('is_active') == 'on'
            
            # Validate required fields
            if not equipment_name:
                flash("Equipment name is required.", "error")
                return render_template('equipment/new.html', 
                                     tanks=tanks, 
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            if not equipment_type:
                flash("Equipment type is required.", "error")
                return render_template('equipment/new.html', 
                                     tanks=tanks, 
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            if not tank_id:
                flash("Tank selection is required.", "error")
                return render_template('equipment/new.html', 
                                     tanks=tanks, 
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            # Verify tank is in current system
            tank_ids = [tank.id for tank in tanks]
            if tank_id not in tank_ids:
                flash("Selected tank is not in current system.", "error")
                return render_template('equipment/new.html', 
                                     tanks=tanks, 
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            # Create new equipment
            equipment = Equipment(
                equipment_name=equipment_name,
                equipment_type=equipment_type,
                tank_id=tank_id,
                power_watts=power_watts,
                brand=brand,
                model=model,
                notes=notes,
                is_active=is_active
            )
            
            db.session.add(equipment)
            db.session.commit()
            
            flash(f"Equipment '{equipment_name}' added successfully!", "success")
            return redirect(url_for('equipment_manage'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Equipment name already exists for this tank.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating equipment: {str(e)}", "error")
    
    return render_template('equipment/new.html', 
                         tanks=tanks, 
                         equipment_types=list(EquipmentTypeEnum),
                         system_name=tank_system.name,
                         system_id=system_id)

@app.route("/equipment/edit/<int:equipment_id>", methods=['GET', 'POST'])
def equipment_edit(equipment_id):
    """Edit existing equipment."""
    system_id = get_current_system_id()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        tanks = get_current_system_tanks()
        tank_ids = [tank.id for tank in tanks]
        
        # Get equipment and verify it belongs to a tank in current system
        equipment = Equipment.query.filter_by(id=equipment_id).first_or_404()
        if equipment.tank_id not in tank_ids:
            flash("Equipment not found in current system.", "error")
            return redirect(url_for('equipment_manage'))
            
    except Exception as e:
        flash(f"Equipment not found: {str(e)}", "error")
        return redirect(url_for('equipment_manage'))
    
    if request.method == 'POST':
        try:
            equipment_name = (request.form.get('equipment_name') or '').strip()
            equipment_type = request.form.get('equipment_type')
            tank_id = request.form.get('tank_id', type=int)
            power_watts = request.form.get('power_watts', type=int)
            brand = (request.form.get('brand') or '').strip() or None
            model = (request.form.get('model') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            is_active = request.form.get('is_active') == 'on'
            
            # Validate required fields
            if not equipment_name:
                flash("Equipment name is required.", "error")
                return render_template('equipment/edit.html', 
                                     tanks=tanks, 
                                     equipment=equipment,
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            if not equipment_type:
                flash("Equipment type is required.", "error")
                return render_template('equipment/edit.html', 
                                     tanks=tanks, 
                                     equipment=equipment,
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            if not tank_id:
                flash("Tank selection is required.", "error")
                return render_template('equipment/edit.html', 
                                     tanks=tanks, 
                                     equipment=equipment,
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            # Verify new tank is in current system
            if tank_id not in tank_ids:
                flash("Selected tank is not in current system.", "error")
                return render_template('equipment/edit.html', 
                                     tanks=tanks, 
                                     equipment=equipment,
                                     equipment_types=list(EquipmentTypeEnum),
                                     system_name=tank_system.name,
                                     system_id=system_id)
            
            # Update equipment
            equipment.equipment_name = equipment_name
            equipment.equipment_type = equipment_type
            equipment.tank_id = tank_id
            equipment.power_watts = power_watts
            equipment.brand = brand
            equipment.model = model
            equipment.notes = notes
            equipment.is_active = is_active
            
            db.session.commit()
            
            flash(f"Equipment '{equipment_name}' updated successfully!", "success")
            return redirect(url_for('equipment_manage'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Equipment name already exists for this tank.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating equipment: {str(e)}", "error")
    
    return render_template('equipment/edit.html', 
                         tanks=tanks, 
                         equipment=equipment,
                         equipment_types=list(EquipmentTypeEnum),
                         system_name=tank_system.name,
                         system_id=system_id)
@app.route("/equipment/delete/<int:equipment_id>", methods=['POST'])
def equipment_delete(equipment_id):
    """Delete equipment."""
    system_id = get_current_system_id()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    try:
        tanks = get_current_system_tanks()
        tank_ids = [tank.id for tank in tanks]
        
        # Get equipment and verify it belongs to a tank in current system
        equipment = Equipment.query.filter_by(id=equipment_id).first_or_404()
        if equipment.tank_id not in tank_ids:
            flash("Equipment not found in current system.", "error")
            return redirect(url_for('equipment_manage'))
        
        equipment_name = equipment.equipment_name
        db.session.delete(equipment)
        db.session.commit()
        
        flash(f'Equipment "{equipment_name}" deleted successfully!', "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting equipment: {str(e)}", "error")
    
    return redirect(url_for('equipment_manage'))

@app.route("/equipment/toggle/<int:equipment_id>", methods=['POST'])
def equipment_toggle(equipment_id):
    """Toggle equipment active status."""
    system_id = get_current_system_id()
    if not system_id:
        return jsonify({"success": False, "error": "No system selected"}), 400
    
    try:
        tanks = get_current_system_tanks()
        tank_ids = [tank.id for tank in tanks]
        
        # Get equipment and verify it belongs to a tank in current system
        equipment = Equipment.query.filter_by(id=equipment_id).first_or_404()
        if equipment.tank_id not in tank_ids:
            return jsonify({"success": False, "error": "Equipment not found in current system"}), 404
        
        equipment.is_active = not equipment.is_active
        db.session.commit()
        
        status = "activated" if equipment.is_active else "deactivated"
        
        return jsonify({"success": True, "is_active": equipment.is_active, "message": f'Equipment "{equipment.equipment_name}" {status} successfully!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
