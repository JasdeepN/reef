from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from app import db
from modules.models import DSchedule, Products, Dosing
from modules.system_context import get_current_system_id, get_current_system_tank_ids, get_current_system_tanks, ensure_system_context
from modules.utils.helper import datatables_response
from modules.timezone_utils import (
    format_time_for_display as tz_format_time_for_display,
    datetime_to_iso_format, get_system_timezone
)
from sqlalchemy import text
import pytz
from zoneinfo import ZoneInfo

bp = Blueprint('schedule_api', __name__, url_prefix='/schedule')

@bp.route('/get/all', methods=['GET'])
def get_sched():
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    if system_id is None or not tank_ids:
        return jsonify({'error': 'No system id provided'}), 400
    
    params = {
        'search': request.args.get('search', ''),
        'sidx': request.args.get('sidx', ''),
        'sord': request.args.get('sord', 'asc'),
        'page': request.args.get('page', 1),
        'rows': request.args.get('rows', 10)
    }
    draw = int(request.args.get('draw', 1))
    rows = (
        db.session.query(
            DSchedule.id,
            DSchedule.trigger_interval,
            DSchedule.amount,
            DSchedule.suspended,
            Products.current_avail,
            Products.total_volume,
            Products.name,
            DSchedule.last_refill

        )
        .join(Products, Products.id == DSchedule.product_id)
        .filter(DSchedule.tank_id.in_(tank_ids))
        .all()
    )
    print('rows', rows)
    data = [
        {
            "id": row[0],
            "trigger_interval": row[1],
            "amount": row[2],
            "suspended": bool(row[3]),
            "current_avail": row[4],
            "total_volume": row[5],
            "name": row[6],
            "last_refill": datetime_to_iso_format(row[7]) if row[7] else "Never",
            
        }
        for row in rows
    ]
    print("data", data)
    response = datatables_response(data, params, draw)
    return jsonify(response)

