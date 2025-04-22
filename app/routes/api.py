import modules
import json
import datetime
from flask import jsonify, request
from app import app, db
from modules.models import TestResults, Products, ManualDosing
from modules.utils import process_test_data
from modules.models import db as models_db  # Import the SQLAlchemy instance from models.py
from sqlalchemy.inspection import inspect
from modules.db_functions import create_row, read_rows, update_row, delete_row

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
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]

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
                if isinstance(value, datetime.date):  # Check for date objects
                    row_data[column.name] = value.strftime("%Y-%m-%d")
                elif isinstance(value, datetime.time):  # Check for time objects
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