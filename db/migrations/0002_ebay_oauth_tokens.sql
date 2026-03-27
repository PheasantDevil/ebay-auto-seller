BEGIN;

CREATE TABLE ebay_oauth_tokens (
  tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  access_token_enc bytea NOT NULL,
  refresh_token_enc bytea NOT NULL,
  token_type text NOT NULL DEFAULT 'Bearer',
  scope text,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER ebay_oauth_tokens_set_updated_at
BEFORE UPDATE ON ebay_oauth_tokens
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;

