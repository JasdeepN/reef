from flask_wtf import FlaskForm
from wtforms import (
    StringField, DecimalField, IntegerField, SelectField, TextAreaField, SubmitField, BooleanField, DateTimeField, FormField, DateField, FileField
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

# --- Coral Form ---
class CoralForm(FlaskForm):
    coral_name = StringField("Coral Name / Species", validators=[Optional(), Length(max=128)])
    coral_type = SelectField(
        "Type",
        choices=[
            ('', 'Select type...'),
            ('SPS', 'SPS'),
            ('LPS', 'LPS'),
            ('Soft', 'Soft'),
            ('Zoanthid', 'Zoanthid'),
            ('Mushroom', 'Mushroom'),
            ('Other', 'Other')
        ],
        validators=[DataRequired()]
    )
    date_acquired = DateField("Date Acquired", validators=[DataRequired()])
    source = StringField("Source", validators=[Optional(), Length(max=128)])
    tank_location = StringField("Tank Location", validators=[Optional(), Length(max=128)])
    lighting = SelectField(
        "Lighting Requirement",
        choices=[('', 'Select...'), ('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')],
        validators=[Optional()]
    )
    par = IntegerField("PAR Value", validators=[Optional()])
    flow = SelectField(
        "Flow Requirement",
        choices=[('', 'Select...'), ('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')],
        validators=[Optional()]
    )
    feeding = StringField("Feeding Requirement", validators=[Optional(), Length(max=128)])
    placement = StringField("Placement", validators=[Optional(), Length(max=128)])
    current_size = StringField("Current Size", validators=[Optional(), Length(max=64)])
    color_morph = StringField("Color Morph", validators=[Optional(), Length(max=64)])
    health_status = SelectField(
        "Health Status",
        choices=[
            ('', 'Select...'),
            ('Healthy', 'Healthy'),
            ('Recovering', 'Recovering'),
            ('New', 'New'),
            ('Stressed', 'Stressed'),
            ('Other', 'Other'),
            ('Dead', 'Dead'),
            ('Dying', 'Dying')
        ],
        validators=[Optional()]
    )
    frag_colony = SelectField(
        "Frag or Colony",
        choices=[('', 'Select...'), ('Frag', 'Frag'), ('Colony', 'Colony')],
        validators=[Optional()]
    )
    growth_rate = StringField("Growth Rate", validators=[Optional(), Length(max=64)])
    last_fragged = DateField("Last Fragged Date", validators=[Optional()])
    unique_id = StringField("Unique ID/Tag", validators=[Optional(), Length(max=64)])
    origin = StringField("Origin (region/ocean)", validators=[Optional(), Length(max=128)])
    compatibility = StringField("Compatibility Notes", validators=[Optional(), Length(max=255)])
    photo = FileField("Photo", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    test_id = IntegerField("Test Results ID", validators=[Optional()])
    submit = SubmitField("Add Coral")

