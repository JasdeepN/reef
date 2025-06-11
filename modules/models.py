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

# Import timezone utilities for consistent timezone handling
from modules.timezone_utils import (
    format_time_for_display, datetime_to_iso_format,
    parse_trigger_time_from_db
)

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
            "test_time": format_time_for_display(self.test_time) if self.test_time else None,
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
            'uses': self.uses,
            'total_volume': self.total_volume,
            'current_avail': self.current_avail,
            'dry_refill': self.dry_refill,
            'last_update': self.last_update.isoformat() if self.last_update else None,
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
    alert_only = 'alert_only'           # Skip missed doses, show alert only (simplified system)

class ScheduleTypeEnum(enum.Enum):
    interval = 'interval'    # Every X seconds/minutes/hours
    daily = 'daily'         # Once per day at specific time
    weekly = 'weekly'       # Specific days of week at specific time
    custom = 'custom'       # Custom repeat pattern

class DoserTypeEnum(enum.Enum):
    kamoer = 'kamoer'
    ghl = 'ghl'
    neptune = 'neptune'
    diy = 'diy'
    other = 'other'

class Dosing(db.Model):
    __tablename__ = 'dosing'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trigger_time = db.Column(db.DateTime(3))
    amount = db.Column(db.Float, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    schedule_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=True)
    
    # Enhanced dosing tracking fields
    dose_type = db.Column(db.Enum('scheduled', 'manual'), default='scheduled', nullable=False)
    doser_id = db.Column(db.Integer, db.ForeignKey('dosers.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=True)
    
    # Relationships
    product = db.relationship('Products', backref=db.backref('dosings', lazy=True))
    schedule = db.relationship('DSchedule', backref=db.backref('dosings', lazy=True))
    doser = db.relationship('Doser', backref=db.backref('dosings', lazy=True))
    tank = db.relationship('Tank', backref=db.backref('dosings', lazy=True))

    def validate(self):
        if self.amount is not None and self.amount < 0:
            raise ValueError("Amount must be non-negative")
        if self.product_id is None:
            raise ValueError("Product must be selected")
        if self.amount is None:
            raise ValueError("Amount must be specified")
        if self.dose_type is None:
            raise ValueError("Dosing type must be specified")
        if self.trigger_time is None:
            raise ValueError("Dosing time must be specified")
    
    def to_dict(self):
        return {
            "id": self.id,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "amount": self.amount,
            "product_id": self.product_id,
            "schedule_id": self.schedule_id,
            "dose_type": self.dose_type,
            "doser_id": self.doser_id,
            "notes": self.notes,
            "tank_id": self.tank_id,
            "product_name": self.product.name if self.product else None,
            "doser_name": self.doser.doser_name if self.doser else None
        }
    
    def __repr__(self):
        return f"<Dosing id={self.id} product_id={self.product_id} amount={self.amount} type={self.dose_type}>"


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

    # --- Enhanced Scheduling Features ---
    schedule_type = db.Column(db.Enum(ScheduleTypeEnum), default=ScheduleTypeEnum.interval, nullable=False)
    trigger_time = db.Column(db.Time, nullable=True)  # Absolute time of day for fixed-time schedules
    offset_minutes = db.Column(db.Integer, nullable=True)  # Offset in minutes for relative schedules
    reference_schedule_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=True)  # Reference schedule for relative dosing
    
    # Week/custom schedule support
    days_of_week = db.Column(db.String(14), nullable=True)  # Comma-separated days (1=Monday, 7=Sunday)
    repeat_every_n_days = db.Column(db.Integer, nullable=True)  # For custom schedules
    last_scheduled_time = db.Column(db.DateTime, nullable=True)  # Last time scheduler processed this
    
    # Doser management
    doser_name = db.Column(db.String(64), nullable=True)  # Legacy doser name
    doser_id = db.Column(db.Integer, db.ForeignKey('dosers.id'), nullable=True)  # Link to dosers table
    
    # Relationships
    reference_schedule = db.relationship('DSchedule', remote_side=[id], uselist=False, post_update=True)
    tank = db.relationship('Tank', backref=db.backref('schedules', lazy=True))
    product = db.relationship('Products', backref=db.backref('schedules', lazy=True))
    doser = db.relationship('Doser', backref=db.backref('schedules', lazy=True))

    def __repr__(self):
        return f"<DSchedule {self.id} (Tank {self.tank_id}, Product {self.product_id}, Type {self.schedule_type.value if self.schedule_type else 'interval'})>"

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
        "missed_dose_notification_enabled": d_schedule.missed_dose_notification_enabled,
        
        # Enhanced scheduling fields
        "schedule_type": d_schedule.schedule_type.value if d_schedule.schedule_type else 'interval',
        "trigger_time": format_time_for_display(d_schedule.trigger_time) if d_schedule.trigger_time else None,
        "offset_minutes": d_schedule.offset_minutes,
        "reference_schedule_id": d_schedule.reference_schedule_id,
        "days_of_week": d_schedule.days_of_week,
        "repeat_every_n_days": d_schedule.repeat_every_n_days,
        "last_scheduled_time": datetime_to_iso_format(d_schedule.last_scheduled_time) if d_schedule.last_scheduled_time else None,
        
        # Doser information
        "doser_name": d_schedule.doser_name,
        "doser_id": d_schedule.doser_id,
        "doser": d_schedule.doser.to_dict() if d_schedule.doser else None
    }

