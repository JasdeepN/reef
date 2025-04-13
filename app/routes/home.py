from flask import render_template
from app import app

@app.route("/")
def index():
    return render_template("home.html")

# Catch all unregistered routes and redirect to the 404 page
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404