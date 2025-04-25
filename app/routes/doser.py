import urllib.parse
from flask import render_template, request
from app import app
from modules.models import Products, TestResults, Dosing  # Import your models
from modules.utils import *

@app.route("/doser", methods=["GET"])
def doser_joined():
    import json
    import urllib.parse
    from app.routes.api import advanced_join_query, TABLE_MAP, db

    # Prepare parameters for advanced_join_query
    table_names = ["products", "dosing"]
    join_type = "inner"
    join_conditions = [getattr(TABLE_MAP["products"], "id") == getattr(TABLE_MAP["dosing"], "prod_id")]

    

    # No filters, order_by, limit, or offset for this simple join
    data = advanced_join_query(
        db=db,
        TABLE_MAP=TABLE_MAP,
        table_names=table_names,
        join_type=join_type,
        join_conditions=join_conditions,
        filters=None,
        order_by=None,
        limit=None,
        offset=None,
    )

    # print(data , 'data')
    tables = "products,dosing"
    conditions = json.dumps([["products.id", "dosing.prod_id"]])  # Proper JSON
    # Do NOT encode here, just send the raw JSON string for JS
    js_safe_url = f"/api/get/advanced_join?tables={tables}&join_type={join_type}&conditions={conditions}"

    cols = generate_columns(data[0].keys()) if data else []
    # print (data)
    return render_template(
        'doser/doser.html',
        tables=[{
            "id": "products_dosing_join",
            "api_url": js_safe_url,  # Pass the JS-safe URL
            "title": "Products & Dosing Join",
            "columns": cols,
            # "data": data,
            # "total": data.total,
        }]
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

    dosing_col_name = get_table_columns(Dosing)
    dosing_cols = generate_columns(dosing_col_name)

    # print('product_cols', product_cols)
    # print('mnaual_cols', dosing_cols)
    tables= [
        {
        "id":"products",
        "api_url":"/api/get/products",
        "title":"Products",
        "columns": product_cols
        },
        {
        "id":"dosing",
        "api_url":"/api/get/dosing",
        "title":"Dosing",
        "columns": dosing_cols
        },
        
    ]
    # print(type(tables))

    return render_template('doser/modify_doser.html', tables=tables)

