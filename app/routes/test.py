from flask import render_template, request, redirect, flash, url_for
from sqlalchemy import desc
from app import app
from modules.models import Tank, TestResults
from modules.forms import test_result_form
from modules.db_functions import insert_test_row
from modules.tank_context import get_current_tank_id

# Parameter status evaluation functions
def get_alk_status(value):
    """Evaluate alkalinity status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if 7.0 <= value <= 12.0:
        return 'status-good'
    elif 6.0 <= value < 7.0 or 12.0 < value <= 14.0:
        return 'status-warning'
    else:
        return 'status-danger'

def get_cal_status(value):
    """Evaluate calcium status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if 380 <= value <= 450:
        return 'status-good'
    elif 350 <= value < 380 or 450 < value <= 500:
        return 'status-warning'
    else:
        return 'status-danger'

def get_mg_status(value):
    """Evaluate magnesium status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if 1250 <= value <= 1400:
        return 'status-good'
    elif 1150 <= value < 1250 or 1400 < value <= 1500:
        return 'status-warning'
    else:
        return 'status-danger'

def get_po4_status(value):
    """Evaluate phosphate status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if value <= 0.1:
        return 'status-good'
    elif 0.1 < value <= 0.2:
        return 'status-warning'
    else:
        return 'status-danger'

def get_no3_status(value):
    """Evaluate nitrate status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if value <= 10:
        return 'status-good'
    elif 10 < value <= 25:
        return 'status-warning'
    else:
        return 'status-danger'

def get_sg_status(value):
    """Evaluate specific gravity status based on reef tank standards."""
    if not value:
        return 'status-unknown'
    if 1.024 <= value <= 1.026:
        return 'status-good'
    elif 1.022 <= value < 1.024 or 1.026 < value <= 1.028:
        return 'status-warning'
    else:
        return 'status-danger'


@app.route("/test")
def test_results():
    tank_id = get_current_tank_id()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    tests = TestResults.query.filter_by(tank_id=tank_id).order_by(TestResults.test_date.desc(), TestResults.test_time.desc()).all()
    
    return render_template("test/results.html", 
                         tests=tests, 
                         tank_id=tank_id,
                         get_alk_status=get_alk_status,
                         get_cal_status=get_cal_status,
                         get_mg_status=get_mg_status,
                         get_po4_status=get_po4_status,
                         get_no3_status=get_no3_status,
                         get_sg_status=get_sg_status)

@app.route("/test/add", methods=['GET', 'POST'])
async def add_test():
    form = test_result_form()
    if form.validate_on_submit():
        result = await insert_test_row(TestResults, form, get_current_tank_id())
        assert result != False, "error inserting"
        return redirect('/test/db')
    elif request.method == 'GET':
        return render_template("test/add_test.html", form=form)
    else:
        flash("form error, no data added", "error")
        return redirect('/test/add')

@app.route("/test/db", methods=['GET'])
def test_modify():
    tank_id = get_current_tank_id()
    if not tank_id:
        flash("No tank selected.", "warning")
        return redirect(url_for('index'))
    from modules.utils.helper import get_table_columns, generate_columns

    test_col_names = get_table_columns(TestResults)
    test_cols = generate_columns(test_col_names)

    tables = [
        {
            "id": "test_results",
            "api_url": "/web/fn/ops/get/test_results",
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

