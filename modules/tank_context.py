from flask import session, request

def is_vscode_simple_browser():
    """Detect if the request is coming from VS Code Simple Browser"""
    user_agent = request.headers.get('User-Agent', '').lower()
    # More permissive detection for VS Code browsers
    is_vscode = ('vscode' in user_agent or 
                 'simple browser' in user_agent or
                 'code/' in user_agent or
                 'electron' in user_agent)
    return is_vscode

def get_current_tank_id():
    """Return the current tank_id from the session, or None if not set."""
    tank_id = session.get('tank_id')
    
    # If no tank_id but this is VS Code, auto-set one
    if tank_id is None and is_vscode_simple_browser():
        session['tank_id'] = 1
        return 1
    
    return tank_id

def set_tank_id_for_testing(tank_id):
    """Set the tank_id in the session for testing purposes."""
    session['tank_id'] = tank_id
    return tank_id

def set_tank_id(tank_id):
    """Set the tank_id in the session."""
    if tank_id:
        session['tank_id'] = tank_id
    return tank_id

def clear_tank_context():
    """Clear the tank context from the session."""
    session.pop('tank_id', None)

def ensure_tank_context():
    """
    Ensure tank context is set. For VS Code Simple Browser, automatically set
    a default tank to prevent redirect loops and memory leaks.
    
    Returns:
        int: tank_id if context exists or was set
        None: if no tank context and not VS Code Simple Browser
    """
    tank_id = get_current_tank_id()
    
    # If context already exists, return it
    if tank_id:
        return tank_id
    
    # Check if this is VS Code Simple Browser
    is_vscode = is_vscode_simple_browser()
    
    # If this is VS Code Simple Browser, automatically set first available tank
    if is_vscode:
        try:
            # Import here to avoid circular imports
            from modules.models import Tank
            first_tank = Tank.query.first()
            if first_tank:
                session['tank_id'] = first_tank.id
                return first_tank.id
        except Exception:
            # If we can't access the database, use a default
            session['tank_id'] = 1
            return 1
    
    return None

def has_tank_context():
    """Check if a tank context is currently set."""
    return session.get('tank_id') is not None

# Future: Add more tank context utilities here (e.g., require_tank_context, etc.)


