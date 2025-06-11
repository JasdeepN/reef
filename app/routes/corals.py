import pprint
from flask import jsonify, render_template, request, redirect, flash, url_for, session
from werkzeug.utils import secure_filename
from app import app, db
from modules.utils import helper
from modules.forms import CoralForm
from modules.models import Coral, Tank, Taxonomy, ColorMorphs
from modules.system_context import get_current_system_id, get_current_system_tank_ids
import os
import datetime
from modules.utils.helper import generate_columns, validate_and_process_data

# Constants to avoid code duplication
NEW_CORAL_TEMPLATE = "coral/new_coral.html"
NEW_CORAL_TITLE = "NEW CORAL"
ERROR_NO_SYSTEM = "No system selected."
ERROR_NO_TANKS = "No tanks in selected system."


@app.route("/timeline")
def timeline():
    return render_template("coral/index.html", title="Timeline")


def get_field(form, field):
    """Extract field value from form object."""
    val = getattr(form, field, None)
    return val.data if val and val.data not in ("", None) else None


def build_coral(form, taxonomy=None, color_morph=None):
    """Build coral object from form data with reduced complexity."""
    # Extract basic fields
    unique_id = get_field(form, "unique_id")
    coral_name = _build_coral_name(taxonomy, color_morph, unique_id, form)
    
    # Create coral with basic data
    coral_data = _extract_coral_data(form)
    coral_data['coral_name'] = coral_name
    
    return Coral(**coral_data)


def _build_coral_name(taxonomy, color_morph, unique_id, form):
    """Build coral name from taxonomy and color morph data."""
    coral_name = None
    
    if taxonomy and color_morph:
        coral_name = _build_name_from_taxonomy_and_morph(taxonomy, color_morph)
    elif taxonomy:
        coral_name = _build_name_from_taxonomy(taxonomy)
    elif color_morph:
        coral_name = color_morph.morph_name
    else:
        coral_name = get_field(form, "coral_name")
    
    # Add unique ID if present
    if unique_id and coral_name:
        coral_name = f"{coral_name} ({unique_id})"
    elif unique_id:
        coral_name = f"({unique_id})"
    
    return coral_name


def _build_name_from_taxonomy_and_morph(taxonomy, color_morph):
    """Build name from both taxonomy and color morph."""
    if taxonomy.common_name and color_morph.morph_name:
        return f"{taxonomy.common_name} {color_morph.morph_name}"
    elif taxonomy.common_name:
        return taxonomy.common_name
    elif color_morph.morph_name:
        return color_morph.morph_name
    else:
        return f"{taxonomy.genus} {taxonomy.species}" if taxonomy else None


def _build_name_from_taxonomy(taxonomy):
    """Build name from taxonomy only."""
    return taxonomy.common_name or f"{taxonomy.genus} {taxonomy.species}"


def _extract_coral_data(form):
    """Extract coral data from form with all fields."""
    return {
        'tank_id': get_field(form, "tank_id"),
        'taxonomy_id': get_field(form, "taxonomy_id"),
        'color_morph_id': get_field(form, "color_morph_id"),
        'unique_id': get_field(form, "unique_id"),
        'current_size': get_field(form, "current_size"),
        'position_x': get_field(form, "position_x"),
        'position_y': get_field(form, "position_y"),
        'health_status': get_field(form, "health_status"),
        'date_acquired': get_field(form, "date_acquired"),
        'cost': get_field(form, "cost"),
        'source': get_field(form, "source"),
        'notes': get_field(form, "notes"),
        'lighting_preference': get_field(form, "lighting_preference"),
        'flow_preference': get_field(form, "flow_preference"),
        'difficulty_level': get_field(form, "difficulty_level")
    }


@app.route("/coral/add", methods=["GET", "POST"])
def new_coral():
    # Ensure system context
    system_id = get_current_system_id()
    if not system_id:
        flash("No system selected.", "warning")
        return redirect(url_for('index'))
    
    # Get tanks in current system for choices
    from modules.system_context import get_current_system_tanks
    system_tanks = get_current_system_tanks()
    if not system_tanks:
        flash("No tanks found in current system.", "warning")
        return redirect(url_for('index'))
    
    form = CoralForm()
    form.tank_id.choices = [(tank.id, tank.name) for tank in system_tanks]
    
    if request.method == "POST":
        print(form.data)
        
        # Validate that selected tank belongs to current system
        selected_tank_id = form.tank_id.data
        if selected_tank_id not in [tank.id for tank in system_tanks]:
            flash("Selected tank does not belong to current system.", "error")
            return render_template(
                NEW_CORAL_TEMPLATE,
                title=NEW_CORAL_TITLE,
                form=form,
                now=datetime.datetime.now,
                form_errors={"tank_id": ["Invalid tank selection"]}
            )
        
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
                NEW_CORAL_TEMPLATE,
                title=NEW_CORAL_TITLE,
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
        NEW_CORAL_TEMPLATE,
        title=NEW_CORAL_TITLE,
        form=form,
        now=datetime.datetime.now,
        form_errors={}
    )


@app.route("/coral/timeline")
def coral_view():
    tank_ids = get_current_system_tank_ids()
    corals = Coral.query.filter(Coral.tank_id.in_(tank_ids)).all() if tank_ids else []
    return render_template("coral/index.html", corals=corals)


@app.route("/coral/view", methods=['GET'])
def coral_db():
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
from modules.system_context import get_current_system_id
import enum
from datetime import date, time

@app.route("/web/fn/get/corals", methods=["GET"])
def get_corals_for_tank():
    try:
        system_id = get_current_system_id()
        tank_ids = get_current_system_tank_ids()
        if not system_id or not tank_ids:
            return jsonify({
                "draw": int(request.args.get('draw', 1)),
                "recordsTotal": 0,
                "recordsFiltered": 0,
                "data": [],
                "error": "No system selected."
            })
        draw = int(request.args.get('draw', 1))
        params = {
            'search': request.args.get('search', ''),
            'sidx': request.args.get('sidx', ''),
            'sord': request.args.get('sord', 'asc'),
            'page': request.args.get('page', 1),
            'rows': request.args.get('rows', 10)
        }
        base_query = Coral.query.filter(Coral.tank_id.in_(tank_ids))
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


