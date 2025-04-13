from flask import render_template
from app import app
from modules.models import Products, ManualDosing, DoseEvents

@app.route("/doser", methods=['GET', 'POST'])
def run_doser():
    products = Products.query.order_by(Products.id).all()
    manual_dosing = ManualDosing.query.order_by(ManualDosing.id).all()
    dose_events = DoseEvents.query.order_by(DoseEvents.dose_id).all()
    return render_template(
        'doser/doser.html',
        products=products,
        manual_dosing=manual_dosing,
        dose_events=dose_events
    )

@app.route("/doser/modify", methods=['GET', 'POST'])
def modify_doser():
    products = Products.query.order_by(Products.id).all()
    manual_dosing = ManualDosing.query.order_by(ManualDosing.id).all()
    return render_template('doser/modify_doser.html', products=products, manual_dosing=manual_dosing)