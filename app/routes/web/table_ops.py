from flask import Blueprint, jsonify, request
from app import db
import modules
from modules.models import db as models_db
from modules.utils.helper import datatables_response, validate_and_process_data
from modules.db_functions import create_row
from modules.utils.table_map import TABLE_MAP
import enum
from datetime import date, time

bp = Blueprint('table_ops_api', __name__, url_prefix='/tables')

@bp.route('/get/<table_name>', methods=['GET'])
def get_table_data(table_name):
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


@bp.route('/get/raw/<table_name>', methods=['GET'])
def get_raw_data(table_name):
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]
        query = table_model.query
        results = query.all()
        # print(results, 'results')
        # print(type(results), 'type(results)')

    # Convert SQLAlchemy model instances to dicts for JSON serialization
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
            # print(data, 'data')   
    
    except Exception as e:
       return jsonify({"error": str(e)}), 500
    return jsonify({"data":data, "success": True}), 200
    
@bp.route('/edit/<table_name>', methods=['POST', 'PUT'])
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
    
@bp.route('/new/<table_name>', methods=['POST'])
def add_new_record(table_name):
    if table_name not in TABLE_MAP:
        return jsonify({"error": f"Table '{table_name}' not found."}), 404

    # Get the table model
    table = TABLE_MAP[table_name]
    # model = table.__name__
    data = request.get_json()
    print('insert into model', table, data)

    data = modules.utils.validate_and_process_data(table, data)
    # print('cleaned data', data)
    # If the cleaned data only has a product id, throw a form error
    if list(data.keys()) == ["prod_id"]:
        return jsonify({'error': 'Form data missing: only product id provided.'}), 400

    try:
        new_row = create_row(table, data)
        db.session.commit()
        return jsonify({'success': True, 'id': new_row.id, 'message': 'Record added successfully'}), 201
    except Exception as e:
        return jsonify({'error': f"Failed to add record: {str(e)}"}), 500
    
@bp.route('/delete/<table_name>', methods=['DELETE'])
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