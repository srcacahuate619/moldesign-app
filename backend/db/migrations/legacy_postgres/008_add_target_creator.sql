-- Migration 008: Add target creator fields
--
-- Agrega:
--   1. creator_id en targets — relación al usuario que lo subió
--   2. creator_username en targets — créditos directos del autor
--

ALTER TABLE targets
    ADD COLUMN IF NOT EXISTS creator_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS creator_username VARCHAR(50);

COMMENT ON COLUMN targets.creator_id IS 'ID del usuario creador (NULL para targets oficiales)';
COMMENT ON COLUMN targets.creator_username IS 'Nombre del usuario que subió el receptor para mostrar créditos';
