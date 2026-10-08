/** LOGOS Analytics Panel — professional charts, sortable+groupable tables, heatmap, pie */

import { useMemo, useState } from 'react';

/* ── Types ──────────────────────────────────────────────────────────────── */
interface Peer { url: string; name: string; capabilities_count: number; trust_score: number; healthy: boolean; }
interface Anomaly { anomaly_id: string; metric: string; severity: string; z_score: number; observed_value: number; expected_value: number; detected_at: string; acknowledged: boolean; }
interface Insight { insight_id: string; kind: string; title: string; severity: string; summary: string; generated_at: string; }
interface Col<T> { key: keyof T; label: string; w?: number; fmt?: (v: any, row: T) => string; }
type SortDir = 'asc' | 'desc';
type T = (k: string, v?: any, d?: string) => string;

/* ── Line Chart ──────────────────────────────────────────────────────────── */
function LineChart({ data, width = 600, height = 180, label = '', t }: { data: Array<{ts:string;v:number}>; width?:number; height?:number; label?:string; t: T }) {
  if (data.length < 2) return <div className="empty-chart">{t('analytics.notEnoughData', undefined, 'Not enough data')}</div>;
  const pad = { top: 20, right: 16, bottom: 28, left: 44 };
  const w = width - pad.left - pad.right, h = height - pad.top - pad.bottom;
  const vals = data.map(d => d.v), min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const xs = data.map((_, i) => pad.left + (i / Math.max(data.length - 1, 1)) * w);
  const ys = vals.map(v => pad.top + h - ((v - min) / range) * h);
  const pts = xs.map((x, i) => `${x},${ys[i]}`).join(' ');
  const yTicks = 4;
  const fmt = (v: number) => v > 1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(0);
  return (
    <div>
      {label && <div className="chart-label">{label}</div>}
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto' }}>
        {Array.from({length:yTicks+1}, (_,i) => {
          const y = pad.top + (h*i)/yTicks, v = max - (range*i)/yTicks;
          return <g key={i}><line x1={pad.left} y1={y} x2={pad.left+w} y2={y} stroke="rgba(255,255,255,0.05)"/><text x={pad.left-6} y={y+4} textAnchor="end" fill="var(--ink-dim)" fontSize={9} fontFamily="ui-monospace,monospace">{fmt(v)}</text></g>;
        })}
        <defs><linearGradient id="areaGrad2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity="0.15"/><stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/></linearGradient></defs>
        <polygon points={`${xs[0]},${pad.top+h} ${pts} ${xs[xs.length-1]},${pad.top+h}`} fill="url(#areaGrad2)"/>
        <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"/>
        {xs.map((x,i) => <circle key={i} cx={x} cy={ys[i]} r={2.5} fill="var(--accent)" opacity={i===xs.length-1?1:0.4}/>)}
      </svg>
    </div>
  );
}

/* ── Donut / Pie Chart ───────────────────────────────────────────────────── */
function DonutChart({ segments, size = 140, label = '', t }: { segments: Array<{label:string;value:number;color:string}>; size?:number; label?:string; t: T }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const denominator = Math.max(total, 1);
  const r = size / 2 - 8, circ = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div style={{ textAlign: 'center' }}>
      {label && <div className="chart-label">{label}</div>}
      <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size }}>
        {segments.map((s, i) => {
          const dash = (s.value / denominator) * circ;
          const seg = <circle key={i} cx={size/2} cy={size/2} r={r} fill="none" stroke={s.color} strokeWidth={10}
            strokeDasharray={`${dash} ${circ - dash}`} strokeDashoffset={-offset}
            strokeLinecap="butt" transform={`rotate(-90 ${size/2} ${size/2})`} />;
          offset += dash;
          return seg;
        })}
        <text x={size/2} y={size/2-4} textAnchor="middle" fill="var(--ink)" fontSize={size*0.2} fontWeight={700} fontFamily="ui-monospace,monospace">{total}</text>
        <text x={size/2} y={size/2+14} textAnchor="middle" fill="var(--ink-dim)" fontSize={10}>{t('analytics.total', undefined, 'total')}</text>
      </svg>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginTop: 6 }}>
        {segments.map((s, i) => <span key={i} style={{ fontSize: 10, color: s.color, fontFamily: 'ui-monospace,monospace' }}>● {s.label}: {s.value}</span>)}
      </div>
    </div>
  );
}

