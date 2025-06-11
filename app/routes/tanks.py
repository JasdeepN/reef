from flask import render_template, request, flash, redirect, url_for, jsonify
from modules.models import Tank
from modules.system_context import ensure_system_context, set_system_id, get_current_system_id, get_current_system_tank_ids
from sqlalchemy.exc import IntegrityError
from app import app, db

# Template constants
TANK_NEW_TEMPLATE = 'tanks/new.html'
TANK_EDIT_TEMPLATE = 'tanks/edit.html'
TANK_SYSTEMS_TEMPLATE = 'tanks/systems.html'
TANK_SYSTEM_NEW_TEMPLATE = 'tanks/system_new.html'
TANK_SYSTEM_EDIT_TEMPLATE = 'tanks/system_edit.html'

# Safely try to import tank system models
TankSystemModel = None
try:
    from modules.models import TankSystems
    TankSystemModel = TankSystems
    print("INFO: Using TankSystems model")
except ImportError:
    try:
        from modules.models import TankSystem
        TankSystemModel = TankSystem
        print("INFO: Using TankSystem model")
    except ImportError:
        print("WARNING: No TankSystem model found, tank system features may not work")

# ==============================================================================
# HELPER FUNCTIONS - Tank Data Validation and Processing
# ==============================================================================
def _validate_tank_data(name, gross_water_vol, net_water_vol):
    """Validate tank form data and return error messages if any."""
    errors = []
    
    if not name or not name.strip():
        errors.append("Tank name is required.")
    
    if gross_water_vol < 0:
        errors.append("Gross water volume cannot be negative.")
    
    if net_water_vol < 0:
        errors.append("Net water volume cannot be negative.")
    
    return errors

def _create_tank_system_for_tank(tank_name):
    """Create a new tank system for a tank if none selected."""
    if not TankSystemModel:
        return None
    
    # Generate a unique system name
    system_name = f"{tank_name} System"
    existing_names = [s.name for s in TankSystemModel.query.all()]
    counter = 1
    original_name = system_name
    
    while system_name in existing_names:
        system_name = f"{original_name} {counter}"
        counter += 1
    
    # Create the new system
    new_system = TankSystemModel(
        name=system_name,
        description=f"System created for tank '{tank_name}'"
    )
    db.session.add(new_system)
    db.session.flush()  # Get ID without committing
    
    print(f"[tank_system] Created new system '{system_name}' (ID: {new_system.id}) for tank '{tank_name}'")
    flash(f'Created new system "{system_name}" for this tank.', "info")
    
    return new_system.id

def _set_system_context_if_needed(tank):
    """Set system context if no current system is selected."""
    current_system_id = ensure_system_context()
    if not current_system_id and tank.tank_system_id:
        set_system_id(tank.tank_system_id)
        flash(f'Tank "{tank.name}" has been created and its system has been set as current.', "info")

def _handle_tank_form_error(error_msg, template, **template_kwargs):
    """Handle tank form errors consistently."""
    flash(error_msg, "error")
    try:
        tank_systems = TankSystemModel.query.all() if TankSystemModel else []
        template_kwargs['tank_systems'] = tank_systems
        return render_template(template, **template_kwargs)
    except Exception as e:
        flash(f"Error loading tank systems: {str(e)}", "error")
        return redirect(url_for('tank_system_list'))

# ==============================================================================
# MAIN TANK MANAGEMENT ROUTES
# ==============================================================================

@app.route("/tanks/manage")
def tank_manage():
    """Tank management dashboard - redirect to tank systems page."""
    return redirect(url_for('tank_system_list'))

@app.route("/tanks/new", methods=['GET', 'POST'])
def tank_new():
    """Create a new tank with comprehensive configuration options."""
    if request.method == 'POST':
        return _handle_tank_creation()
    
    # GET request - load form with tank systems
    return _load_tank_form(TANK_NEW_TEMPLATE)

