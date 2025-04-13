from flask import render_template, request, redirect, flash
from werkzeug.utils import secure_filename
from app import app
from modules import utils
import os

@app.route("/timeline/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        if file and utils.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash('uploaded', 'success')
        return render_template('timeline/upload.html')
    else:
        return render_template('timeline/upload.html')