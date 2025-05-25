-- User and privilege setup for testuser (run after prod DB import)
DROP USER IF EXISTS 'testuser'@'%';
DROP USER IF EXISTS 'testuser'@'localhost';
DROP USER IF EXISTS 'testuser'@'172.0.10.1';
CREATE USER 'testuser'@'%' IDENTIFIED BY 'testpassword';
CREATE USER 'testuser'@'localhost' IDENTIFIED BY 'testpassword';
CREATE USER 'testuser'@'172.0.10.1' IDENTIFIED BY 'testpassword';
ALTER USER 'testuser'@'%' IDENTIFIED BY 'testpassword';
ALTER USER 'testuser'@'localhost' IDENTIFIED BY 'testpassword';
ALTER USER 'testuser'@'172.0.10.1' IDENTIFIED BY 'testpassword';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'%';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'localhost';
GRANT ALL PRIVILEGES ON reef_test.* TO 'testuser'@'172.0.10.1';
FLUSH PRIVILEGES;