def _handle_tank_creation():
    """Handle tank creation form submission."""
    try:
        # Extract form data
        tank_data = _extract_tank_form_data()
        
        # Validate the data
        validation_errors = _validate_tank_data(
            tank_data['name'], 
            tank_data['gross_water_vol'], 
            tank_data['net_water_vol']
        )
        
        if validation_errors:
            for error in validation_errors:
                flash(error, "error")
            return _load_tank_form(TANK_NEW_TEMPLATE)
        
        # Handle tank system assignment
        tank_system_id = tank_data.get('tank_system_id')
        if not tank_system_id:
            tank_system_id = _create_tank_system_for_tank(tank_data['name'])
        
        # Create the tank
        tank = _create_tank_instance(tank_data, tank_system_id)
        db.session.add(tank)
        db.session.commit()
        
        flash(f'Tank "{tank.name}" created successfully!', "success")
        _set_system_context_if_needed(tank)
        
        return redirect(url_for('tank_system_list'))
        
    except IntegrityError:
        db.session.rollback()
        return _handle_tank_form_error("Tank name already exists. Please choose a different name.", TANK_NEW_TEMPLATE)
    except ValueError as e:
        db.session.rollback()
        return _handle_tank_form_error(f"Invalid input: {str(e)}", TANK_NEW_TEMPLATE)
    except Exception as e:
        db.session.rollback()
        return _handle_tank_form_error(f"Error creating tank: {str(e)}", TANK_NEW_TEMPLATE)

def _extract_tank_form_data():
    """Extract and clean tank form data."""
    return {
        'name': (request.form.get('name') or '').strip(),
        'gross_water_vol': request.form.get('gross_water_vol', 0, type=int),
        'net_water_vol': request.form.get('net_water_vol', 0, type=int),
        'live_rock_lbs': request.form.get('live_rock_lbs', 0, type=float),
        'tank_length_inches': request.form.get('tank_length_inches', type=float),
        'tank_width_inches': request.form.get('tank_width_inches', type=float),
        'tank_height_inches': request.form.get('tank_height_inches', type=float),
        'description': (request.form.get('description') or '').strip() or None,
        'tank_system_id': request.form.get('tank_system_id', type=int) or None
    }

def _create_tank_instance(tank_data, tank_system_id):
    """Create a Tank instance from form data."""
    return Tank(
        name=tank_data['name'],
        gross_water_vol=tank_data['gross_water_vol'],
        net_water_vol=tank_data['net_water_vol'],
        live_rock_lbs=tank_data['live_rock_lbs'],
        tank_length_inches=tank_data['tank_length_inches'],
        tank_width_inches=tank_data['tank_width_inches'],
        tank_height_inches=tank_data['tank_height_inches'],
        description=tank_data['description'],
        tank_system_id=tank_system_id
    )

def _load_tank_form(template, **kwargs):
    """Load tank form with tank systems data."""
    try:
        tank_systems = TankSystemModel.query.all() if TankSystemModel else []
        return render_template(template, tank_systems=tank_systems, **kwargs)
    except Exception as e:
        flash(f"Error loading tank systems: {str(e)}", "error")
        return redirect(url_for('tank_system_list'))

@app.route("/tanks/edit/<int:tank_id>", methods=['GET', 'POST'])
def tank_edit(tank_id):
    """Edit an existing tank with full validation."""
    tank = _get_tank_or_404(tank_id)
    if not tank:
        return redirect(url_for('tank_system_list'))
    
    if request.method == 'POST':
        return _handle_tank_update(tank)
    
    # GET request - load form with tank systems
    return _load_tank_form(TANK_EDIT_TEMPLATE, tank=tank)

def _get_tank_or_404(tank_id):
    """Get tank by ID or flash error and return None."""
    try:
        return Tank.query.get_or_404(tank_id)
    except Exception as e:
        flash(f"Tank not found: {str(e)}", "error")
        return None

