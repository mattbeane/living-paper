PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS paper (
  paper_id TEXT PRIMARY KEY,
  title TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim (
  claim_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  claim_type TEXT NOT NULL CHECK (claim_type IN ('empirical','theoretical','methodological','definitional','boundary_condition')),
  text TEXT NOT NULL,
  confidence REAL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','verified','published','retracted','updated')),
  verification_status TEXT DEFAULT 'unverified' CHECK (verification_status IN ('unverified','author_verified','external_verified')),
  verified_by TEXT,
  verified_at TEXT,
  verification_mode TEXT DEFAULT 'public_provenance',
  parent_claim_id TEXT,
  frame_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (paper_id) REFERENCES paper(paper_id),
  FOREIGN KEY (parent_claim_id) REFERENCES claim(claim_id)
);

CREATE TABLE IF NOT EXISTS claim_revision (
  revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT NOT NULL,
  old_text TEXT NOT NULL,
  new_text TEXT NOT NULL,
  old_confidence REAL,
  new_confidence REAL,
  reason TEXT,
  revised_by TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (claim_id) REFERENCES claim(claim_id)
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  sensitivity_tier TEXT NOT NULL CHECK (sensitivity_tier IN ('PUBLIC','CONTROLLED','WITNESS_ONLY')),
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (paper_id) REFERENCES paper(paper_id)
);

CREATE TABLE IF NOT EXISTS claim_evidence_link (
  claim_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  relation TEXT NOT NULL CHECK (relation IN ('supports','challenges','illustrates','qualifies','necessitates')),
  weight TEXT DEFAULT 'supporting' CHECK (weight IN ('central','supporting','peripheral')),
  note TEXT,
  verification_status TEXT DEFAULT 'unverified' CHECK (verification_status IN ('unverified','author_verified','external_verified')),
  verified_by TEXT,
  verified_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (claim_id, evidence_id, relation),
  FOREIGN KEY (claim_id) REFERENCES claim(claim_id),
  FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_paper ON claim(paper_id);
CREATE INDEX IF NOT EXISTS idx_evidence_paper ON evidence(paper_id);
CREATE INDEX IF NOT EXISTS idx_link_claim ON claim_evidence_link(claim_id);
CREATE INDEX IF NOT EXISTS idx_link_evidence ON claim_evidence_link(evidence_id);
