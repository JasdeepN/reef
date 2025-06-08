#!/usr/bin/env python3
"""
ReefDB Timezone Utilities

This module provides centralized timezone handling for all schedule-related operations
in ReefDB to ensure consistency across database storage, API responses, and UI display.
"""

import os
from datetime import datetime, time
from typing import Optional, Union
import pytz
from zoneinfo import ZoneInfo
import tzlocal

# Centralized timezone configuration
DEFAULT_TIMEZONE = 'America/Toronto'  # Eastern Time

def get_system_timezone() -> str:
    """Get the system timezone name"""
    try:
        return tzlocal.get_localzone_name()
    except Exception:
        return DEFAULT_TIMEZONE

def get_configured_timezone() -> str:
    """Get the configured timezone from environment or default"""
    return os.getenv('TIMEZONE', get_system_timezone())

def get_timezone_object() -> ZoneInfo:
    """Get timezone object for the configured timezone"""
    timezone_name = get_configured_timezone()
    return ZoneInfo(timezone_name)

def get_pytz_timezone() -> pytz.timezone:
    """Get pytz timezone object for the configured timezone"""
    timezone_name = get_configured_timezone()
    return pytz.timezone(timezone_name)

def now_in_timezone() -> datetime:
    """Get current datetime in the configured timezone"""
    tz = get_timezone_object()
    return datetime.now(tz)

def to_timezone(dt: datetime, target_tz: Optional[Union[str, ZoneInfo]] = None) -> datetime:
    """
    Convert datetime to specified timezone or configured timezone
    
    Args:
        dt: datetime to convert
        target_tz: target timezone (string name or ZoneInfo object), defaults to configured timezone
    
    Returns:
        datetime in target timezone
    """
    if target_tz is None:
        target_tz = get_timezone_object()
    elif isinstance(target_tz, str):
        target_tz = ZoneInfo(target_tz)
    
    # If datetime is naive, assume it's in the configured timezone
    if dt.tzinfo is None:
        configured_tz = get_timezone_object()
        dt = dt.replace(tzinfo=configured_tz)
    
    return dt.astimezone(target_tz)

def normalize_time_input(time_input: Union[str, time, datetime], date_part: Optional[datetime] = None) -> datetime:
    """
    Normalize time input to a timezone-aware datetime in the configured timezone
    
    Args:
        time_input: time as string (HH:MM), time object, or datetime
        date_part: date to use if time_input is just a time (defaults to today)
    
    Returns:
        timezone-aware datetime in configured timezone
    """
    tz = get_timezone_object()
    
    if date_part is None:
        date_part = datetime.now(tz).date()
    
    if isinstance(time_input, str):
        # Parse time string (HH:MM format)
        try:
            hour, minute = map(int, time_input.split(':'))
            time_obj = time(hour, minute)
        except (ValueError, AttributeError):
            # Default to 9:00 AM if parsing fails
            time_obj = time(9, 0)
    elif isinstance(time_input, time):
        time_obj = time_input
    elif isinstance(time_input, datetime):
        return to_timezone(time_input)
    else:
        # Default to 9:00 AM if invalid input
        time_obj = time(9, 0)
    
    # Combine date and time, then localize to configured timezone
    naive_dt = datetime.combine(date_part, time_obj)
    return naive_dt.replace(tzinfo=tz)

def format_time_for_display(dt: Union[datetime, time], format_string: str = '%H:%M') -> str:
    """
    Format datetime or time for display in the configured timezone
    
    Args:
        dt: datetime or time to format
        format_string: strftime format string
    
    Returns:
        formatted time string in configured timezone
    """
    if isinstance(dt, time):
        # Convert time to datetime using today's date
        dt = normalize_time_input(dt)
    
    local_dt = to_timezone(dt)
    return local_dt.strftime(format_string)

def format_time_for_html_input(dt: Union[datetime, time]) -> str:
    """
    Format datetime or time for HTML time input (HH:MM format) in configured timezone
    
    Args:
        dt: datetime or time to format
    
    Returns:
        time string in HH:MM format
    """
    return format_time_for_display(dt, '%H:%M')

def parse_trigger_time_from_db(trigger_time: Union[str, time, datetime, None]) -> Optional[datetime]:
    """
    Parse trigger_time from database and normalize to configured timezone
    
    Args:
        trigger_time: trigger time from database (various formats)
    
    Returns:
        timezone-aware datetime or None
    """
    if not trigger_time:
        return None
    
    if isinstance(trigger_time, str):
        # Handle time-only strings (HH:MM:SS format from MySQL TIME fields)
        if ':' in trigger_time and len(trigger_time.split(':')) >= 2:
            try:
                parts = trigger_time.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                return normalize_time_input(time(hour, minute))
            except (ValueError, IndexError):
                return None
        else:
            # Handle full datetime strings
            try:
                dt = datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
                return to_timezone(dt)
            except (ValueError, AttributeError):
                return None
    
    elif isinstance(trigger_time, time):
        return normalize_time_input(trigger_time)
    
    elif isinstance(trigger_time, datetime):
        return to_timezone(trigger_time)
    
    return None

def time_to_database_format(dt: Union[datetime, time]) -> str:
    """
    Convert datetime or time to database storage format (TIME field)
    
    Args:
        dt: datetime or time to convert
    
    Returns:
        time string in HH:MM:SS format for database storage
    """
    if isinstance(dt, time):
        # Convert time to datetime using today's date
        dt = normalize_time_input(dt)
    
    local_dt = to_timezone(dt)
    return local_dt.strftime('%H:%M:%S')

def datetime_to_iso_format(dt: Union[datetime, time]) -> str:
    """
    Convert datetime or time to ISO format for API responses
    
    Args:
        dt: datetime or time to convert
    
    Returns:
        ISO formatted datetime string
    """
    if isinstance(dt, time):
        # Convert time to datetime using today's date
        dt = normalize_time_input(dt)
    
    return to_timezone(dt).isoformat()

class TimezoneContext:
    """Context manager for temporarily changing timezone operations"""
    
    def __init__(self, timezone_name: str):
        self.timezone_name = timezone_name
        self.original_env = None
    
    def __enter__(self):
        self.original_env = os.environ.get('TIMEZONE')
        os.environ['TIMEZONE'] = self.timezone_name
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_env is None:
            os.environ.pop('TIMEZONE', None)
        else:
            os.environ['TIMEZONE'] = self.original_env

# Convenience functions for common operations
def get_current_time_string() -> str:
    """Get current time as HH:MM string in configured timezone"""
    return format_time_for_html_input(now_in_timezone())

def is_same_timezone(tz1: str, tz2: str) -> bool:
    """Check if two timezone names refer to the same timezone"""
    try:
        zone1 = ZoneInfo(tz1)
        zone2 = ZoneInfo(tz2)
        now = datetime.now()
        return zone1.utcoffset(now) == zone2.utcoffset(now)
    except Exception:
        return tz1 == tz2