/* ── Bar Chart ────────────────────────────────────────────────────────────── */
function BarChart({ items, label, valueKey, colorKey }: { items: Array<Record<string,any>>; label:string; valueKey:string; colorKey?:string }) {
  const max = Math.max(1, ...items.map(i => Number(i[valueKey]) || 0));
  return (
    <div>
      {label && <div className="chart-label">{label}</div>}
      {items.slice(0, 10).map((item, i) => {
        const v = Number(item[valueKey]) || 0, pct = (v / max) * 100;
        const color = item.healthy === false ? 'var(--bad)' : item.severity === 'critical' ? '#ff2d55' : item.severity === 'high' ? '#ff6b3d' : item.severity === 'medium' ? '#ffcc33' : colorKey || 'var(--accent)';
        return (
          <div key={i} className="bar-row">
            <div className="bar-label" title={String(item.name || item.url || item.label || '')}>{String(item.name || item.url || item.label || '').replace(/^https?:\/\//, '').split('/')[0].slice(0, 16)}</div>
            <div className="bar-track"><div style={{ height: '100%', width: `${Math.max(2, pct)}%`, background: color, borderRadius: 4, transition: 'width .5s ease', minWidth: pct > 0 ? 4 : 0 }} /></div>
            <div className="bar-value">{v}</div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Generic Sortable + Groupable Table ───────────────────────────────────── */
function Table<T extends Record<string,any>>({ rows, columns, groupBy, defaultSort, defaultDir = 'desc' }: {
  rows: T[]; columns: Col<T>[]; groupBy?: { key: keyof T; label: (v: string) => string };
  defaultSort: keyof T; defaultDir?: SortDir;
}) {
  const [sortKey, setSortKey] = useState<keyof T>(defaultSort);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const handleSort = (k: keyof T) => {
    if (k === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir('desc'); }
  };

  const toggleGroup = (g: string) => {
    setCollapsed(prev => { const n = new Set(prev); if (n.has(g)) n.delete(g); else n.add(g); return n; });
  };

  const sorted = useMemo(() => {
    const s = [...rows].sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      const n = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va ?? '').localeCompare(String(vb ?? ''));
      return sortDir === 'desc' ? -n : n;
    });
    return s;
  }, [rows, sortKey, sortDir]);

  if (!groupBy) {
    // Simple table — no grouping
    return (
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr>{columns.map(c => (
            <th key={String(c.key)} onClick={() => handleSort(c.key)} style={{ width: c.w, cursor: 'pointer' }}>
              {c.label} {sortKey === c.key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
            </th>
          ))}</tr></thead>
          <tbody>{sorted.map((row, i) => (
            <tr key={i}>{columns.map(c => <td key={String(c.key)} style={{ width: c.w }}>{c.fmt ? c.fmt(row[c.key], row) : String(row[c.key] ?? '—')}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    );
  }

  // Grouped table
  const groups = new Map<string, T[]>();
  for (const row of sorted) {
    const gv = String(row[groupBy.key] ?? 'other');
    const gl = groupBy.label(gv);
    if (!groups.has(gl)) groups.set(gl, []);
    groups.get(gl)!.push(row);
  }

  return (
    <div className="table-wrap">
      {Array.from(groups.entries()).map(([gname, grows]) => (
        <div key={gname}>
          <div className="group-head" onClick={() => toggleGroup(gname)}>
            <span>{collapsed.has(gname) ? '▸' : '▾'}</span>
            <strong>{gname}</strong>
            <span className="group-count">{grows.length}</span>
          </div>
          {!collapsed.has(gname) && (
            <table className="data-table">
              <thead><tr>{columns.map(c => (
                <th key={String(c.key)} onClick={() => handleSort(c.key)} style={{ width: c.w, cursor: 'pointer' }}>
                  {c.label} {sortKey === c.key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
              ))}</tr></thead>
              <tbody>{grows.map((row, i) => (
                <tr key={i}>{columns.map(c => <td key={String(c.key)} style={{ width: c.w }}>{c.fmt ? c.fmt(row[c.key], row) : String(row[c.key] ?? '—')}</td>)}</tr>
              ))}</tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Anomaly Heatmap Calendar ──────────────────────────────────────────── */
function HeatmapCalendar({ anomalies, days = 90, t }: { anomalies: Anomaly[]; days?: number; t: T }) {
  const cells: Array<{ date: string; count: number; maxSev: number }> = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now); d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    cells.push({ date: key, count: 0, maxSev: 0 });
  }
  for (const a of anomalies) {
    const key = (a.detected_at || '').slice(0, 10);
    const cell = cells.find(c => c.date === key);
    if (cell) { cell.count++; cell.maxSev = Math.max(cell.maxSev, {critical:5,high:4,medium:3,low:2,info:1}[a.severity] || 0); }
  }
  const weeks: typeof cells[] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const colorFor = (maxSev: number, count: number) => {
    if (count === 0) return 'rgba(255,255,255,0.03)';
    if (maxSev >= 5) return 'rgba(255,45,85,0.7)';
    if (maxSev >= 4) return 'rgba(255,107,61,0.6)';
    if (maxSev >= 3) return 'rgba(255,204,51,0.5)';
    return 'rgba(0,229,255,0.35)';
  };

  return (
    <div>
      <div className="chart-label">{t('analytics.heatmapDays', { days }, `Anomaly heatmap (${days} days)`)}</div>
      <div style={{ display: 'flex', gap: 3 }}>
        {weeks.map((week, wi) => (
          <div key={wi} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {week.map(cell => (
              <div key={cell.date} title={`${cell.date}: ${t('analytics.anomaliesCount', { n: cell.count }, `${cell.count} anomalies`)}`}
                style={{ width: 12, height: 12, borderRadius: 2, background: colorFor(cell.maxSev, cell.count), cursor: 'pointer' }} />
            ))}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 9, color: 'var(--ink-dim)' }}>
        <span>{t('analytics.less', undefined, 'Less')}</span>
        {[0,1,3,4,5].map(v => <div key={v} style={{ width: 10, height: 10, borderRadius: 2, background: colorFor(v, v>0?1:0) }} />)}
        <span>{t('analytics.more', undefined, 'More')}</span>
      </div>
    </div>
  );
}

/* ── MAIN PANEL ──────────────────────────────────────────────────────────── */
interface Props { snapshot: any; anomalies: Anomaly[]; insights: Insight[]; anomaliesAvailable: boolean; insightsAvailable: boolean; consData: any; theme: string; t: (k: string, v?: any, d?: string) => string; trendPoints?: Array<{ts:string;v:number}>; }

const SEV_COLORS: Record<string,string> = { critical: '#ff2d55', high: '#ff6b3d', medium: '#ffcc33', low: '#4db8ff', info: '#7a8699' };

export default function AnalyticsPanel({ snapshot, anomalies, insights, anomaliesAvailable, insightsAvailable, theme, t, trendPoints }: Props) {
  const trendData = useMemo(() => {
    if (trendPoints && trendPoints.length > 1) return trendPoints;
    // Never fabricate history: show an explicit insufficient-data state.
    return snapshot?.generated_at && typeof snapshot.total_capabilities === 'number'
      ? [{ ts: snapshot.generated_at, v: snapshot.total_capabilities }]
      : [];
  }, [snapshot, trendPoints]);

  const hubItems = useMemo(() => (snapshot?.peers || []).map((p: Peer) => ({ name: p.name || p.url, url: p.url, caps: p.capabilities_count, trust: Math.round(p.trust_score*100), healthy: p.healthy })), [snapshot]);

  const sevItems = useMemo(() => {
    const c: Record<string,number> = {};
    anomalies.forEach(a => { c[a.severity] = (c[a.severity]||0) + 1; });
    return Object.entries(c).map(([k,v]) => ({ label: k, value: v, color: SEV_COLORS[k] || 'var(--ink-dim)' }));
  }, [anomalies]);

  // ── Table column definitions ─────────────────────────────────────────
  const anomalyCols: Col<Anomaly>[] = [
    { key: 'metric', label: t('analytics.colMetric', undefined, 'Metric'), w: 130, fmt: v => String(v).slice(0, 28) },
    { key: 'severity', label: t('analytics.colSeverity', undefined, 'Sev'), w: 60, fmt: v => String(v).toUpperCase() },
    { key: 'z_score', label: t('analytics.colZ', undefined, 'Z'), w: 50, fmt: v => Number(v).toFixed(1) + 'σ' },
    { key: 'observed_value', label: t('analytics.colObserved', undefined, 'Observed'), w: 70, fmt: v => Number(v).toFixed(1) },
    { key: 'expected_value', label: t('analytics.colExpected', undefined, 'Expected'), w: 70, fmt: v => Number(v).toFixed(1) },
    { key: 'detected_at', label: t('analytics.colDetected', undefined, 'Detected'), w: 120, fmt: v => String(v).slice(0, 19)?.replace('T',' ') },
    { key: 'acknowledged', label: t('analytics.ack', undefined, 'Ack'), w: 40, fmt: v => v ? '✓' : '—' },
  ];

  const insightCols: Col<Insight>[] = [
    { key: 'kind', label: t('analytics.colKind', undefined, 'Kind'), w: 70 },
    { key: 'title', label: t('analytics.colTitle', undefined, 'Title'), w: 200, fmt: v => String(v).slice(0, 40) },
    { key: 'severity', label: t('analytics.colSeverity', undefined, 'Sev'), w: 60, fmt: v => String(v).toUpperCase() },
    { key: 'generated_at', label: t('analytics.colWhen', undefined, 'When'), w: 100, fmt: v => String(v).slice(0, 19)?.replace('T',' ') },
    { key: 'summary', label: t('analytics.colSummary', undefined, 'Summary'), w: 200, fmt: v => String(v).slice(0, 60) },
  ];

  const hubCols: Col<{name:string;url:string;caps:number;trust:number;healthy:boolean}>[] = [
    { key: 'name', label: t('analytics.colHub', undefined, 'Hub'), w: 140 },
    { key: 'caps', label: t('analytics.colCapabilities', undefined, 'Capabilities'), w: 80 },
    { key: 'trust', label: t('analytics.colTrustScore', undefined, 'Trust Score'), w: 80, fmt: v => Number(v) + '%' },
    { key: 'healthy', label: t('analytics.colHealth', undefined, 'Health'), w: 60, fmt: v => v ? '🟢' : '🔴' },
  ];

  const sevGroups: Record<string,string> = {
    critical: `🔴 ${t('analytics.severityCritical', undefined, 'Critical')}`,
    high: `🟠 ${t('analytics.severityHigh', undefined, 'High')}`,
    medium: `🟡 ${t('analytics.severityMedium', undefined, 'Medium')}`,
    low: `🔵 ${t('analytics.severityLow', undefined, 'Low')}`,
    info: `⚪ ${t('analytics.severityInfo', undefined, 'Info')}`,
  };

  return (
    <div className="card">
      <h2>📊 {t('analytics.title', undefined, 'Federation Analytics')}</h2>

      {/* KPI row */}
      <div className="kpi-row">
        <div className="kpi ok"><div className="val">{snapshot?.total_capabilities ?? '—'}</div><div className="lbl">{t('analytics.capabilities', undefined, 'Capabilities')}</div></div>
        <div className="kpi ok"><div className="val">{snapshot?.healthy_hubs == null || snapshot?.total_hubs == null ? '—' : `${snapshot.healthy_hubs}/${snapshot.total_hubs}`}</div><div className="lbl">{t('analytics.healthyHubs', undefined, 'Healthy Hubs')}</div></div>
        <div className={`kpi ${anomaliesAvailable && anomalies.filter(a => !a.acknowledged).length>0?'critical':'ok'}`}><div className="val">{anomaliesAvailable ? anomalies.filter(a => !a.acknowledged).length : '—'}</div><div className="lbl">{t('analytics.activeAnomalies', undefined, 'Active Anomalies')}</div></div>
        <div className="kpi ok"><div className="val">{insightsAvailable ? insights.length : '—'}</div><div className="lbl">{t('analytics.recentInsights', undefined, 'Recent Insights')}</div></div>
      </div>

      {/* Charts row 1 */}
      <div className="chart-grid">
        <div className="chart-card"><LineChart data={trendData} label={t('analytics.capsTrend', undefined, 'Capabilities trend (24h)')} t={t} /></div>
        <div className="chart-card">{anomaliesAvailable ? <DonutChart segments={sevItems} label={t('analytics.anomaliesBySeverity', undefined, 'Anomalies by severity')} t={t} /> : <div className="empty-chart">{t('anomalies.unavailable', undefined, 'Anomaly telemetry is unavailable.')}</div>}</div>
      </div>

      {/* Charts row 2 */}
      <div className="chart-grid">
        <div className="chart-card">{snapshot?.peers_available === false || !snapshot ? <div className="empty-chart">{t('app.dataUnavailable', undefined, 'Federation telemetry is unavailable. No zeroes were inferred.')}</div> : <BarChart items={hubItems} label={t('analytics.perHubCaps', undefined, 'Per-hub capabilities')} valueKey="caps" />}</div>
        <div className="chart-card">{anomaliesAvailable ? <HeatmapCalendar anomalies={anomalies} days={90} t={t} /> : <div className="empty-chart">{t('anomalies.unavailable', undefined, 'Anomaly telemetry is unavailable.')}</div>}</div>
      </div>

      {/* Table: Anomaly Log — grouped by severity */}
      <div className="chart-card" style={{ marginTop: 16 }}>
        <div className="chart-label">{t('analytics.anomalyLog', undefined, 'Anomaly Log — grouped by severity')}</div>
        {anomaliesAvailable ? <Table rows={anomalies} columns={anomalyCols} groupBy={{ key: 'severity', label: v => sevGroups[v] || v }} defaultSort="z_score" /> : <div className="empty-chart">{t('anomalies.unavailable', undefined, 'Anomaly telemetry is unavailable.')}</div>}
      </div>

      {/* Table: Insights — grouped by kind */}
      <div className="chart-card" style={{ marginTop: 16 }}>
        <div className="chart-label">{t('analytics.insightsByKind', undefined, 'Insights — grouped by kind')}</div>
        {insightsAvailable ? <Table rows={insights} columns={insightCols} groupBy={{ key: 'kind', label: v => v.charAt(0).toUpperCase() + v.slice(1) }} defaultSort="generated_at" /> : <div className="empty-chart">{t('app.dataUnavailable', undefined, 'Federation telemetry is unavailable. No zeroes were inferred.')}</div>}
      </div>

      {/* Table: Hubs — simple sortable */}
      <div className="chart-card" style={{ marginTop: 16 }}>
        <div className="chart-label">{t('analytics.hubs', undefined, 'Federation Hubs')}</div>
        {snapshot?.peers_available === false || !snapshot ? <div className="empty-chart">{t('app.dataUnavailable', undefined, 'Federation telemetry is unavailable. No zeroes were inferred.')}</div> : <Table rows={hubItems} columns={hubCols} defaultSort="caps" />}
      </div>
    </div>
  );
}