class DosingAudit(db.Model):
    """Complete audit trail for dose executions with precise timing and confirmations."""
    __tablename__ = 'dosing_audit'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('d_schedule.id'), nullable=False, index=True)
    execution_start = db.Column(db.DateTime(3), nullable=False)  # When dose execution began
    planned_time = db.Column(db.DateTime(3), nullable=False)     # When dose was originally scheduled
    timing_precision_seconds = db.Column(db.Float, nullable=False)       # Seconds difference (planned vs actual)
    amount = db.Column(db.Float, nullable=False)                 # Planned dose amount
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    doser_id = db.Column(db.Integer, db.ForeignKey('dosers.id'), nullable=True, index=True)
    
    # Execution details
    status = db.Column(db.Enum('scheduled', 'executing', 'confirmed', 'failed', 'timeout'), nullable=False)
    confirmation_time = db.Column(db.DateTime(3), nullable=True)  # When physical doser confirmed completion
    actual_amount = db.Column(db.Float, nullable=True)            # Actual amount delivered (if different)
    execution_end = db.Column(db.DateTime(3), nullable=True)      # When execution completed
    error_message = db.Column(db.Text, nullable=True)             # Error details if failed
    
    # Metadata
    raw_audit_data = db.Column(db.JSON, nullable=True)  # Complete audit payload for debugging
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    schedule = db.relationship('DSchedule', backref=db.backref('audit_logs', lazy=True))
    product = db.relationship('Products', backref=db.backref('dose_audit_logs', lazy=True))
    tank = db.relationship('Tank', backref=db.backref('dose_audit_logs', lazy=True))
    doser = db.relationship('Doser', backref=db.backref('dose_audit_logs', lazy=True))
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_dosing_audit_schedule_time', 'schedule_id', 'execution_start'),
        db.Index('idx_dosing_audit_tank_time', 'tank_id', 'execution_start'),
        db.Index('idx_dosing_audit_status_time', 'status', 'execution_start'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'execution_start': self.execution_start.isoformat() if self.execution_start else None,
            'planned_time': self.planned_time.isoformat() if self.planned_time else None,
            'timing_precision': self.timing_precision_seconds,
            'amount': self.amount,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'tank_id': self.tank_id,
            'doser_id': self.doser_id,
            'status': self.status,
            'confirmation_time': self.confirmation_time.isoformat() if self.confirmation_time else None,
            'actual_amount': self.actual_amount,
            'execution_end': self.execution_end.isoformat() if self.execution_end else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<DosingAudit {self.id} (Schedule {self.schedule_id}, {self.status}, {self.timing_precision_seconds:.1f}s precision)>"

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

class TankSystem(db.Model):
    """Tank system for grouping tanks that share sumps (like aquarium shops or multi-tank setups)"""
    __tablename__ = 'tank_systems'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    total_system_volume_gallons = db.Column(db.Numeric(10, 2), nullable=True)  # Calculated total
    shared_sump_volume_gallons = db.Column(db.Numeric(8, 2), nullable=True)  # Shared sump volume
    system_type = db.Column(db.String(50), nullable=True)  # 'shop', 'home_multi', 'single', etc.
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    def __repr__(self):
        return f"<TankSystem {self.name}>"
    
    def calculate_total_system_volume(self):
        """Calculate total water volume across all tanks in the system"""
        if not hasattr(self, 'tanks'):
            return 0.0
        
        total_tank_volume = sum(
            float(tank.get_calculated_volume_gallons() or tank.net_water_vol or tank.gross_water_vol or 0) 
            for tank in self.tanks
        )
        shared_sump = float(self.shared_sump_volume_gallons or 0)
        return round(total_tank_volume + shared_sump, 2)
    
    def get_tank_count(self):
        """Get number of tanks in this system"""
        if not hasattr(self, 'tanks'):
            return 0
        return len(self.tanks)
    
    def to_dict(self):
        """Convert tank system to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "total_system_volume_gallons": float(self.total_system_volume_gallons) if self.total_system_volume_gallons else None,
            "shared_sump_volume_gallons": float(self.shared_sump_volume_gallons) if self.shared_sump_volume_gallons else None,
            "system_type": self.system_type,
            "tank_count": self.get_tank_count(),
            "calculated_total_volume": self.calculate_total_system_volume(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Tank(db.Model):
    __tablename__ = 'tanks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(45), nullable=False)
    gross_water_vol = db.Column(db.Integer)
    net_water_vol = db.Column(db.Integer)
    live_rock_lbs = db.Column(db.Float)
    
    # Enhanced tank configuration fields
    tank_length_inches = db.Column(db.Numeric(6, 2), nullable=True)
    tank_width_inches = db.Column(db.Numeric(6, 2), nullable=True)
    tank_height_inches = db.Column(db.Numeric(6, 2), nullable=True)
    sump_volume_gallons = db.Column(db.Numeric(8, 2), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Tank system relationship
    tank_system_id = db.Column(db.Integer, db.ForeignKey('tank_systems.id'), nullable=True, index=True)
    
    # Relationships
    tank_system = db.relationship('TankSystem', backref=db.backref('tanks', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Tank {self.name}>"
    
    @staticmethod
    def cubic_inches_to_gallons(cubic_inches):
        """Convert cubic inches to US gallons (231 cubic inches = 1 gallon)"""
        if not cubic_inches or cubic_inches <= 0:
            return 0.0
        return round(cubic_inches / 231.0, 2)
    
    def get_calculated_volume_gallons(self):
        """Calculate tank volume from dimensions if available"""
        if all([self.tank_length_inches, self.tank_width_inches, self.tank_height_inches]):
            cubic_inches = float(self.tank_length_inches) * float(self.tank_width_inches) * float(self.tank_height_inches)
            return self.cubic_inches_to_gallons(cubic_inches)
        return None
    
    def get_effective_volume(self):
        """Get the most appropriate volume measurement for this tank"""
        # Priority: calculated from dimensions > net volume > gross volume
        calculated = self.get_calculated_volume_gallons()
        if calculated:
            return calculated
        elif self.net_water_vol:
            return float(self.net_water_vol)
        elif self.gross_water_vol:
            return float(self.gross_water_vol)
        return 0.0
    
    def get_total_system_volume(self):
        """Get total water volume including this tank's contribution to its system"""
        if self.tank_system:
            return self.tank_system.calculate_total_system_volume()
        else:
            # For standalone tanks, include individual sump volume
            tank_volume = self.get_effective_volume()
            sump_volume = float(self.sump_volume_gallons or 0)
            return round(tank_volume + sump_volume, 2)
    
    def is_part_of_system(self):
        """Check if this tank is part of a multi-tank system"""
        return self.tank_system_id is not None
    
    def get_system_name(self):
        """Get the name of the tank system this tank belongs to"""
        if self.tank_system:
            return self.tank_system.name
        return "Standalone Tank"
    
    def calculate_monthly_kwh(self):
        """Calculate estimated monthly kWh usage from active equipment"""
        if not hasattr(self, 'equipment'):
            return 0.0
        
        total_watts = sum(float(eq.power_watts or 0) for eq in self.equipment if eq.is_active and eq.power_watts)
        # Convert watts to kWh: watts * hours_per_day * days_per_month / 1000
        monthly_kwh = (total_watts * 24 * 30.44) / 1000  # 30.44 average days per month
        return round(monthly_kwh, 2)
    
    def get_tank_dimensions_display(self):
        """Get formatted tank dimensions string"""
        if all([self.tank_length_inches, self.tank_width_inches, self.tank_height_inches]):
            return f"{self.tank_length_inches}\" × {self.tank_width_inches}\" × {self.tank_height_inches}\""
        return "—"
    
    def get_volume_summary_display(self):
        """Get comprehensive volume display including calculated and manual values"""
        calculated = self.get_calculated_volume_gallons()
        effective = self.get_effective_volume()
        system_total = self.get_total_system_volume()
        
        summary = []
        if calculated:
            summary.append(f"Calculated: {calculated} gal")
        if self.net_water_vol and calculated != self.net_water_vol:
            summary.append(f"Net: {self.net_water_vol} gal")
        if self.gross_water_vol and calculated != self.gross_water_vol and self.net_water_vol != self.gross_water_vol:
            summary.append(f"Gross: {self.gross_water_vol} gal")
        
        if self.is_part_of_system() and system_total != effective:
            summary.append(f"System Total: {system_total} gal")
        elif self.sump_volume_gallons and not self.is_part_of_system():
            summary.append(f"+ Sump: {self.sump_volume_gallons} gal")
        
        return " | ".join(summary) if summary else "No volume data"
    
    def to_dict(self):
        """Convert tank to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "gross_water_vol": self.gross_water_vol,
            "net_water_vol": self.net_water_vol,
            "live_rock_lbs": float(self.live_rock_lbs) if self.live_rock_lbs else None,
            "tank_length_inches": float(self.tank_length_inches) if self.tank_length_inches else None,
            "tank_width_inches": float(self.tank_width_inches) if self.tank_width_inches else None,
            "tank_height_inches": float(self.tank_height_inches) if self.tank_height_inches else None,
            "sump_volume_gallons": float(self.sump_volume_gallons) if self.sump_volume_gallons else None,
            "description": self.description,
            "tank_system_id": self.tank_system_id,
            "tank_system_name": self.get_system_name(),
            "calculated_volume_gallons": self.get_calculated_volume_gallons(),
            "effective_volume_gallons": self.get_effective_volume(),
            "total_system_volume_gallons": self.get_total_system_volume(),
            "is_part_of_system": self.is_part_of_system(),
            "monthly_kwh_estimate": self.calculate_monthly_kwh(),
            "dimensions_display": self.get_tank_dimensions_display(),
            "volume_summary_display": self.get_volume_summary_display(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Doser(db.Model):
    __tablename__ = 'dosers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    doser_name = db.Column(db.String(64), nullable=False)
    doser_type = db.Column(db.Enum(DoserTypeEnum), default=DoserTypeEnum.other)
    max_daily_volume = db.Column(db.Float, nullable=True)  # ml per day
    pump_calibration_ml_per_second = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relationships
    tank = db.relationship('Tank', backref=db.backref('dosers', lazy=True))
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('tank_id', 'doser_name', name='unique_doser_per_tank'),
    )
    
    def __repr__(self):
        return f"<Doser {self.doser_name} (Tank {self.tank_id}, {self.doser_type.value if self.doser_type else 'other'})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "tank_id": self.tank_id,
            "doser_name": self.doser_name,
            "doser_type": self.doser_type.value if self.doser_type else 'other',
            "max_daily_volume": self.max_daily_volume,
            "pump_calibration_ml_per_second": self.pump_calibration_ml_per_second,
            "is_active": self.is_active,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

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

class EquipmentTypeEnum(enum.Enum):
    lighting = 'lighting'
    pump = 'pump'
    heater = 'heater'
    skimmer = 'skimmer'
    reactor = 'reactor'
    controller = 'controller'
    doser = 'doser'
    other = 'other'

class Equipment(db.Model):
    __tablename__ = 'equipment'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('tanks.id'), nullable=False, index=True)
    equipment_name = db.Column(db.String(128), nullable=False)
    equipment_type = db.Column(db.Enum(EquipmentTypeEnum), default=EquipmentTypeEnum.other, nullable=False)
    power_watts = db.Column(db.Numeric(8, 2), nullable=True)
    brand = db.Column(db.String(64), nullable=True)
    model = db.Column(db.String(128), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    # Relationships
    tank = db.relationship('Tank', backref=db.backref('equipment', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f"<Equipment {self.equipment_name} ({self.equipment_type.value})>"
    
    def to_dict(self):
        """Convert equipment to dictionary for API responses"""
        return {
            "id": self.id,
            "tank_id": self.tank_id,
            "equipment_name": self.equipment_name,
            "equipment_type": self.equipment_type.value,
            "power_watts": float(self.power_watts) if self.power_watts else None,
            "brand": self.brand,
            "model": self.model,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


