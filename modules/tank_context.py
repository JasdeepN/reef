from flask import session

def get_current_tank_id():
    """Return the current tank_id from the session, or None if not set."""
    return session.get('tank_id')

# Future: Add more tank context utilities here (e.g., set_tank_id, require_tank_context, etc.)
def get_current_tank_id():
    return session.get('tank_id')


