from flask import Blueprint, jsonify
from modules.tank_context import get_current_tank_id, ensure_tank_context
from modules.models import Tank, TestResults
from modules.timezone_utils import format_time_for_display

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
    tank_id = ensure_tank_context()  # Use ensure_tank_context for VS Code compatibility
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
    return [
        # Original datasets
        {
            'label': 'Alkalinity (dKH)',
            'data': [],
            'borderColor': 'rgb(75, 192, 192)',
            'backgroundColor': 'rgba(75, 192, 192, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y'
        },
        {
            'label': 'Alkalinity (Interpolated)',
            'data': [],
            'borderColor': 'rgb(75, 192, 192)',
            'backgroundColor': 'rgba(75, 192, 192, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y'
        },
        {
            'label': 'Calcium (ppm)',
            'data': [],
            'borderColor': 'rgb(255, 99, 132)',
            'backgroundColor': 'rgba(255, 99, 132, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y1'
        },
        {
            'label': 'Calcium (Interpolated)',
            'data': [],
            'borderColor': 'rgb(255, 99, 132)',
            'backgroundColor': 'rgba(255, 99, 132, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y1'
        },
        {
            'label': 'Magnesium (ppm)',
            'data': [],
            'borderColor': 'rgb(54, 162, 235)',
            'backgroundColor': 'rgba(54, 162, 235, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y1'
        },
        {
            'label': 'Magnesium (Interpolated)',
            'data': [],
            'borderColor': 'rgb(54, 162, 235)',
            'backgroundColor': 'rgba(54, 162, 235, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y1'
        },
        {
            'label': 'Phosphate (ppm)',
            'data': [],
            'borderColor': 'rgb(255, 206, 86)',
            'backgroundColor': 'rgba(255, 206, 86, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y2'
        },
        {
            'label': 'Phosphate (Interpolated)',
            'data': [],
            'borderColor': 'rgb(255, 206, 86)',
            'backgroundColor': 'rgba(255, 206, 86, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y2'
        },
        {
            'label': 'Nitrate (ppm)',
            'data': [],
            'borderColor': 'rgb(153, 102, 255)',
            'backgroundColor': 'rgba(153, 102, 255, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y3'
        },
        {
            'label': 'Nitrate (Interpolated)',
            'data': [],
            'borderColor': 'rgb(153, 102, 255)',
            'backgroundColor': 'rgba(153, 102, 255, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y3'
        },
        {
            'label': 'Specific Gravity',
            'data': [],
            'borderColor': 'rgb(255, 159, 64)',
            'backgroundColor': 'rgba(255, 159, 64, 0.1)',
            'tension': 0.1,
            'yAxisID': 'y4'
        },
        {
            'label': 'Specific Gravity (Interpolated)',
            'data': [],
            'borderColor': 'rgb(255, 159, 64)',
            'backgroundColor': 'rgba(255, 159, 64, 0.05)',
            'borderDash': [5, 5],
            'tension': 0.1,
            'yAxisID': 'y4'
        }
    ]

def _prepare_interpolated_chart_data(tests):
    """Prepare chart data with interpolation for missing values"""
    labels = []
    datasets = _create_chart_datasets()
    
    # Extract data values for all parameters
    data_values = _extract_test_values(tests, labels)
    
    # Populate datasets with original and interpolated values
    _populate_datasets(datasets, data_values)
    
    return {
        "labels": labels,
        "datasets": datasets
    }

def _extract_test_values(tests, labels):
    """Extract test values and format labels"""
    data_values = {
        'alk': [], 'cal': [], 'mg': [], 
        'po4_ppm': [], 'no3_ppm': [], 'sg': []
    }
    
    for test in tests:
        # Format label
        if test.test_date and test.test_time:
            label = f"{test.test_date.strftime('%Y-%m-%d')} {format_time_for_display(test.test_time)}"
        else:
            label = test.test_date.strftime('%Y-%m-%d') if test.test_date else 'Unknown'
        labels.append(label)
        
        # Extract values using correct column names
        for param in data_values.keys():
            value = getattr(test, param, None)
            data_values[param].append(value if value is not None else None)
    
    return data_values

def _populate_datasets(datasets, data_values):
    """Populate datasets with original and interpolated data"""
    param_indices = {
        'alk': (0, 1), 'cal': (2, 3), 'mg': (4, 5),
        'po4_ppm': (6, 7), 'no3_ppm': (8, 9), 'sg': (10, 11)
    }
    
    for param, values in data_values.items():
        original_idx, interpolated_idx = param_indices[param]
        
        # Add original values
        datasets[original_idx]['data'] = values
        
        # Add properly interpolated values
        interpolated_values = _interpolate_missing_values(values)
        # Only show interpolated points where original data was None
        interpolated_data = []
        for orig, interp in zip(values, interpolated_values):
            interpolated_data.append(interp if orig is None and interp is not None else None)
        
        datasets[interpolated_idx]['data'] = interpolated_data

def _interpolate_missing_values(values):
    """Interpolate missing values in a dataset using linear interpolation"""
    if not values or len(values) < 2:
        return values
    
    interpolated = []
    for i, val in enumerate(values):
        if val is None:
            prev_val, prev_idx, next_val, next_idx = _find_surrounding_values(values, i)
            
            # Interpolate if we have both previous and next values
            if prev_val is not None and next_val is not None:
                steps = next_idx - prev_idx
                step_size = (next_val - prev_val) / steps
                interpolated_val = prev_val + (step_size * (i - prev_idx))
                interpolated.append(interpolated_val)
            else:
                interpolated.append(None)
        else:
            interpolated.append(val)
    
    return interpolated

def _find_surrounding_values(values, target_index):
    """Find the previous and next non-None values around a given index"""
    prev_val = None
    prev_idx = None
    next_val = None
    next_idx = None
    
    # Find previous non-None value
    for i in range(target_index - 1, -1, -1):
        if values[i] is not None:
            prev_val = values[i]
            prev_idx = i
            break
    
    # Find next non-None value
    for i in range(target_index + 1, len(values)):
        if values[i] is not None:
            next_val = values[i]
            next_idx = i
            break
    
    return prev_val, prev_idx, next_val, next_idx
