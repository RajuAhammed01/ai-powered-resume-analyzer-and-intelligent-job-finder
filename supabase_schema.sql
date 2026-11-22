-- ==============================================================================
-- JobSnap: Supabase PostgreSQL Schema & Seed Migration Script
-- Project: oihepjwiogxmpoxsdhti
-- You can run this directly in the Supabase SQL Editor:
-- https://supabase.com/dashboard/project/oihepjwiogxmpoxsdhti/sql/new
-- ==============================================================================

-- 1. Create "user" table (Quotes required because "user" is a PostgreSQL reserved keyword)
CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    phone VARCHAR(50) DEFAULT '',
    location VARCHAR(100) DEFAULT '',
    country VARCHAR(100) DEFAULT '',
    title_role VARCHAR(100) DEFAULT 'Job Seeker',
    date_of_birth VARCHAR(50) DEFAULT '',
    linkedin_url VARCHAR(200) DEFAULT '',
    language VARCHAR(50) DEFAULT 'English',
    theme VARCHAR(20) DEFAULT 'Light',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    last_login TIMESTAMP WITHOUT TIME ZONE,
    last_login_ip VARCHAR(45) DEFAULT '',
    login_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    profile_image VARCHAR(255) DEFAULT '',
    avatar_data TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_user_email ON "user" (email);
CREATE INDEX IF NOT EXISTS ix_user_name ON "user" (name);

-- 2. Create "login_history" table
CREATE TABLE IF NOT EXISTS login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user" (id) ON DELETE CASCADE,
    email VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL,
    ip_address VARCHAR(45) DEFAULT '127.0.0.1',
    user_agent VARCHAR(255) DEFAULT '',
    failure_reason VARCHAR(200) DEFAULT '',
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_login_history_email ON login_history (email);
CREATE INDEX IF NOT EXISTS ix_login_history_user_id ON login_history (user_id);
CREATE INDEX IF NOT EXISTS ix_login_history_timestamp ON login_history (timestamp);

