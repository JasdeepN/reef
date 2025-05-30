"""
API endpoints for managing the automated dosing scheduler.

This module provides REST API endpoints for:
- Starting/stopping the scheduler
- Getting scheduler status
- Manually triggering dose checks
- Getting scheduler configuration
"""

from flask import Blueprint, jsonify, request
from app import app
from datetime import datetime
import sys
from datetime import datetime

bp = Blueprint('scheduler_api', __name__, url_prefix='/scheduler')

def get_scheduler():
    """Get the scheduler instance from the app context"""
    try:
        from flask import current_app
        return getattr(current_app, 'dosing_scheduler', None)
    except Exception:
        return None

@bp.route('/status', methods=['GET'])
def get_scheduler_status():
    """Get current scheduler status and configuration"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized',
                'status': {
                    'enabled': False,
                    'running': False,
                    'initialized': False
                }
            }), 200
        
        status = scheduler.get_status()
        
        return jsonify({
            'success': True,
            'status': status,
            'config': {
                'enabled': app.config.get('SCHEDULER_ENABLED', False),
                'check_interval': app.config.get('SCHEDULER_CHECK_INTERVAL', 60),
                'timezone': app.config.get('SCHEDULER_TIMEZONE', 'UTC'),
                'base_url': app.config.get('SCHEDULER_BASE_URL', 'http://localhost:5000')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting scheduler status: {str(e)}'
        }), 500

@bp.route('/start', methods=['POST'])
def start_scheduler():
    """Start the dosing scheduler"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        if scheduler.is_running:
            return jsonify({
                'success': False,
                'error': 'Scheduler is already running'
            }), 400
        
        scheduler.start()
        
        return jsonify({
            'success': True,
            'message': 'Dosing scheduler started successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error starting scheduler: {str(e)}'
        }), 500

@bp.route('/stop', methods=['POST'])
def stop_scheduler():
    """Stop the dosing scheduler"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        if not scheduler.is_running:
            return jsonify({
                'success': False,
                'error': 'Scheduler is not running'
            }), 400
        
        scheduler.stop()
        
        return jsonify({
            'success': True,
            'message': 'Dosing scheduler stopped successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error stopping scheduler: {str(e)}'
        }), 500

@bp.route('/restart', methods=['POST'])
def restart_scheduler():
    """Restart the dosing scheduler"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        # Use the new restart method that handles thread pool properly
        scheduler.restart()
        
        return jsonify({
            'success': True,
            'message': 'Dosing scheduler restarted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error restarting scheduler: {str(e)}'
        }), 500

@bp.route('/check', methods=['POST'])
def force_check():
    """Manually trigger a check for due doses"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        if not scheduler.is_running:
            return jsonify({
                'success': False,
                'error': 'Scheduler is not running. Start it first.'
            }), 400
        
        success = scheduler.force_check()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Manual dose check triggered successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to trigger manual dose check'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error triggering manual check: {str(e)}'
        }), 500

@bp.route('/due', methods=['GET'])
def get_due_schedules():
    """Get currently due dosing schedules (for monitoring/debugging)"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        # Get due schedules (this requires accessing the private method)
        # In a production system, you might want to make this a public method
        with app.app_context():
            due_schedules = scheduler._get_due_schedules()
        
        return jsonify({
            'success': True,
            'due_schedules': due_schedules,
            'count': len(due_schedules)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting due schedules: {str(e)}'
        }), 500

@bp.route('/logs', methods=['GET'])
def get_scheduler_logs():
    """Get recent scheduler log entries (if available)"""
    try:
        # This is a placeholder - in a production system you might want to
        # implement a log buffer or read from log files
        return jsonify({
            'success': True,
            'message': 'Log viewing not yet implemented',
            'logs': []
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting logs: {str(e)}'
        }), 500

@bp.route('/queue', methods=['GET'])
def get_dose_queue():
    """Get the current dose queue details"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        queue_details = []
        
        with scheduler.queue_lock:
            for timestamp, dose_data in scheduler.dose_queue:
                dose_time = datetime.fromtimestamp(timestamp)
                queue_details.append({
                    'schedule_id': dose_data['schedule_id'],
                    'product_name': dose_data['product_name'],
                    'amount': dose_data['amount'],
                    'tank_id': dose_data['tank_id'],
                    'scheduled_time': dose_time.isoformat(),
                    'seconds_until': int(timestamp - datetime.now().timestamp()),
                    'trigger_interval': dose_data['trigger_interval'],
                    'last_dose_time': dose_data['last_dose_time'].isoformat() if dose_data['last_dose_time'] else None
                })
        
        return jsonify({
            'success': True,
            'queue_size': len(queue_details),
            'queue_refresh_interval': scheduler.queue_refresh_interval,
            'last_queue_refresh': scheduler.last_queue_refresh.isoformat() if scheduler.last_queue_refresh else None,
            'doses': queue_details
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting dose queue: {str(e)}'
        }), 500
