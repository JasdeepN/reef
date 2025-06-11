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
from modules.timezone_utils import datetime_to_iso_format
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
        from modules.system_context import get_current_system_id
        
        # Get current tank context
        tank_id = get_current_system_id()
        if not tank_id:
            return jsonify({
                'success': False,
                'error': 'No tank selected'
            }), 400
        
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized'
            }), 400
        
        # Get due schedules filtered by current tank
        with app.app_context():
            due_schedules = scheduler._get_due_schedules(tank_id=tank_id)
        
        return jsonify({
            'success': True,
            'due_schedules': due_schedules,
            'count': len(due_schedules),
            'tank_id': tank_id
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
def get_enhanced_queue_status():
    """Get enhanced dosing scheduler queue status"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Enhanced scheduler not initialized',
                'queue_status': {}
            }), 200
        
        # Check if this is the enhanced scheduler
        if hasattr(scheduler, 'get_queue_status'):
            queue_status = scheduler.get_queue_status()
            return jsonify({
                'success': True,
                'queue_status': queue_status,
                'scheduler_type': 'enhanced',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Enhanced scheduler methods not available',
                'scheduler_type': 'legacy',
                'queue_status': {}
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting enhanced queue status: {str(e)}',
            'queue_status': {}
        }), 500

@bp.route('/precision', methods=['GET'])
def get_scheduler_precision_status():
    """Get enhanced scheduler precision timing information"""
    try:
        scheduler = get_scheduler()
        
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'Enhanced scheduler not initialized'
            }), 200
        
        # Get precision timing information
        if hasattr(scheduler, 'timing_precision_seconds'):
            precision_info = {
                'target_precision_seconds': scheduler.timing_precision_seconds,
                'queue_refresh_interval': scheduler.queue_refresh_interval,
                'confirmation_timeout': scheduler.confirmation_timeout,
                'scheduler_type': 'enhanced',
                'features': [
                    'precise_timing',
                    'automatic_confirmation',
                    'complete_audit_logging',
                    'error_only_notifications',
                    'queue_based_management'
                ]
            }
            
            return jsonify({
                'success': True,
                'precision_info': precision_info,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Enhanced scheduler precision features not available',
                'scheduler_type': 'legacy'
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting precision status: {str(e)}'
        }), 500

@bp.route('/simulate', methods=['POST'])
def simulate_schedule():
    """
    Simulate a dosing schedule to show predicted dose times without saving or executing.
    This endpoint calculates when doses would occur based on schedule configuration.
    """
    try:
        from modules.system_context import get_current_system_id
        from datetime import datetime, timedelta
        
        # Get current tank context
        tank_id = get_current_system_id()
        if not tank_id:
            return jsonify({
                'success': False,
                'error': 'No tank selected'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No schedule data provided'
            }), 400
        
        # Required fields for simulation
        required_fields = ['schedule_type', 'amount']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Calculate trigger interval based on schedule type
        from app.routes.doser import calculate_trigger_interval
        trigger_interval = calculate_trigger_interval(data, data['schedule_type'])
        
        if trigger_interval is None:
            return jsonify({
                'success': False,
                'error': 'Invalid schedule configuration'
            }), 400
        
        # Calculate simulation results
        simulation_results = calculate_schedule_simulation(data, trigger_interval)
        
        return jsonify({
            'success': True,
            'simulation': simulation_results,
            'tank_id': tank_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error simulating schedule: {str(e)}'
        }), 500


def calculate_schedule_simulation(data, trigger_interval):
    """
    Calculate simulation results for a dosing schedule.
    
    Args:
        data: Schedule configuration data
        trigger_interval: Calculated interval in seconds
        
    Returns:
        Dictionary containing simulation results
    """
    from datetime import datetime
    
    current_time = datetime.now()
    schedule_type = data.get('schedule_type')
    amount = float(data.get('amount', 0))
    
    # Calculate dose times based on schedule type
    dose_times = _calculate_dose_times_by_type(data, schedule_type, current_time, amount)
    
    # Calculate schedule summary
    summary = _calculate_schedule_summary(dose_times, amount, current_time)
    
    return {
        'schedule_type': schedule_type,
        'trigger_interval_seconds': trigger_interval,
        'trigger_interval_human': format_interval(trigger_interval),
        'amount_per_dose': amount,
        'dose_schedule': dose_times,
        'summary': summary
    }


def _calculate_dose_times_by_type(data, schedule_type, current_time, amount):
    """Calculate dose times based on schedule type"""
    if schedule_type == 'interval':
        return _calculate_interval_doses(data, current_time, amount)
    elif schedule_type == 'daily':
        return _calculate_daily_doses(data, current_time, amount)
    elif schedule_type == 'weekly':
        return _calculate_weekly_doses(data, current_time, amount)
    elif schedule_type == 'custom':
        return _calculate_custom_doses(data, current_time, amount)
    else:
        return []


def _calculate_interval_doses(data, current_time, amount):
    """Calculate doses for interval-based scheduling"""
    from datetime import timedelta
    
    trigger_interval = int(data.get('trigger_interval', 3600))
    start_time = data.get('start_time')
    
    if start_time:
        try:
            start_hour, start_minute = map(int, start_time.split(':'))
            next_dose = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            if next_dose <= current_time:
                next_dose += timedelta(days=1)
        except (ValueError, AttributeError):
            next_dose = current_time + timedelta(seconds=trigger_interval)
    else:
        next_dose = current_time + timedelta(seconds=trigger_interval)
    
    dose_times = []
    for i in range(10):
        dose_times.append({
            'dose_number': i + 1,
            'scheduled_time': datetime_to_iso_format(next_dose),
            'relative_time': format_relative_time(next_dose, current_time),
            'amount': amount
        })
        next_dose += timedelta(seconds=trigger_interval)
    
    return dose_times


def _calculate_daily_doses(data, current_time, amount):
    """Calculate doses for daily scheduling"""
    from datetime import timedelta
    
    times_per_day = int(data.get('times_per_day', 1))
    daily_time = data.get('daily_time', '09:00')
    
    try:
        start_hour, start_minute = map(int, daily_time.split(':'))
    except (ValueError, AttributeError):
        start_hour, start_minute = 9, 0
    
    daily_interval = 24 * 3600 // times_per_day if times_per_day > 1 else 24 * 3600
    
    # Find the next upcoming dose time (same day or next day)
    next_dose = _find_next_daily_dose_time(current_time, start_hour, start_minute, times_per_day, daily_interval)
    
    # Generate dose schedule
    return _generate_daily_dose_schedule(next_dose, start_hour, start_minute, times_per_day, daily_interval, amount, current_time)


def _find_next_daily_dose_time(current_time, start_hour, start_minute, times_per_day, daily_interval):
    """Find the next upcoming dose time for daily scheduling"""
    from datetime import timedelta
    
    base_dose_time = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    
    # For multiple doses per day, check if any remaining doses are still upcoming today
    if times_per_day > 1:
        for dose_in_day in range(times_per_day):
            dose_time = base_dose_time + timedelta(seconds=dose_in_day * daily_interval)
            if dose_time > current_time:
                return dose_time
    else:
        # Single dose per day
        if base_dose_time > current_time:
            return base_dose_time
    
    # No upcoming doses today, move to tomorrow
    return base_dose_time + timedelta(days=1)


def _generate_daily_dose_schedule(start_dose, start_hour, start_minute, times_per_day, daily_interval, amount, current_time):
    """Generate the daily dose schedule starting from the given start dose time"""
    from datetime import timedelta
    
    dose_times = []
    dose_count = 0
    
    # Determine if we're starting mid-day
    day_start = start_dose.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    is_mid_day_start = start_dose != day_start
    
    current_day = day_start
    
    if is_mid_day_start:
        # Add remaining doses for the current day
        dose_count = _add_remaining_doses_for_day(dose_times, current_day, start_dose, times_per_day, daily_interval, amount, current_time, dose_count)
        current_day += timedelta(days=1)
    
    # Continue with full days
    while dose_count < 10:
        dose_count = _add_full_day_doses(dose_times, current_day, times_per_day, daily_interval, amount, current_time, dose_count)
        current_day += timedelta(days=1)
    
    return dose_times


def _add_remaining_doses_for_day(dose_times, day_start, start_dose, times_per_day, daily_interval, amount, current_time, dose_count):
    """Add remaining doses for a partial day"""
    from datetime import timedelta
    
    seconds_from_start = (start_dose - day_start).total_seconds()
    dose_offset = int(seconds_from_start // daily_interval)
    
    for dose_in_day in range(dose_offset, times_per_day):
        if dose_count >= 10:
            break
        
        dose_time = day_start + timedelta(seconds=dose_in_day * daily_interval)
        dose_times.append({
            'dose_number': dose_count + 1,
            'scheduled_time': datetime_to_iso_format(dose_time),
            'relative_time': format_relative_time(dose_time, current_time),
            'amount': amount
        })
        dose_count += 1
    
    return dose_count


def _add_full_day_doses(dose_times, day_start, times_per_day, daily_interval, amount, current_time, dose_count):
    """Add all doses for a complete day"""
    from datetime import timedelta
    
    for dose_in_day in range(times_per_day):
        if dose_count >= 10:
            break
        
        dose_time = day_start + timedelta(seconds=dose_in_day * daily_interval)
        dose_times.append({
            'dose_number': dose_count + 1,
            'scheduled_time': datetime_to_iso_format(dose_time),
            'relative_time': format_relative_time(dose_time, current_time),
            'amount': amount
        })
        dose_count += 1
    
    return dose_count


def _calculate_weekly_doses(data, current_time, amount):
    """Calculate doses for weekly scheduling"""
    from datetime import timedelta
    
    weekly_time = data.get('weekly_time', '09:00')
    days_of_week = data.get('days_of_week', '').split(',') if data.get('days_of_week') else ['1']
    
    try:
        start_hour, start_minute = map(int, weekly_time.split(':'))
    except (ValueError, AttributeError):
        start_hour, start_minute = 9, 0
    
    target_weekdays = [(int(day) - 1) % 7 for day in days_of_week if day.isdigit()]
    current_weekday = current_time.weekday()
    
    days_ahead = []
    for target_day in target_weekdays:
        days_to_add = (target_day - current_weekday) % 7
        if days_to_add == 0:
            dose_time = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            if dose_time <= current_time:
                days_to_add = 7
        days_ahead.append(days_to_add)
    
    dose_times = []
    week_offset = 0
    dose_count = 0
    
    while dose_count < 10:
        for days_to_add in sorted(days_ahead):
            if dose_count >= 10:
                break
            
            dose_time = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            dose_time += timedelta(days=days_to_add + (week_offset * 7))
            
            dose_times.append({
                'dose_number': dose_count + 1,
                'scheduled_time': datetime_to_iso_format(dose_time),
                'relative_time': format_relative_time(dose_time, current_time),
                'amount': amount
            })
            dose_count += 1
        
        week_offset += 1
    
    return dose_times


def _calculate_custom_doses(data, current_time, amount):
    """Calculate doses for custom scheduling"""
    from datetime import timedelta
    
    repeat_every_n_days = data.get('repeat_every_n_days')
    custom_time = data.get('custom_time')
    custom_seconds = data.get('custom_seconds')
    
    dose_times = []
    
    if repeat_every_n_days and custom_time:
        # Day-based custom scheduling
        days = int(repeat_every_n_days)
        try:
            start_hour, start_minute = map(int, custom_time.split(':'))
        except (ValueError, AttributeError):
            start_hour, start_minute = 9, 0
        
        next_dose = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        if next_dose <= current_time:
            next_dose += timedelta(days=1)
        
        for i in range(10):
            dose_times.append({
                'dose_number': i + 1,
                'scheduled_time': datetime_to_iso_format(next_dose),
                'relative_time': format_relative_time(next_dose, current_time),
                'amount': amount
            })
            next_dose += timedelta(days=days)
    
    elif custom_seconds:
        # Second-based custom scheduling
        interval_seconds = int(custom_seconds)
        next_dose = current_time + timedelta(seconds=interval_seconds)
        
        for i in range(10):
            dose_times.append({
                'dose_number': i + 1,
                'scheduled_time': datetime_to_iso_format(next_dose),
                'relative_time': format_relative_time(next_dose, current_time),
                'amount': amount
            })
            next_dose += timedelta(seconds=interval_seconds)
    
    return dose_times


def _calculate_schedule_summary(dose_times, amount, current_time):
    """Calculate schedule summary statistics"""
    from datetime import datetime, timedelta
    
    if not dose_times:
        return {
            'total_doses_shown': 0,
            'first_dose_time': datetime_to_iso_format(current_time),
            'time_until_first_dose': 'No doses scheduled',
            'estimated_doses_per_day': 0,
            'estimated_ml_per_day': 0,
            'preview_duration_days': 0
        }
    
    first_dose = datetime.strptime(dose_times[0]['scheduled_time'], '%Y-%m-%d %H:%M:%S')
    last_dose = datetime.strptime(dose_times[-1]['scheduled_time'], '%Y-%m-%d %H:%M:%S')
    total_duration = last_dose - first_dose
    
    total_doses = len(dose_times)
    days_covered = max(1, total_duration.days + 1)
    doses_per_day = total_doses / days_covered
    ml_per_day = doses_per_day * amount
    
    return {
        'total_doses_shown': total_doses,
        'first_dose_time': datetime_to_iso_format(first_dose),
        'time_until_first_dose': format_relative_time(first_dose, current_time),
        'estimated_doses_per_day': round(doses_per_day, 2),
        'estimated_ml_per_day': round(ml_per_day, 2),
        'preview_duration_days': max(1, total_duration.days + 1)
    }


def format_relative_time(future_time, current_time):
    """Format relative time difference in a human-readable way"""
    diff = future_time - current_time
    
    if diff.total_seconds() < 0:
        return "Past"
    
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 60:
        return f"in {total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"in {minutes}m"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes > 0:
            return f"in {hours}h {minutes}m"
        else:
            return f"in {hours}h"
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        if hours > 0:
            return f"in {days}d {hours}h"
        else:
            return f"in {days}d"


def format_interval(seconds):
    """Format interval in seconds to human-readable format"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minutes"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{hours} hours"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours > 0:
            return f"{days}d {hours}h"
        else:
            return f"{days} days"
