from flask import Blueprint, jsonify, request
from app import db
import modules
from modules.models import db as models_db
from modules.utils.helper import datatables_response, validate_and_process_data
from modules.db_functions import create_row
from modules.utils.table_map import TABLE_MAP
from modules.tank_context import get_current_tank_id
import enum
from datetime import date, time

bp = Blueprint('table_ops_api', __name__, url_prefix='/ops')

@bp.route('/get/<table_name>', methods=['GET'])
def get_table_data(table_name):
    try:
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        table_model = TABLE_MAP[table_name]
        draw = int(request.args.get('draw', 1))
        params = {
            'search': request.args.get('search', ''),
            'sidx': request.args.get('sidx', ''),
            'sord': request.args.get('sord', 'asc'),
            'page': request.args.get('page', 1),
            'rows': request.args.get('rows', 10)
        }

        tank_id = get_current_tank_id()
        if hasattr(table_model, 'tank_id') or 'tank_id' in table_model.__table__.columns:
            base_query = table_model.query.filter_by(tank_id=tank_id)
        else:
            base_query = table_model.query

        # Get all records for the tank (before search filter)
        all_results = base_query.all()
        data = []
        for row in all_results:
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

        # Apply DataTables search, ordering, and pagination
        from modules.utils.helper import apply_datatables_query_params_to_dicts
        filtered_data, total_filtered = apply_datatables_query_params_to_dicts(data, params)

        response = {
            "draw": draw,
            "recordsTotal": len(data),  # total for tank
            "recordsFiltered": total_filtered,  # after search
            "data": filtered_data,
        }
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
        input_data = request.get_json()
        # Edit an existing record
        row = table_model.query.get(input_data["id"])
        if not row:
            return jsonify({"error": f"Record with ID {input_data['id']} not found in '{table_name}'."}), 404
        data = validate_and_process_data(table_model, input_data)
        # Fix for legacy/prod_id -> product_id mapping
        if table_name == 'corals':
            if 'prod_id' in data:
                data['product_id'] = data.pop('prod_id')
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
    data = request.get_json()
    print('insert into model', table, data)

    data = validate_and_process_data(table, data)
    # Fix for legacy/prod_id -> product_id mapping
    if table_name == 'corals':
        if 'prod_id' in data:
            data['product_id'] = data.pop('prod_id')
    
    # Prevent duplicate d_schedule for same tank_id and product_id
    if table_name == 'd_schedule':
        product_id = data.get('product_id')
        tank_id = data.get('tank_id')
       
        if product_id and tank_id:
            exists = table.query.filter_by(product_id=product_id, tank_id=tank_id).first()
            if exists:
                return jsonify({'error': 'A schedule already exists for this tank and product.'}), 400

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
        # Accept both 'id' and 'product_id' for primary key
        row_id = data.get("id") or data.get("product_id")
        if not row_id:
            return jsonify({"error": "Missing 'id' or 'product_id' in request data."}), 400

        # Get current tank context for multi-tank validation
        tank_id = get_current_tank_id()
        if not tank_id:
            return jsonify({"error": "No tank selected. Please select a tank first."}), 400

        # Check if the table has tank_id field and filter by tank if applicable
        if hasattr(table_model, 'tank_id') or 'tank_id' in table_model.__table__.columns:
            # Find the record by ID and tank_id for security
            row = table_model.query.filter_by(id=row_id, tank_id=tank_id).first()
            if not row:
                return jsonify({"error": f"Record with ID {row_id} not found in '{table_name}' for current tank."}), 404
        else:
            # For tables without tank_id, use the original logic
            row = table_model.query.get(row_id)
            if not row:
                return jsonify({"error": f"Record with ID {row_id} not found in '{table_name}'."}), 404

        # Delete the record
        db.session.delete(row)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Record deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/datatable/<table_name>', methods=['GET'])
def datatable_fallback(table_name):
    """
    Fallback route to always return a DataTables-compatible response for /web/fn/datatable/<table_name>.
    This ensures DataTables never gets a 404, and always gets the expected JSON format.
    """
    from modules.utils.helper import datatables_response
    draw = int(request.args.get('draw', 1))
    params = {
        'search': request.args.get('search', ''),
        'sidx': request.args.get('sidx', ''),
        'sord': request.args.get('sord', 'asc'),
        'page': request.args.get('page', 1),
        'rows': request.args.get('rows', 10)
    }
    # If the table exists, use the normal logic
    if table_name in TABLE_MAP:
        table_model = TABLE_MAP[table_name]
        tank_id = get_current_tank_id()
        if hasattr(table_model, 'tank_id') or 'tank_id' in table_model.__table__.columns:
            base_query = table_model.query.filter_by(tank_id=tank_id)
        else:
            base_query = table_model.query
        all_results = base_query.all()
        data = []
        for row in all_results:
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
        from modules.utils.helper import apply_datatables_query_params_to_dicts
        filtered_data, total_filtered = apply_datatables_query_params_to_dicts(data, params)
        response = {
            "draw": draw,
            "recordsTotal": len(data),
            "recordsFiltered": total_filtered,
            "data": filtered_data,
        }
        return jsonify(response)
    # If not, return an empty DataTables response
    response = {
        "draw": draw,
        "recordsTotal": 0,
        "recordsFiltered": 0,
        "data": [],
    }
    return jsonify(response)

# Fallback route for DataTables: always returns a DataTables-compatible response
@bp.route('/get/<table_name>/datatable', methods=['GET'])
def get_table_data_datatable(table_name):
    try:
        if table_name not in TABLE_MAP:
            # Always return a DataTables-compatible empty response
            return jsonify({
                "draw": int(request.args.get('draw', 1)),
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
                "error": f"Table '{table_name}' not found."
            })
        # Use the same logic as the main get_table_data route
        table_model = TABLE_MAP[table_name]
        draw = int(request.args.get('draw', 1))
        params = {
            'search': request.args.get('search', ''),
            'sidx': request.args.get('sidx', ''),
            'sord': request.args.get('sord', 'asc'),
            'page': request.args.get('page', 1),
            'rows': request.args.get('rows', 10)
        }
        tank_id = get_current_tank_id()
        if hasattr(table_model, 'tank_id') or 'tank_id' in table_model.__table__.columns:
            base_query = table_model.query.filter_by(tank_id=tank_id)
        else:
            base_query = table_model.query
        all_results = base_query.all()
        data = []
        for row in all_results:
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
        from modules.utils.helper import apply_datatables_query_params_to_dicts
        filtered_data, total_filtered = apply_datatables_query_params_to_dicts(data, params)
        response = {
            "draw": draw,
            "recordsTotal": len(data),
            "recordsFiltered": total_filtered,
            "data": filtered_data,
        }
        return jsonify(response)
    except Exception as e:
        # Always return a DataTables-compatible error response
        return jsonify({
            "draw": int(request.args.get('draw', 1)),
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(e)
        })