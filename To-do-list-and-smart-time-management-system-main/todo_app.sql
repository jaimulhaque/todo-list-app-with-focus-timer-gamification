-- Create the database
CREATE DATABASE IF NOT EXISTS todo_app;

-- Create the user and grant privileges
CREATE USER IF NOT EXISTS 'todo_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON todo_app.* TO 'todo_user'@'localhost';
FLUSH PRIVILEGES;

-- Use the todo_app database
USE todo_app;

-- Create the notes table
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create the schedule table
CREATE TABLE IF NOT EXISTS schedule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task VARCHAR(255) NOT NULL,
    time_slot TIME NOT NULL,
    date DATE NOT NULL,
    completed BOOLEAN DEFAULT FALSE
);

-- Create the reminders table with reminder_time as VARCHAR for 12-hour format
CREATE TABLE IF NOT EXISTS reminders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    reminder_time VARCHAR(50) NOT NULL,
    `repeat` BOOLEAN DEFAULT FALSE
);

-- Set MySQL timezone to Asia/Dhaka (+06:00)
SET GLOBAL time_zone = '+06:00';