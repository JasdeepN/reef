from app import db

from sqlalchemy import Computed

from flask_wtf import FlaskForm 
from wtforms import StringField, DateField, TimeField, DecimalField, RadioField, SelectField, TextAreaField, SubmitField, IntegerField, HiddenField
from wtforms.validators import Optional, DataRequired, Length

import datetime as dt

from modules.forms import BaseForm

class TestResults(db.Model):
    __tablename__ = 'test_results'
    id = db.Column(db.Integer, primary_key=True)
    test_date = db.Column(db.Date)
    test_time = db.Column(db.Time) 
    alk = db.Column(db.Float)
    po4_ppm = db.Column(db.Float)
    po4_ppb = db.Column(db.Integer)
    no3_ppm = db.Column(db.Integer)
    cal = db.Column(db.Integer)
    mg = db.Column(db.Float)
    sg = db.Column(db.Float)

    def __getattribute__(self, name):
        return super().__getattribute__(name)
    

class test_result_form(FlaskForm):
    test_date = DateField("Date", default=dt.datetime.today)
    test_time = TimeField("Test Time", format='%H:%M:%S', default=dt.datetime.now)
    alk = DecimalField("Alkalinity (KH)", [Optional()])
    po4_ppm = DecimalField("Phosphate (PO\u2084\u00b3\u207b PPM)", [Optional()])
    po4_ppb = IntegerField("Phosphate (PO\u2084\u00b3\u207b PPB)", [Optional()])
    no3_ppm = DecimalField("Nitrate (NO\u2083\u207b PPM)", [Optional()])
    cal = IntegerField("Calcium (Ca\u00b2\u207a PPM)", [Optional()])
    mg = IntegerField("Magneisum (Mg\u00b2\u207a PPM)", [Optional()])
    sg = DecimalField("Specific Gravity (SG)", [Optional()])
    submit = SubmitField()

    # Custom validate method
    def validate(self, extra_validators=None):
        if super().validate(extra_validators):
            valid = False
            for k in self.data:
                if k not in ['test_date', 'test_time', 'csrf_token', 'submit'] and self.data[k] is not None:
                    valid = True
            return valid
        return False


class Products(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), nullable=False)
    dose_amt = db.Column(db.Float, nullable=True)
    total_volume = db.Column(db.Float, nullable=True)
    current_avail = db.Column(db.Float, nullable=True)
    used_amt = db.Column(
        db.Float,
        Computed("total_volume - current_avail", persisted=True)  # Generated column
    )

    def __repr__(self):
        return f"<Product {self.name}>"

    def validate(self):
        if not self.name:
            raise ValueError("Name is required")
        if self.dose_amt is not None and self.dose_amt < 0:
            raise ValueError("Dose amount must be non-negative")
        if self.total_volume is not None and self.total_volume < 0:
            raise ValueError("Total volume must be non-negative")
        if self.current_avail is not None and self.current_avail < 0:
            raise ValueError("Current available must be non-negative")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'dose_amt': self.dose_amt,
            'total_volume': self.total_volume,
            'current_avail': self.current_avail,
            'used_amt': self.used_amt
        }


class ProductForm(BaseForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=30)])
    dose_amt = DecimalField("Dose Amount", validators=[Optional()])
    total_volume = DecimalField("Total Volume", validators=[Optional()])
    current_avail = DecimalField("Current Available", validators=[Optional()])
    used_amt = DecimalField("Used Amount", validators=[Optional()])
    submit = SubmitField("Submit")


class ManualDosing(db.Model):
    __tablename__ = 'manual_dosing'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    added_on = db.Column(db.Date, nullable=False)
    dosed_at = db.Column(db.Time, nullable=False)
    product = db.Column(db.String(128), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    reason = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<ManualDosing {self.product}>"
    # Custom validate method
    def validate(self, extra_validators=None):
        if super().validate(extra_validators):
            if not self.added_on:
                raise ValueError("Added on date is required")
            if not self.dosed_at:
                raise ValueError("Dosed at time is required")
            if not self.product:
                raise ValueError("Product is required")
            if self.amount is not None and self.amount < 0:
                raise ValueError("Amount must be non-negative")
            if self.reason and len(self.reason) > 500:
                raise ValueError("Reason must be less than 500 characters")
        
    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added_on.strftime("%Y-%m-%d"),
            'dosed_at': self.dosed_at.strftime("%H:%M:%S"),
            'product': self.product,
            'amount': self.amount,
            'reason': self.reason
        }


class ManualDosingForm(BaseForm):
    added_on = DateField("Added On", validators=[DataRequired()])
    dosed_at = TimeField("Dosed At", format='%H:%M:%S', validators=[DataRequired()])
    product = StringField("Product", validators=[DataRequired(), Length(max=128)])
    amount = DecimalField("Amount", validators=[Optional()])
    reason = TextAreaField("Reason", validators=[Optional()])
    submit = SubmitField("Submit")


class DoseEvents(db.Model):
    __tablename__ = 'dose_events'

    dose_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    repeat_type = db.Column(db.Enum('Hourly', 'Split-Dose', 'Bi-Hourly', 'Quarterly', 'Custom'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    until_no = db.Column(db.Integer, nullable=True)
    f_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    description = db.Column(db.String(30), nullable=True)

    product = db.relationship('Products', backref='dose_events', lazy=True)

    def __repr__(self):
        return f"<DoseEvents {self.description}>"