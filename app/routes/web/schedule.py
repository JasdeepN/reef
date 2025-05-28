from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from app import db
from modules.models import DSchedule, Products, Dosing
from modules.tank_context import get_current_tank_id
from modules.utils.helper import datatables_response
from sqlalchemy import text
import pytz

bp = Blueprint('schedule_api', __name__, url_prefix='/schedule')

@bp.route('/get/all', methods=['GET'])
def get_sched():
    tank_id = get_current_tank_id()
    if tank_id is None:
        return jsonify({'error': 'No tank id provided'}), 400
    
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
        .filter(DSchedule.tank_id == tank_id)
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
            "last_refill": row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else "Never",
            
        }
        for row in rows
    ]
    print("data", data)
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
    tank_id = get_current_tank_id()
    
    if tank_id is None:
        return jsonify({'error': 'No tank id provided'}), 400
    
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
        WHERE d_schedule.tank_id = :tank_id
    """
    params = {}
    params['tank_id'] = tank_id
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
        'last_trigger': '',
        'dosed_amount': 'ml',
        'percent_remaining': '%',
        'doses_remaining': 'doses',
        'days_until_empty': 'days',
        'estimated_empty_datetime': ''
    }
    date_keys = {'last_refill', 'last_trigger', 'estimated_empty_datetime'}
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
    return jsonify({"success": True, "data": stats})

@bp.route('/test/stats/<int:tank_id>', methods=['GET'])
def test_schedule_stats(tank_id):
    """Test endpoint to set tank_id and get schedule stats for testing purposes"""
    from modules.tank_context import set_tank_id_for_testing
    
    # Set the tank_id for testing
    set_tank_id_for_testing(tank_id)
    
    # Call the regular stats endpoint
    return get_schedule_stats()
