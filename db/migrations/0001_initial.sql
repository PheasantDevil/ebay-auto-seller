BEGIN;

-- Aurora Serverless v2 (PostgreSQL) initial schema.
-- Notes:
-- - Secrets/credentials must not be stored in the database. Store only references (e.g., Secrets Manager ARN).
-- - Prices/tax/shipping use USD as the initial assumption; keep currency fields for future expansion.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed');
CREATE TYPE ebay_listing_update_type AS ENUM ('repricing', 'inventory_sync', 'manual');

-- Generic updated_at trigger helper.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email text NOT NULL,
  role text NOT NULL DEFAULT 'admin',
  external_auth_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (char_length(email) <= 320)
);

CREATE UNIQUE INDEX users_tenant_email_uq
  ON users (tenant_id, lower(email));

CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title text NOT NULL,
  brand text,
  category_hint text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER products_set_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE product_variants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  variant_name text NOT NULL, -- e.g., "Black / 2-Pack"
  sku text,
  weight_grams integer, -- used for shipping estimation
  dimensions_cm_json jsonb, -- {length_cm, width_cm, height_cm}
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (weight_grams IS NULL OR weight_grams >= 0)
);

CREATE UNIQUE INDEX product_variants_tenant_sku_uq
  ON product_variants (tenant_id, sku)
  WHERE sku IS NOT NULL;

CREATE TRIGGER product_variants_set_updated_at
BEFORE UPDATE ON product_variants
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE warehouses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name text NOT NULL,
  address_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE inventory_current (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  warehouse_id uuid NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
  on_hand_qty integer NOT NULL DEFAULT 0,
  safety_stock_threshold integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, variant_id, warehouse_id),
  CHECK (on_hand_qty >= 0),
  CHECK (safety_stock_threshold >= 0)
);

CREATE TRIGGER inventory_current_set_updated_at
BEFORE UPDATE ON inventory_current
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Job execution tracking for idempotency and auditing.
-- Used as a reference by snapshots, pricing sync, and eBay updates.
CREATE TABLE job_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  job_type text NOT NULL, -- e.g., "sourcing-scan"
  idempotency_key text, -- optional per job; unique helps prevent duplicates
  status job_status NOT NULL DEFAULT 'queued',
  started_at timestamptz,
  finished_at timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE inventory_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  warehouse_id uuid NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
  on_hand_qty integer NOT NULL,
  captured_at timestamptz NOT NULL DEFAULT now(),
  source_note text,
  captured_by_job_run_id uuid REFERENCES job_runs(id),
  CHECK (on_hand_qty >= 0)
);

-- Supplier/source definitions (Amazon/Walmart/Target etc).
CREATE TABLE sourcing_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source_type text NOT NULL, -- "amazon", "walmart", "target", "custom"
  base_url text,
  auth_ref text, -- reference to Secrets Manager ARN / identifier
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER sourcing_sources_set_updated_at
BEFORE UPDATE ON sourcing_sources
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE sourcing_source_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sourcing_source_id uuid NOT NULL REFERENCES sourcing_sources(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  source_url text NOT NULL,
  external_product_id text,
  active boolean NOT NULL DEFAULT true,
  last_fetched_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, sourcing_source_id, source_url)
);

CREATE TRIGGER sourcing_source_items_set_updated_at
BEFORE UPDATE ON sourcing_source_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE sourcing_item_state_current (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sourcing_source_item_id uuid NOT NULL REFERENCES sourcing_source_items(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  item_price_usd numeric(10,2) NOT NULL,
  estimated_shipping_usd numeric(10,2) NOT NULL,
  estimated_sales_tax_rate_assumed numeric(6,4) NOT NULL, -- e.g., 0.10
  source_stock_qty integer NOT NULL, -- supplier inventory
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_job_run_id uuid REFERENCES job_runs(id),
  PRIMARY KEY (tenant_id, sourcing_source_item_id),
  CHECK (item_price_usd >= 0),
  CHECK (estimated_shipping_usd >= 0),
  CHECK (estimated_sales_tax_rate_assumed >= 0 AND estimated_sales_tax_rate_assumed <= 1),
  CHECK (source_stock_qty >= 0)
);

CREATE TRIGGER sourcing_item_state_current_set_updated_at
BEFORE UPDATE ON sourcing_item_state_current
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE sourcing_item_state_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sourcing_source_item_id uuid NOT NULL REFERENCES sourcing_source_items(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  item_price_usd numeric(10,2) NOT NULL,
  estimated_shipping_usd numeric(10,2) NOT NULL,
  estimated_sales_tax_rate_assumed numeric(6,4) NOT NULL,
  source_stock_qty integer NOT NULL,
  captured_at timestamptz NOT NULL DEFAULT now(),
  captured_by_job_run_id uuid REFERENCES job_runs(id),
  raw_payload jsonb,
  UNIQUE (tenant_id, sourcing_source_item_id, captured_by_job_run_id),
  CHECK (item_price_usd >= 0),
  CHECK (estimated_shipping_usd >= 0),
  CHECK (estimated_sales_tax_rate_assumed >= 0 AND estimated_sales_tax_rate_assumed <= 1),
  CHECK (source_stock_qty >= 0)
);

CREATE INDEX sourcing_item_state_history_variant_captured_at_idx
  ON sourcing_item_state_history (tenant_id, variant_id, captured_at DESC);

-- eBay market statistics used to simulate profit candidates.
CREATE TABLE market_stats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  condition text, -- e.g., "new", "used"
  category_match_confidence numeric(5,4), -- 0..1
  avg_sold_price_usd numeric(10,2) NOT NULL,
  sold_count integer NOT NULL DEFAULT 0,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  raw_payload jsonb
);

