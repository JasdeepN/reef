#!/usr/bin/env python3
"""
Audit Log API for ReefDB - Enhanced dose event tracking and notifications

This module provides audit logging capabilities for dose events, missed doses,
and schedule changes with real-time activity feed support.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from sqlalchemy import text, desc, func
import logging
from app import db
from modules.models import Dosing, DSchedule, Products, Tank
from modules.system_context import get_current_system_id, get_current_system_tank_ids, ensure_system_context, force_system_context_for_vscode
from modules.timezone_utils import datetime_to_iso_format
import logging

bp = Blueprint('audit_api', __name__)

@bp.route('/dose-events', methods=['GET'])
def get_dose_events():
    """Get recent dose events for audit log with enhanced details"""
    # Force VS Code context first
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'vscode' in user_agent or 'simple browser' in user_agent:
        from flask import session
        from modules.models import TankSystem
        try:
            if not session.get('system_id'):
                first_system = TankSystem.query.first()
                if first_system:
                    session['system_id'] = first_system.id
                    session.permanent = True
        except Exception as e:
            session['system_id'] = 4  # Fallback to known system
    
    system_id = ensure_system_context()
    if not system_id:
        return jsonify({
            "success": False,
            "error": "No system selected",
                "data": []
            }), 400
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        return jsonify({
            "success": False,
            "error": "No tanks found for system",
            "data": []
        }), 400
    
    # Get pagination parameters
    limit = min(int(request.args.get('limit', 50)), 200)  # Max 200 events
    offset = max(int(request.args.get('offset', 0)), 0)
    days_back = min(int(request.args.get('days', 7)), 30)  # Max 30 days
    
    # Calculate time window
    start_date = datetime.now() - timedelta(days=days_back)
    
    try:
        # Enhanced query for dose events with comprehensive details
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
                ds.missed_dose_handling,
                ds.amount as scheduled_amount,
                t.name as tank_name,
                ds.doser_id as doser_id,
                ds.doser_name as doser_name,
                dosers.doser_name as doser_actual_name,
                dosers.doser_type as doser_type,
                -- Calculate dose efficiency
                ROUND((d.amount / NULLIF(ds.amount, 0)) * 100, 1) as dose_efficiency_percent,
                -- Calculate time since last dose
                LAG(d.trigger_time) OVER (PARTITION BY d.schedule_id ORDER BY d.trigger_time) as previous_dose_time,
                -- Calculate product usage rate
                ROUND(p.current_avail / NULLIF(p.total_volume, 0) * 100, 1) as product_remaining_percent
            FROM dosing d
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            LEFT JOIN products p ON d.product_id = p.id
            LEFT JOIN tanks t ON ds.tank_id = t.id
            LEFT JOIN dosers ON ds.doser_id = dosers.id
            WHERE ds.tank_id IN :tank_ids
                AND d.trigger_time >= :start_date
            ORDER BY d.trigger_time DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = db.session.execute(text(sql), {
            'tank_ids': tuple(tank_ids),
            'start_date': start_date,
            'limit': limit,
            'offset': offset
        })
        
        dose_events = []
        for row in result:
            # Calculate time intervals
            time_since_previous = None
            if row.previous_dose_time and row.trigger_time:
                time_diff = row.trigger_time - row.previous_dose_time
                time_since_previous = int(time_diff.total_seconds())
            
            # Calculate schedule adherence
            schedule_adherence = 'on_time'
            offset_seconds = None
            if time_since_previous and row.trigger_interval:
                expected_interval = row.trigger_interval
                actual_interval = time_since_previous
                offset_seconds = actual_interval - expected_interval
                variance_percent = abs(actual_interval - expected_interval) / expected_interval * 100
                
                if variance_percent > 25:
                    schedule_adherence = 'late' if actual_interval > expected_interval else 'early'
                elif variance_percent > 10:
                    schedule_adherence = 'slightly_off'
            
            # Determine event status
            event_status = 'success'
            if row.schedule_suspended:
                event_status = 'warning'
            elif row.dose_efficiency_percent and row.dose_efficiency_percent < 80:
                event_status = 'partial'
            elif row.product_remaining_percent and row.product_remaining_percent < 10:
                event_status = 'low_product'
            
            # Calculate next scheduled dose time
            next_scheduled_time = None
            if row.trigger_time and row.trigger_interval:
                next_scheduled_time = row.trigger_time + timedelta(seconds=row.trigger_interval)
            
            # Hour of day for this dose
            dose_hour = row.trigger_time.hour if row.trigger_time else None
            
            # Build comprehensive message
            msg_parts = []
            if row.trigger_time:
                msg_parts.append(f"Dose triggered at {datetime_to_iso_format(row.trigger_time)}")
            # Calculate offset string for schedule adherence
            if offset_seconds is not None:
                if offset_seconds == 0:
                    offset_str = "on time"
                else:
                    mins = abs(offset_seconds) // 60
                    offset_str = f"{mins} min {'late' if offset_seconds > 0 else 'early'}"
            else:
                offset_str = None
            if time_since_previous and row.trigger_interval:
                if offset_str:
                    msg_parts.append(f"Scheduled interval: {row.trigger_interval//60} min, actual: {time_since_previous//60} min ({offset_str})")
                else:
                    msg_parts.append(f"Scheduled interval: {row.trigger_interval//60} min, actual: {time_since_previous//60} min")
            if next_scheduled_time:
                msg_parts.append(f"Next scheduled: {datetime_to_iso_format(next_scheduled_time)}")
            if dose_hour is not None:
                msg_parts.append(f"Dose hour: {dose_hour:02d}:00")
            if row.doser_actual_name or row.doser_name:
                msg_parts.append(f"Doser: {row.doser_actual_name or row.doser_name}")
            comprehensive_message = "; ".join(msg_parts)
            
            dose_event = {
                'id': row.id,
                'type': 'dose_executed',
                'timestamp': row.trigger_time.isoformat() if row.trigger_time else None,
                'title': f"Dosed {row.product_name}",
                'description': f"{row.amount}ml administered",
                'status': event_status,
                'details': {
                    'product_id': row.product_id,
                    'product_name': row.product_name,
                    'product_uses': row.product_uses,
                    'amount': row.amount,
                    'scheduled_amount': row.scheduled_amount,
                    'schedule_id': row.schedule_id,
                    'tank_name': row.tank_name,
                    'dose_efficiency_percent': row.dose_efficiency_percent,
                    'product_remaining_percent': row.product_remaining_percent,
                    'time_since_previous_hours': round(time_since_previous / 3600, 1) if time_since_previous else None,
                    'schedule_adherence': schedule_adherence,
                    'missed_dose_handling': row.missed_dose_handling,
                    'doser_id': row.doser_id,
                    'doser_name': row.doser_actual_name or row.doser_name,
                    'doser_type': row.doser_type,
                    'offset_seconds': offset_seconds,
                    'next_scheduled_time': next_scheduled_time.isoformat() if next_scheduled_time else None,
                    'dose_hour': dose_hour,
                    'comprehensive_message': comprehensive_message
                },
                'metadata': {
                    'current_avail': row.current_avail,
                    'total_volume': row.total_volume,
                    'trigger_interval': row.trigger_interval,
                    'schedule_suspended': row.schedule_suspended
                }
            }
            dose_events.append(dose_event)
        
        # Get missed dose events for the same period
        missed_dose_events = get_missed_dose_events(tank_ids, start_date, limit//2)
        
        # Combine and sort all events
        all_events = dose_events + missed_dose_events
        all_events.sort(key=lambda x: x['timestamp'] or '1970-01-01', reverse=True)
        
        # Get summary statistics
        stats = get_audit_summary(tank_ids, days_back)
        
        return jsonify({
            "success": True,
            "data": {
                "events": all_events[:limit],
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": len(all_events) >= limit
                },
                "summary": stats,
                "filter": {
                    "tank_ids": tank_ids,
                    "days_back": days_back,
                    "start_date": start_date.isoformat()
                }
            }
        })
        
    except Exception:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve dose events.",
            "data": []
        }), 500

def get_missed_dose_events(tank_ids: list, start_date: datetime, limit: int) -> list:
    """Get missed dose events for the audit log"""
    try:
        sql = """
            SELECT 
                mdr.id,
                mdr.missed_dose_time,
                mdr.detected_time,
                mdr.hours_missed,
                mdr.status,
                mdr.approved_by,
                mdr.approved_time,
                mdr.notes,
                ds.id as schedule_id,
                p.name as product_name,
                ds.amount as scheduled_amount,
                ds.missed_dose_handling,
                t.name as tank_name
            FROM missed_dose_requests mdr
            LEFT JOIN d_schedule ds ON mdr.schedule_id = ds.id
            LEFT JOIN products p ON ds.product_id = p.id
            LEFT JOIN tanks t ON ds.tank_id = t.id
            WHERE ds.tank_id IN :tank_ids
                AND mdr.detected_time >= :start_date
            ORDER BY mdr.detected_time DESC
            LIMIT :limit
        """
        
        result = db.session.execute(text(sql), {
            'tank_ids': tuple(tank_ids),
            'start_date': start_date,
            'limit': limit
        })
        
        missed_events = []
        for row in result:
            # Determine event status based on missed dose status
            event_status = {
                'pending': 'warning',
                'approved': 'success',
                'rejected': 'error',
                'expired': 'error',
                'auto_dosed': 'info'
            }.get(row.status, 'warning')
            
            missed_event = {
                'id': f"missed_{row.id}",
                'type': 'missed_dose',
                'timestamp': row.detected_time.isoformat() if row.detected_time else None,
                'title': f'Missed Dose: {row.product_name}',
                'description': f'{row.hours_missed:.1f}h overdue - {row.status.replace("_", " ").title()}',
                'status': event_status,
                'details': {
                    'missed_dose_id': row.id,
                    'product_name': row.product_name,
                    'scheduled_amount': row.scheduled_amount,
                    'schedule_id': row.schedule_id,
                    'tank_name': row.tank_name,
                    'hours_missed': row.hours_missed,
                    'missed_dose_time': row.missed_dose_time.isoformat() if row.missed_dose_time else None,
                    'status': row.status,
                    'approved_by': row.approved_by,
                    'approved_time': row.approved_time.isoformat() if row.approved_time else None,
                    'notes': row.notes,
                    'missed_dose_handling': row.missed_dose_handling
                },
                'metadata': {
                    'requires_action': row.status == 'pending'
                }
            }
            missed_events.append(missed_event)
        
        return missed_events
        
    except Exception as e:
        # Return empty list on error, don't fail the main request
        return []

def get_audit_summary(tank_ids: list, days_back: int) -> dict:
    """Get summary statistics for the audit period"""
    try:
        start_date = datetime.now() - timedelta(days=days_back)
        
        # Get dose statistics
        dose_stats_sql = """
            SELECT 
                COUNT(*) as total_doses,
                COUNT(DISTINCT d.schedule_id) as active_schedules,
                SUM(d.amount) as total_volume_dosed,
                AVG(d.amount) as avg_dose_amount,
                COUNT(DISTINCT d.product_id) as products_dosed
            FROM dosing d
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            WHERE ds.tank_id IN :tank_ids
                AND d.trigger_time >= :start_date
        """
        
        result = db.session.execute(text(dose_stats_sql), {
            'tank_ids': tuple(tank_ids),
            'start_date': start_date
        }).fetchone()
        
        # Get missed dose statistics
        missed_stats_sql = """
            SELECT 
                COUNT(*) as total_missed,
                COUNT(CASE WHEN mdr.status = 'pending' THEN 1 END) as pending_approval,
                COUNT(CASE WHEN mdr.status = 'approved' THEN 1 END) as approved,
                COUNT(CASE WHEN mdr.status = 'rejected' THEN 1 END) as rejected
            FROM missed_dose_requests mdr
            LEFT JOIN d_schedule ds ON mdr.schedule_id = ds.id
            WHERE ds.tank_id IN :tank_ids
                AND mdr.detected_time >= :start_date
        """
        
        missed_result = db.session.execute(text(missed_stats_sql), {
            'tank_ids': tuple(tank_ids),
            'start_date': start_date
        }).fetchone()
        
        # Calculate success rate
        total_expected = (result.total_doses or 0) + (missed_result.total_missed or 0)
        success_rate = round((result.total_doses or 0) / max(total_expected, 1) * 100, 1)
        
        return {
            'period_days': days_back,
            'total_doses': result.total_doses or 0,
            'total_volume_dosed': round(result.total_volume_dosed or 0, 2),
            'avg_dose_amount': round(result.avg_dose_amount or 0, 2),
            'active_schedules': result.active_schedules or 0,
            'products_dosed': result.products_dosed or 0,
            'missed_doses': {
                'total': missed_result.total_missed or 0,
                'pending': missed_result.pending_approval or 0,
                'approved': missed_result.approved or 0,
                'rejected': missed_result.rejected or 0
            },
            'success_rate_percent': success_rate,
            'performance_rating': get_performance_rating(success_rate)
        }
        
    except Exception as e:
        return {
            'error': f"Failed to calculate summary: {str(e)}",
            'period_days': days_back,
            'total_doses': 0,
            'total_volume_dosed': 0,
            'success_rate_percent': 0,
            'performance_rating': 'unknown'
        }

def get_performance_rating(success_rate: float) -> str:
    """Get performance rating based on success rate"""
    if success_rate >= 95:
        return 'excellent'
    elif success_rate >= 85:
        return 'good'
    elif success_rate >= 70:
        return 'fair'
    else:
        return 'needs_improvement'

@bp.route('/dose-events/recent', methods=['GET'])
def get_recent_dose_events():
    """Get the most recent dose events for real-time updates"""
    # Force VS Code context first
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'vscode' in user_agent or 'simple browser' in user_agent:
        from flask import session
        from modules.models import TankSystem
        try:
            if not session.get('system_id'):
                first_system = TankSystem.query.first()
                if first_system:
                    session['system_id'] = first_system.id
                    session.permanent = True
        except Exception as e:
            session['system_id'] = 4  # Fallback to known system
    
    system_id = ensure_system_context()
    if not system_id:
        return jsonify({
            "success": False,
            "error": "No system selected",
            "data": []
        }), 400
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        return jsonify({
            "success": False,
            "error": "No tanks found for system",
            "data": []
        }), 400
    
    # Get only the last 5 events from the past hour
    since = datetime.now() - timedelta(hours=1)
    limit = 5
    
    try:
        sql = """
            SELECT 
                d.id,
                d.trigger_time,
                d.amount,
                p.name as product_name,
                ds.id as schedule_id,
                'dose_executed' as event_type
            FROM dosing d
            LEFT JOIN d_schedule ds ON d.schedule_id = ds.id
            LEFT JOIN products p ON d.product_id = p.id
            WHERE ds.tank_id IN :tank_ids
                AND d.trigger_time >= :since
            ORDER BY d.trigger_time DESC
            LIMIT :limit
        """
        
        result = db.session.execute(text(sql), {
            'tank_ids': tuple(tank_ids),
            'since': since,
            'limit': limit
        })
        
        recent_events = []
        for row in result:
            recent_events.append({
                'id': row.id,
                'type': row.event_type,
                'timestamp': row.trigger_time.isoformat() if row.trigger_time else None,
                'title': f'Dosed {row.product_name}',
                'amount': row.amount,
                'schedule_id': row.schedule_id
            })
        
        return jsonify({
            "success": True,
            "data": recent_events
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve recent events: {str(e)}",
            "data": []
        }), 500

@bp.route('/schedule-changes', methods=['GET'])
def get_schedule_changes():
    """Get recent schedule changes for audit tracking"""
    # Force VS Code context first
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'vscode' in user_agent or 'simple browser' in user_agent:
        from flask import session
        from modules.models import TankSystem
        try:
            if not session.get('system_id'):
                first_system = TankSystem.query.first()
                if first_system:
                    session['system_id'] = first_system.id
                    session.permanent = True
        except Exception as e:
            session['system_id'] = 4  # Fallback to known system
    
    system_id = ensure_system_context()
    if not system_id:
        return jsonify({
            "success": False,
            "error": "No system selected",
            "data": []
        }), 400
    
    tank_ids = get_current_system_tank_ids()
    if not tank_ids:
        return jsonify({
            "success": False,
            "error": "No tanks found for system",
            "data": []
        }), 400
    
    days_back = min(int(request.args.get('days', 7)), 30)
    start_date = datetime.now() - timedelta(days=days_back)
    
    try:
        # Get recently modified schedules
        sql = """
            SELECT 
                ds.id,
                ds.created_at,
                ds.updated_at,
                ds.suspended,
                ds.amount,
                ds.trigger_interval,
                p.name as product_name,
                t.name as tank_name,
                CASE 
                    WHEN ds.created_at >= :start_date THEN 'created'
                    WHEN ds.updated_at >= :start_date THEN 'modified'
                    ELSE 'unknown'
                END as change_type
            FROM d_schedule ds
            LEFT JOIN products p ON ds.product_id = p.id
            LEFT JOIN tanks t ON ds.tank_id = t.id
            WHERE ds.tank_id IN :tank_ids
                AND (ds.created_at >= :start_date OR ds.updated_at >= :start_date)
            ORDER BY COALESCE(ds.updated_at, ds.created_at) DESC
        """
        
        result = db.session.execute(text(sql), {
            'tank_ids': tuple(tank_ids),
            'start_date': start_date
        })
        
        schedule_changes = []
        for row in result:
            change_time = row.updated_at or row.created_at
            
            schedule_change = {
                'id': f"schedule_{row.id}_{change_time.timestamp()}",
                'type': 'schedule_change',
                'timestamp': change_time.isoformat() if change_time else None,
                'title': f'Schedule {row.change_type.title()}: {row.product_name}',
                'description': f'{row.amount}ml every {format_interval(row.trigger_interval)}',
                'status': 'warning' if row.suspended else 'info',
                'details': {
                    'schedule_id': row.id,
                    'product_name': row.product_name,
                    'tank_name': row.tank_name,
                    'change_type': row.change_type,
                    'amount': row.amount,
                    'trigger_interval': row.trigger_interval,
                    'suspended': row.suspended
                }
            }
            schedule_changes.append(schedule_change)
        
        return jsonify({
            "success": True,
            "data": schedule_changes
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve schedule changes: {str(e)}",
            "data": []
        }), 500

@bp.route('/scheduler-event', methods=['POST'])
def log_scheduler_event():
    """Receive and log scheduler events for audit tracking"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Extract event data
        event_type = data.get('event_type', 'unknown')
        schedule_id = data.get('schedule_id')
        tank_id = data.get('tank_id')
        message = data.get('message', '')
        
        # Log to application logger for immediate visibility
        logger = logging.getLogger('dosing_scheduler.audit')
        logger.info(f"[{event_type}] Tank {tank_id}, Schedule {schedule_id}: {message}")
        
        return jsonify({
            "success": True,
            "message": "Scheduler event logged successfully"
        }), 201
        
    except Exception:
        logger = logging.getLogger('dosing_scheduler.audit')
        logger.error("Error logging scheduler event")
        return jsonify({
            "success": False,
            "error": "Failed to log scheduler event"
        }), 500

def format_interval(seconds: int) -> str:
    """Format interval seconds into human readable string"""
    if not seconds:
        return "unknown"
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else f"{seconds}s"
