import urllib.parse
from flask import jsonify, render_template, request
from app import app
from modules.models import *  # Import your models
from modules.utils import *
from app.routes.api import TABLE_MAP, db
import enum
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired


@app.route("/doser", methods=["GET"])
def doser_joined():
    import json
    import urllib.parse
    from app.routes.api import advanced_join_query, TABLE_MAP, db

    # Prepare parameters for advanced_join_query
    print(request.args, 'request.args')
    # we know what tables went to join in this route
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
            "initial_data": data,
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

@app.route("/doser/db", methods=['GET'])
def db_doser():

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
                # If this is the prod_id column, replace with product name
                if col == "prod_id":
                    val = product.name  # Assuming Products has a 'name' field
                    row["dosing_product_name"] = val
                else:
                    row[f"dosing_{col}"] = val
            product_dosing.append(row)


    # join_data = datatables_response(product_dosing, None, 1)
    # print(join_data, 'join_data')
    # Prepare tables for template
    # print(product_dosing, 'product_dosing')

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

    return render_template('doser/dosing_db.html', tables=tables)

@app.route("/doser/modify", methods=["GET", "POST"])
def modify_doser():
    d_form = DosingForm()
    p_form = ProductForm()
    s_form = DScheduleForm()
    if d_form.validate_on_submit():
        # Handle form submission logic here (e.g., save to DB)
        # Example:
        # new_dosing = Dosing(
        #     _time=form._time.data,
        #     _type=form._type.data,
        #     amount=form.amount.data,
        #     reason=form.reason.data,
        #     per_dose=form.per_dose.data,
        #     prod_id=form.prod_id.data,
        #     total_dose=form.total_dose.data,
        #     daily_number_of_doses=form.daily_number_of_doses.data
        # )
        # db.session.add(new_dosing)
        # db.session.commit()
        pass  # Implement as needed
    
    # forms = [(form, "dosing add")]


    return render_template("doser/modify.html", d_form=d_form, p_form=p_form, s_form=s_form, title="Modify Dosing")

@app.route("/doser/schedule", methods=["GET", "POST"])
def run_schedule():

    cols =  ['id', 'trigger_interval', 'amount', 'current_avail', 'total_volume', 'name']

    named_cols = generate_columns(cols)
    # print(named_cols, 'named_cols')
    table=[
        {  
            "id": "schedule",
            "api_url": '/api/get/schedule',
            "title": "Schedule",
            "columns": named_cols,
            "datatable_options": {
                "dom": "frtip", 
                "buttons": [],
                "serverSide": False,
                "processing": False,
            },
        }
    ]
    # packaged = datatables_response(result, None, 1)
    # print(packaged, 'packaged')
    return render_template("doser/schedule.html", tables=table, title="Schedule Dosing")