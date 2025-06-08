#!/usr/bin/env python3
"""
Calendar-based Audit API for ReefDB - Calendar view of dose events

Provides calendar-focused endpoints for displaying daily dose counts
and detailed drill-down information for specific dates.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, date
from sqlalchemy import text, func
import calendar
from app import db
from modules.tank_context import get_current_tank_id
from modules.timezone_utils import datetime_to_iso_format

bp = Blueprint('audit_calendar_api', __name__)

def calculate_next_refill_estimate(product_id, tank_id, current_avail, total_volume):
    """Calculate estimated next refill date based on consumption patterns"""
    try:
        # Get recent consumption data (last 30 days)
        sql = """
            SELECT AVG(daily_consumption) as avg_daily_consumption
            FROM (
                SELECT DATE(d.trigger_time) as dose_date, SUM(d.amount) as daily_consumption
                FROM dosing d
                LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
                WHERE d.product_id = :product_id 
                    AND ds.tank_id = :tank_id
                    AND d.trigger_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY DATE(d.trigger_time)
            ) daily_totals
        """
        
        result = db.session.execute(text(sql), {
            'product_id': product_id,
            'tank_id': tank_id
        }).fetchone()
        
        if not result or not result.avg_daily_consumption or result.avg_daily_consumption <= 0:
            return None
        
        avg_daily_consumption = float(result.avg_daily_consumption)
        
        # Calculate days until refill needed (when current_avail reaches 10% of total_volume)
        refill_threshold = total_volume * 0.1  # Refill when 10% remaining
        if current_avail <= refill_threshold:
            return date.today()  # Need refill now
        
        days_until_refill = (current_avail - refill_threshold) / avg_daily_consumption
        
        if days_until_refill > 0:
            return date.today() + timedelta(days=int(days_until_refill))
        else:
            return date.today()
            
    except Exception as e:
        print(f"Error calculating next refill estimate: {e}")
        return None

def get_refill_events_for_month(tank_id, month_start, month_end):
    """Get refill events and estimates for the given month"""
    refill_events = {}
    
    # Get historical refill events (when last_refill falls within the month)
    sql = """
        SELECT 
            DATE(ds.last_refill) as refill_date,
            p.id as product_id,
            p.name as product_name,
            ds.last_refill,
            p.current_avail,
            p.total_volume
        FROM d_schedule ds
        JOIN products p ON ds.product_id = p.id
        WHERE ds.tank_id = :tank_id
            AND ds.last_refill IS NOT NULL
            AND DATE(ds.last_refill) >= :month_start
            AND DATE(ds.last_refill) <= :month_end
        GROUP BY DATE(ds.last_refill), p.id
        ORDER BY ds.last_refill
    """
    
    result = db.session.execute(text(sql), {
        'tank_id': tank_id,
        'month_start': month_start,
        'month_end': month_end
    })
    
    for row in result:
        refill_date_str = row.refill_date.isoformat()
        
        if refill_date_str not in refill_events:
            refill_events[refill_date_str] = {
                'refills': [],
                'estimates': []
            }
        
        refill_events[refill_date_str]['refills'].append({
            'product_id': row.product_id,
            'product_name': row.product_name,
            'refill_time': row.last_refill.isoformat() if row.last_refill else None,
            'current_avail': row.current_avail,
            'total_volume': row.total_volume
        })
    
    # Get next refill estimates for all products with schedules in this tank
    sql = """
        SELECT DISTINCT
            p.id as product_id,
            p.name as product_name,
            p.current_avail,
            p.total_volume
        FROM d_schedule ds
        JOIN products p ON ds.product_id = p.id
        WHERE ds.tank_id = :tank_id
            AND p.current_avail IS NOT NULL
            AND p.total_volume IS NOT NULL
    """
    
    result = db.session.execute(text(sql), {'tank_id': tank_id})
    
    for row in result:
        next_refill_date = calculate_next_refill_estimate(
            row.product_id, tank_id, row.current_avail, row.total_volume
        )
        
        if (next_refill_date and 
            next_refill_date >= month_start and 
            next_refill_date <= month_end):
            
            refill_date_str = next_refill_date.isoformat()
            
            if refill_date_str not in refill_events:
                refill_events[refill_date_str] = {
                    'refills': [],
                    'estimates': []
                }
            
            refill_events[refill_date_str]['estimates'].append({
                'product_id': row.product_id,
                'product_name': row.product_name,
                'estimated_date': next_refill_date.isoformat(),
                'current_avail': row.current_avail,
                'total_volume': row.total_volume,
                'low_threshold': row.total_volume * 0.1
            })
    
    return refill_events

@bp.route('/calendar/monthly-summary', methods=['GET'])
def get_monthly_summary():
    """Get monthly calendar summary showing daily dose counts per product"""
    tank_id = get_current_tank_id()
    if not tank_id:
        return jsonify({
            "success": False,
            "error": "No tank selected",
            "data": {}
        }), 400
    
    # Get month/year parameters (default to current month)
    try:
        year = int(request.args.get('year', datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Invalid year or month parameter"
        }), 400
    
    # Validate month/year
    if month < 1 or month > 12:
        return jsonify({
            "success": False,
            "error": "Month must be between 1 and 12"
        }), 400
    
    if year < 2020 or year > 2030:
        return jsonify({
            "success": False,
            "error": "Year must be between 2020 and 2030"
        }), 400
    
    try:
        # Calculate month boundaries
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        
        # Query for daily dose counts per product
        sql = """
            SELECT 
                DATE(d.trigger_time) as dose_date,
                p.id as product_id,
                p.name as product_name,
                p.uses as product_uses,
                COUNT(*) as dose_count,
                SUM(d.amount) as total_amount,
                AVG(d.amount) as avg_amount,
                MIN(d.trigger_time) as first_dose_time,
                MAX(d.trigger_time) as last_dose_time
            FROM dosing d
            LEFT JOIN products p ON d.product_id = p.id
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            WHERE ds.tank_id = :tank_id
                AND DATE(d.trigger_time) >= :month_start
                AND DATE(d.trigger_time) <= :month_end
            GROUP BY DATE(d.trigger_time), p.id, p.name, p.uses
            ORDER BY dose_date, p.name
        """
        
        result = db.session.execute(text(sql), {
            'tank_id': tank_id,
            'month_start': month_start,
            'month_end': month_end
        })
        
        # Organize data by date
        calendar_data = {}
        product_totals = {}
        
        for row in result:
            dose_date_str = row.dose_date.isoformat()
            
            if dose_date_str not in calendar_data:
                calendar_data[dose_date_str] = {
                    'date': dose_date_str,
                    'total_doses': 0,
                    'total_volume': 0,
                    'products': {},
                    'product_count': 0
                }
            
            calendar_data[dose_date_str]['total_doses'] += row.dose_count
            calendar_data[dose_date_str]['total_volume'] += row.total_amount
            calendar_data[dose_date_str]['products'][row.product_name] = {
                'product_id': row.product_id,
                'product_name': row.product_name,
                'product_uses': row.product_uses,
                'dose_count': row.dose_count,
                'total_amount': row.total_amount,
                'avg_amount': round(row.avg_amount, 1),
                'first_dose_time': row.first_dose_time.isoformat() if row.first_dose_time else None,
                'last_dose_time': row.last_dose_time.isoformat() if row.last_dose_time else None
            }
            calendar_data[dose_date_str]['product_count'] = len(calendar_data[dose_date_str]['products'])
            
            # Track product totals for the month
            if row.product_name not in product_totals:
                product_totals[row.product_name] = {
                    'product_id': row.product_id,
                    'product_name': row.product_name,
                    'product_uses': row.product_uses,
                    'total_doses': 0,
                    'total_volume': 0,
                    'days_active': 0
                }
            
            product_totals[row.product_name]['total_doses'] += row.dose_count
            product_totals[row.product_name]['total_volume'] += row.total_amount
            product_totals[row.product_name]['days_active'] += 1
        
        # Get refill events for the month
        refill_events = get_refill_events_for_month(tank_id, month_start, month_end)
        
        # Calculate month summary statistics
        total_doses_month = sum(day['total_doses'] for day in calendar_data.values())
        total_volume_month = sum(day['total_volume'] for day in calendar_data.values())
        active_days = len(calendar_data)
        avg_doses_per_day = round(total_doses_month / max(active_days, 1), 1)
        
        return jsonify({
            "success": True,
            "data": {
                "calendar": calendar_data,
                "refill_events": refill_events,
                "summary": {
                    "year": year,
                    "month": month,
                    "month_name": calendar.month_name[month],
                    "total_doses": total_doses_month,
                    "total_volume": round(total_volume_month, 1),
                    "active_days": active_days,
                    "avg_doses_per_day": avg_doses_per_day,
                    "products": list(product_totals.values())
                },
                "tank_id": tank_id
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve calendar data: {str(e)}",
            "data": {}
        }), 500


@bp.route('/calendar/day-details', methods=['GET'])
def get_day_details():
    """Get detailed dose information for a specific date with timing and amounts"""
    tank_id = get_current_tank_id()
    if not tank_id:
        return jsonify({
            "success": False,
            "error": "No tank selected",
            "data": {}
        }), 400
    
    # Get date parameter
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({
            "success": False,
            "error": "Date parameter is required (YYYY-MM-DD format)"
        }), 400
    
    try:
        # Parse and validate date
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    
    try:
        # Query for detailed dose information for the specific date
        sql = """
            SELECT 
                d.id,
                d.trigger_time,
                d.amount,
                d.product_id,
                d.schedule_id,
                p.name as product_name,
                p.uses as product_uses,
                p.current_avail,
                p.total_volume,
                ds.trigger_interval,
                ds.suspended as schedule_suspended,
                ds.amount as scheduled_amount,
                ds.doser_name,
                ds.missed_dose_handling,
                dosers.doser_name as doser_actual_name,
                dosers.doser_type as doser_type,
                -- Calculate interval since previous dose
                LAG(d.trigger_time) OVER (PARTITION BY d.schedule_id ORDER BY d.trigger_time) as previous_dose_time,
                -- Calculate dose efficiency
                ROUND((d.amount / NULLIF(ds.amount, 0)) * 100, 1) as dose_efficiency_percent
            FROM dosing d
            LEFT JOIN products p ON d.product_id = p.id
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            LEFT JOIN dosers ON ds.doser_id = dosers.id
            WHERE ds.tank_id = :tank_id
                AND DATE(d.trigger_time) = :selected_date
            ORDER BY d.trigger_time, p.name
        """
        
        result = db.session.execute(text(sql), {
            'tank_id': tank_id,
            'selected_date': selected_date
        })
        
        # Process detailed dose records
        doses = []
        products_summary = {}
        
        for row in result:
            # Calculate timing precision
            time_since_previous = None
            schedule_adherence = 'unknown'
            
            if row.previous_dose_time and row.trigger_interval:
                time_diff = row.trigger_time - row.previous_dose_time
                time_since_previous = int(time_diff.total_seconds())
                expected_interval = row.trigger_interval
                variance_percent = abs(time_since_previous - expected_interval) / expected_interval * 100
                
                if variance_percent <= 5:
                    schedule_adherence = 'on_time'
                elif variance_percent <= 15:
                    schedule_adherence = 'slightly_off'
                elif time_since_previous > expected_interval:
                    schedule_adherence = 'late'
                else:
                    schedule_adherence = 'early'
            
            dose_record = {
                'id': row.id,
                'trigger_time': row.trigger_time.isoformat() if row.trigger_time else None,
                'trigger_time_display': row.trigger_time.strftime('%H:%M:%S') if row.trigger_time else 'Unknown',
                'amount': row.amount,
                'scheduled_amount': row.scheduled_amount,
                'dose_efficiency_percent': row.dose_efficiency_percent,
                'product_id': row.product_id,
                'product_name': row.product_name,
                'product_uses': row.product_uses,
                'schedule_id': row.schedule_id,
                'doser_name': row.doser_actual_name or row.doser_name,
                'doser_type': row.doser_type,
                'schedule_adherence': schedule_adherence,
                'time_since_previous_minutes': round(time_since_previous / 60, 1) if time_since_previous else None,
                'trigger_interval_minutes': round(row.trigger_interval / 60, 1) if row.trigger_interval else None,
                'missed_dose_handling': row.missed_dose_handling,
                'schedule_suspended': bool(row.schedule_suspended)
            }
            
            doses.append(dose_record)
            
            # Update products summary
            if row.product_name not in products_summary:
                products_summary[row.product_name] = {
                    'product_id': row.product_id,
                    'product_name': row.product_name,
                    'product_uses': row.product_uses,
                    'dose_count': 0,
                    'total_amount': 0,
                    'avg_amount': 0,
                    'min_amount': float('inf'),
                    'max_amount': 0,
                    'first_dose_time': None,
                    'last_dose_time': None,
                    'schedule_adherence_summary': {
                        'on_time': 0,
                        'slightly_off': 0,
                        'late': 0,
                        'early': 0,
                        'unknown': 0
                    }
                }
            
            summary = products_summary[row.product_name]
            summary['dose_count'] += 1
            summary['total_amount'] += row.amount
            summary['min_amount'] = min(summary['min_amount'], row.amount)
            summary['max_amount'] = max(summary['max_amount'], row.amount)
            
            if not summary['first_dose_time'] or row.trigger_time < datetime.fromisoformat(summary['first_dose_time']):
                summary['first_dose_time'] = row.trigger_time.isoformat()
            if not summary['last_dose_time'] or row.trigger_time > datetime.fromisoformat(summary['last_dose_time']):
                summary['last_dose_time'] = row.trigger_time.isoformat()
            
            summary['schedule_adherence_summary'][schedule_adherence] += 1
        
        # Calculate averages for products summary
        for product in products_summary.values():
            if product['dose_count'] > 0:
                product['avg_amount'] = round(product['total_amount'] / product['dose_count'], 1)
                if product['min_amount'] == float('inf'):
                    product['min_amount'] = 0
        
        # Calculate day summary statistics
        total_doses = len(doses)
        total_volume = sum(dose['amount'] for dose in doses)
        unique_products = len(products_summary)
        
        # Get refill information for this specific date
        refill_info = {
            'refills': [],
            'estimates': []
        }
        
        # Check for historical refills on this date
        refill_sql = """
            SELECT 
                p.id as product_id,
                p.name as product_name,
                ds.last_refill,
                p.current_avail,
                p.total_volume
            FROM d_schedule ds
            JOIN products p ON ds.product_id = p.id
            WHERE ds.tank_id = :tank_id
                AND ds.last_refill IS NOT NULL
                AND DATE(ds.last_refill) = :selected_date
            GROUP BY p.id
        """
        
        refill_result = db.session.execute(text(refill_sql), {
            'tank_id': tank_id,
            'selected_date': selected_date
        })
        
        for row in refill_result:
            refill_info['refills'].append({
                'product_id': row.product_id,
                'product_name': row.product_name,
                'refill_time': row.last_refill.isoformat() if row.last_refill else None,
                'refill_time_display': row.last_refill.strftime('%H:%M:%S') if row.last_refill else 'Unknown',
                'current_avail': row.current_avail,
                'total_volume': row.total_volume
            })
        
        # Check for estimated refills on this date
        estimate_sql = """
            SELECT DISTINCT
                p.id as product_id,
                p.name as product_name,
                p.current_avail,
                p.total_volume
            FROM d_schedule ds
            JOIN products p ON ds.product_id = p.id
            WHERE ds.tank_id = :tank_id
                AND p.current_avail IS NOT NULL
                AND p.total_volume IS NOT NULL
        """
        
        estimate_result = db.session.execute(text(estimate_sql), {'tank_id': tank_id})
        
        for row in estimate_result:
            next_refill_date = calculate_next_refill_estimate(
                row.product_id, tank_id, row.current_avail, row.total_volume
            )
            
            if next_refill_date == selected_date:
                refill_info['estimates'].append({
                    'product_id': row.product_id,
                    'product_name': row.product_name,
                    'estimated_date': next_refill_date.isoformat(),
                    'current_avail': row.current_avail,
                    'total_volume': row.total_volume,
                    'low_threshold': row.total_volume * 0.1,
                    'days_remaining': 0  # It's today
                })
        
        return jsonify({
            "success": True,
            "data": {
                "date": selected_date.isoformat(),
                "doses": doses,
                "refill_info": refill_info,
                "products_summary": list(products_summary.values()),
                "day_summary": {
                    "total_doses": total_doses,
                    "total_volume": round(total_volume, 1),
                    "unique_products": unique_products,
                    "avg_dose_amount": round(total_volume / max(total_doses, 1), 1),
                    "first_dose_time": doses[0]['trigger_time'] if doses else None,
                    "last_dose_time": doses[-1]['trigger_time'] if doses else None
                },
                "tank_id": tank_id
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve day details: {str(e)}",
            "data": {}
        }), 500


@bp.route('/calendar/date-range-summary', methods=['GET'])
def get_date_range_summary():
    """Get dose summary for a custom date range (useful for weekly/bi-weekly views)"""
    tank_id = get_current_tank_id()
    if not tank_id:
        return jsonify({
            "success": False,
            "error": "No tank selected",
            "data": {}
        }), 400
    
    # Get date range parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not start_date_str or not end_date_str:
        return jsonify({
            "success": False,
            "error": "Both start_date and end_date parameters are required (YYYY-MM-DD format)"
        }), 400
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format. Use YYYY-MM-DD for both dates"
        }), 400
    
    if end_date < start_date:
        return jsonify({
            "success": False,
            "error": "End date must be after start date"
        }), 400
    
    # Limit range to prevent excessive queries
    if (end_date - start_date).days > 90:
        return jsonify({
            "success": False,
            "error": "Date range cannot exceed 90 days"
        }), 400
    
    try:
        # Query for date range summary
        sql = """
            SELECT 
                DATE(d.trigger_time) as dose_date,
                p.id as product_id,
                p.name as product_name,
                p.uses as product_uses,
                COUNT(*) as dose_count,
                SUM(d.amount) as total_amount,
                AVG(d.amount) as avg_amount,
                MIN(d.trigger_time) as first_dose_time,
                MAX(d.trigger_time) as last_dose_time
            FROM dosing d
            LEFT JOIN products p ON d.product_id = p.id
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            WHERE ds.tank_id = :tank_id
                AND DATE(d.trigger_time) >= :start_date
                AND DATE(d.trigger_time) <= :end_date
            GROUP BY DATE(d.trigger_time), p.id, p.name, p.uses
            ORDER BY dose_date, p.name
        """
        
        result = db.session.execute(text(sql), {
            'tank_id': tank_id,
            'start_date': start_date,
            'end_date': end_date
        })
        
        # Organize data similar to monthly summary
        range_data = {}
        
        for row in result:
            dose_date_str = row.dose_date.isoformat()
            
            if dose_date_str not in range_data:
                range_data[dose_date_str] = {
                    'date': dose_date_str,
                    'total_doses': 0,
                    'total_volume': 0,
                    'products': {},
                    'product_count': 0
                }
            
            range_data[dose_date_str]['total_doses'] += row.dose_count
            range_data[dose_date_str]['total_volume'] += row.total_amount
            range_data[dose_date_str]['products'][row.product_name] = {
                'product_id': row.product_id,
                'product_name': row.product_name,
                'product_uses': row.product_uses,
                'dose_count': row.dose_count,
                'total_amount': row.total_amount,
                'avg_amount': round(row.avg_amount, 1)
            }
            range_data[dose_date_str]['product_count'] = len(range_data[dose_date_str]['products'])
        
        return jsonify({
            "success": True,
            "data": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days_in_range": (end_date - start_date).days + 1,
                "range_data": range_data,
                "tank_id": tank_id
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve date range data: {str(e)}",
            "data": {}
        }), 500
