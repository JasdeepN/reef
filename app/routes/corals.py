from flask import render_template, request, redirect, flash, url_for
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

@app.route("/coral/add", methods=["GET", "POST"])
def new_coral():
    form = CoralForm()
    tanks = Tank.query.all()
    if request.method == "POST":
        if form.validate_on_submit():
            taxonomy_id = request.form.get("coral_species")
            taxonomy = Taxonomy.query.get(taxonomy_id) if taxonomy_id else None
            coral_name = taxonomy.common_name if taxonomy else form.coral_name.data

            # Helper to get value or None
            def get_field(field):
                val = getattr(form, field, None)
                return val.data if val and val.data not in ("", None) else None

            coral = Coral(
                coral_name=coral_name,
                coral_type=get_field("coral_type"),
                date_acquired=get_field("date_acquired"),
                source=get_field("source"),
                tank_id=request.form.get("tank_id") or None,
                taxonomy_id=taxonomy.id if taxonomy else None,  # <-- Set taxonomy_id here
                lighting=get_field("lighting"),
                par=get_field("par"),
                flow=get_field("flow"),
                feeding=get_field("feeding"),
                placement=get_field("placement"),
                current_size=get_field("current_size"),
                color_morph=get_field("color_morph"),
                health_status=get_field("health_status"),
                frag_colony=get_field("frag_colony"),
                growth_rate=get_field("growth_rate"),
                last_fragged=get_field("last_fragged"),
                unique_id=get_field("unique_id"),
                origin=get_field("origin"),
                compatibility=get_field("compatibility"),
                photo=form.photo.data.filename if form.photo.data else None,
                notes=get_field("notes"),
                test_id=get_field("test_id")
            )
            db.session.add(coral)
            db.session.commit()
            flash("Coral added successfully!", "success")
            return redirect(url_for("coral_db"))
        else:
            flash("Please correct the errors in the form.", "danger")
            print('form errors', form.errors)
            print('form data', form.data)
            
    return render_template(
        "coral/new_coral.html",
        title="NEW CORAL",
        form=form,
        tanks=tanks,
        now=datetime.datetime.now
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

