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

from flask_sqlalchemy import SQLAlchemy


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

    def to_dict(self):
        return {
            "id": self.id,
            "test_date": self.test_date.isoformat() if self.test_date else None,
            "test_time": self.test_time.strftime('%H:%M:%S') if self.test_time else None,
            "alk": self.alk,
            "po4_ppm": self.po4_ppm,
            "po4_ppb": self.po4_ppb,
            "no3_ppm": self.no3_ppm,
            "cal": self.cal,
            "mg": self.mg,
            "sg": self.sg,
        }
    

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
    name = db.Column(db.String(30))
    total_volume = db.Column(db.Float)
    current_avail = db.Column(db.Float)
    used_amt = db.Column(db.Float)  # This is a generated column in MySQL, not directly supported in SQLAlchemy
    dry_refill = db.Column(db.Float)
    last_update = db.Column(db.TIMESTAMP, server_default=None, onupdate=db.func.current_timestamp())

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
    trigger_time = db.Column(db.DateTime(3))
    amount = db.Column(db.Float, nullable=False)
    prod_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    sched_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=True)
    product = db.relationship('Products', backref=db.backref('dosings', lazy=True))
    schedule = db.relationship('DSchedule', backref=db.backref('dosings', lazy=True))



    def validate(self):
        if self.amount is not None and self.amount < 0:
            raise ValueError("Amount must be non-negative")
        if self.prod_id is None:
            raise ValueError("Product must be selected")
        if self.amount is None:
            raise ValueError("Amount must be specified")
        if self._type is None:
            raise ValueError("Dosing type must be specified")
        if self.trigger_time is None:
            raise ValueError("Dosing time must be specified")


class DSchedule(db.Model):
    __tablename__ = 'd_schedule'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trigger_interval = db.Column(db.Integer, nullable=False)
    suspended = db.Column(db.Boolean, default=False)
    last_refill = db.Column(db.DateTime, default=None)
    amount = db.Column(db.Float, nullable=False)
    tanks_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    products_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)

    # Relationships
    tank = db.relationship('Tank', backref=db.backref('schedules', lazy=True))
    product = db.relationship('Products', backref=db.backref('schedules', lazy=True))

    def __repr__(self):
        return f"<DSchedule {self.id} (Tank {self.tanks_id}, Product {self.products_id})>"

def get_d_schedule_dict(d_schedule):
    """Helper to serialize DSchedule model to dict."""
    return {
        "id": d_schedule.id,
        "product_name": d_schedule.product.name if d_schedule.product else None,
        "trigger_interval": d_schedule.trigger_interval,
        "suspended": d_schedule.suspended,
        "last_refill": d_schedule.last_refill.isoformat() if d_schedule.last_refill else None,
        "amount": d_schedule.amount
    }

class Coral(db.Model):
    __tablename__ = 'corals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coral_name = db.Column(db.String(128), nullable=False, index=True)
    date_acquired = db.Column(db.Date, nullable=False, index=True)
    par = db.Column(db.Integer)
    flow = db.Column(db.Enum('Low', 'Medium', 'High'))
    current_size = db.Column(db.String(64))
    health_status = db.Column(db.Enum(
        'Healthy', 'Recovering', 'New', 'Stressed', 'Dying', 'Dead', 'Other'
    ))
    frag_colony = db.Column(db.Enum('Frag', 'Colony'))
    last_fragged = db.Column(db.Date)
    unique_id = db.Column(db.String(64))
    photo = db.Column(db.String(255))
    notes = db.Column(db.Text)
    test_id = db.Column(db.Integer, db.ForeignKey('test_results.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp()
    )

    taxonomy_id = db.Column(db.Integer, db.ForeignKey('taxonomy.id'), nullable=False, index=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    vendors_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    color_morphs_id = db.Column(db.Integer, db.ForeignKey('color_morphs.id'), nullable=True, index=True)

    # Relationships
    test_result = db.relationship('TestResults', backref='corals', lazy=True)
    tank = db.relationship('Tank', backref='corals', lazy=True)
    taxonomy = db.relationship('Taxonomy', backref='corals', lazy=True)
    vendor = db.relationship('Vendors', backref='corals', lazy=True)
    color_morph = db.relationship('ColorMorphs', backref='corals', lazy=True)

class Tank(db.Model):
    __tablename__ = 'tanks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(45), nullable=False)
    gross_water_vol = db.Column(db.Integer)
    net_water_vol = db.Column(db.Integer)
    live_rock_lbs = db.Column(db.Float)

    def __repr__(self):
        return f"<Tank {self.name}>"

class Taxonomy(db.Model):
    __tablename__ = 'taxonomy'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    genus = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(100))
    family = db.Column(db.String(255))
    type = db.Column(db.Enum('SPS', 'LPS', 'Soft', 'Mushroom', 'Zoanthid'), nullable=False)
    picture_uri = db.Column(db.String(2083))
    common_name = db.Column(db.String(255))
    __table_args__ = (
        db.UniqueConstraint('genus', 'species', name='genus'),
    )

    def __repr__(self):
        return f"<Taxonomy {self.common_name} ({self.genus} {self.species})>"

class Vendors(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tag = db.Column(db.String(8), nullable=False)
    name = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f"<Vendor {self.name}>"

class ColorMorphs(db.Model):
    __tablename__ = 'color_morphs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('taxonomy.id'), nullable=False, index=True)
    morph_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    rarity = db.Column(db.Enum('Common', 'Uncommon', 'Rare', 'Ultra'))
    source = db.Column(db.String(100))
    image_url = db.Column(db.Text)

    taxonomy = db.relationship('Taxonomy', backref=db.backref('color_morphs', lazy=True))

    def __repr__(self):
        return f"<ColorMorph {self.morph_name}>"

class CareReqs(db.Model):
    __tablename__ = 'care_reqs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    genus = db.Column(db.String(100), nullable=False, unique=True)
    temperature = db.Column(db.Numeric(4,2))
    salinity = db.Column(db.Numeric(5,3))
    pH = db.Column('pH', db.Numeric(3,2))
    alkalinity = db.Column(db.Numeric(4,2))
    calcium = db.Column(db.Integer)
    magnesium = db.Column(db.Integer)
    par = db.Column(db.Integer)
    flow = db.Column(db.Enum('Low', 'Moderate', 'High'))
    notes = db.Column(db.Text)

    def __repr__(self):
        return f"<CareReqs {self.genus}>"

class TaxonomyForm(FlaskForm):
    common_name = StringField("Common Name", validators=[DataRequired(), Length(max=128)])
    type = StringField("Type", validators=[DataRequired(), Length(max=32)])
    species = StringField("Species", validators=[DataRequired(), Length(max=128)])
    genus = StringField("Genus", validators=[DataRequired(), Length(max=128)])
    family = StringField("Family", validators=[DataRequired(), Length(max=128)])
    picture_uri = StringField("Picture URI", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Submit")



