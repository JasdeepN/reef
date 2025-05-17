from flask import Blueprint, jsonify
from modules.models import TestResults  # Adjust import if your model is named differently
from app import db

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