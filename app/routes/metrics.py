from app import app
from app import x_metrics
from flask import render_template
from sqlalchemy import desc
from modules.models import * 

# Track the number of requests to the /test endpoint
@app.route('/x/test')
@x_metrics.counter('test_requests_total', 'Total requests to the /test endpoint')
def run_metrics():
    result = TestResults.query.order_by(desc(TestResults.id))
    return render_template("metrics/test_metrics.html", db_response=result)