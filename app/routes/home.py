from flask import render_template, request, redirect, flash, url_for, session, jsonify
from datetime import datetime
from sqlalchemy import text
from app import app, db
from modules.models import Tank, TestResults
from modules.tank_context import get_current_tank_id, ensure_tank_context
from modules.timezone_utils import format_time_for_display, datetime_to_iso_format

@app.route("/", methods=["GET"])
def index():
    # No need to pass tanks or tank_id, context processor handles it
    return render_template("home.html")

@app.route("/set_tank", methods=["POST"])
def set_tank():
    tank_id = request.form.get('tank_id', type=int)
    if tank_id:
        session['tank_id'] = tank_id
    return redirect(request.referrer or url_for('index'))

@app.route("/api/tank-context", methods=["GET"])
def get_tank_context():
    """API endpoint to check current tank context without causing redirects"""
    tank_id = get_current_tank_id()
    return jsonify({
        "has_context": tank_id is not None,
        "tank_id": tank_id,
        "tanks": [{"id": tank.id, "name": tank.name} for tank in Tank.query.all()]
    })

@app.route("/chart", methods=["GET"])
def test_results_chart():
    """Route for displaying test results in chart format"""
    tank_id = ensure_tank_context()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    return render_template("chart/test_results_chart.html")

def _create_chart_datasets():
    """Create the dataset configuration for Chart.js"""
    return [
        {
            "label": "Alkalinity (dKH)",
            "data": [],
            "borderColor": "rgb(75, 192, 192)",
            "backgroundColor": "rgba(75, 192, 192, 0.2)",
            "yAxisID": "y"
        },
        {
            "label": "Calcium (ppm)",
            "data": [],
            "borderColor": "rgb(255, 99, 132)",
            "backgroundColor": "rgba(255, 99, 132, 0.2)",
            "yAxisID": "y1"
        },
        {
            "label": "Magnesium (ppm)",
            "data": [],
            "borderColor": "rgb(54, 162, 235)",
            "backgroundColor": "rgba(54, 162, 235, 0.2)",
            "yAxisID": "y1"
        },
        {
            "label": "PO4 (ppm)",
            "data": [],
            "borderColor": "rgb(255, 206, 86)",
            "backgroundColor": "rgba(255, 206, 86, 0.2)",
            "yAxisID": "y2"
        },
        {
            "label": "NO3 (ppm)",
            "data": [],
            "borderColor": "rgb(153, 102, 255)",
            "backgroundColor": "rgba(153, 102, 255, 0.2)",
            "yAxisID": "y3"
        },
        {
            "label": "Specific Gravity",
            "data": [],
            "borderColor": "rgb(255, 159, 64)",
            "backgroundColor": "rgba(255, 159, 64, 0.2)",
            "yAxisID": "y4"
        }
    ]

def _format_test_label(test):
    """Format test date and time for chart labels"""
    if test.test_date and test.test_time:
        return f"{test.test_date.strftime('%Y-%m-%d')} {format_time_for_display(test.test_time)}"
    return test.test_date.strftime('%Y-%m-%d') if test.test_date else 'Unknown'

def _extract_test_values(test):
    """Extract test values for chart data points"""
    return [
        test.alk if test.alk is not None else None,
        test.cal if test.cal is not None else None,
        test.mg if test.mg is not None else None,
        test.po4_ppm if test.po4_ppm is not None else None,
        test.no3_ppm if test.no3_ppm is not None else None,
        test.sg if test.sg is not None else None
    ]

def _find_surrounding_values(values, index):
    """Find the previous and next non-None values around a given index"""
    prev_val = prev_idx = next_val = next_idx = None
    
    # Look backward for previous value
    for j in range(index - 1, -1, -1):
        if values[j] is not None:
            prev_val, prev_idx = values[j], j
            break
    
    # Look forward for next value
    for j in range(index + 1, len(values)):
        if values[j] is not None:
            next_val, next_idx = values[j], j
            break
    
    return prev_val, prev_idx, next_val, next_idx

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

def _create_interpolated_datasets(tests):
    """Create datasets with original and interpolated data"""
    datasets = []
    base_datasets = _create_chart_datasets()
    
    # Extract all values for each parameter
    all_values = [[] for _ in range(6)]  # 6 parameters
    
    for test in tests:
        values = _extract_test_values(test)
        for i, value in enumerate(values):
            all_values[i].append(value)
    
    # Create datasets with interpolation
    for i, base_dataset in enumerate(base_datasets):
        original_values = all_values[i]
        interpolated_values = _interpolate_missing_values(original_values)
        
        # Create original data dataset (solid line)
        original_dataset = base_dataset.copy()
        original_dataset["data"] = original_values
        original_dataset["spanGaps"] = False
        datasets.append(original_dataset)
        
        # Create interpolated data dataset (dashed line) 
        # Only show interpolated points where original data was None
        interpolated_dataset = base_dataset.copy()
        interpolated_dataset["label"] = f"{base_dataset['label']} (Interpolated)"
        interpolated_dataset["borderDash"] = [5, 5]
        interpolated_dataset["backgroundColor"] = "transparent"
        interpolated_dataset["pointRadius"] = 0  # Hide points for interpolated line
        interpolated_dataset["pointHoverRadius"] = 3
        
        # Create data array with interpolated values only where original was None
        interpolated_data = []
        for orig, interp in zip(original_values, interpolated_values):
            interpolated_data.append(interp if orig is None and interp is not None else None)
        
        interpolated_dataset["data"] = interpolated_data
        interpolated_dataset["spanGaps"] = True
        datasets.append(interpolated_dataset)
    
    return datasets

def _prepare_interpolated_chart_data(tests):
    """Prepare chart data with interpolation for missing values"""
    labels = [_format_test_label(test) for test in tests]
    datasets = _create_interpolated_datasets(tests)
    
    return {
        "labels": labels,
        "datasets": datasets
    }

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Docker and monitoring systems"""
    health_status = {
        "status": "healthy",
        "service": "reefdb",
        "timestamp": datetime.now().isoformat()
    }
    
    # Test database connectivity
    try:
        db.session.execute(text("SELECT 1"))
        health_status["database"] = "connected"
        status_code = 200
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["database"] = "disconnected" 
        health_status["database_error"] = str(e)
        # Return 200 instead of 503 to prevent container restart during startup
        status_code = 200
    
    return jsonify(health_status), status_code

# Catch all unregistered routes and redirect to the 404 page
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404