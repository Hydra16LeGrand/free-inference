-- PostgreSQL Initialization for LiteLLM Proxy
-- Target: PostgreSQL 16 (Alpine)
--
-- NOTE: LiteLLM v1.83.7-stable uses Prisma ORM to auto-generate and migrate
-- its application schema on first boot (tables: LiteLLM_UserTable,
-- LiteLLM_SpendLogs, LiteLLM_TeamTable, LiteLLM_VerificationToken, etc.).
-- Therefore, this script does NOT create application tables manually.
-- It only ensures required system extensions are present.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Future custom views or functions for billing reconciliation can be added here
-- under a dedicated schema (e.g., billing_views) to avoid collisions with Prisma.
