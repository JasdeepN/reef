from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, IntegerField, SelectField, TextAreaField, SubmitField, BooleanField, DateTimeField, FormField
)
from wtforms.validators import DataRequired, Optional, Length
import enum

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
    prod_id = SelectField("Product", coerce=int, validators=[Optional()])
    amount = DecimalField("Amount", validators=[Optional()])
    submit = SubmitField("Submit Dosing")

# --- DSchedule Form ---
class DScheduleForm(FlaskForm):
    csrf = False
    last_trigger = DateTimeField("Last Trigger", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    trigger_interval = IntegerField("Trigger Interval (minutes)", validators=[DataRequired()])
    last_refill = DateTimeField("Last Refill", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
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

class BaseForm(FlaskForm):
    def validate(self, extra_validators=None):
        """Default validate method for forms."""
        if not super().validate(extra_validators):
            return False

        # Add any default validation logic here if needed
        return True