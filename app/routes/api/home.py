from flask import Blueprint, jsonify
from modules.tank_context import get_current_tank_id
from modules.models import Tank, TestResults

bp = Blueprint('home_api', __name__, url_prefix='/home')

@bp.route('/tank-context', methods=['GET'])
def get_tank_context():
    """API endpoint to check current tank context without causing redirects"""
    tank_id = get_current_tank_id()
    return jsonify({
        "has_context": tank_id is not None,
        "tank_id": tank_id,
        "tanks": [{"id": tank.id, "name": tank.name} for tank in Tank.query.all()]
    })

@bp.route('/test-results-data', methods=['GET'])
def get_test_results_data():
    """API endpoint to get test results data for charting"""
    tank_id = get_current_tank_id()
    if not tank_id:
        return jsonify({"error": "No tank selected"}), 400
    
    # Get test results ordered by date (ascending for time series)
    tests = TestResults.query.filter_by(tank_id=tank_id).order_by(
        TestResults.test_date.asc(), 
        TestResults.test_time.asc()
    ).all()
    
    if not tests:
        return jsonify({"labels": [], "datasets": _create_chart_datasets()})
    
    # Prepare data for Chart.js with interpolation
    chart_data = _prepare_interpolated_chart_data(tests)
    
    return jsonify(chart_data)

def _create_chart_datasets():
    """Create empty chart datasets structure"""
    return {
        'alkalinity': {
            'label': 'Alkalinity (dKH)',
            'data': [],
            'borderColor': 'rgb(75, 192, 192)',
            'tension': 0.1
        },
        'calcium': {
            'label': 'Calcium (ppm)',
            'data': [],
            'borderColor': 'rgb(255, 99, 132)',
            'tension': 0.1
        },
        'magnesium': {
            'label': 'Magnesium (ppm)',
            'data': [],
            'borderColor': 'rgb(54, 162, 235)',
            'tension': 0.1
        }
    }

def _prepare_interpolated_chart_data(tests):
    """Prepare chart data with interpolation for missing values"""
    # This would contain the complex interpolation logic
    # For now, return basic structure
    labels = []
    datasets = _create_chart_datasets()
    
    for test in tests:
        label = f"{test.test_date} {test.test_time or ''}"
        labels.append(label.strip())
        
        if test.alkalinity is not None:
            datasets['alkalinity']['data'].append(test.alkalinity)
        if test.calcium is not None:
            datasets['calcium']['data'].append(test.calcium)
        if test.magnesium is not None:
            datasets['magnesium']['data'].append(test.magnesium)
    
    return {
        "labels": labels,
        "datasets": list(datasets.values())
    }
