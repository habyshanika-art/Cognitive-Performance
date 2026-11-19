-- =============================================================================
-- Seed Data for Cognitive Performance Monitoring System
-- Run after schema.sql
-- =============================================================================

USE cognitive_monitoring_db;

-- Default roles
INSERT INTO role (name, description) VALUES
    ('user', 'Regular participant who performs cognitive assessments'),
    ('researcher', 'Research staff who analyze data and publish findings'),
    ('admin', 'System administrator with full access')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- Note: Default admin/researcher accounts are created via init_db.py
-- which generates proper password hashes. Run: python init_db.py

-- Default system settings
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
    ('site_name', 'Cognitive Performance Monitoring System', 'Application display name'),
    ('assessments_per_cycle', '5', 'Number of attempts required per assessment'),
    ('maintenance_mode', '0', '1 = maintenance mode enabled'),
    ('contact_email', 'haby@gmail.com', 'Public contact email')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);