-- 3. Create "resume" table
CREATE TABLE IF NOT EXISTS resume (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    filename VARCHAR(200) DEFAULT 'Resume.pdf',
    file_path VARCHAR(300),
    extracted_text TEXT,
    extracted_skills TEXT,
    education TEXT,
    experience TEXT,
    contact_info TEXT,
    completeness_score INTEGER DEFAULT 0,
    ats_score INTEGER DEFAULT 85,
    upload_date TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_resume_user_id ON resume (user_id);
CREATE INDEX IF NOT EXISTS ix_resume_upload_date ON resume (upload_date);

-- 4. Create "job_preference" table
CREATE TABLE IF NOT EXISTS job_preference (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    target_role VARCHAR(200) DEFAULT 'Machine Learning Engineer, Data Scientist',
    location_preference VARCHAR(100) DEFAULT 'Any Location',
    location VARCHAR(100) DEFAULT 'Remote',
    country VARCHAR(100) DEFAULT 'All',
    experience_level VARCHAR(50) DEFAULT 'Entry Level',
    expected_salary VARCHAR(50) DEFAULT 'Any',
    job_type VARCHAR(50) DEFAULT 'Full-time',
    preferred_skills TEXT DEFAULT '["Python", "TensorFlow", "scikit-learn", "SQL"]'
);

CREATE INDEX IF NOT EXISTS ix_job_preference_user_id ON job_preference (user_id);

-- 5. Create "saved_job" table
CREATE TABLE IF NOT EXISTS saved_job (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    job_id VARCHAR(100) DEFAULT 'j001',
    job_title VARCHAR(200),
    company VARCHAR(200),
    location VARCHAR(100) DEFAULT 'Remote',
    employment_type VARCHAR(50) DEFAULT 'Full-time',
    match_score INTEGER DEFAULT 85,
    matched_skills TEXT DEFAULT '[]',
    missing_skills TEXT DEFAULT '[]',
    apply_link VARCHAR(500),
    status VARCHAR(50) DEFAULT 'Saved',
    applied_date TIMESTAMP WITHOUT TIME ZONE,
    saved_date TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_saved_job_user_id ON saved_job (user_id);

-- ==============================================================================
-- 6. Initial Seed Data (Demo Candidate User & Preferences)
-- ==============================================================================

INSERT INTO "user" (
    name, email, password_hash, phone, location, country, title_role, status, created_at, login_count
) VALUES (
    'Demo Candidate',
    'demo@jobsnap.com',
    'scrypt:32768:8:1$oQBSBzXKZFlvH2oD$975d970d8fffbbccf23208c7b8730998a555334584dc1ee8d32e4c9b1d8b137f873c3afd6f764f35081b8752999fc6ee22676e9494eaec01fbda25eb8fc7bc4b',
    '+8801712345678',
    'Dhaka, Bangladesh',
    'Bangladesh',
    'Full Stack Engineer',
    'active',
    NOW(),
    1
) ON CONFLICT (email) DO NOTHING;

-- Seed Job Preferences for the demo user
INSERT INTO job_preference (
    user_id, target_role, location_preference, location, country, experience_level, expected_salary, job_type, preferred_skills
)
SELECT 
    id,
    'Full Stack Engineer',
    'Remote / Hybrid',
    'Dhaka',
    'Bangladesh',
    'Mid Level',
    '$25,000 - $40,000 / yr',
    'Full-time',
    '["Python", "Flask", "React", "PostgreSQL", "Docker", "REST APIs", "AWS"]'
FROM "user"
WHERE email = 'demo@jobsnap.com'
  AND NOT EXISTS (SELECT 1 FROM job_preference jp WHERE jp.user_id = "user".id);

-- Seed Sample Verified Company Jobs for the demo user
INSERT INTO saved_job (
    user_id, job_id, job_title, company, location, employment_type, match_score, matched_skills, missing_skills, apply_link, status
)
SELECT 
    u.id, 'bs23_py_01', 'Senior Python / Cloud Solutions Engineer', 'Brain Station 23', 'Dhaka, Bangladesh / Hybrid', 'Full-time', 94, '["Python", "Flask", "PostgreSQL", "Docker", "AWS"]', '["Kubernetes"]', 'https://brainstation-23.com/career/', 'Saved'
FROM "user" u WHERE u.email = 'demo@jobsnap.com' AND NOT EXISTS (SELECT 1 FROM saved_job sj WHERE sj.user_id = u.id AND sj.job_id = 'bs23_py_01');

INSERT INTO saved_job (
    user_id, job_id, job_title, company, location, employment_type, match_score, matched_skills, missing_skills, apply_link, status
)
SELECT 
    u.id, 'bjit_fs_02', 'Full Stack Software Engineer (Python/React)', 'BJIT Group', 'Dhaka, Bangladesh', 'Full-time', 91, '["Python", "React", "PostgreSQL", "REST APIs"]', '["TypeScript"]', 'https://bjitgroup.com/career', 'Saved'
FROM "user" u WHERE u.email = 'demo@jobsnap.com' AND NOT EXISTS (SELECT 1 FROM saved_job sj WHERE sj.user_id = u.id AND sj.job_id = 'bjit_fs_02');

INSERT INTO saved_job (
    user_id, job_id, job_title, company, location, employment_type, match_score, matched_skills, missing_skills, apply_link, status
)
SELECT 
    u.id, 'pathao_be_03', 'Backend Platform Engineer', 'Pathao', 'Dhaka, Bangladesh', 'Full-time', 88, '["Python", "PostgreSQL", "Docker", "REST APIs"]', '["Kafka", "Go"]', 'https://pathao.com/careers/', 'Applied'
FROM "user" u WHERE u.email = 'demo@jobsnap.com' AND NOT EXISTS (SELECT 1 FROM saved_job sj WHERE sj.user_id = u.id AND sj.job_id = 'pathao_be_03');

-- Seed Initial Login Audit Record
INSERT INTO login_history (
    user_id, email, status, ip_address, user_agent, failure_reason, timestamp
)
SELECT
    id, 'demo@jobsnap.com', 'SUCCESS', '127.0.0.1', 'JobSnap Supabase Setup/1.0', 'Initial seed login audit', NOW()
FROM "user"
WHERE email = 'demo@jobsnap.com'
  AND NOT EXISTS (SELECT 1 FROM login_history lh WHERE lh.user_id = "user".id);
