import numpy as np
import logging
from datetime import datetime
from modules.models import db, AlkalinityDoseModel

logger = logging.getLogger("alkalinity_model")


def initialize_alkalinity_model(tank_id, product_id, slope=1.0, intercept=0.0, weight_decay=0.9, r2_score=None, notes=None):
    logger.info(f"Initializing AlkalinityDoseModel for tank_id={tank_id}, product_id={product_id}, slope={slope}, intercept={intercept}, weight_decay={weight_decay}")
    model = AlkalinityDoseModel(
        tank_id=tank_id,
        product_id=product_id,
        slope=slope,
        intercept=intercept,
        weight_decay=weight_decay,
        last_trained=datetime.utcnow(),
        r2_score=r2_score,
        notes=notes or "Initialized with default parameters."
    )
    db.session.add(model)
    db.session.commit()
    logger.info(f"Model initialized and committed: id={model.id}")
    return model


def get_alkalinity_model(tank_id, product_id):
    logger.debug(f"Fetching AlkalinityDoseModel for tank_id={tank_id}, product_id={product_id}")
    model = AlkalinityDoseModel.query.filter_by(tank_id=tank_id, product_id=product_id).order_by(AlkalinityDoseModel.last_trained.desc()).first()
    if model:
        logger.debug(f"Found model: id={model.id}, slope={model.slope}, intercept={model.intercept}")
    else:
        logger.debug("No model found.")
    return model


def should_update_alkalinity_model(tank_id, product_id, retrain_interval_days=7):
    logger.info(f"Checking if model should be updated for tank_id={tank_id}, product_id={product_id}")
    model = get_alkalinity_model(tank_id, product_id)
    if not model:
        logger.info("No model found, should update.")
        return True
    days_since = (datetime.utcnow() - model.last_trained).days
    logger.info(f"Days since last trained: {days_since}")
    if days_since >= retrain_interval_days:
        logger.info("Retrain interval exceeded, should update.")
        return True
    logger.info("No update needed.")
    return False


def update_alkalinity_model(tank_id, product_id, dose_history, alk_history, weight_decay=0.9, notes=None):
    logger.info(f"Updating model for tank_id={tank_id}, product_id={product_id}")
    logger.debug(f"Dose history: {dose_history}")
    logger.debug(f"Alk history: {alk_history}")
    if len(dose_history) != len(alk_history) or len(dose_history) < 2:
        logger.error("Need at least 2 matching dose and alk values.")
        raise ValueError("Need at least 2 matching dose and alk values.")
    # Exponential weights: most recent = highest weight
    weights = np.array([weight_decay ** (len(dose_history) - i - 1) for i in range(len(dose_history))])
    logger.debug(f"Weights: {weights}")
    X = np.array(dose_history).reshape(-1, 1)
    y = np.array(alk_history)
    # Weighted linear regression
    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X, y, sample_weight=weights)
    slope = float(model.coef_[0])
    intercept = float(model.intercept_)
    r2 = float(model.score(X, y, sample_weight=weights))
    logger.info(f"Fitted model: slope={slope}, intercept={intercept}, r2={r2}")
    # Update or create model
    alk_model = get_alkalinity_model(tank_id, product_id)
    if not alk_model:
        alk_model = initialize_alkalinity_model(tank_id, product_id, slope, intercept, weight_decay, r2, notes)
    else:
        alk_model.slope = slope
        alk_model.intercept = intercept
        alk_model.weight_decay = weight_decay
        alk_model.last_trained = datetime.utcnow()
        alk_model.r2_score = r2
        alk_model.notes = notes or "Model updated."
        db.session.commit()
        logger.info(f"Model updated and committed: id={alk_model.id}")
    return alk_model


def predict_alkalinity_dose(tank_id, product_id, target_alk):
    logger.info(f"Predicting dose for tank_id={tank_id}, product_id={product_id}, target_alk={target_alk}")
    model = get_alkalinity_model(tank_id, product_id)
    if not model or model.slope == 0:
        logger.error("No valid model found or slope is zero.")
        raise ValueError("No valid model found or slope is zero.")
    dose = (target_alk - model.intercept) / model.slope
    logger.info(f"Predicted dose: {dose}")
    return dose


def get_alkalinity_training_data(tank_id, product_id, window_days=30):
    logger.info(f"Fetching training data for tank_id={tank_id}, product_id={product_id}, window_days={window_days}")
    from modules.models import Dosing, DSchedule, TestResults
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    window_start = now - timedelta(days=window_days)
    # Get the dosing schedule for this tank/product
    schedule = DSchedule.query.filter_by(tank_id=tank_id, products_id=product_id).order_by(DSchedule.id.desc()).first()
    if not schedule:
        logger.warning(f"No dosing schedule found for tank_id={tank_id}, product_id={product_id}")
        return [], [], [], []
    dose_amount = schedule.amount
    # Get all test results for this tank in the window
    alk_tests = TestResults.query.filter(
        TestResults.tank_id == tank_id,
        TestResults.alk != None,
        TestResults.test_date >= window_start.date()
    ).order_by(TestResults.test_date.asc()).all()
    if len(alk_tests) < 2:
        logger.error(f"Not enough alkalinity test results to train: found {len(alk_tests)} (need at least 2). Tank: {tank_id}, Product: {product_id}, Window: {window_days} days.")
        raise ValueError(f"Not enough alkalinity test results to train the model. Found {len(alk_tests)}, need at least 2.\nTank: {tank_id}, Product: {product_id}, Window: {window_days} days.")
    # For each test result, assume the dose is constant (from schedule)
    dose_history = [dose_amount for _ in alk_tests]
    dose_times = [t.test_date for t in alk_tests]  # Use test date as the 'dose time' for modeling
    alk_history = [t.alk for t in alk_tests]
    alk_times = [t.test_date for t in alk_tests]
    logger.info(f"Fetched {len(dose_history)} test results and used constant dose {dose_amount} from schedule.")
    return dose_history, alk_history, dose_times, alk_times
