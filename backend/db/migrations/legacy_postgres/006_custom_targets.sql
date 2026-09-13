-- Migración para soportar targets subidos por el usuario (Custom Targets)
ALTER TABLE targets ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE targets ADD COLUMN IF NOT EXISTS is_community BOOLEAN DEFAULT FALSE NOT NULL;
