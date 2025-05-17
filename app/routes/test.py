from flask import render_template, request, redirect, flash, url_for
from sqlalchemy import desc
from app import app
from modules.models import TestResults, test_result_form, Tank
from modules.db_functions import insert_test_row
from modules.tank_context import get_current_tank_id


@app.route("/test")
def test_results():
    tank_id = get_current_tank_id()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    tests = TestResults.query.filter_by(tank_id=tank_id).order_by(TestResults.test_date.desc(), TestResults.test_time.desc()).all()
    return render_template("test/results.html", tests=tests)

@app.route("/test/add", methods=['GET', 'POST'])
async def add_test():
    tank_id = get_current_tank_id()
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

@app.route("/test/db", methods=['GET'])
def test_modify():
    tank_id = get_current_tank_id()
    from modules.utils.helper import get_table_columns, generate_columns

    test_col_names = get_table_columns(TestResults)
    test_cols = generate_columns(test_col_names)

    tables = [
        {
            "id": "test_results",
            "api_url": "/web/fn/get/test_results",
            "title": "Test Results",
            "columns": test_cols,
            "datatable_options": {
                "dom": "Bfrtip",
                "buttons": [
                    {"text": "Add", "action": "add"},
                    {"text": "Edit", "action": "edit"},
                    {"text": "Delete", "action": "delete"}
                ]
            }
        }
    ]
    return render_template('test/modify_test.html', tables=tables)