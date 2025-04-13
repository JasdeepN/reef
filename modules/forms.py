from flask_wtf import FlaskForm

class BaseForm(FlaskForm):
    def validate(self, extra_validators=None):
        """Default validate method for forms."""
        if not super().validate(extra_validators):
            return False

        # Add any default validation logic here if needed
        return True