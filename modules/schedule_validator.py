#!/usr/bin/env python3
"""
Schedule validation utilities for ReefDB dosing scheduler.

Provides validation functions to prevent conflicting schedule configurations
and ensure data integrity for dosing schedules.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, time as dt_time

logger = logging.getLogger(__name__)

class ScheduleValidationError(Exception):
    """Raised when schedule configuration is invalid"""
    pass

class ScheduleValidator:
    """Validates dosing schedule configurations for consistency and safety"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_schedule_configuration(self, schedule_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate schedule configuration for consistency.
        
        Args:
            schedule_data: Dictionary containing schedule configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        schedule_type = schedule_data.get('schedule_type', 'interval')
        
        # Validate based on schedule type
        if schedule_type == 'interval':
            errors.extend(self._validate_interval_schedule(schedule_data))
        elif schedule_type == 'daily':
            errors.extend(self._validate_daily_schedule(schedule_data))
        elif schedule_type == 'weekly':
            errors.extend(self._validate_weekly_schedule(schedule_data))
        elif schedule_type == 'custom':
            errors.extend(self._validate_custom_schedule(schedule_data))
        else:
            errors.append(f"Invalid schedule_type: {schedule_type}")
        
        # Check for conflicting configurations
        errors.extend(self._check_conflicting_configurations(schedule_data))
        
        return len(errors) == 0, errors
    
    def _validate_interval_schedule(self, data: Dict) -> List[str]:
        """Validate interval-based schedule configuration"""
        errors = []
        
        trigger_interval = data.get('trigger_interval')
        trigger_time = data.get('trigger_time')
        repeat_every_n_days = data.get('repeat_every_n_days')
        
        # Interval schedules should NOT have specific trigger_time
        if trigger_time is not None:
            errors.append(
                "Interval schedules should not specify trigger_time. "
                "Use 'daily' schedule type for time-specific dosing."
            )
        
        # Interval schedules should NOT use repeat_every_n_days
        if repeat_every_n_days is not None:
            errors.append(
                "Interval schedules should not use repeat_every_n_days. "
                "Use 'custom' schedule type for day-based intervals."
            )
        
        # Must have valid trigger_interval
        if trigger_interval is None or trigger_interval <= 0:
            errors.append("Interval schedules must have positive trigger_interval")
        
        return errors
    
    def _validate_daily_schedule(self, data: Dict) -> List[str]:
        """Validate daily schedule configuration"""
        errors = []
        
        trigger_time = data.get('trigger_time')
        trigger_interval = data.get('trigger_interval', 86400)  # Default 1 day
        repeat_every_n_days = data.get('repeat_every_n_days')
        
        # Daily schedules MUST have trigger_time
        if trigger_time is None:
            errors.append("Daily schedules must specify trigger_time")
        
        # Daily schedules can have various intervals for multiple doses per day
        # Allow any interval that divides evenly into 24 hours (86400 seconds)
        if trigger_interval is None or trigger_interval <= 0:
            errors.append("Daily schedules must have positive trigger_interval")
        elif trigger_interval > 86400:
            errors.append(
                f"Daily schedules cannot have intervals longer than 1 day (86400 seconds), got {trigger_interval}"
            )
        elif 86400 % trigger_interval != 0:
            errors.append(
                f"Daily schedule interval must divide evenly into 24 hours. "
                f"Interval {trigger_interval} does not divide evenly into 86400 seconds."
            )
        
        # Daily schedules should NOT use repeat_every_n_days (that's for custom schedules)
        if repeat_every_n_days is not None:
            errors.append(
                "Daily schedules should not use repeat_every_n_days. "
                "Use 'custom' schedule type for multi-day intervals."
            )
        
        return errors
    
    def _validate_weekly_schedule(self, data: Dict) -> List[str]:
        """Validate weekly schedule configuration"""
        errors = []
        
        trigger_time = data.get('trigger_time')
        trigger_interval = data.get('trigger_interval', 604800)  # Default 1 week
        days_of_week = data.get('days_of_week')
        
        # Weekly schedules MUST have trigger_time
        if trigger_time is None:
            errors.append("Weekly schedules must specify trigger_time")
        
        # Weekly schedules should have days_of_week or default interval
        if not days_of_week and trigger_interval != 604800:
            errors.append(
                "Weekly schedules must specify days_of_week or use 604800 (1 week) interval"
            )
        
        return errors
    
    def _validate_custom_schedule(self, data: Dict) -> List[str]:
        """Validate custom schedule configuration"""
        errors = []
        
        trigger_time = data.get('trigger_time')
        repeat_every_n_days = data.get('repeat_every_n_days')
        trigger_interval = data.get('trigger_interval')
        
        # Custom schedules MUST have repeat_every_n_days
        if repeat_every_n_days is None or repeat_every_n_days <= 0:
            errors.append("Custom schedules must have positive repeat_every_n_days")
        
        # Custom schedules MUST have trigger_time
        if trigger_time is None:
            errors.append("Custom schedules must specify trigger_time")
        
        # For custom schedules, trigger_interval should match days calculation
        if repeat_every_n_days and trigger_interval:
            expected_interval = repeat_every_n_days * 24 * 3600
            if trigger_interval != expected_interval:
                errors.append(
                    f"Custom schedule trigger_interval ({trigger_interval}) should match "
                    f"repeat_every_n_days * 86400 ({expected_interval})"
                )
        
        return errors
    
    def _check_conflicting_configurations(self, data: Dict) -> List[str]:
        """Check for conflicting configuration combinations"""
        errors = []
        
        schedule_type = data.get('schedule_type', 'interval')
        trigger_interval = data.get('trigger_interval')
        trigger_time = data.get('trigger_time')
        
        # Check for the specific conflict that was found in schedule ID 1
        if (schedule_type == 'interval' and 
            trigger_time is not None and 
            trigger_interval and trigger_interval != 86400):
            errors.append(
                f"CRITICAL CONFLICT: schedule_type='interval' with trigger_interval={trigger_interval} "
                f"AND trigger_time={trigger_time}. This creates ambiguous scheduling logic. "
                f"Use 'daily' type for time-specific dosing or 'interval' without trigger_time."
            )
        
        return errors
    
    def fix_conflicting_schedule(self, schedule_data: Dict) -> Dict:
        """
        Automatically fix common conflicting schedule configurations.
        
        Returns corrected schedule_data dictionary.
        """
        fixed_data = schedule_data.copy()
        schedule_type = fixed_data.get('schedule_type', 'interval')
        trigger_time = fixed_data.get('trigger_time')
        trigger_interval = fixed_data.get('trigger_interval')
        
        # Fix: interval schedule with specific time -> convert to daily
        if (schedule_type == 'interval' and 
            trigger_time is not None and 
            trigger_interval and trigger_interval != 86400):
            
            logger.warning(
                "Auto-fixing conflicting schedule: interval + trigger_time -> daily schedule"
            )
            fixed_data['schedule_type'] = 'daily'
            fixed_data['trigger_interval'] = 86400  # 1 day
            fixed_data['repeat_every_n_days'] = None  # Clear for daily schedules
        
        # Fix: daily schedule without proper interval
        elif schedule_type == 'daily' and trigger_interval and 86400 % trigger_interval != 0:
            logger.warning(
                "Auto-fixing daily schedule: interval must divide evenly into 24 hours"
            )
            fixed_data['trigger_interval'] = 86400  # Default to once per day
        
        # Fix: custom schedule without proper interval calculation
        elif (schedule_type == 'custom' and 
              fixed_data.get('repeat_every_n_days') and 
              trigger_interval):
            expected_interval = fixed_data['repeat_every_n_days'] * 24 * 3600
            if trigger_interval != expected_interval:
                logger.warning(
                    f"Auto-fixing custom schedule interval: {trigger_interval} -> {expected_interval}"
                )
                fixed_data['trigger_interval'] = expected_interval
        
        return fixed_data

def validate_and_fix_schedule(schedule_data: Dict) -> Tuple[Dict, List[str]]:
    """
    Convenience function to validate and auto-fix schedule configuration.
    
    Returns:
        Tuple of (fixed_schedule_data, remaining_errors)
    """
    validator = ScheduleValidator()
    
    # First attempt validation
    is_valid, _ = validator.validate_schedule_configuration(schedule_data)
    
    if not is_valid:
        # Try to auto-fix
        fixed_data = validator.fix_conflicting_schedule(schedule_data)
        
        # Re-validate after fixes
        is_valid_after_fix, remaining_errors = validator.validate_schedule_configuration(fixed_data)
        
        if is_valid_after_fix:
            logger.info("Successfully auto-fixed schedule configuration conflicts")
            return fixed_data, []
        else:
            logger.error(f"Could not auto-fix all schedule conflicts: {remaining_errors}")
            return fixed_data, remaining_errors
    
    return schedule_data, []
