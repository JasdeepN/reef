from flask import render_template, request, redirect, flash
from sqlalchemy import desc
from app import app
from modules.models import TestResults, test_result_form
from modules.db_functions import insert_test_row


@app.route("/test")
def run_test():
    result = TestResults.query.order_by(desc(TestResults.id))
    return render_template("test/test_page.html", db_response=result)

@app.route("/test/add", methods=['GET', 'POST'])
async def add_test():
    form = test_result_form()
    if form.validate_on_submit():
        result = await insert_test_row(TestResults, form)
        assert result != False, "error inserting"
        return redirect('/test')
    elif request.method == 'GET':
        return render_template("test/add_test.html", form=form)
    else:
        flash("form error, no data added", "error")
        return redirect('/test/add')

# @app.route("/test/modify", methods=['GET', 'POST'])
# def test_modify():
#     grid = TestResults.query.order_by(desc(TestResults.id))
#     return render_template('test/modify_test.html', grid=grid)


@app.route("/test/db", methods=['GET'])
def test_modify():
    tables= [
        {
        "id":"test_results",
        "api_url":"/api/get/test_results",
        "title":"Test Results",
        "columns" : [
            {"label": "ID", "data": "id"},
            {"label": "Test Date", "data": "test_date"},
            {"label": "Test Time", "data": "test_time"},
            {"label": "Alkalinity (KH)", "data": "alk"},
            {"label": "Phosphate (PO₄³⁻ ppm)", "data": "po4_ppm"},
            {"label": "Phosphate (PO₄³⁻ ppb)", "data": "po4_ppb"},
            {"label": "Nitrate (NO₃⁻ ppm)", "data": "no3_ppm"},
            {"label": "Calcium (Ca²⁺ ppm)", "data": "cal"},
            {"label": "Magnesium (Mg²⁺ ppm)", "data": "mg"},
            {"label": "Specific Gravity (SG)", "data": "sg"}
        ],
        }
    ]
    return render_template('test/modify_test.html', tables=tables)