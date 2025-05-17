from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, IntegerField, SelectField, TextAreaField, SubmitField, BooleanField, DateTimeField, FormField, DateField, FileField, RadioField
)
from wtforms.validators import DataRequired, Optional, Length
import enum
from datetime import date

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
    tank_id = IntegerField("Tank", validators=[DataRequired()])
    vendors_id = IntegerField("Vendor", validators=[Optional()])
    color_morphs_id = IntegerField("Color Morph", validators=[DataRequired()])
    created_at = DateTimeField("Created At", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    updated_at = DateTimeField("Updated At", format='%Y-%m-%d %H:%M:%S', validators=[Optional()])
    submit = SubmitField("Add Coral")

