-- =============================================================================
-- Cognitive Performance Monitoring System
-- Database Schema for MySQL (XAMPP)
-- Objective 3: Web-based continuous cognitive performance monitoring
-- =============================================================================

-- Create database
CREATE DATABASE IF NOT EXISTS cognitive_monitoring_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cognitive_monitoring_db;

-- =============================================================================
-- ROLE TABLE
-- Stores system roles: user, researcher, admin
-- Relationship: ROLE (1) ----< (N) USER
-- =============================================================================
CREATE TABLE IF NOT EXISTS role (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- =============================================================================
-- USER TABLE
-- All system actors (User, Researcher, Admin) share this table
-- Relationship: USER (N) >---- (1) ROLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(20),
    phone VARCHAR(20),
    profile_picture VARCHAR(255),
    is_blocked TINYINT(1) DEFAULT 0,
    email_verified TINYINT(1) DEFAULT 0,
    email_verified_at DATETIME NULL,
    email_otp_hash VARCHAR(255) NULL,
    email_otp_expires_at DATETIME NULL,
    email_otp_attempts INT DEFAULT 0,
    email_otp_sent_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =============================================================================
-- SESSION TABLE
-- Tracks user login/assessment sessions
-- Relationship: USER (1) ----< (N) SESSION
-- =============================================================================
CREATE TABLE IF NOT EXISTS session (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(64) NOT NULL UNIQUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    is_active TINYINT(1) DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- TASK TABLE
-- Individual assessment attempts (typing, reaction, concentration, memory)
-- Relationship: SESSION (1) ----< (N) TASK
--                 USER (1) ----< (N) TASK
-- =============================================================================
CREATE TABLE IF NOT EXISTS task (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    user_id INT NOT NULL,
    task_type ENUM('typing', 'reaction', 'concentration', 'memory') NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    completion_time_ms INT,
    score DECIMAL(10,2),
    status ENUM('in_progress', 'completed', 'abandoned') DEFAULT 'in_progress',
    FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_task_user_type (user_id, task_type)
) ENGINE=InnoDB;

-- =============================================================================
-- INTERACTION_DATA TABLE
-- Raw interaction metrics collected during assessments
-- Relationship: TASK (1) ----< (N) INTERACTION_DATA
-- =============================================================================
CREATE TABLE IF NOT EXISTS interaction_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    user_id INT NOT NULL,
    session_id INT NOT NULL,
    typing_speed_wpm DECIMAL(10,2),
    response_time_ms INT,
    task_completion_time_ms INT,
    error_rate DECIMAL(5,2),
    event_type VARCHAR(50),
    event_data JSON,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- COGNITIVE_METRICS TABLE
-- Per-attempt calculated cognitive metrics
-- Relationship: USER (1) ----< (N) COGNITIVE_METRICS
--                 TASK (1) ----< (1) COGNITIVE_METRICS
-- =============================================================================
CREATE TABLE IF NOT EXISTS cognitive_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    task_id INT NOT NULL,
    task_type ENUM('typing', 'reaction', 'concentration', 'memory') NOT NULL,
    attempt_number INT NOT NULL,
    typing_speed_wpm DECIMAL(10,2),
    response_time_ms INT,
    concentration_score DECIMAL(10,2),
    memory_score DECIMAL(10,2),
    error_rate DECIMAL(5,2),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- AGGREGATED_METRICS TABLE
-- Averages after completing 5 attempts per assessment type
-- Relationship: USER (1) ----< (N) AGGREGATED_METRICS
-- =============================================================================
CREATE TABLE IF NOT EXISTS aggregated_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    avg_typing_speed DECIMAL(10,2),
    avg_response_time DECIMAL(10,2),
    avg_concentration_score DECIMAL(10,2),
    avg_memory_score DECIMAL(10,2),
    overall_cognitive_score DECIMAL(10,2),
    cycle_number INT DEFAULT 1,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- ALERT TABLE
-- System alerts for researchers (e.g. performance drops)
-- Relationship: USER (1) ----< (N) ALERT
-- =============================================================================
CREATE TABLE IF NOT EXISTS alert (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    severity ENUM('low', 'medium', 'high') DEFAULT 'medium',
    is_read TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- PUBLICATION TABLE
-- Research publications managed by researchers
-- Relationship: USER/Researcher (1) ----< (N) PUBLICATION
-- =============================================================================
CREATE TABLE IF NOT EXISTS publication (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content LONGTEXT,
    date_published DATE,
    status ENUM('draft', 'published', 'hidden') DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- FEEDBACK_REQUEST TABLE
-- User requests for researcher feedback
-- Relationship: USER (1) ----< (N) FEEDBACK_REQUEST
-- =============================================================================
CREATE TABLE IF NOT EXISTS feedback_request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    researcher_id INT NULL,
    status ENUM('pending', 'accepted', 'ignored', 'completed') DEFAULT 'pending',
    user_message TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (researcher_id) REFERENCES user(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =============================================================================
-- FEEDBACK TABLE
-- Researcher feedback sent to users
-- Relationship: FEEDBACK_REQUEST (1) ----< (1) FEEDBACK
-- =============================================================================
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    feedback_request_id INT NOT NULL,
    researcher_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_request_id) REFERENCES feedback_request(id) ON DELETE CASCADE,
    FOREIGN KEY (researcher_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- NOTIFICATION TABLE
-- User notifications: feedback, publications, assessment reminders
-- Relationship: USER (1) ----< (N) NOTIFICATION
-- =============================================================================
CREATE TABLE IF NOT EXISTS notification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    notification_type ENUM('feedback', 'publication', 'assessment_reminder', 'system',
                           'performance_alert', 'cycle_complete', 'consent', 'password_code') NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    link_url VARCHAR(255),
    is_read TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_notification_user_read (user_id, is_read)
) ENGINE=InnoDB;

-- =============================================================================
-- ANALYTICS_REPORT TABLE
-- Simple reports generated by researchers
-- Relationship: USER/Researcher (1) ----< (N) ANALYTICS_REPORT
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytics_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    researcher_id INT NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (researcher_id) REFERENCES user(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- SYSTEM_LOG TABLE
-- Audit trail for admin monitoring
-- Relationship: USER (1) ----< (N) SYSTEM_LOG (nullable for system events)
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =============================================================================
-- SYSTEM_SETTINGS TABLE
-- Key-value store for admin system settings
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    description VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
