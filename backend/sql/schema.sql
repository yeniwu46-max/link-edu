-- 临客 Link · MySQL 表结构
-- 请先执行 00_create_database.sql 或确保已 USE link;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  account VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(64) NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'student',
  avatar_url VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_users_account (account)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS courses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(128) NOT NULL,
  category VARCHAR(64) NOT NULL,
  description TEXT NULL,
  lesson_count INT NOT NULL DEFAULT 0,
  cover_url VARCHAR(255) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS training_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  course_id INT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'in_progress',
  progress_percent INT NOT NULL DEFAULT 0,
  duration_minutes INT NOT NULL DEFAULT 0,
  started_at DATETIME NULL,
  last_trained_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_training_user (user_id),
  INDEX idx_training_course (course_id),
  CONSTRAINT fk_training_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_training_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ai_feedbacks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  session_id INT NULL,
  overall_score INT NOT NULL,
  clarity_score INT NULL,
  pace_score INT NULL,
  interaction_score INT NULL,
  suggestion TEXT NULL,
  report_json TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_feedback_user (user_id),
  INDEX idx_feedback_session (session_id),
  CONSTRAINT fk_feedback_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_feedback_session FOREIGN KEY (session_id) REFERENCES training_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS resources (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(128) NOT NULL,
  category VARCHAR(64) NULL,
  description VARCHAR(255) NULL,
  file_url VARCHAR(255) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- RAG 知识库（backend/rag）：文档元数据 + 切片与 float32 向量；进程内索引由 kb_chunks 重建
CREATE TABLE IF NOT EXISTS kb_documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  file_type VARCHAR(16) NOT NULL,
  category VARCHAR(32) NOT NULL,
  tags JSON NOT NULL,
  source VARCHAR(255) NULL,
  description TEXT NULL,
  sha256 VARCHAR(64) NOT NULL UNIQUE,
  size_bytes INT NOT NULL,
  storage_path VARCHAR(255) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'processing',
  error VARCHAR(255) NULL,
  page_count INT NULL,
  chunk_count INT NOT NULL DEFAULT 0,
  embedding_model VARCHAR(128) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  uploaded_by INT NULL,
  content_version VARCHAR(32) NOT NULL DEFAULT '1',
  license_note VARCHAR(255) NULL,
  valid_until VARCHAR(10) NULL,
  last_audited_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_documents_category (category),
  INDEX idx_kb_documents_status (status),
  CONSTRAINT fk_kb_documents_user FOREIGN KEY (uploaded_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS kb_chunks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NOT NULL,
  ordinal INT NOT NULL,
  kind VARCHAR(16) NOT NULL DEFAULT 'text',
  text TEXT NOT NULL,
  heading_path JSON NOT NULL,
  page_start INT NULL,
  page_end INT NULL,
  char_count INT NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  embedding BLOB NOT NULL,
  embedding_model VARCHAR(128) NOT NULL,
  embedding_dim INT NOT NULL,
  extra JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_kb_chunk_ordinal (document_id, ordinal),
  INDEX idx_kb_chunks_document (document_id),
  INDEX idx_kb_chunks_model (embedding_model),
  CONSTRAINT fk_kb_chunks_document FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS kb_audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  document_id INT NULL,
  action VARCHAR(32) NOT NULL,
  actor_id INT NULL,
  detail JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_kb_audit_document (document_id),
  CONSTRAINT fk_kb_audit_document FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
