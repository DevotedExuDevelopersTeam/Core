CREATE TABLE IF NOT EXISTS bans (
    id BIGINT PRIMARY KEY,
    unban_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temproles (
    id BIGINT,
    role_id BIGINT,
    remove_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS afks (
    id BIGINT PRIMARY KEY,
    afk TEXT,
    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rules (
    id VARCHAR(5) PRIMARY KEY,
    content TEXT
);

CREATE TABLE IF NOT EXISTS warns (
    id SERIAL PRIMARY KEY,
    target_id BIGINT,
    issuer_id BIGINT,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rule_violated VARCHAR(5) REFERENCES rules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS levels (
    required_score INT,
    role_id BIGINT
);

CREATE TABLE IF NOT EXISTS scores (
    id BIGINT PRIMARY KEY,
    score_total INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS selfroles (
    id BIGINT PRIMARY KEY,
    selfrole_id BIGINT
);

CREATE TABLE IF NOT EXISTS button_roles (
    id VARCHAR(32) PRIMARY KEY,
    role_id BIGINT,
    message_id BIGINT
);

CREATE TABLE IF NOT EXISTS locked_channels (
    id BIGINT PRIMARY KEY,
    unlock_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS youtubers (
    id BIGINT PRIMARY KEY,
    youtube_id TEXT,
    last_video TEXT,
    is_premium BOOLEAN,
    times_advertised INT DEFAULT 0
);
