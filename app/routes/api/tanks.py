from flask import Blueprint, request, jsonify
from modules.models import Tank, TankSystem, db
from modules.system_context import get_current_system_id, get_current_system_tank_ids
from sqlalchemy.exc import IntegrityError

# Create blueprint for tank API routes
tanks_api = Blueprint('tanks_api', __name__)

@tanks_api.route('/tanks', methods=['GET'])
def get_tanks():
    """Get all tanks for the current user."""
    try:
        tanks = Tank.query.all()
        tanks_data = []
        for tank in tanks:
            tanks_data.append(tank.to_dict())
        
        return jsonify({
            'success': True,
            'tanks': tanks_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/system/tanks', methods=['GET'])
def get_system_tanks():
    """Get tanks in the current system."""
    try:
        from modules.system_context import get_current_system_tanks
        tanks = get_current_system_tanks()
        
        if not tanks:
            return jsonify({
                'success': True,
                'data': []
            })
        
        tanks_data = []
        for tank in tanks:
            tanks_data.append({
                'id': tank.id,
                'name': tank.name,
                'display_name': tank.display_name or tank.name
            })
        
        return jsonify({
            'success': True,
            'data': tanks_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tanks/<int:tank_id>', methods=['GET'])
def get_tank(tank_id):
    """Get a specific tank by ID."""
    try:
        tank = Tank.query.get_or_404(tank_id)
        return jsonify({
            'success': True,
            'tank': tank.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tanks', methods=['POST'])
def create_tank():
    """Create a new tank."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Tank name is required'
            }), 400
        
        # Create new tank
        tank = Tank(
            name=data['name'],
            gross_water_vol=data.get('gross_water_vol', 0),
            net_water_vol=data.get('net_water_vol', 0),
            live_rock_lbs=data.get('live_rock_lbs', 0.0)
        )
        
        db.session.add(tank)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tank created successfully',
            'tank': {
                'id': tank.id,
                'name': tank.name,
                'gross_water_vol': tank.gross_water_vol,
                'net_water_vol': tank.net_water_vol,
                'live_rock_lbs': tank.live_rock_lbs
            }
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Tank name already exists'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tanks/<int:tank_id>', methods=['PUT'])
def update_tank(tank_id):
    """Update an existing tank."""
    try:
        tank = Tank.query.get_or_404(tank_id)
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Update tank fields
        if 'name' in data:
            if not data['name']:
                return jsonify({
                    'success': False,
                    'error': 'Tank name cannot be empty'
                }), 400
            tank.name = data['name']
        
        if 'gross_water_vol' in data:
            tank.gross_water_vol = data['gross_water_vol']
        
        if 'net_water_vol' in data:
            tank.net_water_vol = data['net_water_vol']
            
        if 'live_rock_lbs' in data:
            tank.live_rock_lbs = data['live_rock_lbs']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tank updated successfully',
            'tank': {
                'id': tank.id,
                'name': tank.name,
                'gross_water_vol': tank.gross_water_vol,
                'net_water_vol': tank.net_water_vol,
                'live_rock_lbs': tank.live_rock_lbs
            }
        })
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Tank name already exists'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tanks/<int:tank_id>', methods=['DELETE'])
def delete_tank(tank_id):
    """Delete a tank."""
    try:
        tank = Tank.query.get_or_404(tank_id)
        
        # Check if this tank belongs to the current system
        current_tank_ids = get_current_system_tank_ids()
        if tank_id in current_tank_ids:
            # If this is the only tank in the system, prevent deletion
            if len(current_tank_ids) == 1:
                return jsonify({
                    'success': False,
                    'error': 'Cannot delete the only tank in the current system.'
                }), 400
        
        tank_name = tank.name
        db.session.delete(tank)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank "{tank_name}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Tank System API Routes

@tanks_api.route('/tank-systems', methods=['GET'])
def get_tank_systems():
    """Get all tank systems."""
    try:
        tank_systems = TankSystem.query.all()
        systems_data = []
        for system in tank_systems:
            systems_data.append(system.to_dict())
        
        return jsonify({
            'success': True,
            'tank_systems': systems_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems/<int:system_id>', methods=['GET'])
def get_tank_system(system_id):
    """Get a specific tank system by ID."""
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        system_data = tank_system.to_dict()
        
        # Include tank details
        system_data['tanks'] = [tank.to_dict() for tank in tank_system.tanks]
        
        return jsonify({
            'success': True,
            'tank_system': system_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems', methods=['POST'])
def create_tank_system():
    """Create a new tank system."""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Tank system name is required'
            }), 400
        
        tank_system = TankSystem(
            name=data['name'],
            description=data.get('description'),
            total_system_volume_gallons=data.get('total_system_volume_gallons'),
            shared_sump_volume_gallons=data.get('shared_sump_volume_gallons'),
            system_type=data.get('system_type', 'multi_tank')
        )
        
        db.session.add(tank_system)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank system "{tank_system.name}" created successfully',
            'tank_system': tank_system.to_dict()
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Tank system name already exists'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems/<int:system_id>', methods=['PUT'])
def update_tank_system(system_id):
    """Update an existing tank system."""
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Update fields
        if 'name' in data:
            tank_system.name = data['name']
        if 'description' in data:
            tank_system.description = data['description']
        if 'total_system_volume_gallons' in data:
            tank_system.total_system_volume_gallons = data['total_system_volume_gallons']
        if 'shared_sump_volume_gallons' in data:
            tank_system.shared_sump_volume_gallons = data['shared_sump_volume_gallons']
        if 'system_type' in data:
            tank_system.system_type = data['system_type']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank system "{tank_system.name}" updated successfully',
            'tank_system': tank_system.to_dict()
        })
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Tank system name already exists'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems/<int:system_id>', methods=['DELETE'])
def delete_tank_system(system_id):
    """Delete a tank system."""
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        
        # Check if system has tanks
        if tank_system.tanks:
            return jsonify({
                'success': False,
                'error': f'Cannot delete tank system "{tank_system.name}" because it contains {len(tank_system.tanks)} tank(s)'
            }), 400
        
        system_name = tank_system.name
        db.session.delete(tank_system)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank system "{system_name}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems/<int:system_id>/add-tank/<int:tank_id>', methods=['POST'])
def add_tank_to_system(system_id, tank_id):
    """Add a tank to a tank system."""
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        tank = Tank.query.get_or_404(tank_id)
        
        # Check if tank is already in a system
        if tank.tank_system_id:
            return jsonify({
                'success': False,
                'error': f'Tank "{tank.name}" is already assigned to a system'
            }), 400
        
        # Add tank to system
        tank.tank_system_id = system_id
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank "{tank.name}" added to system "{tank_system.name}" successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tanks_api.route('/tank-systems/<int:system_id>/remove-tank/<int:tank_id>', methods=['POST'])
def remove_tank_from_system(system_id, tank_id):
    """Remove a tank from a tank system."""
    try:
        tank_system = TankSystem.query.get_or_404(system_id)
        tank = Tank.query.get_or_404(tank_id)
        
        # Verify tank belongs to this system
        if tank.tank_system_id != system_id:
            return jsonify({
                'success': False,
                'error': f'Tank "{tank.name}" does not belong to system "{tank_system.name}"'
            }), 400
        
        # Remove tank from system
        tank.tank_system_id = None
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tank "{tank.name}" removed from system "{tank_system.name}" successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500