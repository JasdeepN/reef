import modules
import json
from datetime import date, time 
from flask import jsonify, request
from app import app, db
from modules.models import *
from modules.utils import *
from modules.models import db as models_db  # Import the SQLAlchemy instance from models.py
from sqlalchemy.inspection import inspect
from modules.db_functions import create_row, read_rows, update_row, delete_row
import enum

import pprint

import modules.utils
from modules.utils import datatables_response
import ast

# Dynamically generate TABLE_MAP from models.py
TABLE_MAP = {
    model.__tablename__: model
    for model in models_db.Model.registry._class_registry.values()
    if isinstance(model, type) and hasattr(model, "__tablename__")
} 

@app.route('/api/get/schedule', methods=['GET'])
def get_sched():
   
    params = {
        'search': request.args.get('search', ''),
        'sidx': request.args.get('sidx', ''),
        'sord': request.args.get('sord', 'asc'),
        'page': request.args.get('page', 1),
        'rows': request.args.get('rows', 10)
    }

    draw = int(request.args.get('draw', 1))
    
    # print('params', params)
    
    # Equivalent SQLAlchemy query for:
    # select d_schedule.id, trigger_interval, amount, current_avail, total_volume, products.name
    # from d_schedule join products on products.id=prod_id;
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
            "suspended": row[3],
            "current_avail": row[4],
            "total_volume": row[5],
            "name": row[6]
        }
        for row in rows
    ]
    
    response = datatables_response(data, params, draw)
    # print(response, 'response')
    return jsonify(response)

@app.route('/api/get/schedule_stats', methods=['GET'])
def get_schedule_stats():
    """
    Returns stats for each product being dosed, including:
    - product name
    - trigger_interval (seconds)
    - amount per dose
    - current_avail
    - total_volume
    - doses_remaining
    - doses_per_day
    - days_until_empty
    - estimated_empty_datetime
    """
    from datetime import datetime, timedelta

    rows = (
        db.session.query(
            DSchedule.id,
            DSchedule.trigger_interval,
            DSchedule.amount,
            DSchedule.suspended,
            DSchedule.last_trigger,
            DSchedule.last_refill,
            Products.total_volume,
            Products.current_avail,
            Products.name
        )
        .join(Products, Products.id == DSchedule.prod_id)
        .all()
    )

    print(rows)
    stats = []
    now = datetime.utcnow()
    for row in rows:
        (
            sched_id,
            trigger_interval,
            amount,
            suspended,
            last_trigger,
            last_refill,
            total_volume,
            current_avail,
            name,
            
        ) = row

        # Avoid division by zero
        doses_remaining = int(current_avail // amount) if amount and current_avail else 0
        doses_per_day = int(86400 // trigger_interval) if trigger_interval else 0  # 86400 seconds in a day
        days_until_empty = (doses_remaining / doses_per_day) if doses_per_day else None
        # estimated_empty_datetime = (now + timedelta(days=days_until_empty)).isoformat() if days_until_empty else None
        if doses_remaining > 0 and last_trigger and trigger_interval:
            # The last dose was at last_trigger, so the next dose will be after trigger_interval seconds, etc.
            estimated_empty_datetime = (
                (last_trigger + timedelta(seconds=trigger_interval * doses_remaining)).isoformat()
            )
        else:
            estimated_empty_datetime = None
        amount_used_per_day = amount * doses_per_day if amount and doses_per_day else 0
        # Calculate days when full and percent remaining
        days_when_full = (total_volume // amount) / doses_per_day if amount and doses_per_day else None
        percent_remaining = (current_avail / total_volume * 100) if total_volume else None
        # Format the last_trigger and last_refill dates
        last_trigger = last_trigger.isoformat() if last_trigger else None
        last_refill = last_refill.isoformat() if last_refill else None
        # Format the estimated_empty_datetime
        if trigger_interval:
            hours = trigger_interval // 3600
            minutes = (trigger_interval % 3600) // 60
            trigger_interval_hhmm = f"{int(hours):02d}:{int(minutes):02d}"
        else:
            trigger_interval_hhmm = None
        trigger_interval = trigger_interval_hhmm
        stats.append({
            "id": sched_id,
            "product_name": name,
            "trigger_interval": trigger_interval,
            "amount_per_dose": amount,
            "current_avail": current_avail,
            "total_volume": total_volume,
            "doses_remaining": doses_remaining,
            "doses_per_day": doses_per_day,
            "days_until_empty": round(days_until_empty, 2) if days_until_empty is not None else None,
            "estimated_empty_datetime": estimated_empty_datetime,
            "amount_used_per_day": amount_used_per_day,
            "days_when_full": round(days_when_full, 2) if days_when_full is not None else None,
            "percent_remaining": round(percent_remaining, 2) if percent_remaining is not None else None,
            "last_trigger": last_trigger,
            "last_refill": last_refill,
            "suspended": suspended
        })

    return jsonify(stats)

@app.route('/api/get/<table_name>', methods=['GET'])
def get_table_data(table_name):
    # print('get_table_data', table_name)
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]
        # print('table_model', table_model)
        # Get DataTables parameters
        draw = int(request.args.get('draw', 1))  # Draw counter

        params = {
            'search': request.args.get('search', ''),
            'sidx': request.args.get('sidx', ''),
            'sord': request.args.get('sord', 'asc'),
            'page': request.args.get('page', 1),
            'rows': request.args.get('rows', 10)
        }

        # Base query
        query = table_model.query
        results = query.all()
        # Process results to handle date and time objects
        data = []
        for row in results:
            row_data = {}
            for column in table_model.__table__.columns:
                value = getattr(row, column.name)
                if isinstance(value, enum.Enum):
                    row_data[column.name] = value.value
                elif isinstance(value, date):
                    row_data[column.name] = value.strftime("%Y-%m-%d")
                elif isinstance(value, time):
                    row_data[column.name] = value.strftime("%H:%M:%S")
                else:
                    row_data[column.name] = value
            data.append(row_data)

        # filterd = apply_datatables_query_params_to_dicts(data, params)
    # print(filterd, 'filterd')
        
        response = datatables_response(data, params, draw)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/api/edit/<table_name>', methods=['POST', 'PUT'])
def edit_table(table_name):
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]
        # Parse JSON data
        input = request.get_json();
        # Edit an existing record
        row = table_model.query.get(input["id"])
        if not row:
            return jsonify({"error": f"Record with ID {input['id']} not found in '{table_name}'."}), 404
        data = modules.utils.validate_and_process_data(table_model, input)
        for key, value in data.items():
            if key != "id" and hasattr(row, key):
                setattr(row, key, value)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Record updated successfully'}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        

@app.route('/api/new/<table_name>', methods=['POST'])
def add_new_record(table_name):
    if table_name not in TABLE_MAP:
        return jsonify({"error": f"Table '{table_name}' not found."}), 404

    # Get the table model
    table = TABLE_MAP[table_name]
    # model = table.__name__
    data = request.get_json()
    # print('insert into model', table, data)

    data = modules.utils.validate_and_process_data(table, data)
    print('cleaned data', data)

    try:
        new_row = create_row(table, data)
        db.session.commit()
        return jsonify({'success': True, 'id': new_row.id, 'message': 'Record added successfully'}), 201
    except Exception as e:
        return jsonify({'error': f"Failed to add record: {str(e)}"}), 500
    

@app.route('/api/delete/<table_name>', methods=['DELETE'])
def delete_record(table_name):
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]

        # Parse JSON data
        data = request.get_json()
        row_id = data.get("id")
        if not row_id:
            return jsonify({"error": "Missing 'id' in request data."}), 400

        # Find the record by ID
        row = table_model.query.get(row_id)
        if not row:
            return jsonify({"error": f"Record with ID {row_id} not found in '{table_name}'."}), 404

        # Delete the record
        db.session.delete(row)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Record deleted successfully'}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/get/advanced_join', methods=['GET'])
