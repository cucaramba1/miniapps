CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  first_name TEXT NOT NULL DEFAULT '',
  username TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE entitlements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  days INTEGER NOT NULL CHECK (days > 0),
  source TEXT NOT NULL CHECK (source IN ('stars','review','grant')),
  ref TEXT UNIQUE,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX idx_ent_user ON entitlements(user_id);
CREATE TABLE districts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name_ru TEXT NOT NULL,
  geojson TEXT NOT NULL
);
CREATE TABLE places (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  osm_id TEXT UNIQUE,
  name TEXT NOT NULL,
  name_fold TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'hotel',
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  district_id INTEGER REFERENCES districts(id),
  price_from_vnd INTEGER,
  price_to_vnd INTEGER,
  basics TEXT NOT NULL DEFAULT '{}',
  official_photos TEXT NOT NULL DEFAULT '[]',
  commercial INTEGER NOT NULL DEFAULT 0,
  aliases TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending','rejected')),
  created_by INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_places_geo ON places(lat, lon);
CREATE INDEX idx_places_status ON places(status);
CREATE TABLE reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  place_id INTEGER NOT NULL REFERENCES places(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL CHECK (status IN ('published','held','rejected','revoked')),
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  text TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  accuracy_m REAL,
  photos TEXT NOT NULL DEFAULT '[]',
  hold_reason TEXT,
  text_hash TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_reviews_place ON reviews(place_id, status);
CREATE INDEX idx_reviews_user ON reviews(user_id, created_at);
CREATE INDEX idx_reviews_hash ON reviews(text_hash);
CREATE TABLE review_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  review_id INTEGER NOT NULL REFERENCES reviews(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  UNIQUE(review_id, user_id)
);
CREATE TABLE signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  place_id INTEGER NOT NULL REFERENCES places(id),
  source TEXT NOT NULL,
  tag TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  url TEXT,
  confirmed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_signals_place ON signals(place_id);
CREATE TABLE amenities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  osm_id TEXT UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  cheap_local INTEGER
);
CREATE INDEX idx_amen_geo ON amenities(lat, lon);
CREATE TABLE listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_url TEXT UNIQUE,
  title TEXT NOT NULL,
  price_vnd INTEGER,
  bedrooms INTEGER,
  district_text TEXT NOT NULL DEFAULT '',
  posted_at TEXT,
  place_id INTEGER REFERENCES places(id),
  chats_count INTEGER NOT NULL DEFAULT 0,
  contacts TEXT NOT NULL DEFAULT '{}',
  expires_at TEXT NOT NULL
);
CREATE TABLE realtors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'vi' CHECK (kind IN ('ru','vi')),
  languages TEXT NOT NULL DEFAULT '[]',
  commission_free_confirmed INTEGER NOT NULL DEFAULT 0,
  confirmed_at TEXT,
  notes TEXT NOT NULL DEFAULT '',
  contacts TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE flags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  label TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  place_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_flags_user ON flags(user_id);
CREATE TABLE favorites (
  user_id INTEGER NOT NULL REFERENCES users(id),
  place_id INTEGER NOT NULL REFERENCES places(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, place_id)
);
CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  plan TEXT NOT NULL,
  stars INTEGER NOT NULL,
  charge_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  refunded_at TEXT
);
