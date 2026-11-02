-- =======================================================
-- Road Accident Data Analysis System
-- Database Schema for MySQL
-- =======================================================

CREATE DATABASE IF NOT EXISTS accident_analysis_db
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

USE accident_analysis_db;

-- Table 1: locations
-- Stores geographical information: Region (e.g., Downtown, North Corridor) and optional Road Name
CREATE TABLE IF NOT EXISTS locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    road_name VARCHAR(150) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    UNIQUE KEY uq_location (region, road_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table 2: accidents
-- Stores recorded accident events linked to location_id
CREATE TABLE IF NOT EXISTS accidents (
    accident_id INT AUTO_INCREMENT PRIMARY KEY,
    accident_datetime DATETIME NOT NULL,
    location_id INT NOT NULL,
    vehicle_type ENUM('Bike', 'Car', 'Bus', 'Truck', 'Auto', 'Other') NOT NULL,
    severity ENUM('Minor', 'Serious', 'Fatal') NOT NULL,
    weather ENUM('Clear', 'Rainy', 'Foggy', 'Overcast', 'Windy', 'Other') DEFAULT 'Clear',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    INDEX idx_datetime (accident_datetime),
    INDEX idx_severity (severity),
    INDEX idx_vehicle (vehicle_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table 3: users
-- Stores user accounts with role-based authorization (admin / user)
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(191) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email),
    INDEX idx_user_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table 4: otp_verifications
-- Stores hashed one-time passwords for signup and password reset verification
CREATE TABLE IF NOT EXISTS otp_verifications (
    otp_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(191) NOT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    purpose VARCHAR(50) NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    is_used TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_otp_email_purpose (email, purpose),
    INDEX idx_otp_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
