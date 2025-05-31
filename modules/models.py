from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum
from sqlalchemy import Computed

from flask_wtf import FlaskForm 
from wtforms import StringField, DateField, TimeField, DecimalField, RadioField, SelectField, TextAreaField, SubmitField, IntegerField, HiddenField
from wtforms.validators import Optional, DataRequired, Length
from wtforms.fields import DateTimeField

import numpy as np
from datetime import datetime
from flask import session

# Import db from extensions to avoid circular imports
from extensions import db

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
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    
    # Relationships
    tank = db.relationship('Tank', backref=db.backref('test_results', lazy=True))

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
            "tank_id": self.tank_id,
        }
    
              

class Products(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    uses = db.Column(db.String(32), nullable=True)  # e.g. '+Alk', '-NO3', etc.
    total_volume = db.Column(db.Float)
    current_avail = db.Column(db.Float)
    # used_amt = db.Column(db.Float)  # This is a generated column in MySQL, not directly supported in SQLAlchemy
    dry_refill = db.Column(db.Float)
    last_update = db.Column(db.TIMESTAMP, server_default=None, onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f"<Products id={self.id} name={self.name} uses={self.uses}>"

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


class DosingTypeEnum(enum.Enum):
    recurring = 'recurring'
    single = 'single'
    intermittent = 'intermittent'

class MissedDoseHandlingEnum(enum.Enum):
    alert_only = 'alert_only'           # Skip missed doses, show alert
    grace_period = 'grace_period'       # Allow dosing within grace window
    manual_approval = 'manual_approval' # Require user confirmation

class Dosing(db.Model):
    __tablename__ = 'dosing'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trigger_time = db.Column(db.DateTime(3))
    amount = db.Column(db.Float, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    schedule_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=True)
    product = db.relationship('Products', backref=db.backref('dosings', lazy=True))
    schedule = db.relationship('DSchedule', backref=db.backref('dosings', lazy=True))

    def validate(self):
        if self.amount is not None and self.amount < 0:
            raise ValueError("Amount must be non-negative")
        if self.product_id is None:
            raise ValueError("Product must be selected")
        if self.amount is None:
            raise ValueError("Amount must be specified")
        if hasattr(self, '_type') and self._type is None:
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
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    
    # Missed dose handling configuration
    missed_dose_handling = db.Column(db.Enum(MissedDoseHandlingEnum), default=MissedDoseHandlingEnum.alert_only, nullable=False)
    missed_dose_grace_period_hours = db.Column(db.Integer, default=12)  # Grace period in hours for grace_period mode
    missed_dose_notification_enabled = db.Column(db.Boolean, default=True)  # Enable missed dose notifications

    # Relationships
    tank = db.relationship('Tank', backref=db.backref('schedules', lazy=True))
    product = db.relationship('Products', backref=db.backref('schedules', lazy=True))

    def __repr__(self):
        return f"<DSchedule {self.id} (Tank {self.tank_id}, Product {self.product_id})>"

def get_d_schedule_dict(d_schedule):
    """Helper to serialize DSchedule model to dict."""
    return {
        "id": d_schedule.id,
        "product_name": d_schedule.product.name if d_schedule.product else None,
        "trigger_interval": d_schedule.trigger_interval,
        "suspended": d_schedule.suspended,
        "last_refill": d_schedule.last_refill.isoformat() if d_schedule.last_refill else None,
        "amount": d_schedule.amount,
        "missed_dose_handling": d_schedule.missed_dose_handling.value if d_schedule.missed_dose_handling else 'alert_only',
        "missed_dose_grace_period_hours": d_schedule.missed_dose_grace_period_hours,
        "missed_dose_notification_enabled": d_schedule.missed_dose_notification_enabled
    }

class MissedDoseRequest(db.Model):
    """Model for tracking missed doses that require manual approval or tracking."""
    __tablename__ = 'missed_dose_requests'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=False)
    missed_dose_time = db.Column(db.DateTime, nullable=False)  # When the dose was originally scheduled
    detected_time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())  # When missed dose was detected
    hours_missed = db.Column(db.Float, nullable=False)  # Hours past scheduled time
    status = db.Column(db.Enum('pending', 'approved', 'rejected', 'expired', 'auto_dosed'), nullable=False, default='pending')
    approved_by = db.Column(db.String(64))  # User who approved/rejected
    approved_time = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Relationships
    schedule = db.relationship('DSchedule', backref=db.backref('missed_dose_requests', lazy=True))
    
    def __repr__(self):
        return f"<MissedDoseRequest {self.id} (Schedule {self.schedule_id}, {self.hours_missed:.1f}h missed)>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "product_name": self.schedule.product.name if self.schedule and self.schedule.product else "Unknown",
            "missed_dose_time": self.missed_dose_time.isoformat() if self.missed_dose_time else None,
            "detected_time": self.detected_time.isoformat() if self.detected_time else None,
            "hours_missed": self.hours_missed,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_time": self.approved_time.isoformat() if self.approved_time else None,
            "notes": self.notes,
            "amount": self.schedule.amount if self.schedule else None,
            "tank_id": self.schedule.tank_id if self.schedule else None
        }

