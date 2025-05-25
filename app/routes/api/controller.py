from flask import Blueprint, request, jsonify, current_app
from app import db
from sqlalchemy import text
from datetime import datetime
import pytz

bp = Blueprint('controller_api', __name__, url_prefix='/controller')

@bp.route('/dose', methods=['POST'])
def create_dosing():
    data = request.get_json()
    schedule_id = data.get('schedule_id')
    tank_id = data.get('tank_id')

    if not schedule_id:
        return jsonify({'success': False, 'error': 'Missing schedule ID'}), 400

    # Check for existing schedule with same product_id and tank_id
    check_sql = '''
        SELECT 1 FROM d_schedule WHERE id = :schedule_id AND tank_id = :tank_id
    '''
    exists = db.session.execute(text(check_sql), {'schedule_id': schedule_id, 'tank_id': tank_id}).fetchone()
    if not exists:
        return jsonify({'success': False, 'error': 'No schedule found for this tank and schedule_id'}), 400

    sql = """
        SELECT 
            d_schedule.product_id,
            d_schedule.amount,
            products.current_avail
        FROM d_schedule
        JOIN products ON d_schedule.product_id = products.id
        WHERE d_schedule.id = :schedule_id
    """
    result = db.session.execute(text(sql), {'schedule_id': schedule_id}).fetchone()
    if not result:
        return jsonify({'success': False, 'error': 'Schedule or product not found'}), 404

    product_id, amount, current_avail = result
    try:
        amount_float = float(amount)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid dose amount in schedule'}), 400

    if current_avail is None or current_avail < amount_float:
        return jsonify({'success': False, 'error': 'Not enough available product'}), 400

    update_sql = "UPDATE products SET current_avail = current_avail - :amount WHERE id = :product_id"
    insert_sql = """
        INSERT INTO dosing (product_id, schedule_id, tank_id, amount, trigger_time)
        VALUES (:product_id, :schedule_id, :tank_id, :amount, :trigger_time)
    """
    # Use datetime(3) precision for trigger_time in configured timezone
    tzname = current_app.config.get('TIMEZONE', 'UTC')
    tz = pytz.timezone(tzname)

    trigger_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S.%f')
    # print(f"Trigger time: {trigger_time}")
    try:
        db.session.execute(text(update_sql), {'amount': amount_float, 'product_id': product_id})
        db.session.execute(
            text(insert_sql),
            {
                'product_id': product_id,
                'schedule_id': schedule_id,
                'tank_id': tank_id,
                'amount': amount_float,
                'trigger_time': trigger_time
            }
        )
        db.session.commit()
        return jsonify({'success': True}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/refill', methods=['POST'])
def refill_product():
    data = request.get_json()
    prod_id = data.get('prod_id')
    refill_amount = data.get('amount')

    if not prod_id:
        return jsonify({'success': False, 'error': 'Missing product ID'}), 400

    # Get current product info
    sql = """
        SELECT current_avail, total_volume
        FROM products
        WHERE id = :prod_id
    """
    result = db.session.execute(text(sql), {'prod_id': prod_id}).fetchone()
    if not result:
        return jsonify({'success': False, 'error': 'Product not found'}), 404

    current_avail, total_volume = result

    try:
        if refill_amount is not None:
            refill_amount = float(refill_amount)
            new_avail = (current_avail or 0) + refill_amount
        else:
            # Fill to total_volume
            new_avail = total_volume
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid refill amount'}), 400

    # Set last_refill to current time in configured timezone
    tzname = current_app.config.get('TIMEZONE', 'UTC')
    tz = pytz.timezone(tzname)
    last_refill = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    update_sql = """
        UPDATE products
        SET current_avail = :new_avail, last_refill = :last_refill
        WHERE id = :prod_id
    """
    try:
        db.session.execute(text(update_sql), {'new_avail': new_avail, 'last_refill': last_refill, 'prod_id': prod_id})
        db.session.commit()
        return jsonify({'success': True, 'current_avail': new_avail, 'last_refill': last_refill}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/toggle/schedule', methods=['POST'])
def toggle_schedule():
    data = request.get_json()
    sched_id = data.get('sched_id')

    if sched_id is None:
        return jsonify({'success': False, 'error': 'Missing schedule ID'}), 400

    # Fetch current suspended value
    sql = "SELECT suspended FROM d_schedule WHERE id = :sched_id"
    result = db.session.execute(text(sql), {'sched_id': sched_id}).fetchone()
    if not result:
        return jsonify({'success': False, 'error': 'Schedule not found'}), 404

    current_value = result[0]
    new_value = 0 if current_value else 1

    update_sql = """
        UPDATE d_schedule
        SET suspended = :suspend
        WHERE id = :sched_id
    """
    try:
        db.session.execute(text(update_sql), {'suspend': new_value, 'sched_id': sched_id})
        db.session.commit()
        return jsonify({'success': True, 'suspended': new_value}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/toggle/dosing_pump', methods=['POST'])
def toggle_dosing_pump():
    data = request.get_json()
    pump_id = data.get('id')
    if pump_id is None:
        return jsonify({'success': False, 'error': 'Missing dosing pump ID'}), 400
    # Placeholder: No action performed
    return jsonify({'success': True, 'message': 'Dosing pump toggle placeholder', 'id': pump_id}), 200

