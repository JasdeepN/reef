from flask import session, request

def is_vscode_simple_browser():
    """Detect if the request is coming from VS Code Simple Browser"""
    user_agent = request.headers.get('User-Agent', '').lower()
    print(f"[system_context] User-Agent: {user_agent}")
    # VS Code Simple Browser contains "code/" and "electron" in the user agent
    is_vscode = ('vscode' in user_agent or 'simple browser' in user_agent or 
                 ('code/' in user_agent and 'electron' in user_agent))
    print(f"[system_context] Is VS Code detection: {is_vscode}")
    return is_vscode

def force_system_context_for_vscode():
    """Force set system context for VS Code - simple and reliable"""
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'vscode' in user_agent or 'simple browser' in user_agent:
        try:
            from modules.models import TankSystem
            first_system = TankSystem.query.first()
            if first_system:
                session['system_id'] = first_system.id
                session.permanent = True
                print(f"[FORCE] Set system_id={first_system.id} for VS Code")
                return first_system.id
        except Exception as e:
            print(f"[FORCE] Failed to set system context: {e}")
    return None

def get_current_system_id():
    """Return the current system_id from the session, or None if not set."""
    return session.get('system_id')

def get_current_system_tank_ids():
    """
    Return a list of tank IDs that belong to the current system.
    This is used for database queries that need to filter by tank_id.
    """
    system_id = get_current_system_id()
    if not system_id:
        return []
    
    try:
        # Import here to avoid circular imports
        from modules.models import Tank
        tanks = Tank.query.filter_by(tank_system_id=system_id).all()
        return [tank.id for tank in tanks]
    except Exception as e:
        print(f"[system_context] Error getting tank IDs for system {system_id}: {e}")
        return []

def get_current_system_tanks():
    """
    Return Tank objects that belong to the current system.
    Useful when you need the full tank objects, not just IDs.
    """
    system_id = get_current_system_id()
    if not system_id:
        return []
    
    try:
        # Import here to avoid circular imports
        from modules.models import Tank
        return Tank.query.filter_by(tank_system_id=system_id).all()
    except Exception as e:
        print(f"[system_context] Error getting tanks for system {system_id}: {e}")
        return []

def set_system_id_for_testing(system_id):
    """Set the system_id in the session for testing purposes."""
    session['system_id'] = system_id
    return system_id

def set_system_id(system_id):
    """Set the system_id in the session."""
    if system_id:
        session['system_id'] = system_id
    return system_id

def clear_system_context():
    """Clear the system context from the session."""
    session.pop('system_id', None)

def ensure_system_context():
    """
    Ensure system context is set. For VS Code Simple Browser, automatically set
    a default system to prevent redirect loops and memory leaks.
    
    Returns:
        int: system_id if context exists or was set
        None: if no system context and not VS Code Simple Browser
    """
    system_id = get_current_system_id()
    print(f"[system_context] ensure_system_context() called - current system_id: {system_id}")
    
    # If context already exists, return it
    if system_id:
        print(f"[system_context] System context exists: {system_id}")
        return system_id
    
    # Check if this is VS Code Simple Browser
    is_vscode = is_vscode_simple_browser()
    print(f"[system_context] Is VS Code Simple Browser: {is_vscode}")
    
    # If this is VS Code Simple Browser, automatically set first available system
    # Also handle API requests that might not have persistent sessions
    if is_vscode or request.path.startswith('/api/'):
        try:
            # Import here to avoid circular imports
            from modules.models import TankSystem
            first_system = TankSystem.query.first()
            print(f"[system_context] First system from database: {first_system}")
            if first_system:
                session['system_id'] = first_system.id
                session.permanent = True  # Make session persistent
                print(f"[system_context] Auto-set system_id for VS Code/API: {first_system.id}")
                return first_system.id
        except Exception as e:
            print(f"[system_context] Database error, using default system_id=4: {e}")
            # Use system_id=4 which we know exists from database check
            session['system_id'] = 4
            session.permanent = True
            return 4
    
    print("[system_context] No system context and not VS Code - returning None")
    return None

def has_system_context():
    """Check if a system context is currently set."""
    return session.get('system_id') is not None

# Backward compatibility functions that map tank operations to system operations
def get_current_tank_id():
    """
    DEPRECATED: Use get_current_system_id() and get_current_system_tank_ids() instead.
    For backward compatibility, returns the first tank ID in the current system.
    """
    tank_ids = get_current_system_tank_ids()
    return tank_ids[0] if tank_ids else None

def set_tank_id_for_testing(tank_id):
    """
    DEPRECATED: Use set_system_id_for_testing() instead.
    For backward compatibility, finds the system for the given tank and sets system context.
    """
    try:
        from modules.models import Tank
        tank = Tank.query.get(tank_id)
        if tank and tank.tank_system_id:
            return set_system_id_for_testing(tank.tank_system_id)
        else:
            # If tank has no system, create a temporary system context
            return set_system_id_for_testing(1)  # Default system
    except Exception as e:
        print(f"[system_context] Error setting tank context {tank_id}: {e}")
        return set_system_id_for_testing(1)

def ensure_tank_context():
    """
    DEPRECATED: Use ensure_system_context() instead.
    For backward compatibility.
    """
    return ensure_system_context()

def set_tank_id(tank_id):
    """
    DEPRECATED: Use set_system_id() instead.
    For backward compatibility, finds the system for the given tank and sets system context.
    """
    try:
        from modules.models import Tank
        tank = Tank.query.get(tank_id)
        if tank and tank.tank_system_id:
            return set_system_id(tank.tank_system_id)
        else:
            return set_system_id(1)  # Default system
    except Exception as e:
        print(f"[system_context] Error setting tank context {tank_id}: {e}")
        return set_system_id(1)

# Future: Add more system context utilities here (e.g., require_system_context, etc.)
