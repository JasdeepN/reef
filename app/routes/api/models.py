from flask import Blueprint, jsonify, request
from modules.models import AlkalinityDoseModel
from modules.model_utils import alkalinity_model as akm

bp = Blueprint('models_api', __name__)

@bp.route('/get/models/<model_type>', methods=['GET'])
def get_model_entries(model_type):
    # Only 'alkalinity' supported for now
    if model_type.lower() == 'alkalinity':
        entries = AlkalinityDoseModel.query.order_by(AlkalinityDoseModel.last_trained.desc()).all()
        results = [
            {
                'id': entry.id,
                'tank_id': entry.tank_id,
                'product_id': entry.product_id,
                'slope': entry.slope,
                'intercept': entry.intercept,
                'weight_decay': entry.weight_decay,
                'last_trained': entry.last_trained,
                'r2_score': entry.r2_score,
                'notes': entry.notes
            }
            for entry in entries
        ]
        return jsonify({'model_type': 'alkalinity', 'results': results})
    else:
        return jsonify({'error': f'Model type {model_type} not supported.'}), 400

@bp.route('/models/alkalinity/retrain', methods=['POST'])
def retrain_alkalinity_model():
    import time
    data = request.get_json() or {}
    tank_id = data.get('tank_id')
    product_id = data.get('product_id')
    window_days = int(data.get('window_days', 30))
    n_compare = int(data.get('n_compare', 3))  # How many previous models to compare
    if not tank_id or not product_id:
        return jsonify({'error': 'tank_id and product_id are required'}), 400
    # Fetch training data
    start_time = time.time()
    dose_history, alk_history, _, _ = akm.get_alkalinity_training_data(tank_id, product_id, window_days)
    n_points = len(dose_history)
    if n_points < 2 or len(alk_history) < 2:
        return jsonify({'error': 'Not enough data to retrain model', 'data': {"doses": dose_history, "alk": alk_history}}), 400
    # Save new model (history is preserved by always inserting new row)
    model = akm.update_alkalinity_model(tank_id, product_id, dose_history, alk_history)
    elapsed = time.time() - start_time
    # Compare to last n_compare models
    from modules.models import AlkalinityDoseModel
    history = AlkalinityDoseModel.query.filter_by(
        tank_id=tank_id, product_id=product_id
    ).order_by(AlkalinityDoseModel.last_trained.desc()).limit(n_compare+1).all()
    shift_report = []
    if len(history) > 1:
        for i in range(1, len(history)):
            prev = history[i]
            curr = history[i-1]
            delta_slope = abs(curr.slope - prev.slope)
            delta_intercept = abs(curr.intercept - prev.intercept)
            shift_report.append({
                'compare_to_model_id': prev.id,
                'delta_slope': delta_slope,
                'delta_intercept': delta_intercept,
                'prev_slope': prev.slope,
                'curr_slope': curr.slope,
                'prev_intercept': prev.intercept,
                'curr_intercept': curr.intercept,
                'major_shift': delta_slope > 0.2 * abs(prev.slope) or delta_intercept > 0.2 * abs(prev.intercept)
            })
    suggestions = []
    if n_points < 10:
        suggestions.append("Add more test results for better accuracy (at least 10 recommended).")
    if model.r2_score is not None and model.r2_score < 0.7:
        suggestions.append("Model fit is low (R^2 < 0.7). Check for outliers or inconsistent dosing/testing.")
    suggestions.append("Ensure dosing schedule matches actual dosing and test regularly for best results.")
    return jsonify({
        'success': True,
        'model': {
            'id': model.id,
            'tank_id': model.tank_id,
            'product_id': model.product_id,
            'slope': model.slope,
            'intercept': model.intercept,
            'weight_decay': model.weight_decay,
            'last_trained': model.last_trained,
            'r2_score': model.r2_score,
            'notes': model.notes
        },
        'stats': {
            'n_points': n_points,
            'train_time_sec': round(elapsed, 3),
            'suggestions': suggestions,
            'shift_report': shift_report
        }
    })
