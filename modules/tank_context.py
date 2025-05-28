from flask import session

def get_current_tank_id():
    """Return the current tank_id from the session, or None if not set."""
    return session.get('tank_id')

def set_tank_id_for_testing(tank_id):
    """Set the tank_id in the session for testing purposes."""
    session['tank_id'] = tank_id
    return tank_id

# Future: Add more tank context utilities here (e.g., set_tank_id, require_tank_context, etc.)


