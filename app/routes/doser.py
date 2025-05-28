from datetime import timedelta
import urllib.parse
from flask import jsonify, render_template, request, redirect, url_for, session, flash
from app import app
from modules.models import *  # Import your models
from modules.utils.helper import *
from modules.tank_context import get_current_tank_id
from modules.forms import CombinedDosingScheduleForm
# import db
import enum
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired


@app.route("/doser")
def doser_main():
    tank_id = get_current_tank_id()
    if not tank_id:
        flash("No tank selected.", "warning")
    # Define columns for the doser table
    columns = [
        {"data": "id", "label": "ID"},
        # {"data": "tank_id", "label": "Tank ID"},
        {"data": "name", "label": "Product Name"},
        {"data": "trigger_interval", "label": "Interval"},
        {"data": "suspended", "label": "Suspended"},
        {"data": "last_refill", "label": "Last Refill"},
        {"data": "amount", "label": "Amount"},
    ]
    config = {
        "id": "doser_table",
        "title": "Dosing Schedules",
        "columns": columns,
        "api_urls": {
            "get": "/web/fn/schedule/get/all",
            "delete": "/web/fn/schedule/delete/",
            "post": "/web/fn/schedule/new/",
            "put": "/web/fn/schedule/edit/",
        },
        "datatable_options": {
            "dom": "Bfrtip",
            "buttons": [
                {"text": "Add", "action": "add"},
                {"text": "Edit", "action": "edit"},
                {"text": "Delete", "action": "delete"}
            ],
            "serverSide": True,
            "processing": True,
        },
        "initial_data": [],
    }
    return render_template("doser/main.html", title="Doser", table=config)


@app.route("/doser/db", methods=['GET'])
def db_doser():
    from sqlalchemy import text
    tank_id = get_current_tank_id()
    sql = """
        SELECT dosing.*, d_schedule.id AS schedule_id
        FROM dosing
        JOIN d_schedule ON dosing.schedule_id = d_schedule.id
        WHERE d_schedule.tank_id = :tank_id;
    """
    result = db.session.execute(text(sql), {'tank_id': tank_id}).mappings()
    rows = []
    for row in result:
        row_dict = dict(row)
        # Convert timedelta fields to string or seconds
        for k, v in row_dict.items():
            if isinstance(v, timedelta):
                row_dict[k] = str(v)
            # Convert boolean/int fields to "Yes"/"No" for booleans (including 0/1)
            if k == "suspended":
                row_dict[k] = "Yes" if bool(v) else "No"
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
    tank_id = get_current_tank_id()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    # Define columns for d_schedule table using the actual model fields
    cols = ['id', 'tank_id', 'product_id', 'trigger_interval', 'suspended', 'last_refill', 'amount']
    columns = generate_columns(cols)
    # Only show schedules for the current tank context
    schedules = DSchedule.query.filter_by(tank_id=tank_id).all()
    # Convert schedules to dicts for JSON serialization (if needed by frontend)
    schedules_dicts = [s.__dict__.copy() for s in schedules]
    for s in schedules_dicts:
        s.pop('_sa_instance_state', None)
    d_schedule_table = {
        "id": "d_schedule",
        "api_url": "/web/fn/ops/get/d_schedule",
        "title": "Edit Dosing Schedules",
        "columns": columns,
        "datatable_options": {
            "dom": "Bfrtip",
            "buttons": [
                {"text": "Edit", "action": "edit"},
                {"text": "Delete", "action": "delete"}
            ],
            "serverSide": True,
            "processing": True,
        },
        "initial_data": schedules_dicts,
    }
    form = CombinedDosingScheduleForm()
    return render_template(
        "doser/modify.html",
        forms=form,
        selector=form.options(),
        title="Modify Dosing",
        d_schedule_table=d_schedule_table
    )

@app.route("/doser/schedule", methods=["GET", "POST"])
def run_schedule():
    tank_id = get_current_tank_id()
    urls = {
        "GET": "/web/fn/schedule/get/stats",  # always use the context, not a tank_id param
        "DELETE": "/web/fn/ops/delete/d_schedule",
        "POST": "/web/fn/ops/new/d_schedule",
        "PUT": "/web/fn/ops/edit/d_schedule"
    }
    return render_template("doser/schedule.html", title="Schedule", api_urls=urls, tank_id=tank_id)
    




@app.route("/doser/submit", methods=["POST"])
def doser_submit():
    tank_id = get_current_tank_id()
    if not tank_id:
        return jsonify({"success": False, "error": "No tank selected"}), 400
    data = request.get_json()
    form_type = data.get("form_type")
    if not form_type:
        return jsonify({"success": False, "error": "Missing form_type"}), 400

    # --- Handle new product creation if needed ---
    if data.get("product_id") == "add_new_product":
        product_fields = {"name", "total_volume", "current_avail", "dry_refill"}
        product_data = {k: v for k, v in data.items() if k in product_fields}
        from app import app as flask_app
        with flask_app.test_request_context():
            with flask_app.test_client() as client:
                resp = client.post("/web/fn/ops/new/products", json=product_data)
                prod_resp = resp.get_json()
                if not prod_resp or not prod_resp.get("success") or not prod_resp.get("id"):
                    return jsonify({"success": False, "error": "Failed to create new product"}), 400
                data["product_id"] = prod_resp["id"]

    if not data.get("product_id"):
        return jsonify({"success": False, "error": "Product ID is required"}), 400

    if "schedule_time" in data:
        data["_time"] = data["schedule_time"]
        data.pop("schedule_time", None)

    # Always set tank_id in the data dict for downstream API calls
    # data["tank_id"] = tank_id

    from app import app as flask_app
    with flask_app.test_request_context():
        with flask_app.test_client() as client:
            
            if form_type == "recurring":
                # Validation for recurring
                required_fields = ["amount", "product_id", "trigger_interval", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for recurring: {', '.join(missing)}"
                    }), 400
                # Insert only into d_schedule (not dosing)
                schedule_data = {
                    "amount": data["amount"],
                    "product_id": data["product_id"],
                    "trigger_interval": data["trigger_interval"],
                    "suspended": data.get("suspended", False),
                    "tank_id": tank_id,
                }
                sched_resp = client.post("/web/fn/ops/new/d_schedule", json=schedule_data)
                return sched_resp.get_data(), sched_resp.status_code, sched_resp.headers.items()
            elif form_type in ("single", "intermittent"):
                required_fields = ["amount", "product_id", "_time"]
                missing = [field for field in required_fields if not data.get(field)]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields for {form_type}: {', '.join(missing)}"
                    }), 400
                api_url = "/web/fn/ops/new/dosing"
                dosing_data = {
                    "amount": data["amount"],
                    "product_id": data["product_id"],
                    "trigger_time": data["_time"],
                }
                resp = client.post(api_url, json=dosing_data)
                return resp.get_data(), resp.status_code, resp.headers.items()
            else:
                return jsonify({"success": False, "error": "Unknown form_type"}), 400
            

@app.route("/doser/products", methods=["GET"])
def get_products():
    urls = {
        "GET": "/web/fn/products/stats",
        "DELETE": "/web/fn/ops/delete/products",
        "POST": "/web/fn/ops/new/products",
        "PUT": "/web/fn/ops/edit/products"
    }
    return render_template("doser/products.html", title="Products", api_urls=urls)