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
# Dynamically generate TABLE_MAP from models.py
TABLE_MAP = {
    model.__tablename__: model
    for model in models_db.Model.registry._class_registry.values()
    if isinstance(model, type) and hasattr(model, "__tablename__")
}


@app.route('/api/get/<table_name>', methods=['GET'])
def get_table_data(table_name):
    print('get_table_data', table_name)
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]
        # print('table_model', table_model)
        # Get DataTables parameters
        draw = int(request.args.get('draw', 1))  # Draw counter
        page = int(request.args.get('page', 1))  # Current page number
        rows = int(request.args.get('rows', 10))  # Number of rows per page
        sort_column = request.args.get('sidx', 'id')  # Column to sort by
        sort_order = request.args.get('sord', 'asc')  # Sort order (asc/desc)
        search_value = request.args.get('search', '')  # Global search value

        # Base query
        query = table_model.query

        # Apply global search
        if search_value:
            search_filters = []
            for column in table_model.__table__.columns:
                search_filters.append(column.like(f"%{search_value}%"))
            query = query.filter(db.or_(*search_filters))

        # Apply sorting
        if sort_column and hasattr(table_model, sort_column):
            if sort_order == 'asc':
                query = query.order_by(getattr(table_model, sort_column).asc())
            else:
                query = query.order_by(getattr(table_model, sort_column).desc())

        # Pagination
        total_records = query.count()
        query = query.offset((page - 1) * rows).limit(rows)

        # Fetch results
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

        # Prepare response
        response = {
            "draw": draw,  # Pass back the draw counter
            "recordsTotal": total_records,  # Total records in the database
            "recordsFiltered": total_records,  # Total records after filtering
            "data": data,  # Data for the current page
        }
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
    try:
        import json

        # Parse tables
        table_names = request.args.get("tables", "")
        table_names = [t.strip() for t in table_names.split(",") if t.strip()]

        # Join type
        join_type = request.args.get("join_type", "inner").lower()

        # Join conditions
        conditions_json = request.args.get("conditions", "[]")
        join_conditions_raw = json.loads(conditions_json)
        print('join_conditions_raw', join_conditions_raw)
        join_conditions = []
        for pair in join_conditions_raw:
            left_table, left_col = pair[0].split('.')
            right_table, right_col = pair[1].split('.')
            left_model = TABLE_MAP[left_table]
            right_model = TABLE_MAP[right_table]
            join_conditions.append(getattr(left_model, left_col) == getattr(right_model, right_col))

        # Filters
        filters_json = request.args.get("filters", "[]")
        filters_raw = json.loads(filters_json)
        filters = []
        for f in filters_raw:
            table_col, op, value = f
            table_name, col_name = table_col.split('.')
            model = TABLE_MAP[table_name]
            col = getattr(model, col_name)
            if op == "like":
                filters.append(col.like(value))
            elif op == "=":
                filters.append(col == value)
            elif op == ">":
                filters.append(col > value)
            elif op == "<":
                filters.append(col < value)
            # Add more operators as needed

        # Order by
        order_by_json = request.args.get("order_by", "[]")
        order_by_raw = json.loads(order_by_json)
        order_by = []
        for ob in order_by_raw:
            order_by.append(tuple(ob))

        # Limit and offset
        limit = request.args.get("limit", None)
        offset = request.args.get("offset", None)
        limit = int(limit) if limit is not None else None
        offset = int(offset) if offset is not None else None

        # Call the advanced join query function
        data = advanced_join_query(
            db=db,
            TABLE_MAP=TABLE_MAP,
            table_names=table_names,
            join_type=join_type,
            join_conditions=join_conditions,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )


        draw = int(request.args.get('draw', 1))  # Draw counter
        total_records = len(data)  # Total records in the database
        response = {
            "draw": draw,  # Pass back the draw counter
            "recordsTotal": total_records,  # Total records in the database
            "recordsFiltered": total_records,  # Total records after filtering
            "data": data,  # Data for the current page
        }
        # return jsonify({
        #     "recordsTotal": len(data),
        #     "data": data
        # })
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
