from flask import Blueprint, jsonify
from app import db
from datetime import datetime, timedelta
from sqlalchemy import text

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
    # Define units for each field (add or adjust as needed)
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
    for row in rows:
        row_dict = dict(zip(columns, row))
        stat = {}
        # Always include product name for card title
        stat['card_title'] = ['Product Name', row_dict.get('name'), row_dict.get('id')]
        for key in columns:
            label = key.replace('_', ' ').title()
            value = row_dict.get(key)
            unit = units.get(key, '')
            # Convert suspended to boolean for display
            if key == 'suspended' and value is not None:
                value = bool(value)
            stat[key] = [label, value, unit]
        # If schedule_id exists, get related dosing data
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
                    stat[k] = [k.replace('_', ' ').title(), v, dosing_units.get(k, '')]
            else:
                for k in dosing_columns:
                    stat[k] = [k.replace('_', ' ').title(), None, dosing_units.get(k, '')]
        # Calculated fields
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
                ).isoformat()
                stat['estimated_empty_datetime'] = ['Estimated Empty Date', estimated_empty_datetime, '']
            else:
                stat['days_until_empty'] = ['Days Until Empty', None, 'days']
                stat['estimated_empty_datetime'] = ['Estimated Empty Date', None, '']
        except Exception:
            stat['percent_remaining'] = ['% Remaining', None, '%']
            stat['doses_remaining'] = ['Doses Remaining', None, 'doses']
            stat['days_until_empty'] = ['Days Until Empty', None, 'days']
            stat['estimated_empty_datetime'] = ['Estimated Empty Date', None, '']
        
        stat.pop('name', None)  # Remove name from the stat dictionary
        stats.append(stat)
    return jsonify(stats)
