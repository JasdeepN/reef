from flask import render_template, request, redirect, flash
from sqlalchemy import desc
from app import app
from modules.models import test_results, test_result_form
from modules.db_functions import insert_test_row

@app.route("/test")
def run_test():
    result = test_results.query.order_by(desc(test_results.id))
    return render_template("test/test_page.html", db_response=result)

@app.route("/test/add", methods=['GET', 'POST'])
async def add_test():
    form = test_result_form()
    if form.validate_on_submit():
        result = await insert_test_row(test_results, form)
        assert result != False, "error inserting"
        return redirect('/test')
    elif request.method == 'GET':
        return render_template("test/add_test.html", form=form)
    else:
        flash("form error, no data added", "error")
        return redirect('/test/add')

@app.route("/test/modify", methods=['GET', 'POST'])
def test_modify():
    grid = test_results.query.order_by(desc(test_results.id))
    return render_template('test/modify_test.html', grid=grid)