from flask import render_template, request, redirect, flash, url_for, session
from app import app, db
from modules.models import Tank, TestResults, get_current_tank_id

@app.route("/", methods=["GET"])
def index():
    # No need to pass tanks or tank_id, context processor handles it
    return render_template("home.html")

@app.route("/set_tank", methods=["POST"])
def set_tank():
    tank_id = request.form.get('tank_id', type=int)
    if tank_id:
        session['tank_id'] = tank_id
    return redirect(request.referrer or url_for('index'))

@app.route("/test")
def tests():
    tank_id = session.get('tank_id')
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    tests = TestResults.query.filter_by(tank_id=tank_id).order_by(TestResults.test_date.desc(), TestResults.test_time.desc()).all()
    return render_template("test/results.html", tests=tests)

# Catch all unregistered routes and redirect to the 404 page
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404