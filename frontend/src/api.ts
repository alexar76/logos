/** LOGOS API client — typed, offline-safe. */

export interface Insight {
  insight_id: string;
  kind: string;
  title: string;
  severity: string;
  summary: string;
  explanation: string;
  sources: Array<{ name: string; hub_url: string; status: string }>;
  recommendations: Array<{ priority: number; action: string; impact: string; verification: string }>;
  generated_at: string;
  generated_by: string;
}

export interface Anomaly {
  anomaly_id: string;
  metric: string;
  hub_url: string;
  severity: string;
  z_score: number;
  observed_value: number;
  expected_value: number;
  description: string;
  detected_at: string;
  acknowledged: boolean;
}

export interface DailyReport {
  report_id: string;
  date: string;
  generated_at: string;
  overall_status: string;
  summary: string;
  kpis: Array<{ label: string; value: string; status: string }>;
  insights: Insight[];
  anomalies: Anomaly[];
}

export interface Snapshot {
  status: 'ok' | 'partial' | 'unreachable';
  peers_available?: boolean;
  manifest_available?: boolean;
  generated_at: string | null;
  total_hubs: number | null;
  healthy_hubs: number | null;
  total_capabilities: number | null;
  local_capabilities: number | null;
  federated_capabilities: number | null;
  peers: Array<{
    url: string;
    name: string;
    capabilities_count: number;
    trust_score: number;
    healthy: boolean;
    latency_ms?: number | null;
  }>;
  anomaly_count: number | null;
}

const BASE = '';

async function get<T>(url: string): Promise<T> {
  const r = await fetch(BASE + url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as Promise<T>;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  snapshot: () => get<Snapshot>('/api/v1/snapshot'),
  ask: (query: string, maxInsights = 5) =>
    post<{ insights: Insight[]; interpreted_intent: string; taken_ms: number }>(
      '/api/v1/ask',
      { query, max_insights: maxInsights },
    ),
  insights: (since?: string) =>
    get<{ insights: Insight[] }>(`/api/v1/insights${since ? `?since=${encodeURIComponent(since)}` : ''}`),
  dailyReport: () => get<DailyReport>('/api/v1/report/daily'),
  /** status: 'open' (unacknowledged), 'acknowledged', or 'all' for history. */
  anomalies: (status: 'open' | 'acknowledged' | 'all' = 'open') =>
    get<{ anomalies: Anomaly[] }>(`/api/v1/anomalies?status=${status}`),
  acknowledgeAnomaly: (id: string) =>
    post<{ status: string }>(`/api/v1/anomalies/${encodeURIComponent(id)}/acknowledge`, {}),
  peers: () => get<{ peers: Snapshot['peers'] }>('/api/v1/federation/peers'),
};
