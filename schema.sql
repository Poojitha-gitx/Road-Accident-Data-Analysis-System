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
