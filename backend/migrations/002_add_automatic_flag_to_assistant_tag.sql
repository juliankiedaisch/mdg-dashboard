-- Add 'automatic' boolean column to assistant_tag table.
-- Automatic tags are derived from BookStack role → group UUID mapping
-- and cannot be deleted or renamed by admins.
ALTER TABLE assistant_tag ADD COLUMN IF NOT EXISTS automatic BOOLEAN DEFAULT FALSE NOT NULL;
