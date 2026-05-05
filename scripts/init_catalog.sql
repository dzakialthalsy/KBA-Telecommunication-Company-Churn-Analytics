-- ═══════════════════════════════════════════════════════════════════════════
-- init_catalog.sql
-- Dijalankan otomatis oleh PostgreSQL saat pertama kali container dibuat.
-- Berisi seed data roles & users untuk RBAC catalog.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS roles (
    id        SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id        SERIAL PRIMARY KEY,
    username  VARCHAR(50) UNIQUE NOT NULL,
    role_id   INTEGER REFERENCES roles(id),
    full_name VARCHAR(100)
);

-- Seed roles
INSERT INTO roles (role_name) VALUES
    ('Executive'),
    ('Operational'),
    ('Analyst')
ON CONFLICT (role_name) DO NOTHING;

-- Seed users
INSERT INTO users (username, role_id, full_name)
SELECT 'ceo_user', id, 'VP / Direktur'
FROM roles WHERE role_name = 'Executive'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, role_id, full_name)
SELECT 'ops_manager', id, 'Manager Operasional & CR'
FROM roles WHERE role_name = 'Operational'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, role_id, full_name)
SELECT 'data_analyst', id, 'Data / BI Analyst'
FROM roles WHERE role_name = 'Analyst'
ON CONFLICT (username) DO NOTHING;