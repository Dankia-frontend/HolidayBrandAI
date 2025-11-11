-- ============================================================================
-- Create park_configurations table for storing location-specific settings
-- ============================================================================
-- This table stores configuration for different parks (GHL sub-accounts)
-- including Newbook API credentials and GHL pipeline/stage IDs
-- ============================================================================

CREATE TABLE IF NOT EXISTS park_configurations (
    -- Primary identification
    id INT AUTO_INCREMENT PRIMARY KEY,
    location_id VARCHAR(255) NOT NULL UNIQUE COMMENT 'GHL location ID (unique identifier)',
    park_name VARCHAR(255) NOT NULL COMMENT 'Human-readable park name',
    
    -- Newbook API Configuration
    newbook_api_token VARCHAR(500) NOT NULL COMMENT 'Newbook API token for this park',
    newbook_api_key VARCHAR(500) NOT NULL COMMENT 'Newbook API key for this park',
    newbook_region VARCHAR(100) NOT NULL COMMENT 'Newbook region code (e.g., US, AU)',
    
    -- GHL Pipeline Configuration
    ghl_pipeline_id VARCHAR(255) NOT NULL COMMENT 'GHL pipeline ID for this park',
    
    -- GHL Stage IDs for different booking statuses
    stage_arriving_soon VARCHAR(255) DEFAULT NULL COMMENT 'Stage ID for bookings arriving in 1-7 days',
    stage_arriving_today VARCHAR(255) DEFAULT NULL COMMENT 'Stage ID for bookings arriving today',
    stage_arrived VARCHAR(255) DEFAULT NULL COMMENT 'Stage ID for bookings that have arrived',
    stage_departing_today VARCHAR(255) DEFAULT NULL COMMENT 'Stage ID for bookings departing today',
    stage_departed VARCHAR(255) DEFAULT NULL COMMENT 'Stage ID for bookings that have departed',
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Whether this configuration is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When the configuration was created',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
    
    -- Indexes for performance
    INDEX idx_location_id (location_id),
    INDEX idx_is_active (is_active),
    INDEX idx_park_name (park_name)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Park-specific configurations for Newbook and GHL integrations';

-- ============================================================================
-- Example INSERT statements
-- ============================================================================

-- Example 1: Full configuration with all stage IDs
-- INSERT INTO park_configurations (
--     location_id, 
--     park_name, 
--     newbook_api_token, 
--     newbook_api_key, 
--     newbook_region, 
--     ghl_pipeline_id,
--     stage_arriving_soon,
--     stage_arriving_today,
--     stage_arrived,
--     stage_departing_today,
--     stage_departed
-- ) VALUES (
--     'loc_xyz123abc',
--     'Sunny Meadows RV Park',
--     'your_newbook_token_here',
--     'your_newbook_key_here',
--     'US',
--     'pipeline_abc123',
--     '3aeae130-f411-4ac7-bcca-271291fdc3b9',
--     'b429a8e9-e73e-4590-b4c5-8ea1d65e0daf',
--     '99912993-0e69-48f9-9943-096ae68408d7',
--     'fc60b2fa-8c2d-4202-9347-ac2dd32a0e43',
--     '8b54e5e5-27f3-463a-9d81-890c6dfd27eb'
-- );

-- Example 2: Minimal configuration (stage IDs can be NULL)
-- INSERT INTO park_configurations (
--     location_id, 
--     park_name, 
--     newbook_api_token, 
--     newbook_api_key, 
--     newbook_region, 
--     ghl_pipeline_id
-- ) VALUES (
--     'loc_def456',
--     'Mountain View Campground',
--     'another_token',
--     'another_key',
--     'AU',
--     'pipeline_def456'
-- );

-- ============================================================================
-- Useful queries for management
-- ============================================================================

-- View all active configurations
-- SELECT location_id, park_name, newbook_region, is_active, created_at 
-- FROM park_configurations 
-- WHERE is_active = TRUE 
-- ORDER BY park_name;

-- Update a configuration
-- UPDATE park_configurations 
-- SET newbook_api_token = 'new_token', 
--     newbook_api_key = 'new_key',
--     updated_at = NOW()
-- WHERE location_id = 'loc_xyz123abc';

-- Soft delete (deactivate) a configuration
-- UPDATE park_configurations 
-- SET is_active = FALSE, 
--     updated_at = NOW()
-- WHERE location_id = 'loc_xyz123abc';

-- Hard delete (permanent removal)
-- DELETE FROM park_configurations 
-- WHERE location_id = 'loc_xyz123abc';

-- Count active configurations
-- SELECT COUNT(*) as active_parks 
-- FROM park_configurations 
-- WHERE is_active = TRUE;

-- ============================================================================

