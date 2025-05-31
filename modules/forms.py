from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, IntegerField, SelectField, TextAreaField, SubmitField, BooleanField, DateTimeField, FormField, DateField, FileField, RadioField, TimeField
)
from wtforms.validators import DataRequired, Optional, Length
import enum
from datetime import date
import datetime as dt

class MissedDoseHandlingEnum(enum.Enum):
    alert_only = 'alert_only'           # Skip missed doses, show alert
    grace_period = 'grace_period'       # Allow dosing within grace window
    manual_approval = 'manual_approval' # Require user confirmation

class BaseForm(FlaskForm):
    def validate(self, extra_validators=None):
        """Default validate method for forms."""
        if not super().validate(extra_validators):
            return False

        # Add any default validation logic here if needed
        return True
    
# --- Product Form ---
class ProductForm(FlaskForm):
    csrf = False
    name = StringField("Name", validators=[DataRequired(), Length(max=30)])
    total_volume = DecimalField("Total Volume", validators=[Optional()])
    current_avail = DecimalField("Current Available", validators=[Optional()])
    dry_refill = DecimalField("Dry Refill", validators=[Optional()])
    submit = SubmitField("Add Product")

# --- Dosing Type Enum ---
class DosingTypeEnum(enum.Enum):
    recurring = 'recurring'
    single = 'single'
    intermittent = 'intermittent'

# --- Dosing Form ---
class DosingForm(FlaskForm):
    csrf = False
    time = DateTimeField("Dosing Time", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    product_id = SelectField("Product", coerce=int, validators=[Optional()])
    amount = DecimalField("Amount", validators=[Optional()])
    submit = SubmitField("Submit Dosing")


class ProductForm(BaseForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=30)])
    total_volume = DecimalField("Total Volume", validators=[Optional()])
    current_avail = DecimalField("Current Available", validators=[Optional()])
    dry_refill = DecimalField("Dry Refill", validators=[Optional()])
    submit = SubmitField("Submit")


# --- DSchedule Form ---
class DScheduleForm(FlaskForm):
    csrf = False
    last_trigger = DateTimeField("Last Trigger", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    trigger_interval = IntegerField("Trigger Interval (minutes)", validators=[DataRequired()])
    last_refill = DateTimeField("Last Refill", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    
    # Missed dose handling configuration
    missed_dose_handling = SelectField(
        "Missed Dose Handling",
        choices=[
            ('alert_only', 'Alert Only (Skip missed doses)'),
            ('grace_period', 'Grace Period (Allow within time window)'),
            ('manual_approval', 'Manual Approval Required')
        ],
        default='alert_only',
        validators=[DataRequired()]
    )
    missed_dose_grace_period_hours = IntegerField("Grace Period (hours)", default=12, validators=[Optional()])
    missed_dose_notification_enabled = BooleanField("Enable Missed Dose Notifications", default=True)
    
    submit = SubmitField("Submit Schedule")

# --- Combined Form ---
class CombinedDosingScheduleForm(FlaskForm):
    dosing = FormField(DosingForm)
    schedule = FormField(DScheduleForm)
    product = FormField(ProductForm)

    def options(self):
        """Return a list of options for the select picker in the UI."""
        return [
            ('recurring', 'Recurring Dosing'),
            ('single', 'Single Dosing'),
            ('intermittent', 'Intermittent Dosing'),
        ]

class test_result_form(FlaskForm):
    test_date = DateField("Date", default=dt.datetime.today)
    test_time = TimeField("Test Time", format='%H:%M:%S', default=dt.datetime.now)
    alk = DecimalField("Alkalinity (KH)", [Optional()])
    po4_ppb = IntegerField("Phosphate (PO\u2084\u00b3\u207b PPB)", [Optional()])
    no3_ppm = DecimalField("Nitrate (NO\u2083\u207b PPM)", [Optional()])
    cal = IntegerField("Calcium (Ca\u00b2\u207a PPM)", [Optional()])
    mg = IntegerField("Magneisum (Mg\u00b2\u207a PPM)", [Optional()])
    sg = DecimalField("Specific Gravity (SG)", [Optional()])

    submit = SubmitField()

    # Custom validate method
    def validate(self, extra_validators=None):
        valid = False

        # print('start')
        if not super().validate(extra_validators):
            print('Form validation errors:', self.errors)
            return valid
        # print('validating')
        for k, v in self.data.items():
            if k not in ['test_date', 'test_time', 'csrf_token', 'submit']:
                if v not in (None, '', [], {}):
                    valid = True
        if hasattr(self, 'tank_id') and (self.tank_id.data in (None, '', 0)):
            print('tank_id missing or invalid')
            return valid
        
        if not valid:
            self.errors.setdefault('form', []).append('Validation failed: no test data received.')

        return valid

# --- Coral Form ---
class CoralForm(FlaskForm):
    # coral_name = SelectField("Coral Name / Species", validators=[])
    date_acquired = DateField("Date Acquired", default=date.today, format='%Y-%m-%d', validators=[DataRequired()])
    par = IntegerField("PAR Value", validators=[Optional()])
    flow = SelectField(
        "Flow",
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        validators=[Optional()]
    )
    current_size = StringField("Current Size", validators=[Optional(), Length(max=64)])
    health_status = SelectField(
        "Health Status",
        choices=[
            ('', 'Select...'),
            ('Healthy', 'Healthy'),
            ('Recovering', 'Recovering'),
            ('New', 'New'),
            ('Stressed', 'Stressed'),
            ('Dying', 'Dying'),
            ('Dead', 'Dead'),
            ('Other', 'Other')
        ],
        validators=[Optional()]
    )
    frag_colony = RadioField(
        "Frag or Colony",
        choices=[('Frag', 'Frag'), ('Colony', 'Colony')],
        validators=[Optional()],
        default='Frag'
    )
    last_fragged = DateField("Last Fragged Date", validators=[Optional()])
    unique_id = StringField("Unique ID/Tag", validators=[Optional(), Length(max=64)])
    photo = FileField("Photo", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    test_id = IntegerField("Test Results ID", validators=[Optional()])
    vendors_id = IntegerField("Vendor", validators=[Optional()])
    color_morphs_id = IntegerField("Color Morph", validators=[DataRequired()])
    created_at = DateTimeField("Created At", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    updated_at = DateTimeField("Updated At", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    submit = SubmitField("Add Coral")

