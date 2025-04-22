from flask import render_template
from app import app
from modules.models import Products, ManualDosing, DoseEvents
from modules.models import TestResults, ManualDosing, Products  # Import your models
from modules.utils import get_table_columns, generate_columns

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

# @app.route("/doser/modify", methods=['GET', 'POST'])
# def modify_doser():
#     products = Products.query.order_by(Products.id).all()
#     manual_dosing = ManualDosing.query.order_by(ManualDosing.id).all()
#     return render_template('doser/modify_doser.html', products=products, manual_dosing=manual_dosing)

@app.route("/doser/db", methods=['GET'])
def test_doser():
    product_col_name = get_table_columns(Products)
    product_cols = generate_columns(product_col_name)

    manual_dosing_col_name = get_table_columns(ManualDosing)
    manaual_cols = generate_columns(manual_dosing_col_name)

    # print('product_cols', product_cols)
    # print('mnaual_cols', manaual_cols)
    tables= [
        {
        "id":"products",
        "api_url":"/api/get/products",
        "title":"Products",
        "columns": product_cols
        },
        {
        "id":"manual_dosing",
        "api_url":"/api/get/manual_dosing",
        "title":"Manual Dosing",
        "columns": manaual_cols
        },
        
    ]
    print(type(tables))

    return render_template('doser/modify_doser.html', tables=tables)

