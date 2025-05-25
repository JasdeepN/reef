-- tests/seed.sql: Seed data for reef_test matching SQLAlchemy models

-- Tanks table
CREATE TABLE IF NOT EXISTS tanks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(45) NOT NULL,
    gross_water_vol INT,
    net_water_vol INT,
    live_rock_lbs FLOAT
);
INSERT INTO tanks (id, name, gross_water_vol, net_water_vol, live_rock_lbs) VALUES
(1, 'Main Display', 100, 90, 50.0);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    uses VARCHAR(32),
    total_volume FLOAT,
    used_amt FLOAT DEFAULT 0,
    current_avail FLOAT,
    dry_refill FLOAT,
    last_update TIMESTAMP NULL DEFAULT NULL
);
INSERT INTO products (id, name, uses, total_volume, used_amt, current_avail, dry_refill) VALUES
(1, 'Alk Buffer', '+Alk', 1000, 100, 900, 100);

-- TestResults table
CREATE TABLE IF NOT EXISTS test_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    test_date DATE,
    test_time TIME,
    alk FLOAT,
    po4_ppm FLOAT,
    po4_ppb INT,
    no3_ppm INT,
    cal INT,
    mg FLOAT,
    sg FLOAT,
    tank_id INT NOT NULL,
    FOREIGN KEY (tank_id) REFERENCES tanks(id)
);
INSERT INTO test_results (id, test_date, test_time, alk, po4_ppm, po4_ppb, no3_ppm, cal, mg, sg, tank_id) VALUES
(1, '2025-05-22', '12:00:00', 8.5, 0.03, 30, 5, 420, 1300, 1.025, 1);

-- DSchedule table
CREATE TABLE IF NOT EXISTS d_schedule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_interval INT NOT NULL,
    suspended BOOLEAN DEFAULT FALSE,
    last_refill DATETIME DEFAULT NULL,
    amount FLOAT NOT NULL,
    tank_id INT NOT NULL,
    product_id INT NOT NULL,
    FOREIGN KEY (tank_id) REFERENCES tanks(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
INSERT INTO d_schedule (id, trigger_interval, suspended, last_refill, amount, tank_id, product_id) VALUES
(1, 24, FALSE, '2025-05-21 08:00:00', 10.0, 1, 1);

-- Dosing table
CREATE TABLE IF NOT EXISTS dosing (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_time DATETIME(3),
    amount FLOAT NOT NULL,
    product_id INT,
    schedule_id INT,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (schedule_id) REFERENCES d_schedule(id)
);
INSERT INTO dosing (id, trigger_time, amount, product_id, schedule_id) VALUES
(1, '2025-05-22 09:00:00', 10.0, 1, 1);

-- Ensure testuser exists and has privileges (for local/dev environments)
DROP USER IF EXISTS 'testuser'@'%';
DROP USER IF EXISTS 'testuser'@'localhost';
DROP USER IF EXISTS 'testuser'@'172.0.10.1';
CREATE USER 'testuser'@'%' IDENTIFIED BY 'testpassword';
CREATE USER 'testuser'@'localhost' IDENTIFIED BY 'testpassword';
CREATE USER 'testuser'@'172.0.10.1' IDENTIFIED BY 'testpassword';
ALTER USER 'testuser'@'%' IDENTIFIED WITH mysql_native_password BY 'testpassword';
ALTER USER 'testuser'@'localhost' IDENTIFIED WITH mysql_native_password BY 'testpassword';
ALTER USER 'testuser'@'172.0.10.1' IDENTIFIED WITH mysql_native_password BY 'testpassword';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'%';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'localhost';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'172.0.10.1';
FLUSH PRIVILEGES;

-- Add more tables and seed data as needed for your tests
