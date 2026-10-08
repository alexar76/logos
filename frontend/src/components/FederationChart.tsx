/** SVG-based federation health chart — hubs online, capabilities, trust distribution. */

interface HubPeer { url: string; name: string; capabilities_count: number; trust_score: number; healthy: boolean; }

export function FederationChart({ peers, theme, t }: { peers: HubPeer[]; theme: 'dark' | 'light';
  t?: (k: string, v?: any, d?: string) => string }) {
  const W = 440, H = 180, R = 10, pad = 30;
  const ink = theme === 'dark' ? '#8ea6c0' : '#5a6070';
  const accent = '#00e5ff';
  const good = '#4ade80';
  const bad = '#ff2d55';

  const sorted = [...peers].sort((a, b) => b.capabilities_count - a.capabilities_count).slice(0, 8);
  if (sorted.length === 0) return <div className="empty-chart">{t ? t('analytics.noPeersChart', undefined, 'No peers') : 'No peers'}</div>;

  const maxCaps = Math.max(1, ...sorted.map(p => p.capabilities_count));
  const barW = Math.max(12, (W - pad * 2) / sorted.length - 8);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
      {/* Bars */}
      {sorted.map((p, i) => {
        const bh = Math.max(4, (p.capabilities_count / maxCaps) * (H - pad * 2 - 20));
        const x = pad + i * ((W - pad * 2) / sorted.length) + ((W - pad * 2) / sorted.length - barW) / 2;
        const y = H - pad - bh;
        return (
          <g key={p.url}>
            <rect x={x} y={y} width={barW} height={bh} rx={4}
                  fill={p.healthy ? good : bad} opacity={p.healthy ? 0.8 : 0.6} />
            <text x={x + barW / 2} y={H - pad + 14} textAnchor="middle" fill={ink} fontSize={9}
                  fontFamily="ui-monospace,monospace">
              {p.name ? p.name.slice(0, 8) : p.url.slice(0, 8)}
            </text>
          </g>
        );
      })}
      {/* Axes */}
      <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke={ink} strokeOpacity={0.2} />
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke={ink} strokeOpacity={0.2} />
    </svg>
  );
}

/** Sparkline — tiny trend indicator. */
export function Sparkline({ data, width = 120, height = 30, theme = 'dark' }: {
  data: number[]; width?: number; height?: number; theme?: 'dark' | 'light';
}) {
  if (data.length < 2) return null;
  const accent = '#00e5ff';
  const ink = theme === 'dark' ? 'rgba(142,166,192,0.3)' : 'rgba(90,96,112,0.3)';
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (width - pad * 2));
  const ys = data.map(v => pad + ((max - v) / range) * (height - pad * 2));
  const points = xs.map((x, i) => `${x},${ys[i]}`).join(' ');
  const lastY = ys[ys.length - 1];
  const area = `${xs[0]},${height - pad} ${points} ${xs[xs.length - 1]},${height - pad}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width, height, display: 'inline-block', verticalAlign: 'middle' }}>
      <polygon points={area} fill={accent} opacity={0.08} />
      <polyline points={points} fill="none" stroke={accent} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xs[xs.length - 1]} cy={lastY} r={2.5} fill={accent} />
    </svg>
  );
}

/** Simple donut gauge — useful for treasury depletion or health ratio. */
export function DonutGauge({ pct, label, size = 80, theme = 'dark' }: {
  pct: number; label: string; size?: number; theme?: 'dark' | 'light';
}) {
  const r = size / 2 - 6;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.min(1, Math.max(0, pct)));
  const color = pct < 0.3 ? '#ff2d55' : pct < 0.6 ? '#ffcc33' : '#4ade80';
  const ink = theme === 'dark' ? '#eaf6ff' : '#1c1017';

  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: size, height: size }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(142,166,192,0.15)" strokeWidth={5} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={5}
              strokeDasharray={circ} strokeDashoffset={offset}
              strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x={size / 2} y={size / 2 + 1} textAnchor="middle" dominantBaseline="middle"
            fill={ink} fontSize={size * 0.2} fontWeight={700} fontFamily="ui-monospace,monospace">
        {Math.round(pct * 100)}%
      </text>
      <text x={size / 2} y={size / 2 + size * 0.18} textAnchor="middle" fill="#8ea6c0"
            fontSize={size * 0.12} fontFamily="ui-monospace,monospace">{label}</text>
    </svg>
  );
}

/** Timeline chart for anomaly history. */
export function TimelineChart({ points, width = 400, height = 100, theme = 'dark' }: {
  points: Array<{ ts: string; value: number }>; width?: number; height?: number; theme?: 'dark' | 'light';
}) {
  if (points.length < 2) return null;
  const accent = '#00e5ff';
  const ink = theme === 'dark' ? 'rgba(142,166,192,0.3)' : 'rgba(90,96,112,0.3)';
  const pad = 20;
  const vals = points.map(p => p.value);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (width - pad * 2));
  const ys = vals.map(v => pad + ((max - v) / range) * (height - pad * 2));
  const pts = xs.map((x, i) => `${x},${ys[i]}`).join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto' }}>
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke={ink} />
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke={ink} />
      <polyline points={pts} fill="none" stroke={accent} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      {points.slice(-1).map((p, i) => (
        <text key={i} x={width - pad} y={pad - 6} textAnchor="end" fill={ink} fontSize={9} fontFamily="ui-monospace,monospace">
          {p.value.toFixed(1)}
        </text>
      ))}
    </svg>
  );
}
