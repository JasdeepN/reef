from app import db
from sqlalchemy import Enum
import enum
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




class DosingTypeEnum(enum.Enum):
    recurring = 'recurring'
    single = 'single'
    intermittent = 'intermittent'

class Dosing(db.Model):
    __tablename__ = 'dosing'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _time = db.Column(db.DateTime)
    _type = db.Column(Enum(DosingTypeEnum), nullable=False)
    amount = db.Column(db.Float, default=0)
    reason = db.Column(db.Text)
    per_dose = db.Column(db.Float)
    prod_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    total_dose = db.Column(db.Float, nullable=False)
    daily_number_of_doses = db.Column(db.Integer)

    # Optional: relationship to Products
    product = db.relationship('Products', backref=db.backref('dosings', lazy=True))
