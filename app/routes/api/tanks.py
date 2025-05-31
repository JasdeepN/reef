from flask import Blueprint, request, jsonify
from modules.models import Tank, db
from modules.tank_context import get_current_tank_id
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
            tanks_data.append({
                'id': tank.id,
                'name': tank.name,
                'gross_water_vol': tank.gross_water_vol,
                'net_water_vol': tank.net_water_vol,
                'live_rock_lbs': tank.live_rock_lbs
            })
        
        return jsonify({
            'success': True,
            'tanks': tanks_data
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
        tank_data = {
            'id': tank.id,
            'name': tank.name,
            'gross_water_vol': tank.gross_water_vol,
            'net_water_vol': tank.net_water_vol,
            'live_rock_lbs': tank.live_rock_lbs
        }
        
        return jsonify({
            'success': True,
            'tank': tank_data
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
        
        # Check if this is the current tank
        current_tank_id = get_current_tank_id()
        if current_tank_id == tank_id:
            return jsonify({
                'success': False,
                'error': 'Cannot delete the currently selected tank. Please select a different tank first.'
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