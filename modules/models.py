from app import db
from sqlalchemy import Enum
import enum
from sqlalchemy import Computed

from flask_wtf import FlaskForm 
from wtforms import StringField, DateField, TimeField, DecimalField, RadioField, SelectField, TextAreaField, SubmitField, IntegerField, HiddenField
from wtforms.validators import Optional, DataRequired, Length
from wtforms.fields import DateTimeField

import datetime as dt

from modules.forms import *

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
    total_volume = db.Column(db.Float, nullable=True)
    current_avail = db.Column(db.Float, nullable=True)
    dry_refill = db.Column(db.Float, nullable=True, default=None)
    used_amt = db.Column(
        db.Float,
        Computed("total_volume - current_avail", persisted=True)  # Generated column
    )

    def __repr__(self):
        return f"<Product {self.name}>"

    def validate(self):
        """Raise ValueError if any field is invalid."""
        if not self.name or not self.name.strip():
            raise ValueError("Name is required")
        if self.total_volume is not None and self.total_volume < 0:
            raise ValueError("Total volume must be non-negative")
        if self.current_avail is not None and self.current_avail < 0:
            raise ValueError("Current available must be non-negative")
        if self.dry_refill is not None and self.dry_refill < 0:
            raise ValueError("Dry refill must be non-negative")

    def to_dict(self, include_private=False):
        """Serialize product to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'total_volume': self.total_volume,
            'current_avail': self.current_avail,
            'used_amt': self.used_amt,
            'dry_refill': self.dry_refill,
        }
        if include_private:
            data['_sa_instance_state'] = getattr(self, '_sa_instance_state', None)
        return data

    @staticmethod
    def from_dict(data):
        """Create a Products instance from a dictionary, ignoring unknown keys."""
        allowed = {'name', 'total_volume', 'current_avail', 'dry_refill'}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return Products(**filtered)


class ProductForm(BaseForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=30)])
    total_volume = DecimalField("Total Volume", validators=[Optional()])
    current_avail = DecimalField("Current Available", validators=[Optional()])
    dry_refill = DecimalField("Dry Refill", validators=[Optional()])
    submit = SubmitField("Submit")


class DosingTypeEnum(enum.Enum):
    recurring = 'recurring'
    single = 'single'
    intermittent = 'intermittent'

class Dosing(db.Model):
    __tablename__ = 'dosing'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _time = db.Column(db.DateTime)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    prod_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    product = db.relationship('Products', backref=db.backref('dosings', lazy=True))

    def validate(self):
        if self.amount is not None and self.amount < 0:
            raise ValueError("Amount must be non-negative")
        if self.prod_id is None:
            raise ValueError("Product must be selected")
        if self._time is None:
            raise ValueError("Dosing time must be specified")
        if self.amount is None:
            raise ValueError("Amount must be specified")
        if self._type is None:
            raise ValueError("Dosing type must be specified")
        if self._time is None:
            raise ValueError("Dosing time must be specified")


class DSchedule(db.Model):
    __tablename__ = 'd_schedule'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prod_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    last_trigger = db.Column(db.DateTime, default=None)
    trigger_interval = db.Column(db.Integer, nullable=False)
    suspended = db.Column(db.Boolean, default=False)
    last_refill = db.Column(db.DateTime, default=None)
    amount = db.Column(db.Float, default=None, nullable=False)

    # Relationship to Products
    product = db.relationship('Products', backref=db.backref('schedules', lazy=True))

def get_d_schedule_dict(d_schedule):
    """Helper to serialize DSchedule model to dict."""
    return {
        "id": d_schedule.id,
        "product_name": d_schedule.product.name if d_schedule.product else None,
        "last_trigger": d_schedule.last_trigger.isoformat() if d_schedule.last_trigger else None,
        "trigger_interval": d_schedule.trigger_interval,
        "suspended": d_schedule.suspended,
        "last_refill": d_schedule.last_refill.isoformat() if d_schedule.last_refill else None,
        "amount": d_schedule.amount
    }


