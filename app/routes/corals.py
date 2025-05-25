import pprint
from flask import jsonify, render_template, request, redirect, flash, url_for, session
from werkzeug.utils import secure_filename
from app import app, db
from modules.utils import helper
from modules.forms import CoralForm
from modules.models import Coral, Tank, Taxonomy, ColorMorphs # Add Taxonomy, ColorMorph
from modules.tank_context import get_current_tank_id
import os
import datetime
from modules.utils.helper import generate_columns, validate_and_process_data


@app.route("/timeline")
def timeline():
    return render_template("coral/index.html", title="Timeline")


def get_field(form, field):
    val = getattr(form, field, None)
    return val.data if val and val.data not in ("", None) else None


def build_coral(form, taxonomy=None, color_morph=None):
    # Build coral_name using taxonomy and color morph objects, and append unique_id if present
    unique_id = get_field(form, "unique_id")
    if taxonomy and color_morph:
        if taxonomy.common_name and color_morph.morph_name:
            coral_name = f"{taxonomy.common_name} {color_morph.morph_name}"
        elif taxonomy.common_name:
            coral_name = taxonomy.common_name
        elif color_morph.morph_name:
            coral_name = color_morph.morph_name
        else:
            coral_name = f"{taxonomy.genus} {taxonomy.species}" if taxonomy else None
    elif taxonomy:
        coral_name = taxonomy.common_name or f"{taxonomy.genus} {taxonomy.species}"
    elif color_morph:
        coral_name = color_morph.morph_name
    else:
        coral_name = form.coral_name.data if hasattr(form, "coral_name") else None

    if unique_id:
        coral_name = f"{coral_name} ({unique_id})" if coral_name else f"({unique_id})"

    return Coral(
        coral_name=coral_name,
        date_acquired=get_field(form, "date_acquired"),
        tank_id=get_current_tank_id(),
        taxonomy_id=taxonomy.id if taxonomy else None,
        color_morphs_id=color_morph.id if color_morph else None,
        vendors_id=request.form.get("vendors_id") or form.vendors_id.data,
        par=get_field(form, "par"),
        flow=get_field(form, "flow"),
        placement=get_field(form, "placement"),
        current_size=get_field(form, "current_size"),
        health_status=get_field(form, "health_status"),
        frag_colony=get_field(form, "frag_colony"),
        # growth_rate=get_field(form, "growth_rate"),
        last_fragged=get_field(form, "last_fragged"),
        unique_id=get_field(form, "unique_id"),
        # origin=get_field(form, "origin"),
        # compatibility=get_field(form, "compatibility"),
        photo=form.photo.data.filename if form.photo.data else None,
        notes=get_field(form, "notes"),
        test_id=get_field(form, "test_id")
    )


@app.route("/coral/add", methods=["GET", "POST"])
def new_coral():
    form = CoralForm()
    if request.method == "POST":
        print(form.data)
        morph_id = request.form.get("color_morphs_id") or form.color_morphs_id.data
        species_id = request.form.get("species_id") or getattr(form, "species_id", None)
        color_morph = ColorMorphs.query.get(morph_id) if morph_id else None
        taxonomy = None
        if species_id:
            taxonomy = Taxonomy.query.get(species_id)
        elif color_morph:
            taxonomy = color_morph.taxonomy
        print("Selected taxonomy:", taxonomy)
        print("Selected color morph:", color_morph)
        if not form.validate_on_submit():
            errors = form.errors
            return render_template(
                "coral/new_coral.html",
                title="NEW CORAL",
                form=form,
                now=datetime.datetime.now,
                form_errors=errors
            )
        coral = build_coral(form, taxonomy=taxonomy, color_morph=color_morph)
        db.session.add(coral)
        db.session.commit()
        print("Coral object created:", coral)
        return redirect(url_for("coral_db"))
    return render_template(
        "coral/new_coral.html",
        title="NEW CORAL",
        form=form,
        now=datetime.datetime.now,
        form_errors={}
    )


@app.route("/coral/timeline")
def coral_view():
    corals = Coral.query.filter_by(tank_id=get_current_tank_id()).all()
    return render_template("coral/index.html", corals=corals)


@app.route("/coral/view", methods=['GET'])
def coral_db():
    tank_id = get_current_tank_id()
    urls = {
        "GET": "/web/fn/get/corals",
        "DELETE": "/web/fn/delete/corals",
        "POST": "/web/fn/new/corals",
        "PUT": "/web/fn/edit/corals"
    }
    return render_template('coral/gallery.html', title="Corals", api_urls=urls)


# DataTables-compatible endpoint for corals filtered by tank context
from flask import Blueprint, jsonify, request
from modules.models import Coral
from modules.tank_context import get_current_tank_id
import enum
from datetime import date, time

@app.route("/web/fn/get/corals", methods=["GET"])
def get_corals_for_tank():
    try:
        tank_id = get_current_tank_id()
        if not tank_id:
            return jsonify({
                "draw": int(request.args.get('draw', 1)),
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
                "error": "No tank selected."
            })
        draw = int(request.args.get('draw', 1))
        params = {
            'search': request.args.get('search', ''),
            'sidx': request.args.get('sidx', ''),
            'sord': request.args.get('sord', 'asc'),
            'page': request.args.get('page', 1),
            'rows': request.args.get('rows', 10)
        }
        base_query = Coral.query.filter_by(tank_id=tank_id)
        all_results = base_query.all()
        data = []
        for row in all_results:
            row_data = {}
            for column in Coral.__table__.columns:
                value = getattr(row, column.name)
                if isinstance(value, enum.Enum):
                    row_data[column.name] = value.value
                elif isinstance(value, date):
                    row_data[column.name] = value.strftime("%Y-%m-%d")
                elif isinstance(value, time):
                    row_data[column.name] = value.strftime("%H:%M:%S")
                else:
                    row_data[column.name] = value
            data.append(row_data)
        from modules.utils.helper import apply_datatables_query_params_to_dicts
        filtered_data, total_filtered = apply_datatables_query_params_to_dicts(data, params)
        response = {
            "draw": draw,
            "recordsTotal": len(data),
            "recordsFiltered": total_filtered,
            "data": filtered_data,
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({
            "draw": int(request.args.get('draw', 1)),
            "recordsTotal": 0,
            "recordsFiltered": 0,
            "data": [],
            "error": str(e)
        })

@app.route("/web/fn/new/corals", methods=["POST"])
def new_coral_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        # Required fields check (customize as needed)
        required = ["coral_name", "tank_id"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400
        # Use validate_and_process_data if needed
        processed = validate_and_process_data(Coral, data) if 'validate_and_process_data' in globals() else data
        coral = Coral(**{k: v for k, v in processed.items() if hasattr(Coral, k)})
        db.session.add(coral)
        db.session.commit()
        return jsonify({"success": True, "id": coral.id, "message": "Coral added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/web/fn/edit/corals", methods=["POST", "PUT"])
def edit_coral_api():
    try:
        data = request.get_json()
        if not data or not data.get("id"):
            return jsonify({"success": False, "error": "No data or missing coral ID"}), 400
        coral = Coral.query.get(data["id"])
        if not coral:
            return jsonify({"success": False, "error": "Coral not found"}), 404
        processed = validate_and_process_data(Coral, data) if 'validate_and_process_data' in globals() else data
        for k, v in processed.items():
            if k != "id" and hasattr(coral, k):
                setattr(coral, k, v)
        db.session.commit()
        return jsonify({"success": True, "message": "Coral updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


