PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS dataset (
  dataset_id TEXT PRIMARY KEY,
  name TEXT,
  irb_protocol_id TEXT,
  retention_policy TEXT, -- e.g., 'keep', 'destroy_after:2030-06-01'
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_doc (
  source_doc_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL,
  kind TEXT NOT NULL,          -- transcript, fieldnote, observation_log, etc.
  path TEXT NOT NULL,          -- local filesystem path (protected)
  file_sha256 TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (dataset_id) REFERENCES dataset(dataset_id)
);

CREATE TABLE IF NOT EXISTS source_span (
  span_id TEXT PRIMARY KEY,
  source_doc_id TEXT NOT NULL,
  start_line INTEGER,
  end_line INTEGER,
  start_char INTEGER,
  end_char INTEGER,
  anchor_hash TEXT,            -- sha256(nonce || canonicalized_span_text)
  nonce TEXT,                  -- stored privately
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_doc_id) REFERENCES source_doc(source_doc_id)
);

CREATE TABLE IF NOT EXISTS evidence_span_link (
  evidence_id TEXT NOT NULL,
  span_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (evidence_id, span_id)
);
