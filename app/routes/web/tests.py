from flask import Blueprint, jsonify
from modules.models import TestResults  # Adjust import if your model is named differently
from app import db
from modules.system_context import get_current_system_id, get_current_system_tank_ids, get_current_system_tanks, ensure_system_context

bp = Blueprint('tests_api', __name__, url_prefix='/tests')

@bp.route('/get/all', methods=['GET'])
def get_all_tests():
    tests = TestResults.query.order_by(TestResults.id.desc()).all()
    results = [test.to_dict() for test in tests]
    return jsonify(results=results)

@bp.route('/get/latest', methods=['GET'])
def get_latest_test():
    test = TestResults.query.order_by(TestResults.id.desc()).first()
    return jsonify(result=test.to_dict() if test else None)

@bp.route('/get/<int:test_id>', methods=['GET'])
def get_test_by_id(test_id):
    test = TestResults.query.get(test_id)
    return jsonify(result=test.to_dict() if test else None)

@bp.route("/tank/get/all")
def all_tank_results():
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    if not system_id or not tank_ids:
        # Handle the case where no system is selected
        return jsonify({'error': 'No system selected.'}), 400
    tests = TestResults.query.filter(TestResults.tank_id.in_(tank_ids)).order_by(TestResults.test_date.desc(), TestResults.test_time.desc()).all()
    return jsonify(results=tests)


@bp.route("/tank/get/latest")
def latest_tank_result():
    system_id = ensure_system_context()
    tank_ids = get_current_system_tank_ids()
    if not system_id or not tank_ids:
        # Handle the case where no system is selected
        return jsonify({'error': 'No system selected.'}), 400
    test = TestResults.query.filter(TestResults.tank_id.in_(tank_ids)).order_by(TestResults.id.desc()).first()
    return jsonify(results=test.to_dict() if test else None)