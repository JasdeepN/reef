from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from app import db
from modules.models import DSchedule, Products, Dosing
from modules.utils.helper import datatables_response
from sqlalchemy import text
import pytz

bp = Blueprint('schedule_api', __name__, url_prefix='/schedule')

@bp.route('/get/all', methods=['GET'])
def get_sched():
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
            Products.name
        )
        .join(Products, Products.id == DSchedule.prod_id)
        .all()
    )
    data = [
        {
            "id": row[0],
            "trigger_interval": row[1],
            "amount": row[2],
            "suspended": bool(row[3]),
            "current_avail": row[4],
            "total_volume": row[5],
            "name": row[6]
        }
        for row in rows
    ]
    response = datatables_response(data, params, draw)
    return jsonify(response)

# @bp.route('/scheduler/new/dose/<schedule_id>', methods=['POST'])
# def add_dosing_entry(schedule_id):
   
#     if not schedule_id:
#         return jsonify({'error': 'schedule_id is required'}), 400
    
#     # Get the product by ID
#     sched = DSchedule.query.get(schedule_id)

#     # Create new dosing entry
#     new_dosing = Dosing(
#         prod_id=sched.prod_id,
#         sched_id=sched.id,
#         amount=sched.amount,
#         trigger_time=datetime.utcnow()
#     )
#     db.session.add(new_dosing)
#     db.session.commit()
#     return ({'success': True, 'added': new_dosing.id}), 201


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
    sql = """
        SELECT 
            products.id as product_id,
            products.name, 
            products.total_volume,
            products.used_amt,
            products.total_volume,
            products.dry_refill,
            products.current_avail,
            d_schedule.id as schedule_id,
            d_schedule.amount as set_amount,
            d_schedule.last_refill,
            d_schedule.suspended,
            d_schedule.trigger_interval,
            dosing.trigger_time as last_trigger,
            dosing.amount as dosed_amount
        FROM products 
        LEFT JOIN d_schedule ON products.id = d_schedule.prod_id
        JOIN dosing ON dosing.id = (
            SELECT max(ID) FROM dosing WHERE products.id = dosing.prod_id
        )
    """
    result = db.session.execute(text(sql))
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
        'last_trigger': '',
        'dosed_amount': 'ml',
        'percent_remaining': '%',
        'doses_remaining': 'doses',
        'days_until_empty': 'days',
        'estimated_empty_datetime': ''
    }
    date_keys = {'last_refill', 'last_trigger', 'estimated_empty_datetime'}
    # Get timezone from app config
    # tzname = current_app.config.get('TIMEZONE', 'UTC')
    # tz = pytz.timezone(tzname)
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
                # estimated_empty_datetime = pytz.utc.localize(estimated_empty_datetime).astimezone(tz)
                stat['estimated_empty_datetime'] = [
                    'Estimated Empty Date',
                    estimated_empty_datetime.strftime('%b %d %Y %H:%M:%S %Z'),
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
