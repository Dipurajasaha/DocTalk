-- Init script for Docker Postgres to enable extensions used by the project
-- This runs only on first initialization of the DB volume

CREATE EXTENSION IF NOT EXISTS vector;
