from datetime import timedelta
import urllib.parse
from flask import jsonify, render_template, request, redirect, url_for
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
    # import json
    # import urllib.parse
    # from app.routes.api import advanced_join_query, TABLE_MAP, db

    # # Prepare parameters for advanced_join_query
    # print(request.args, 'request.args')
    # # we know what tables went to join in this route
    # table_names = ["products", "dosing"]
    # join_type = "inner"
    # join_conditions = [getattr(TABLE_MAP["products"], "id") == getattr(TABLE_MAP["dosing"], "prod_id")]

    # # No filters, order_by, limit, or offset for this simple join
    # data = advanced_join_query(
    #     db=db,
    #     TABLE_MAP=TABLE_MAP,
    #     table_names=table_names,
    #     join_type=join_type,
    #     join_conditions=join_conditions,
    #     filters=None,
    #     order_by=None,
    #     limit=None,
    #     offset=None,
    # )

    # # print(data , 'data')
    # tables = "products,dosing"
    # conditions = json.dumps([["products.id", "dosing.prod_id"]])  # Proper JSON
    # # Do NOT encode here, just send the raw JSON string for JS
    # js_safe_url = f"/api/get/advanced_join?tables={tables}&join_type={join_type}&conditions={conditions}"

    # cols = generate_columns(data[0].keys()) if data else []
    # # print (data)
    # return render_template(
    #     'doser/doser.html',
    #     tables=[{
    #         "id": "products_dosing_join",
    #         "api_url": js_safe_url,  # Pass the JS-safe URL
    #         "title": "Products & Dosing Join",
    #         "columns": cols,
    #         "initial_data": data,
    #         "datatable_options": {
    #             "dom": "Bfrtip",
    #             "buttons": [
    #                 {"text": "Add", "action": "add"},
    #                 {"text": "Edit", "action": "edit"},
    #                 {"text": "Delete", "action": "delete"}
    #             ]
    #         }
    #     }]
    # )
    return jsonify({
        "success": True,
        "message": "This is a placeholder for the joined data."
    })

@app.route("/doser/db", methods=['GET'])
def db_doser():
    from sqlalchemy import text
    sql = """
        select * from  d_schedule join products on d_schedule.prod_id=products.id;
    """
    result = db.session.execute(text(sql)).mappings()
    rows = []
    for row in result:
        row_dict = dict(row)
        # Convert timedelta fields to string or seconds
        for k, v in row_dict.items():
            if isinstance(v, timedelta):
                row_dict[k] = str(v)  # or v.total_seconds() if you want seconds as int/float
        rows.append(row_dict)

    columns = generate_columns(rows[0].keys()) if rows else []

    tables = [
        {
            "id": "products_dosing_schedule_join",
            "api_url": None,
            "title": "Products & Dosing Schedule Join",
            "columns": columns,
            "initial_data": rows,
            "datatable_options": {
                "dom": "Bfrtip",
                  "buttons": [
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ],
                "serverSide": False,
                "processing": False,
            },
        }
    ]

    return render_template('doser/dosing_db.html', tables=tables)

@app.route("/doser/modify", methods=["GET", "POST"])
def modify_doser():
    form = CombinedDosingScheduleForm()
    return render_template(
        "doser/modify.html",
        forms=form,  # CombinedDosingScheduleForm instance
        selector=form.options(),  # For the dosing type dropdown
        title="Modify Dosing"
    )

@app.route("/doser/schedule", methods=["GET", "POST"])
def run_schedule():

    cols =  ['id', 'suspended', 'trigger_interval', 'amount', 'current_avail', 'total_volume', 'name']

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

from flask import request, jsonify
import requests

@app.route("/doser/submit", methods=["POST"])
def doser_submit():
    data = request.get_json()
    form_type = data.get("form_type")
    if not form_type:
        return jsonify({"success": False, "error": "Missing form_type"}), 400

    # --- Handle new product creation if needed ---
    if data.get("prod_id") == "add_new_product":
        product_fields = {"name", "dose_amt", "total_volume", "current_avail", "dry_refill"}
        product_data = {k: v for k, v in data.items() if k in product_fields}
        from app import app as flask_app
        with flask_app.test_request_context():
            with flask_app.test_client() as client:
                resp = client.post("/api/new/products", json=product_data)
                prod_resp = resp.get_json()
                if not prod_resp or not prod_resp.get("success") or not prod_resp.get("id"):
                    return jsonify({"success": False, "error": "Failed to create new product"}), 400
                data["prod_id"] = prod_resp["id"]

    if not data.get("prod_id"):
        return jsonify({"success": False, "error": "Product ID is required"}), 400

    if "schedule_time" in data:
        data["_time"] = data["schedule_time"]
        data.pop("schedule_time", None)

    from app import app as flask_app
    with flask_app.test_request_context():
        with flask_app.test_client() as client:
            if form_type == "recurring":
                # Validation for recurring
                required_fields = ["amount", "prod_id", "trigger_interval", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for recurring: {', '.join(missing)}"
                    }), 400
                # Insert only into d_schedule (not dosing)
                schedule_data = {
                    "amount": data["amount"],
                    "prod_id": data["prod_id"],
                    "trigger_interval": data["trigger_interval"],
                    "_time": data["_time"]
                }
                
                sched_resp = client.post("/api/new/d_schedule", json=schedule_data)
                return sched_resp.get_data(), sched_resp.status_code, sched_resp.headers.items()
            elif form_type in ("single", "intermittent"):
                required_fields = ["amount", "prod_id", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for {form_type}: {', '.join(missing)}"
                    }), 400
                api_url = "/api/new/dosing"
                resp = client.post(api_url, json={k: data[k] for k in ["amount", "prod_id", "_time"]})
                return resp.get_data(), resp.status_code, resp.headers.items()
            else:
                return jsonify({"success": False, "error": "Unknown form_type"}), 400