-- Migration: Add trigger_time, offset_minutes, reference_schedule_id to d_schedule
ALTER TABLE d_schedule
  ADD COLUMN trigger_time TIME NULL,
  ADD COLUMN offset_minutes INT NULL,
  ADD COLUMN reference_schedule_id INT NULL,
  ADD CONSTRAINT fk_reference_schedule
    FOREIGN KEY (reference_schedule_id) REFERENCES d_schedule(id)
    ON DELETE SET NULL;