def api_advanced_join():
    """
    Example usage:
    /api/get/advanced_join?tables=products,dosing
        &join_type=inner
        &conditions=%5B%5B%22products.id%22%2C%22dosing.prod_id%22%5D%5D
        &filters=%5B%5B%22products.name%22%2C%22like%22%2C%22Neo%25%22%5D%5D
        &order_by=%5B%5B%22products%22%2C%22id%22%2C%22asc%22%5D%5D
        &limit=10
        &offset=0
    """
    import json

    # Parse query parameters
    tables = request.args.get('tables', '').split(',')
    join_type = request.args.get('join_type', 'inner')
    conditions = request.args.get('conditions', '[]')
    filters = request.args.get('filters', '[]')
    order_by = request.args.get('order_by', '[]')
    limit = request.args.get('limit', None)
    offset = request.args.get('offset', None)

    # Convert JSON strings to Python objects
    try:
        join_conditions_raw = json.loads(conditions)
        filters = json.loads(filters)
        order_by = json.loads(order_by)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON in query parameters: {str(e)}"}), 400

    # Build join_conditions as SQLAlchemy expressions
    join_conditions = []
    for pair in join_conditions_raw:
        if len(pair) != 2:
            return jsonify({"error": "Each join condition must be a pair [left, right]."}), 400
        left_table, left_col = pair[0].split('.')
        right_table, right_col = pair[1].split('.')
        left = getattr(TABLE_MAP[left_table], left_col)
        right = getattr(TABLE_MAP[right_table], right_col)
        join_conditions.append(left == right)

    # Convert limit/offset to int if present
    limit = int(limit) if limit is not None else None
    offset = int(offset) if offset is not None else None

    draw = int(request.args.get('draw', 1))  # Draw counter

    params = {
        'search': request.args.get('search', ''),
        'sidx': request.args.get('sidx', ''),
        'sord': request.args.get('sord', 'asc'),
        'page': request.args.get('page', 1),
        'rows': request.args.get('rows', 10)
    }

    # Call advanced_join_query with parsed parameters
    data = advanced_join_query(
        db=db,
        TABLE_MAP=TABLE_MAP,
        table_names=tables,
        join_type=join_type,
        join_conditions=join_conditions,
        filters=filters,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )

    try:
        response = datatables_response(data, params, draw)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
