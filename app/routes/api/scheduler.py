from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from app import db
from modules.models import DSchedule, Products, Dosing
from modules.utils import datatables_response
from sqlalchemy import text

bp = Blueprint('schedule_api', __name__)

@bp.route('/get/schedule', methods=['GET'])
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

@bp.route('/scheduler/new/dose/<schedule_id>', methods=['POST'])
def add_dosing_entry(schedule_id):
   
    if not schedule_id:
        return jsonify({'error': 'schedule_id is required'}), 400
    
    # Get the product by ID
    sched = DSchedule.query.get(schedule_id)

    # Create new dosing entry
    new_dosing = Dosing(
        prod_id=sched.prod_id,
        sched_id=sched.id,
        amount=sched.amount,
        trigger_time=datetime.utcnow()
    )
    db.session.add(new_dosing)
    db.session.commit()
    return ({'success': True, 'added': new_dosing.id}), 201


@bp.route('/scheduler/delete/<int:id>', methods=['DELETE'])
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

@bp.route('/scheduler/get/<int:schedule_id>', methods=['GET'])
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



@bp.route('/get/schedule_stats', methods=['GET'])
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
    stats = []
    for row in rows:
        stat = dict(zip(columns, row))
        # --- Calculated fields ---
        try:
            # % Remaining
            stat['percent_remaining'] = (
                (stat['current_avail'] / stat['total_volume']) * 100
                if stat['total_volume'] else None
            )
            # Doses Remaining
            stat['doses_remaining'] = (
                stat['current_avail'] / stat['set_amount']
                if stat['set_amount'] else None
            )
            # Days Until Empty
            if stat['used_amt'] and stat['used_amt'] > 0:
                days_until_empty = stat['current_avail'] / stat['used_amt']
                stat['days_until_empty'] = days_until_empty
                # Estimated Empty Date
                stat['estimated_empty_datetime'] = (
                    datetime.utcnow() + timedelta(days=days_until_empty)
                ).isoformat()
            else:
                stat['days_until_empty'] = None
                stat['estimated_empty_datetime'] = None
            
        
        except Exception:
            stat['percent_remaining'] = None
            stat['doses_remaining'] = None
            stat['days_until_empty'] = None
            stat['estimated_empty_datetime'] = None
        stats.append(stat)
    # Return the stats as JSON
    print(stats, 'stats')
    return jsonify(stats)
