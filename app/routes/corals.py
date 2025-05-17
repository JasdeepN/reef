import pprint
from flask import jsonify, render_template, request, redirect, flash, url_for, session
from werkzeug.utils import secure_filename
from app import app, db
from modules.utils import helper
from modules.forms import CoralForm
from modules.models import Coral, Tank, Taxonomy, ColorMorphs, get_current_tank_id # Add Taxonomy, ColorMorph, and get_current_tank_id import
from modules.tank_context import get_current_tank_id
import os
import datetime
from modules.utils.helper import generate_columns


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
        tank_id=request.form.get("tank_id") or form.tank_id.data,
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
    urls = {
        "GET": "/web/fn/get/coral_stats",
        "DELETE": "/web/fn/delete/corals",
        "POST": "/web/fn/new/corals",
        "PUT": "/web/fn/edit/corals"
    }
    return render_template('coral/gallery.html', title="Corals", api_urls=urls)