def _handle_tank_update(tank):
    """Handle tank update form submission."""
    try:
        # Extract and validate form data
        tank_data = _extract_tank_form_data()
        validation_errors = _validate_tank_data(
            tank_data['name'],
            tank_data['gross_water_vol'],
            tank_data['net_water_vol']
        )
        
        if validation_errors:
            for error in validation_errors:
                flash(error, "error")
            return _load_tank_form(TANK_EDIT_TEMPLATE, tank=tank)
        
        # Update tank properties
        _update_tank_properties(tank, tank_data)
        db.session.commit()
        
        flash(f'Tank "{tank.name}" updated successfully!', "success")
        return redirect(url_for('tank_system_list'))
        
    except IntegrityError:
        db.session.rollback()
        return _handle_tank_form_error("Tank name already exists. Please choose a different name.", TANK_EDIT_TEMPLATE, tank=tank)
    except ValueError as e:
        db.session.rollback()
        return _handle_tank_form_error(f"Invalid input: {str(e)}", TANK_EDIT_TEMPLATE, tank=tank)
    except Exception as e:
        db.session.rollback()
        return _handle_tank_form_error(f"Error updating tank: {str(e)}", TANK_EDIT_TEMPLATE, tank=tank)

def _update_tank_properties(tank, tank_data):
    """Update tank object with form data."""
    tank.name = tank_data['name']
    tank.gross_water_vol = tank_data['gross_water_vol']
    tank.net_water_vol = tank_data['net_water_vol']
    tank.live_rock_lbs = tank_data['live_rock_lbs']
    tank.tank_length_inches = tank_data['tank_length_inches']
    tank.tank_width_inches = tank_data['tank_width_inches']
    tank.tank_height_inches = tank_data['tank_height_inches']
    tank.description = tank_data['description']
    tank.tank_system_id = tank_data['tank_system_id']

@app.route("/tanks/delete/<int:tank_id>", methods=['POST'])
def tank_delete(tank_id):
    """Delete a tank with proper validation and cleanup."""
    try:
        tank = Tank.query.get_or_404(tank_id)
        
        # Perform pre-deletion checks
        if not _can_delete_tank(tank):
            return redirect(url_for('tank_system_list'))
        
        # Delete the tank
        tank_name = tank.name
        db.session.delete(tank)
        db.session.commit()
        
        flash(f'Tank "{tank_name}" deleted successfully!', "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting tank: {str(e)}", "error")
    
    return redirect(url_for('tank_system_list'))

def _can_delete_tank(tank):
    """Check if tank can be safely deleted."""
    # Check if tank is in current system
    current_system_tank_ids = get_current_system_tank_ids()
    if tank.id in current_system_tank_ids:
        flash("Cannot delete a tank from the currently selected system. Please select a different system first.", "error")
        return False
    
    # Check for related schedules
    if hasattr(tank, 'schedules') and tank.schedules:
        flash(f"Cannot delete tank '{tank.name}' because it has {len(tank.schedules)} dosing schedule(s). Please remove or reassign them first.", "warning")
        return False
    
    # Check for related corals
    if hasattr(tank, 'corals') and tank.corals:
        flash(f"Cannot delete tank '{tank.name}' because it has {len(tank.corals)} coral(s). Please remove or reassign them first.", "warning")
        return False
    
    return True

# Tank System Management Routes

@app.route("/tank-systems")
def tank_system_list():
    """List all tank systems with their tanks and statistics."""
    if not TankSystemModel:
        flash("Tank system functionality is not available.", "warning")
        return render_template(TANK_SYSTEMS_TEMPLATE, system_stats=[], standalone_tanks=[])
    
    try:
        tank_systems = TankSystemModel.query.all()
        standalone_tanks = Tank.query.filter_by(tank_system_id=None).all()
        system_stats = _calculate_system_statistics(tank_systems)
        
        return render_template(TANK_SYSTEMS_TEMPLATE, 
                             system_stats=system_stats,
                             standalone_tanks=standalone_tanks)
    except Exception as e:
        flash(f"Error loading tank systems: {str(e)}", "error")
        return render_template(TANK_SYSTEMS_TEMPLATE, system_stats=[], standalone_tanks=[])

