from flask import jsonify, render_template, request, redirect, flash, url_for
from werkzeug.utils import secure_filename
from app import app, db
from modules import utils
from modules.forms import CoralForm
from modules.models import Coral, Tank, Taxonomy  # Add Taxonomy import
import os
import datetime
from modules.utils import generate_columns


@app.route("/timeline")
def timeline():
    return render_template("coral/index.html", title="Timeline")


def get_field(form, field):
    val = getattr(form, field, None)
    return val.data if val and val.data not in ("", None) else None


def build_coral(form, taxonomy=None):
    # Set coral name according to your rules
    if taxonomy:
        if taxonomy.common_name and form.color_morph.data:
            coral_name = f"{taxonomy.common_name} {form.color_morph.data}"
        elif taxonomy.common_name:
            coral_name = taxonomy.common_name
        elif form.color_morph.data:
            coral_name = form.color_morph.data
        else:
            coral_name = taxonomy.species_name if hasattr(taxonomy, "species_name") else None
    else:
        coral_name = form.coral_name.data if hasattr(form, "coral_name") else None

    return Coral(
        coral_name=coral_name,
        coral_type=get_field(form, "coral_type"),
        date_acquired=get_field(form, "date_acquired"),
        source=get_field(form, "source"),
        tank_id=request.form.get("tank_id") or None,
        taxonomy_id=taxonomy.id if taxonomy else None,
        lighting=get_field(form, "lighting"),
        par=get_field(form, "par"),
        flow=get_field(form, "flow"),
        feeding=get_field(form, "feeding"),
        placement=get_field(form, "placement"),
        current_size=get_field(form, "current_size"),
        color_morph=get_field(form, "color_morph"),
        health_status=get_field(form, "health_status"),
        frag_colony=get_field(form, "frag_colony"),
        growth_rate=get_field(form, "growth_rate"),
        last_fragged=get_field(form, "last_fragged"),
        unique_id=get_field(form, "unique_id"),
        origin=get_field(form, "origin"),
        compatibility=get_field(form, "compatibility"),
        photo=form.photo.data.filename if form.photo.data else None,
        notes=get_field(form, "notes"),
        test_id=get_field(form, "test_id")
    )


@app.route("/coral/add", methods=["GET", "POST"])
def new_coral():
    form = CoralForm()
    tanks = Tank.query.all()
    if request.method == "POST":
        print(form.data)
        # Get submitted IDs from the form
        genus_id = form.genus_id.data
        taxonomy_id = form.taxonomy_id.data

        # Try to find taxonomy by color morph first, then by genus
        taxonomy = None
        if taxonomy_id:
            taxonomy = Taxonomy.query.filter_by(taxonomy_id=taxonomy_id).first()
        if not taxonomy and genus_id:
            taxonomy = Taxonomy.query.filter_by(genus_id=genus_id).first()

        # Now set taxonomy_id for the coral
        if taxonomy:
            form.taxonomy_id.data = taxonomy.id
        else:
            form.taxonomy_id.data = None  # Or handle as error

        if not form.validate_on_submit():
            errors = form.errors
            return render_template(
                "coral/new_coral.html",
                title="NEW CORAL",
                form=form,
                tanks=tanks,
                now=datetime.datetime.now,
                form_errors=errors
            )

        coral = build_coral(form, taxonomy)
        db.session.add(coral)
        db.session.commit()
        print("Coral object created:", coral)
        return jsonify({"status": "success", "message": "Coral added successfully!"})

    return render_template(
        "coral/new_coral.html",
        title="NEW CORAL",
        form=form,
        tanks=tanks,
        now=datetime.datetime.now,
        form_errors={}
    )


@app.route("/coral/view", methods=['GET'])
def coral_db():

    urls = {
        "GET": "/api/get/coral_stats",
        "DELETE": "/api/delete/corals",
        "POST": "/api/new/corals",
        "PUT": "/api/edit/corals"
    }
    return render_template('coral/gallery.html', title="Corals", api_urls=urls)

