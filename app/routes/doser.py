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
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }
        }]
    )

@app.route("/doser/modify", methods=['GET'])
def modify_doser():
    from modules.utils import get_table_columns, generate_columns
    from app.routes.api import TABLE_MAP, db
    import enum

    # Get all products
    product_col_name = get_table_columns(Products)
    product_cols = generate_columns(product_col_name)
    products = Products.query.order_by(Products.id).all()

    # For each product, get related dosing entries
    dosing_col_name = get_table_columns(Dosing)
    dosing_cols = generate_columns(dosing_col_name)
    product_dosing = []
    for product in products:
        dosing_entries = Dosing.query.filter_by(prod_id=product.id).all()
        for dosing in dosing_entries:
            # Combine product and dosing info in a dict
            row = {}
            for col in product_col_name:
                val = getattr(product, col)
                if isinstance(val, enum.Enum):
                    val = val.value
                row[f"product_{col}"] = val
            for col in dosing_col_name:
                val = getattr(dosing, col)
                if isinstance(val, enum.Enum):
                    val = val.value
                row[f"dosing_{col}"] = val
            product_dosing.append(row)

    # print(product_dosing, 'product_dosing')

    # join_data = datatables_response(product_dosing, None, 1)
    # print(join_data, 'join_data')
    # Prepare tables for template
    tables = [
        {
            "id": "products",
            "api_url": "/api/get/products",
            "title": "Products",
            "columns": product_cols,
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }
        },
        {
            "id": "dosing",
            "api_url": "/api/get/dosing",
            "title": "Dosing",
            "columns": dosing_cols,
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }

        },
        {  
            "id": "products_dosing_join",
            "api_url": None,
            "title": "Products & Dosing Join",
            "columns": generate_columns(list(product_dosing[0].keys()) if product_dosing else []),
            "initial_data": product_dosing,
            "datatable_options": {
                "dom": "frtip", 
                "buttons": [],
                "serverSide": False,
                "processing": False,
            },
        }
    ]

    return render_template('doser/modify_doser.html', tables=tables)

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
        "columns": product_cols,
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }
        },
        {
        "id":"dosing",
        "api_url":"/api/get/dosing",
        "title":"Dosing",
        "columns": dosing_cols,
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }
        },
        
    ]
    # print(type(tables))

    return render_template('doser/modify_doser.html', tables=tables)

