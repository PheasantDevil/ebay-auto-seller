<template>
  <div class="container">
    <h2>Research</h2>
    <p class="sub">
      Enter your <code>tenant_id</code>, then load profit-positive listing candidates.
    </p>

    <div class="controls">
      <label>
        tenant_id
        <input v-model="tenantId" class="input" placeholder="UUID" />
      </label>

      <label>
        limit
        <input v-model.number="limit" type="number" class="input" min="1" max="500" />
      </label>

      <button class="button" :disabled="pending || !tenantId" @click="loadCandidates">
        {{ pending ? 'Loading...' : 'Load candidates' }}
      </button>
    </div>

    <p v-if="error" class="error">Failed: {{ error }}</p>

    <div v-if="candidates.length > 0" class="list">
      <div v-for="c in candidates" :key="c.variant_id" class="card">
        <div class="card-title">{{ c.product_title }}</div>
        <div class="card-sub">{{ c.variant_name }}</div>

        <div class="metrics">
          <div>Avg sold: ${{ format2(c.avg_sold_price_usd) }}</div>
          <div>Item cost: ${{ format2(c.item_price_usd) }}</div>
          <div>Shipping: ${{ format2(c.estimated_shipping_usd) }}</div>
          <div>eBay fee: ${{ format2(c.ebay_fee_usd) }}</div>
          <div>Sales tax: ${{ format2(c.sales_tax_usd) }}</div>
          <div class="net">Net profit: ${{ format2(c.net_profit_usd) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { useRoute, useRuntimeConfig } from '#imports';

type ResearchCandidate = {
  variant_id: string;
  variant_name: string;
  product_title: string;
  avg_sold_price_usd: number;
  item_price_usd: number;
  estimated_shipping_usd: number;
  ebay_fee_usd: number;
  sales_tax_usd: number;
  net_profit_usd: number;
};

type ResearchCandidatesResponse = {
  candidates: ResearchCandidate[];
};

const runtimeConfig = useRuntimeConfig();

const tenantId = ref<string>((useRoute().query.tenant_id as string | undefined) ?? '');
const limit = ref<number>(50);

const pending = ref(false);
const error = ref<string | null>(null);
const candidates = ref<ResearchCandidate[]>([]);

function format2(v: number): string {
  return v.toFixed(2);
}

async function loadCandidates(): Promise<void> {
  if (!tenantId.value) return;

  pending.value = true;
  error.value = null;
  try {
    const apiBaseUrl = runtimeConfig.public.apiBaseUrl as string;
    const url = apiBaseUrl ? `${apiBaseUrl}/research/candidates` : '/research/candidates';

    const res = await $fetch<ResearchCandidatesResponse>(url, {
      method: 'GET',
      query: {
        tenant_id: tenantId.value,
        limit: limit.value,
      },
    });
    candidates.value = res.candidates;
  } catch (e) {
    candidates.value = [];
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    pending.value = false;
  }
}
</script>

<style scoped>
.container {
  padding: 8px 0;
}

.sub {
  margin: 6px 0 12px;
  color: #6b7280;
}

.controls {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.input {
  display: block;
  min-width: 260px;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.button {
  padding: 10px 14px;
  border: 1px solid #111827;
  border-radius: 8px;
  background: #111827;
  color: white;
  cursor: pointer;
}

.button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: #b91c1c;
}

.list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
}

.card-title {
  font-weight: 700;
}

.card-sub {
  color: #6b7280;
  margin-bottom: 8px;
}

.metrics {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
  color: #374151;
  font-size: 14px;
}

.net {
  font-weight: 800;
  color: #065f46;
}
</style>
