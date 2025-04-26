import modules
import json
from datetime import date, time 
from flask import jsonify, request
from app import app, db
from modules.models import TestResults, Products, Dosing
from modules.utils import *
from modules.models import db as models_db  # Import the SQLAlchemy instance from models.py
from sqlalchemy.inspection import inspect
from modules.db_functions import create_row, read_rows, update_row, delete_row
import enum

import pprint

import modules.utils
from modules.utils import datatables_response

# Dynamically generate TABLE_MAP from models.py
TABLE_MAP = {
    model.__tablename__: model
    for model in models_db.Model.registry._class_registry.values()
    if isinstance(model, type) and hasattr(model, "__tablename__")
}


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

        filterd = apply_datatables_query_params_to_dicts(data, params)
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
        create_row(table, data)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Record added successfully'}), 201
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

    - tables: comma-separated table names
    - join_type: inner, left, right, full
    - conditions: JSON list of pairs, each pair is [left, right] for join condition
    - filters: JSON list of [table.column, op, value] (e.g., [["products.name", "like", "Neo%"]])
    - order_by: JSON list of [table, column, direction]
    - limit, offset: integers
    """


    # Prepare parameters for advanced_join_query
    table_names = ["products", "dosing"]
    join_type = "inner"
    join_conditions = [getattr(TABLE_MAP["products"], "id") == getattr(TABLE_MAP["dosing"], "prod_id")]

    draw = int(request.args.get('draw', 1))  # Draw counter

    params = {
        'search': request.args.get('search', ''),
        'sidx': request.args.get('sidx', ''),
        'sord': request.args.get('sord', 'asc'),
        'page': request.args.get('page', 1),
        'rows': request.args.get('rows', 10)
    }


    # No filters, order_by, limit, or offset for this simple join
    data = advanced_join_query(
        db=db,
        TABLE_MAP=TABLE_MAP,
        table_names=table_names,
        join_type=join_type,
        join_conditions=join_conditions,
        filters=None,
        order_by=None,
        limit=None,
        offset=None,
    )

    
    
    try:
        response = datatables_response(data, params, draw)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
