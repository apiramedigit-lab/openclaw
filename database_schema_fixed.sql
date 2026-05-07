-- ═══════════════════════════════════════════════════════════
-- Server Management Portal - PostgreSQL Database Schema
-- CORRECTED VERSION - No Errors
-- ═══════════════════════════════════════════════════════════

-- Drop existing views first (order matters!)
DROP VIEW IF EXISTS vm_project_counts;
DROP VIEW IF EXISTS vms_with_servers;

-- Drop existing tables if they exist
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS vms CASCADE;
DROP TABLE IF EXISTS servers CASCADE;

-- ═══════════════════════════════════════════════════════════
-- SERVERS TABLE
-- ═══════════════════════════════════════════════════════════
CREATE TABLE servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ip_address VARCHAR(50) NOT NULL UNIQUE,
    purpose TEXT,
    cpu_cores INTEGER DEFAULT 0,
    ram_gb INTEGER DEFAULT 0,
    disk_tb DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'online' CHECK (status IN ('online', 'degraded', 'offline')),
    proxmox_api_url VARCHAR(255),
    proxmox_node VARCHAR(50),
    proxmox_username VARCHAR(100),
    proxmox_password VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster queries
CREATE INDEX idx_servers_status ON servers(status);
CREATE INDEX idx_servers_ip ON servers(ip_address);

-- ═══════════════════════════════════════════════════════════
-- VMS TABLE
-- ═══════════════════════════════════════════════════════════
CREATE TABLE vms (
    id SERIAL PRIMARY KEY,
    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    os VARCHAR(50) NOT NULL CHECK (os IN ('ubuntu', 'windows', 'debian', 'centos', 'other')),
    os_version VARCHAR(50),
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'stopped', 'maintenance')),
    cpu VARCHAR(20) DEFAULT '—',
    ram VARCHAR(20) DEFAULT '—',
    disk VARCHAR(20) DEFAULT '—',
    ssh_port VARCHAR(10) DEFAULT '22',
    ssh_user VARCHAR(50),
    ssh_password VARCHAR(255),
    proxmox_vmid INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(server_id, name)
);

-- Indexes for faster queries
CREATE INDEX idx_vms_server ON vms(server_id);
CREATE INDEX idx_vms_status ON vms(status);
CREATE INDEX idx_vms_ip ON vms(ip_address);

-- ═══════════════════════════════════════════════════════════
-- PROJECTS TABLE (Apps running on VMs)
-- ═══════════════════════════════════════════════════════════
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    vm_id INTEGER NOT NULL REFERENCES vms(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    port VARCHAR(10),
    path TEXT,
    domain VARCHAR(255),
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'stopped', 'maintenance')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX idx_projects_vm ON projects(vm_id);
CREATE INDEX idx_projects_status ON projects(status);

-- ═══════════════════════════════════════════════════════════
-- TRIGGERS - Auto-update timestamps
-- ═══════════════════════════════════════════════════════════

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for each table
CREATE TRIGGER update_servers_updated_at BEFORE UPDATE ON servers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vms_updated_at BEFORE UPDATE ON vms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════════
-- SAMPLE DATA (Optional - for testing)
-- ═══════════════════════════════════════════════════════════

-- Insert sample server
INSERT INTO servers (name, ip_address, purpose, cpu_cores, ram_gb, disk_tb, status, proxmox_node)
VALUES 
('proxmoxl01.severdigitweb.uk', '192.168.1.100', 'Production Server', 48, 220, 1.84, 'online', 'pve');

-- Insert sample VMs
INSERT INTO vms (server_id, name, ip_address, os, os_version, status, cpu, ram, disk, ssh_user, proxmox_vmid)
VALUES 
(1, 'Windows-Desktop-Staff1', '192.168.1.101', 'windows', 'Windows 11 Pro', 'running', '4', '8 GB', '60 GB', 'Staff1', 100),
(1, 'ubuntu-gpu', '192.168.1.102', 'ubuntu', 'Ubuntu 22.04', 'running', '8', '16 GB', '100 GB', 'root', 102);

-- Insert sample projects
INSERT INTO projects (vm_id, name, port, path, domain, status, description)
VALUES 
(2, 'Web Server', '80', '/var/www/html', 'example.com', 'running', 'Main website'),
(2, 'API Backend', '3000', '/opt/api', 'api.example.com', 'running', 'REST API service');

-- ═══════════════════════════════════════════════════════════
-- VIEWS - Useful queries
-- ═══════════════════════════════════════════════════════════

-- View: All VMs with server info
CREATE OR REPLACE VIEW vms_with_servers AS
SELECT 
    v.id,
    v.name AS vm_name,
    v.ip_address AS vm_ip,
    v.os,
    v.os_version,
    v.status AS vm_status,
    v.cpu,
    v.ram,
    v.disk,
    s.id AS server_id,
    s.name AS server_name,
    s.ip_address AS server_ip,
    s.status AS server_status
FROM vms v
JOIN servers s ON v.server_id = s.id;

-- View: Project counts per VM (CORRECTED - v.id instead of v.vm_id)
CREATE OR REPLACE VIEW vm_project_counts AS
SELECT 
    v.id AS vm_id,
    v.name AS vm_name,
    COUNT(p.id) AS project_count
FROM vms v
LEFT JOIN projects p ON v.id = p.vm_id
GROUP BY v.id, v.name;

-- ═══════════════════════════════════════════════════════════
-- SUCCESS! All tables and views created
-- ═══════════════════════════════════════════════════════════