CREATE INDEX market_stats_variant_retrieved_at_idx
  ON market_stats (tenant_id, variant_id, retrieved_at DESC);

-- Fee/tax/shipping assumptions and profit targets used for repricing simulation.
CREATE TABLE pricing_assumptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  active boolean NOT NULL DEFAULT true,
  ebay_fee_rate numeric(6,4) NOT NULL, -- eBay final value fee rate as decimal (e.g., 0.1250)
  sales_tax_rate_assumed numeric(6,4) NOT NULL, -- initial buffer (e.g., 0.10)
  shipping_method text, -- identifier for your own shipping model
  target_profit_usd numeric(10,2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (ebay_fee_rate >= 0 AND ebay_fee_rate <= 1),
  CHECK (sales_tax_rate_assumed >= 0 AND sales_tax_rate_assumed <= 1),
  CHECK (target_profit_usd >= 0)
);

CREATE UNIQUE INDEX pricing_assumptions_active_uq
  ON pricing_assumptions (tenant_id, variant_id)
  WHERE active;

CREATE TRIGGER pricing_assumptions_set_updated_at
BEFORE UPDATE ON pricing_assumptions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- eBay listings tracked by our system.
CREATE TABLE ebay_listings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  ebay_item_id text NOT NULL,
  condition text,
  fixed_price_usd numeric(10,2) NOT NULL DEFAULT 0,
  quantity integer NOT NULL DEFAULT 0,
  currency char(3) NOT NULL DEFAULT 'USD',
  policy jsonb,
  listing_status text NOT NULL DEFAULT 'active',
  last_synced_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (fixed_price_usd >= 0),
  CHECK (quantity >= 0)
);

CREATE UNIQUE INDEX ebay_listings_tenant_ebay_item_id_uq
  ON ebay_listings (tenant_id, ebay_item_id);

CREATE INDEX ebay_listings_tenant_variant_idx
  ON ebay_listings (tenant_id, variant_id);

CREATE TRIGGER ebay_listings_set_updated_at
BEFORE UPDATE ON ebay_listings
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE ebay_listing_updates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  ebay_listing_id uuid NOT NULL REFERENCES ebay_listings(id) ON DELETE CASCADE,
  ebay_item_id text NOT NULL,
  update_type ebay_listing_update_type NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  idempotency_key text NOT NULL,
  old_price_usd numeric(10,2),
  new_price_usd numeric(10,2),
  old_qty integer,
  new_qty integer,
  reason text,
  context jsonb,
  UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ebay_listing_updates_listing_updated_at_idx
  ON ebay_listing_updates (tenant_id, ebay_listing_id, updated_at DESC);

-- Order/sales results used for accurate profit reporting.
CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  ebay_order_id text NOT NULL,
  ebay_transaction_id text,
  ebay_listing_id uuid REFERENCES ebay_listings(id),
  ebay_item_id text,
  variant_id uuid REFERENCES product_variants(id),
  sold_at timestamptz NOT NULL,
  sale_price_usd numeric(10,2) NOT NULL,
  shipping_paid_usd numeric(10,2),
  tax_paid_usd numeric(10,2),
  ebay_fees_usd numeric(10,2),
  cogs_usd numeric(10,2), -- unit cost at time of sale (best-effort)
  net_profit_usd numeric(10,2),
  currency char(3) NOT NULL DEFAULT 'USD',
  return_status text, -- e.g., "none", "requested", "approved", "received"
  cogs_source_snapshot_id uuid REFERENCES sourcing_item_state_history(id),
  raw_payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, ebay_order_id)
);

CREATE INDEX orders_tenant_sold_at_idx
  ON orders (tenant_id, sold_at DESC);

COMMIT;

