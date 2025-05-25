from flask import render_template, request, redirect, flash, url_for, jsonify
from app import app, db
from modules.models import AlkalinityDoseModel
from modules.models import Products  # Import Products model
from modules.models import Tank
from modules.tank_context import get_current_tank_id
from flask_wtf import FlaskForm
from wtforms import IntegerField, DecimalField, DateTimeField, SubmitField
from wtforms.validators import DataRequired

def get_products_for_model(model_type):
    """
    Return a list of (id, name) tuples for products that match the model_type.
    Uses the 'uses' column in Products, e.g. '+Alk', '-NO3', etc.
    """
    tag_map = {
        'Alkalinity': '+Alk',
        'Nitrate': ['+NO3', '-NO3'],
        'Phosphate': ['+PO4', '-PO4'],
        'Calcium': '+Ca',
        'Magnesium': '+Mg',
    }
    tag = tag_map.get(model_type)
    if isinstance(tag, list):
        products = Products.query.filter(Products.uses.in_(tag)).all()
    else:
        products = Products.query.filter(Products.uses == tag).all()
    return [(p.id, p.name) for p in products]

class AlkalinityModelTuningForm(FlaskForm):
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    product_id = IntegerField("Product", validators=[DataRequired()])
    test_time = DateTimeField("Test Time", format="%Y-%m-%d %H:%M:%S", validators=[DataRequired()])
    alk_dkh = DecimalField("Alkalinity (dKH)", validators=[DataRequired()])
    submit = SubmitField("Submit")

class NitrateModelTuningForm(FlaskForm):
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    product_id = IntegerField("Product", validators=[DataRequired()])
    test_time = DateTimeField("Test Time", format="%Y-%m-%d %H:%M:%S", validators=[DataRequired()])
    nitrate_ppm = DecimalField("Nitrate (ppm)", validators=[DataRequired()])
    submit = SubmitField("Submit")

class PhosphateModelTuningForm(FlaskForm):
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    product_id = IntegerField("Product", validators=[DataRequired()])
    test_time = DateTimeField("Test Time", format="%Y-%m-%d %H:%M:%S", validators=[DataRequired()])
    phosphate_ppb = IntegerField("Phosphate (ppb)", validators=[DataRequired()])
    submit = SubmitField("Submit")

class CalciumModelTuningForm(FlaskForm):
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    product_id = IntegerField("Product", validators=[DataRequired()])
    test_time = DateTimeField("Test Time", format="%Y-%m-%d %H:%M:%S", validators=[DataRequired()])
    calcium_ppm = IntegerField("Calcium (ppm)", validators=[DataRequired()])
    submit = SubmitField("Submit")

class MagnesiumModelTuningForm(FlaskForm):
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    product_id = IntegerField("Product", validators=[DataRequired()])
    test_time = DateTimeField("Test Time", format="%Y-%m-%d %H:%M:%S", validators=[DataRequired()])
    magnesium_ppm = IntegerField("Magnesium (ppm)", validators=[DataRequired()])
    submit = SubmitField("Submit")

@app.route("/models/tuning/alkalinity", methods=["GET", "POST"])
def model_tuning_alkalinity():
    form = AlkalinityModelTuningForm()
    form.product_id.choices = get_products_for_model("Alkalinity")
    if form.validate_on_submit():
        # Here you would update or create the AlkalinityDoseModel for this tank/product
        # Example: (fit model elsewhere, just save params here)
        alk_model = AlkalinityDoseModel(
            tank_id=form.tank_id.data,
            product_id=form.product_id.data,
            slope=1.0,  # Replace with actual fit
            intercept=0.0,  # Replace with actual fit
            weight_decay=0.9,
            r2_score=1.0,
            notes="Auto-generated from submission"
        )
        db.session.add(alk_model)
        db.session.commit()
        return jsonify({"status": "success", "message": "Alkalinity model updated!"})
    return render_template("models/base.html", model_type='Alkalinity', data=None)

@app.route("/models/view", methods=["GET"])
def model_tuning_view():
    entries = AlkalinityDoseModel.query.order_by(AlkalinityDoseModel.id.desc()).all()
    rendered = render_template("models/view.html", entries=entries)
    json_data = [{
        "id": entry.id,
        "tank_id": entry.tank_id,
        "product_id": entry.product_id,
        "slope": entry.slope,
        "intercept": entry.intercept,
        "weight_decay": entry.weight_decay,
        "last_trained": entry.last_trained,
        "r2_score": entry.r2_score,
        "notes": entry.notes
    } for entry in entries]
    return rendered, 200, {"Content-Type": "text/html", "X-Model-Data": str(json_data)}
