from flask import Blueprint, jsonify, current_app
from app import db
from datetime import datetime, timedelta
from sqlalchemy import text
import pytz

bp = Blueprint('product_api', __name__)

@bp.route('/get/product_stats', methods=['GET'])
def get_product_stats():
    sql = """
        SELECT     
            products.id as product_id,      
            products.name, 
            products.total_volume,
            products.used_amt,
            products.dry_refill,
            products.current_avail,
            d_schedule.amount as set_amount,
            d_schedule.last_refill,
            d_schedule.suspended,
            d_schedule.trigger_interval 
        FROM products 
        LEFT JOIN d_schedule ON products.id = d_schedule.prod_id
    """
    result = db.session.execute(text(sql))
    rows = result.fetchall()
    columns = result.keys()
    units = {
        'total_volume': 'ml',
        'used_amt': 'ml',
        'dry_refill': 'g|ml',
        'current_avail': 'ml',
        'set_amount': 'ml',
        'last_refill': '',
        'suspended': '',
        'trigger_interval': 's',
        'amount': 'ml'
    }
    stats = []
    date_keys = {'last_refill', 'estimated_empty_datetime', 'trigger_time'}
    # Get timezone from app config
    tzname = current_app.config.get('TIMEZONE', 'UTC')
    tz = pytz.timezone(tzname)
    for row in rows:
        row_dict = dict(zip(columns, row))
        stat = {}
        stat['card_title'] = ['Product Name', row_dict.get('name'), row_dict.get('id')]
        for key in columns:
            label = key.replace('_', ' ').title()
            value = row_dict.get(key)
            unit = units.get(key, '')
            if key == 'suspended' and value is not None:
                value = bool(value)
            if key in date_keys and value:
                try:
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    # Only convert if dt is naive and you know it's UTC
                    # If your DB stores local time, do NOT convert
                    value = dt.strftime('%b %d %Y %H:%M:%S %Z')
                except Exception:
                    pass
            stat[key] = [label, value, unit]
        if row_dict.get('schedule_id'):
            dosing_sql = """
                SELECT 
                    amount, trigger_time
                FROM dosing
                WHERE sched_id = :sched_id
                ORDER BY trigger_time DESC
                LIMIT 1
            """
            dosing_result = db.session.execute(
                text(dosing_sql), {'sched_id': row_dict['schedule_id']}
            ).fetchone()
            dosing_columns = ['dose_amount', 'trigger_time']
            dosing_units = {
                'dose_amount': 'ml',
                'trigger_time': ''
            }
            if dosing_result:
                for k, v in zip(dosing_columns, dosing_result):
                    if k == 'trigger_time' and v:
                        try:
                            if isinstance(v, str):
                                dt = datetime.fromisoformat(v)
                            else:
                                dt = v
                            if dt.tzinfo is None:
                                dt = pytz.utc.localize(dt)
                            dt = dt.astimezone(tz)
                            v = dt.strftime('%b %d %Y %H:%M:%S')
                        except Exception:
                            pass
                    stat[k] = [k.replace('_', ' ').title(), v, dosing_units.get(k, '')]
            else:
                for k in dosing_columns:
                    stat[k] = [k.replace('_', ' ').title(), None, dosing_units.get(k, '')]
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
                estimated_empty_datetime = (
                    datetime.utcnow() + timedelta(days=days_until_empty)
                )
                # Localize and convert to configured timezone
                # estimated_empty_datetime = pytz.utc.localize(estimated_empty_datetime).astimezone(tz)
                stat['estimated_empty_datetime'] = [
                    'Estimated Empty Date',
                    estimated_empty_datetime.strftime('%b %d %Y %H:%M:%S'),
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
    return jsonify(stats)