@bp.route('/get/history', methods=['GET'])
def get_dosing_history():
    """Get dosing history with comprehensive details about recent dose events"""
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    
    if system_id is None or not tank_ids:
        return jsonify({'error': 'No system id provided'}), 400
    
    # Get pagination parameters
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # Query to get dosing history with product and schedule details
    tank_ids_placeholders = ','.join([':tank_id_{}'.format(i) for i in range(len(tank_ids))])
    sql = f"""
        SELECT 
            dosing.id,
            dosing.trigger_time,
            dosing.amount,
            products.id as product_id,
            products.name as product_name,
            products.uses as product_uses,
            d_schedule.id as schedule_id,
            d_schedule.trigger_interval,
            d_schedule.suspended as schedule_suspended,
            dosing.product_id,
            dosing.schedule_id
        FROM dosing
        LEFT JOIN products ON dosing.product_id = products.id
        LEFT JOIN d_schedule ON dosing.schedule_id = d_schedule.id
        WHERE d_schedule.tank_id IN ({tank_ids_placeholders})
        ORDER BY dosing.trigger_time DESC
        LIMIT :limit OFFSET :offset
    """
    
    # Get total count for pagination
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM dosing
        LEFT JOIN d_schedule ON dosing.schedule_id = d_schedule.id
        WHERE d_schedule.tank_id IN ({tank_ids_placeholders})
    """
    
    try:
        # Build parameters dictionary
        params = {'limit': limit, 'offset': offset}
        for i, tank_id in enumerate(tank_ids):
            params[f'tank_id_{i}'] = tank_id
        
        # Execute queries
        result = db.session.execute(text(sql), params)
        count_result = db.session.execute(text(count_sql), {k: v for k, v in params.items() if 'tank_id' in k})
        
        rows = result.fetchall()
        total_count = count_result.fetchone()[0]
        
        # Convert to list of dictionaries
        history_data = []
        for row in rows:
            # Convert trigger_time to ISO format if it exists
            trigger_time_iso = None
            if row.trigger_time:
                if isinstance(row.trigger_time, str):
                    # Parse string datetime and convert to ISO
                    dt = datetime.fromisoformat(row.trigger_time.replace('Z', '+00:00'))
                    trigger_time_iso = dt.isoformat()
                else:
                    # Assume it's already a datetime object
                    trigger_time_iso = row.trigger_time.isoformat()
            
            history_item = {
                'id': row.id,
                'trigger_time': trigger_time_iso,
                'trigger_time_display': format_time_display(row.trigger_time) if row.trigger_time else 'Unknown',
                'amount': row.amount,
                'product_id': row.product_id,
                'product_name': row.product_name or 'Unknown Product',
                'product_uses': row.product_uses or '',
                'schedule_id': row.schedule_id,
                'trigger_interval': row.trigger_interval,
                'schedule_suspended': bool(row.schedule_suspended) if row.schedule_suspended is not None else False,
                'interval_display': format_interval_display(row.trigger_interval) if row.trigger_interval else 'N/A'
            }
            history_data.append(history_item)
        
        return jsonify({
            "success": True,
            "data": history_data,
            "total": total_count,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def format_time_display(trigger_time):
    """Format trigger time for display with timezone awareness"""
    if not trigger_time:
        return 'Unknown'
    
    try:
        # Use timezone-aware formatting from timezone utilities
        return tz_format_time_for_display(trigger_time)
    except Exception:
        # Fallback to basic string representation
        return str(trigger_time)
        return "Unknown"

def format_interval_display(interval_seconds):
    """Format trigger interval for display"""
    if not interval_seconds:
        return 'N/A'
    
    try:
        seconds = int(interval_seconds)
        if seconds < 3600:
            minutes = seconds // 60
            return f"Every {minutes} min"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"Every {hours} hrs"
        else:
            days = seconds // 86400
            return f"Every {days} days"
    except Exception:
        return 'N/A'

@bp.route('/delete/<int:id>', methods=['DELETE'])
def delete_schedule_entry(id):
    schedule = DSchedule.query.get(id)
    if not schedule:
        return jsonify({'error': 'Schedule entry not found'}), 404

    # Optionally, handle cascading deletes or nullify references in Dosing, etc.
    # For example, to delete all dosing entries for this schedule:
    # Dosing.query.filter_by(sched_id=id).delete()

    db.session.delete(schedule)
    db.session.commit()
    
    # CRITICAL: Immediately refresh the enhanced scheduler queue to remove deleted schedule
    try:
        from modules.enhanced_dosing_scheduler import refresh_scheduler_queue
        import logging
        logger = logging.getLogger(__name__)
        refresh_success = refresh_scheduler_queue()
        logger.info(f"Enhanced scheduler queue refresh after deletion: {'successful' if refresh_success else 'failed'}")
    except Exception as refresh_error:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to refresh enhanced scheduler queue after deletion: {refresh_error}")
    
    return jsonify({'success': True, 'deleted_id': id}), 200

@bp.route('/get/<int:schedule_id>', methods=['GET'])
def get_doses_for_schedule(schedule_id):
    doses = Dosing.query.filter_by(sched_id=schedule_id).all()
    result = [
        {
            'id': dose.id,
            'prod_id': dose.prod_id,
            'sched_id': dose.sched_id,
            'amount': dose.amount,
            'trigger_time': dose.trigger_time.isoformat() if dose.trigger_time else None
        }
        for dose in doses
    ]
    return jsonify({'success': True, 'doses': result}), 200

@bp.route('/get/stats', methods=['GET'])
def get_schedule_stats():
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    
    if system_id is None or not tank_ids:
        return jsonify({'error': 'No system id provided'}), 400
    
    # Updated query to return ALL scheduled products, regardless of dosing history
    sql = """
        SELECT 
            products.id as product_id,
            products.name, 
            products.total_volume,
            products.used_amt,
            products.dry_refill,
            products.current_avail,
            products.uses,
            d_schedule.id as schedule_id,
            d_schedule.amount as set_amount,
            d_schedule.last_refill,
            d_schedule.suspended,
            d_schedule.trigger_interval,
            d_schedule.schedule_type,
            d_schedule.trigger_time,
            latest_dosing.trigger_time as last_trigger,
            latest_dosing.amount as dosed_amount
        FROM d_schedule 
        LEFT JOIN products ON d_schedule.product_id = products.id
        LEFT JOIN (
            SELECT 
                product_id,
                trigger_time,
                amount,
                ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY trigger_time DESC) as rn
            FROM dosing
        ) latest_dosing ON products.id = latest_dosing.product_id AND latest_dosing.rn = 1
        WHERE d_schedule.tank_id IN ({})
    """.format(','.join([':tank_id_{}'.format(i) for i in range(len(tank_ids))]))
    
    params = {}
    for i, tank_id in enumerate(tank_ids):
        params[f'tank_id_{i}'] = tank_id
    result = db.session.execute(text(sql), params)
    rows = result.fetchall()
    columns = result.keys()
    units = {
        'product_id': '',
        'name': '',
        'total_volume': 'ml',
        'used_amt': 'ml',
        'dry_refill': 'g|ml',
        'current_avail': 'ml',
        'schedule_id': '',
        'set_amount': 'ml',
        'last_refill': '',
        'suspended': '',
        'trigger_interval': 's',
        'schedule_type': '',
        'trigger_time': '',
        'last_trigger': '',
        'dosed_amount': 'ml',
        'percent_remaining': '%',
        'doses_remaining': 'doses',
        'days_until_empty': 'days',
        'estimated_empty_datetime': ''
    }
    date_keys = {'last_refill', 'last_trigger', 'estimated_empty_datetime'}
    time_keys = {'trigger_time'}  # For time objects (not datetime)
    stats = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        stat = {}
        stat['card_title'] = ['Product Name', row_dict.get('name'), row_dict.get('product_id')]
        for key in columns:
            label = key.replace('_', ' ').title()
            value = row_dict.get(key)
            unit = units.get(key, '')
            if key == 'suspended' and value is not None:
                value = bool(value)
            if key in time_keys and value:
                # Handle time objects (HH:MM:SS)
                try:
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%H:%M:%S')
                    else:
                        value = str(value)
                except Exception:
                    value = str(value) if value else None
            if key in date_keys and value:
                try:
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    value = tz_format_time_for_display(dt)
                except Exception:
                    pass
            stat[key] = [label, value, unit]
        try:
            percent_remaining = (
                (row_dict['current_avail'] / row_dict['total_volume']) * 100
                if row_dict['total_volume'] else None
            )
            stat['percent_remaining'] = ['% Remaining', percent_remaining, '%']
            doses_remaining = (
                row_dict['current_avail'] / row_dict['set_amount']
                if row_dict['set_amount'] else None
            )
            stat['doses_remaining'] = ['Doses Remaining', doses_remaining, 'doses']
            if row_dict['used_amt'] and row_dict['used_amt'] > 0:
                days_until_empty = row_dict['current_avail'] / row_dict['used_amt']
                stat['days_until_empty'] = ['Days Until Empty', days_until_empty, 'days']
                # Convert days to a datetime using timezone-aware current time
                from modules.timezone_utils import now_in_timezone
                estimated_empty_datetime = (
                    now_in_timezone() + timedelta(days=float(days_until_empty))
                )
                stat['estimated_empty_datetime'] = [
                    'Estimated Empty Date',
                    datetime_to_iso_format(estimated_empty_datetime),
                    ''
                ]
            else:
                stat['days_until_empty'] = ['Days Until Empty', None, 'days']
                stat['estimated_empty_datetime'] = ['Estimated Empty Date', None, '']
        except Exception:
            stat['percent_remaining'] = ['% Remaining', None, '%']
            stat['doses_remaining'] = ['Doses Remaining', None, 'doses']
            stat['days_until_empty'] = ['Days Until Empty', None, 'days']
            stat['estimated_empty_datetime'] = ['Estimated Empty Date', None, '']
        stat.pop('name', None)
        stats.append(stat)
    return jsonify({"success": True, "data": stats})

@bp.route('/get/next-doses', methods=['GET'])
def get_next_doses():
    """Get the next 3 scheduled doses for the current system - uses enhanced scheduler logic"""
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    
    if system_id is None or not tank_ids:
        return jsonify({'error': 'No system id provided'}), 400
    
    try:
        # Get scheduled doses with enhanced scheduler fields
        sql = """
            SELECT 
                ds.id as schedule_id,
                ds.tank_id,
                ds.product_id,
                ds.amount,
                ds.trigger_interval,
                ds.last_refill,
                ds.schedule_type,
                ds.trigger_time,
                ds.offset_minutes,
                p.name as product_name,
                p.current_avail,
                MAX(d.trigger_time) as actual_last_dose_time
            FROM d_schedule ds
            LEFT JOIN products p ON ds.product_id = p.id
            LEFT JOIN dosing d ON ds.id = d.schedule_id
            WHERE ds.tank_id IN ({})
            AND ds.suspended = 0
            AND p.current_avail >= ds.amount
            GROUP BY ds.id, ds.tank_id, ds.product_id, ds.amount, ds.trigger_interval, 
                     ds.last_refill, ds.schedule_type, ds.trigger_time, ds.offset_minutes,
                     p.name, p.current_avail
            ORDER BY ds.id
        """.format(','.join([':tank_id_{}'.format(i) for i in range(len(tank_ids))]))
        
        # Build parameters for tank IDs
        params = {}
        for i, tank_id in enumerate(tank_ids):
            params[f'tank_id_{i}'] = tank_id
        
        result = db.session.execute(text(sql), params)
        scheduled_doses = []
        
        for row in result:
            # Get current time in Eastern timezone
            eastern = ZoneInfo("America/New_York")
            current_time = datetime.now(eastern)
            
            schedule_type = row.schedule_type or 'interval'
            
            if schedule_type == 'daily' and row.trigger_time:
                # For daily schedules, calculate next occurrence of trigger_time
                # Parse trigger_time (format: "HH:MM:SS")
                time_parts = str(row.trigger_time).split(':')
                target_hour = int(time_parts[0])
                target_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                target_second = int(time_parts[2]) if len(time_parts) > 2 else 0
                
                # Create next dose time for today
                next_dose_time = current_time.replace(
                    hour=target_hour, 
                    minute=target_minute, 
                    second=target_second, 
                    microsecond=0
                )
                
                # If the time has already passed today, schedule for tomorrow
                if next_dose_time <= current_time:
                    next_dose_time += timedelta(days=1)
                
                # Use actual last dose time from database
                last_dose_time = row.actual_last_dose_time
                if last_dose_time and last_dose_time.tzinfo is None:
                    last_dose_time = last_dose_time.replace(tzinfo=eastern)
            else:
                # For interval schedules, use enhanced scheduler logic with offset_minutes
                last_dose_time = row.actual_last_dose_time
                
                # If last_dose_time is timezone-naive, assume it's in Eastern Time
                if last_dose_time and last_dose_time.tzinfo is None:
                    last_dose_time = last_dose_time.replace(tzinfo=eastern)
                
                # Calculate next dose time using enhanced scheduler logic
                if last_dose_time:
                    # Use actual last dose time as base
                    next_dose_time = last_dose_time + timedelta(seconds=row.trigger_interval)
                else:
                    # No previous dose - calculate from current time with interval alignment
                    # This matches the enhanced scheduler's logic for first-time scheduling
                    interval_seconds = row.trigger_interval
                    
                    # For hourly schedules (3600 seconds), apply offset_minutes
                    if interval_seconds == 3600 and row.offset_minutes is not None:
                        # Calculate next occurrence at offset minutes past the hour
                        offset_minutes = row.offset_minutes
                        
                        # Start from the current hour with offset
                        next_hour = current_time.replace(minute=offset_minutes, second=0, microsecond=0)
                        
                        # If this time has already passed, move to next hour
                        if next_hour <= current_time:
                            next_hour += timedelta(hours=1)
                        
                        next_dose_time = next_hour
                    else:
                        # For non-hourly intervals, start from current time + interval
                        next_dose_time = current_time + timedelta(seconds=interval_seconds)
                
                # Keep calculating next dose times until we find a future one (skip missed doses)
                while next_dose_time <= current_time:
                    next_dose_time += timedelta(seconds=row.trigger_interval)
            
            dose_data = {
                'schedule_id': row.schedule_id,
                'tank_id': row.tank_id,
                'product_id': row.product_id,
                'amount': row.amount,
                'trigger_interval': row.trigger_interval,
                'product_name': row.product_name,
                'current_avail': row.current_avail,
                'last_dose_time': last_dose_time.isoformat() if last_dose_time else None,
                'next_dose_time': next_dose_time.isoformat(),
                'offset_minutes': row.offset_minutes  # Include offset_minutes for debugging
            }
            scheduled_doses.append(dose_data)
        
        # Sort by next dose time and return the next 3
        scheduled_doses.sort(key=lambda x: x['next_dose_time'])
        next_three_doses = scheduled_doses[:3]
        
        return jsonify({
            "success": True,
            "data": next_three_doses,
            "count": len(next_three_doses)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/test/stats/<int:tank_id>', methods=['GET'])
def test_schedule_stats(tank_id):
    """Test endpoint to set tank_id and get schedule stats for testing purposes"""
    from modules.system_context import set_tank_id_for_testing
    
    # Set the tank_id for testing (backward compatibility function)
    set_tank_id_for_testing(tank_id)
    
    # Call the regular stats endpoint
    return get_schedule_stats()

@bp.route('/test/history/<int:tank_id>', methods=['GET'])
def test_dosing_history(tank_id):
    """Test endpoint to set tank_id and get dosing history for testing purposes"""
    from modules.system_context import set_tank_id_for_testing
    
    # Set the tank_id for testing (backward compatibility function)
    set_tank_id_for_testing(tank_id)
    
    # Call the regular history endpoint
    return get_dosing_history()

@bp.route('/test/next-doses/<int:tank_id>', methods=['GET'])
def test_next_doses(tank_id):
    """Test endpoint to set tank_id and get next doses for testing purposes"""
    from modules.system_context import set_tank_id_for_testing
    
    # Set the tank_id for testing (backward compatibility function)
    set_tank_id_for_testing(tank_id)
    
    # Call the regular next doses endpoint
    return get_next_doses()
