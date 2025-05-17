from flask import Blueprint, jsonify, request
from app import db
from modules.models import db as models_db
from modules.utils.helper import datatables_response, advanced_join_query
from modules.utils.table_map import TABLE_MAP
import json

bp = Blueprint('advanced_join_api', __name__)

@bp.route('/get/advanced_join', methods=['GET'])
def api_advanced_join():
    """
    Example usage:
    /web/fn/get/advanced_join?tables=products,dosing
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
