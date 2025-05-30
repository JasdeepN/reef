from flask import Blueprint, jsonify

bp = Blueprint('tests_api', __name__, url_prefix='/tests')

@bp.route('/get/all', methods=['GET'])
def get_all_tests():
    # Import here to avoid circular import
    from modules.models import TestResults
    from app import db
    
    tests = TestResults.query.order_by(TestResults.id.desc()).all()
    results = [test.to_dict() for test in tests]
    return jsonify(results=results)

@bp.route('/get/latest', methods=['GET'])
def get_latest_test():
    # Import here to avoid circular import
    from modules.models import TestResults
    from app import db
    
    test = TestResults.query.order_by(TestResults.id.desc()).first()
    return jsonify(result=test.to_dict() if test else None)

@bp.route('/get/<int:test_id>', methods=['GET'])
def get_test_by_id(test_id):
    # Import here to avoid circular import
    from modules.models import TestResults
    from app import db
    
    test = TestResults.query.get(test_id)
    return jsonify(result=test.to_dict() if test else None)