def _calculate_system_statistics(tank_systems):
    """Calculate statistics for tank systems."""
    system_stats = []
    for system in tank_systems:
        system_stats.append({
            'system': system,
            'tank_count': system.get_tank_count(),
            'total_volume': system.calculate_total_system_volume(),
            'tanks': system.tanks
        })
    return system_stats

@app.route("/tank-systems/new", methods=['GET', 'POST'])
def tank_system_new():
    """Create a new tank system."""
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            description = (request.form.get('description') or '').strip() or None
            total_system_volume_gallons = request.form.get('total_system_volume_gallons', type=float)
            shared_sump_volume_gallons = request.form.get('shared_sump_volume_gallons', type=float)
            system_type = request.form.get('system_type') or 'multi_tank'
            
            # Validate required fields
            if not name:
                flash("Tank system name is required.", "error")
                return render_template(TANK_SYSTEM_NEW_TEMPLATE)
            
            # Create new tank system
            tank_system = TankSystemModel(
                name=name,
                description=description,
                total_system_volume_gallons=total_system_volume_gallons,
                shared_sump_volume_gallons=shared_sump_volume_gallons,
                system_type=system_type
            )
            
            db.session.add(tank_system)
            db.session.commit()
            
            flash(f'Tank system "{name}" created successfully!', "success")
            return redirect(url_for('tank_system_list'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Tank system name already exists. Please choose a different name.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating tank system: {str(e)}", "error")
    
    return render_template(TANK_SYSTEM_NEW_TEMPLATE)

@app.route("/tank-systems/edit/<int:system_id>", methods=['GET', 'POST'])
def tank_system_edit(system_id):
    """Edit an existing tank system."""
    try:
        tank_system = TankSystemModel.query.get_or_404(system_id)
    except Exception as e:
        flash(f"Tank system not found: {str(e)}", "error")
        return redirect(url_for('tank_system_list'))
    
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            description = (request.form.get('description') or '').strip() or None
            total_system_volume_gallons = request.form.get('total_system_volume_gallons', type=float)
            shared_sump_volume_gallons = request.form.get('shared_sump_volume_gallons', type=float)
            system_type = request.form.get('system_type') or 'multi_tank'
            
            # Validate required fields
            if not name:
                flash("Tank system name is required.", "error")
                return render_template(TANK_SYSTEM_EDIT_TEMPLATE, tank_system=tank_system)
            
            # Update tank system
            tank_system.name = name
            tank_system.description = description
            tank_system.total_system_volume_gallons = total_system_volume_gallons
            tank_system.shared_sump_volume_gallons = shared_sump_volume_gallons
            tank_system.system_type = system_type
            
            db.session.commit()
            
            flash(f'Tank system "{name}" updated successfully!', "success")
            return redirect(url_for('tank_system_list'))
            
        except IntegrityError:
            db.session.rollback()
            flash("Tank system name already exists. Please choose a different name.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating tank system: {str(e)}", "error")
    
    return render_template(TANK_SYSTEM_EDIT_TEMPLATE, tank_system=tank_system)

@app.route("/tank-systems/<int:system_id>/delete", methods=['POST'])
def tank_system_delete(system_id):
    """Delete a tank system."""
    try:
        print(f"Attempting to delete tank system {system_id}")
        
        # Find the tank system
        system, model_name = _find_tank_system(system_id)
        if not system:
            flash(f"Tank system with ID {system_id} not found", "error")
            return redirect(url_for('tank_system_list'))
        
        # Get system name for feedback
        system_name = _get_system_name(system)
        print(f"Deleting {model_name}: {system_name} (ID: {system_id})")
        
        # Handle dependent records
        _handle_dependent_tanks(system_id)
        
        # Delete the system
        _delete_tank_system(system, model_name, system_id)
        
        flash(f"Tank system '{system_name}' has been deleted successfully.", "success")
        print(f"Successfully deleted: {system_name}")
        
    except Exception as e:
        db.session.rollback()
        error_msg = _format_deletion_error(e)
        flash(error_msg, "error")
        print(f"Deletion error for system {system_id}: {error_msg}")
        
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    return redirect(url_for('tank_system_list'))

def _find_tank_system(system_id):
    """Find tank system using available methods."""
    # Try direct SQL query first
    try:
        from modules.models import db
        result = db.session.execute(db.text("SELECT * FROM tank_systems WHERE id = :system_id"), {"system_id": system_id})
        row = result.fetchone()
        if row:
            class TankSystemRecord:
                def __init__(self, row_data):
                    self.id = row_data[0] if row_data else None
                    self.name = row_data[1] if len(row_data) > 1 else "Unknown System"
                    self.description = row_data[2] if len(row_data) > 2 else None
            
            system = TankSystemRecord(row)
            print(f"Found tank system using direct SQL query: {system.name} (ID: {system.id})")
            return system, "tank_systems"
    except Exception as e:
        print(f"Direct SQL query failed: {e}")
    
    # Fallback to model imports
    try:
        from modules.models import TankSystems
        system = TankSystems.query.filter_by(id=system_id).first()
        if system:
            print("Found system using TankSystems model")
            return system, "TankSystems"
    except (ImportError, AttributeError):
        pass
    
    try:
        from modules.models import TankSystem
        system = TankSystem.query.filter_by(id=system_id).first()
        if system:
            print("Found system using TankSystem model")
            return system, "TankSystem"
    except (ImportError, AttributeError):
        pass
    
    print("No suitable model found for tank systems")
    return None, None

def _get_system_name(system):
    """Get system name from system object."""
    if hasattr(system, 'name') and system.name:
        return system.name
    elif hasattr(system, 'system_name') and system.system_name:
        return system.system_name
    elif hasattr(system, 'id'):
        return f"System {system.id}"
    return "Unknown System"

def _handle_dependent_tanks(system_id):
    """Handle dependent tanks before system deletion."""
    try:
        from modules.models import Tank
        tanks_in_system = Tank.query.filter_by(tank_system_id=system_id).all()
        if tanks_in_system:
            print(f"Found {len(tanks_in_system)} tanks in system - removing references before deletion")
            for tank in tanks_in_system:
                print(f"Removing tank '{tank.name}' (ID: {tank.id}) from system before deletion")
                tank.tank_system_id = None
            db.session.flush()  # Apply changes but don't commit yet
    except Exception as tank_update_error:
        print(f"Warning: Could not update dependent tanks: {tank_update_error}")

def _delete_tank_system(system, model_name, system_id):
    """Delete the tank system using appropriate method."""
    if model_name == "tank_systems":
        # Use direct SQL delete for tank_systems table
        db.session.execute(db.text("DELETE FROM tank_systems WHERE id = :system_id"), {"system_id": system_id})
    else:
        # Use ORM delete for other models
        db.session.delete(system)
    db.session.commit()

def _format_deletion_error(error):
    """Format deletion error message."""
    error_details = str(error)
    
    if "cannot be null" in error_details:
        return "Cannot delete tank system: Missing required tank association."
    elif "foreign key constraint" in error_details.lower():
        return "Cannot delete tank system: It is still referenced by other records."
    else:
        return f"Error deleting tank system: {error_details}"

@app.route("/tank-systems/<int:system_id>/remove-tank/<int:tank_id>", methods=['POST'])
def tank_system_remove_tank(system_id, tank_id):
    """Remove a tank from a tank system."""
    try:
        tank_system = _get_tank_system_by_id(system_id)
        tank = Tank.query.get_or_404(tank_id)
        
        # Verify tank belongs to this system
        if tank.tank_system_id != system_id:
            flash("Tank does not belong to this system.", "error")
            return redirect(url_for('tank_system_list'))
        
        # Remove tank from system
        tank.tank_system_id = None
        db.session.commit()
        
        flash(f'Tank "{tank.name}" removed from system "{tank_system.name}" successfully!', "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing tank from system: {str(e)}", "error")
    
    return redirect(url_for('tank_system_list'))

def _get_tank_system_by_id(system_id):
    """Get tank system by ID using the appropriate model."""
    if not TankSystemModel:
        raise ValueError("Tank system model not available")
    return TankSystemModel.query.get_or_404(system_id)