class Coral(db.Model):
    __tablename__ = 'corals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coral_name = db.Column(db.String(128), nullable=False, index=True)
    date_acquired = db.Column(db.Date, nullable=False, index=True)
    par = db.Column(db.Integer)
    flow = db.Column(db.Enum('Low', 'Medium', 'High'))
    placement = db.Column(db.Enum('Top', 'Middle', 'Bottom'))
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
    color_morphs = db.relationship('ColorMorphs', back_populates='taxonomy')
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
    morph_name = db.Column(db.String(64))
    description = db.Column(db.Text)
    rarity = db.Column(db.Enum('Common', 'Uncommon', 'Rare', 'Ultra'))
    source = db.Column(db.String(100))
    image_url = db.Column(db.Text)
    taxonomy = db.relationship('Taxonomy', back_populates='color_morphs')

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

class AlkalinityDoseModel(db.Model):
    __tablename__ = 'alkalinity_dose_model'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True, index=True)
    slope = db.Column(db.Float, nullable=False)
    intercept = db.Column(db.Float, nullable=False)
    weight_decay = db.Column(db.Float, default=0.9)
    last_trained = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    r2_score = db.Column(db.Float)
    notes = db.Column(db.Text)

    # Relationships
    tank = db.relationship('Tank', backref=db.backref('alkalinity_dose_models', lazy=True, cascade='all, delete-orphan'))
    product = db.relationship('Products', backref=db.backref('alkalinity_dose_models', lazy=True))

    def __repr__(self):
        return f"<AlkalinityDoseModel id={self.id} tank_id={self.tank_id} product_id={self.product_id}>"

# --- AlkalinityDoseModel helpers ---

def initialize_alkalinity_model(tank_id, product_id, slope=1.0, intercept=0.0, weight_decay=0.9, r2_score=None, notes=None):
    """Create a new AlkalinityDoseModel entry with initial/default parameters."""
    model = AlkalinityDoseModel(
        tank_id=tank_id,
        product_id=product_id,
        slope=slope,
        intercept=intercept,
        weight_decay=weight_decay,
        last_trained=datetime.utcnow(),
        r2_score=r2_score,
        notes=notes or "Initialized with default parameters."
    )
    db.session.add(model)
    db.session.commit()
    return model

def get_alkalinity_model(tank_id, product_id):
    """Fetch the most recent AlkalinityDoseModel for a tank and product."""
    return AlkalinityDoseModel.query.filter_by(tank_id=tank_id, product_id=product_id).order_by(AlkalinityDoseModel.last_trained.desc()).first()

def should_update_alkalinity_model(tank_id, product_id, retrain_interval_days=7):
    """Return True if the model should be retrained (e.g., if last_trained is too old)."""
    model = get_alkalinity_model(tank_id, product_id)
    if not model:
        return True
    if (datetime.utcnow() - model.last_trained).days >= retrain_interval_days:
        return True
    return False

def update_alkalinity_model(tank_id, product_id, dose_history, alk_history, weight_decay=0.9, notes=None):
    """
    Fit a weighted linear regression to dose_history and alk_history, update the model in DB.
    dose_history: list/array of dose amounts (x)
    alk_history: list/array of resulting alk values (y)
    """
    if len(dose_history) != len(alk_history) or len(dose_history) < 2:
        raise ValueError("Need at least 2 matching dose and alk values.")
    # Exponential weights: most recent = highest weight
    weights = np.array([weight_decay ** (len(dose_history) - i - 1) for i in range(len(dose_history))])
    X = np.array(dose_history).reshape(-1, 1)
    y = np.array(alk_history)
    # Weighted linear regression
    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X, y, sample_weight=weights)
    slope = float(model.coef_[0])
    intercept = float(model.intercept_)
    r2 = float(model.score(X, y, sample_weight=weights))
    # Update or create model
    alk_model = get_alkalinity_model(tank_id, product_id)
    if not alk_model:
        alk_model = initialize_alkalinity_model(tank_id, product_id, slope, intercept, weight_decay, r2, notes)
    else:
        alk_model.slope = slope
        alk_model.intercept = intercept
        alk_model.weight_decay = weight_decay
        alk_model.last_trained = datetime.utcnow()
        alk_model.r2_score = r2
        alk_model.notes = notes or "Model updated."
        db.session.commit()
    return alk_model

def predict_alkalinity_dose(tank_id, product_id, target_alk):
    """Given a target alkalinity, return the required dose using the latest model."""
    model = get_alkalinity_model(tank_id, product_id)
    if not model or model.slope == 0:
        raise ValueError("No valid model found or slope is zero.")
    dose = (target_alk - model.intercept) / model.slope
    return dose


