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
    # used_amt = DecimalField("Used Amount", validators=[])
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

    def validate(self):
        if self.amount is not None and self.amount < 0:
            raise ValueError("Amount must be non-negative")
        if self.per_dose is not None and self.per_dose < 0:
            raise ValueError("Per dose must be non-negative")
        if self.total_dose is not None and self.total_dose < 0:
            raise ValueError("Total dose must be non-negative")
        if self.daily_number_of_doses is not None and self.daily_number_of_doses < 0:
            raise ValueError("Daily number of doses must be non-negative")
        if self.prod_id is None:
            raise ValueError("Product must be selected")
        if self._type is None:
            raise ValueError("Dosing type must be specified")


class DosingForm(FlaskForm):
    type = SelectField(
        "Dosing Type",
        choices=[(e.value, e.value.capitalize()) for e in DosingTypeEnum],
        validators=[DataRequired()]
    )
    time = DateField("Dosing Time", format='%Y-%m-%d', validators=[Optional()])
    prod_id = SelectField("Product", coerce=int, validators=[Optional()])
    per_dose = DecimalField("Per Dose", validators=[Optional()])
   
    total_dose = DecimalField("Total Dose", validators=[DataRequired()])
    daily_number_of_doses = IntegerField("Daily Number of Doses", validators=[Optional()])
    amount = DecimalField("Amount", validators=[Optional()])
    reason = TextAreaField("Reason", validators=[Optional(), Length(max=255)])
   
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate product choices from the database
        self.prod_id.choices = [
            (p.id, p.name) for p in Products.query.order_by(Products.name).all()
        ]


class DSchedule(db.Model):
    __tablename__ = 'd_schedule'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prod_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    amount = db.Column(db.Float)
    last_trigger = db.Column(db.DateTime, default=None)
    trigger_interval = db.Column(db.Integer, nullable=False)

    # Relationship to Products
    product = db.relationship('Products', backref=db.backref('schedules', lazy=True))

    def __repr__(self):
        return f"<DSchedule id={self.id} prod_id={self.prod_id} amount={self.amount}>"


class DScheduleForm(FlaskForm):
    prod_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", validators=[DataRequired()])
    last_trigger = DateField("Last Trigger", format='%Y-%m-%d', validators=[Optional()])
    trigger_interval = IntegerField("Trigger Interval (minutes)", validators=[DataRequired()])
    submit = SubmitField("Submit")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate product choices from the database
        self.prod_id.choices = [
            (p.id, p.name) for p in Products.query.order_by(Products.name).all()
        ]

def get_d_schedule_dict(d_schedule):
    """Helper to serialize DSchedule model to dict."""
    return {
        "id": d_schedule.id,
        "prod_id": d_schedule.prod_id,
        "product_name": d_schedule.product.name if d_schedule.product else None,
        "amount": d_schedule.amount,
        "last_trigger": d_schedule.last_trigger.isoformat() if d_schedule.last_trigger else None,
        "trigger_interval": d_schedule.trigger_interval,
    }


