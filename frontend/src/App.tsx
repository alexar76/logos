import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, startTransition } from 'react';
import { useI18n } from './i18n/context';
import { api, type Insight, type Anomaly, type DailyReport, type Snapshot } from './api';
import { FederationChart, Sparkline, DonutGauge } from './components/FederationChart';
const DataConstellation = lazy(() => import('./components/DataConstellation'));
const AnalyticsPanel = lazy(() => import('./components/AnalyticsPanel'));

function AnimatedNumber({ value, suffix = '', locale = 'en' }: { value: number; suffix?: string; locale?: string }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0; const duration = 600; const step = Math.max(1, Math.round(value / (duration / 16)));
    const iv = setInterval(() => { start += step; if (start >= value) { setDisplay(value); clearInterval(iv); } else setDisplay(start); }, 16);
    return () => clearInterval(iv);
  }, [value]);
  return <>{display.toLocaleString(locale === 'zh' ? 'zh-CN' : locale)}{suffix}</>;
}

interface CapInfo { capability_id: string; description: string; price_per_call_usd: number; provider_hub: string; }

function HintTip({ text }: { text: string }) {
  return (
    <span className="hint-tip" tabIndex={0} aria-label={text}>
      <span className="hint-tip-mark" aria-hidden>?</span>
      <span className="hint-tip-bubble" role="tooltip">{text}</span>
    </span>
  );
}

/** Searchable capability picker — avoids native <select> freezes on large catalogs. */
function NexusCapPicker({
  caps,
  value,
  onSelect,
  disabled,
  busy,
  catalogLoading,
  t,
}: {
  caps: CapInfo[];
  value: string;
  onSelect: (id: string) => void;
  disabled?: boolean;
  busy?: boolean;
  catalogLoading?: boolean;
  t: (k: string, v?: Record<string, string | number>, d?: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selecting, setSelecting] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = caps.find((item) => item.capability_id === value) || null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return caps;
    return caps.filter((c) =>
      c.capability_id.toLowerCase().includes(q)
      || (c.description || '').toLowerCase().includes(q)
      || (c.provider_hub || '').toLowerCase().includes(q),
    );
  }, [caps, query]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const priceLabel = (c: CapInfo) => (
    c.price_per_call_usd > 0
      ? `$${Number(c.price_per_call_usd).toFixed(5).replace(/0+$/, '').replace(/\.$/, '')}`
      : t('nexus.free', undefined, 'free')
  );

  const pick = (id: string) => {
    setSelecting(true);
    setOpen(false);
    setQuery('');
    requestAnimationFrame(() => {
      startTransition(() => onSelect(id));
      window.setTimeout(() => setSelecting(false), 140);
    });
  };

  const showSpinner = Boolean(busy || selecting || catalogLoading);

  return (
    <div className={`nexus-cap-picker ${open ? 'is-open' : ''} ${showSpinner ? 'is-busy' : ''}`} ref={rootRef}>
      <button
        type="button"
        className={`nexus-cap-trigger ${selected ? 'has-value' : ''}`}
        disabled={disabled || catalogLoading}
        aria-expanded={open}
        aria-haspopup="listbox"
        title={t('nexus.pickHint', undefined, 'Open the catalog and choose one capability')}
        onClick={() => { if (!disabled && !catalogLoading) setOpen((v) => !v); }}
      >
        <span className="nexus-cap-trigger-copy">
          <small>{t('nexus.capabilityLabel', undefined, 'Capability')}</small>
          <strong className="nexus-cap-label">
            {showSpinner
              ? t('nexus.preparing', undefined, 'Preparing…')
              : (selected ? selected.capability_id : t('nexus.selectCapability', undefined, '— Select a capability —'))}
          </strong>
          {selected && !showSpinner && (
            <em>
              {priceLabel(selected)}
              {selected.provider_hub ? ` · ${selected.provider_hub.replace(/^https?:\/\//, '')}` : ''}
            </em>
          )}
        </span>
        {showSpinner ? <i className="nexus-cap-spinner" aria-hidden /> : <span className="nexus-cap-chevron" aria-hidden>▾</span>}
      </button>
      {open && (
        <div className="nexus-cap-menu" role="listbox">
          <div className="nexus-cap-menu-head">
            <span>{t('nexus.catalogTitle', undefined, 'Federation catalog')}</span>
            <small>{t('nexus.catalogCount', { n: caps.length }, `${caps.length} capabilities`)}</small>
          </div>
          <input
            ref={inputRef}
            className="nexus-cap-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('nexus.searchCapability', undefined, 'Search by name, description, or hub…')}
            aria-label={t('nexus.searchCapability', undefined, 'Search by name, description, or hub…')}
          />
          <div className="nexus-cap-list">
            {filtered.length === 0 ? (
              <div className="nexus-cap-empty">{t('nexus.noMatch', undefined, 'No matching capabilities')}</div>
            ) : filtered.map((c) => (
              <button
                type="button"
                key={c.capability_id}
                role="option"
                aria-selected={c.capability_id === value}
                className={`nexus-cap-option ${c.capability_id === value ? 'is-selected' : ''}`}
                title={c.description || c.capability_id}
                onClick={() => pick(c.capability_id)}
              >
                <span className="nexus-cap-option-main">
                  <strong>{c.capability_id}</strong>
                  {c.description ? <small>{c.description}</small> : null}
                  {c.provider_hub ? <em>{c.provider_hub.replace(/^https?:\/\//, '')}</em> : null}
                </span>
                <span className="nexus-cap-price">{priceLabel(c)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

type View = 'query' | 'report' | 'chat' | 'nexus' | 'consumption' | 'analytics';

interface ConsData {
  status: 'ok' | 'partial' | 'unreachable'; stats_available: boolean; catalog_available: boolean;
  invocations_24h: number | null; settled_volume_usd: number | null; volume_24h_usd: number | null; active_channels: number | null;
  total_capabilities: number | null; paid_capabilities: number | null; free_capabilities: number | null;
  max_price_per_call: number | null; estimated_daily_spend_usd: number | null;
  estimated_monthly_spend_usd: number | null; spend_basis?: string;
  by_hub: Array<{url:string;capabilities:number;paid_capabilities:number;max_price:number}>;
  source: string; source_key?: string; note: string;
}

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem('logos-theme');
      if (stored === 'light' || stored === 'dark') return stored;
    }
    return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useLayoutEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('logos-theme', theme);
  }, [theme]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileNavOpen(false);
    };
    const desktop = window.matchMedia('(min-width: 761px)');
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileNavOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    desktop.addEventListener('change', closeOnDesktop);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      desktop.removeEventListener('change', closeOnDesktop);
    };
  }, []);
  const [view, setView] = useState<View>('query');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [insightsAvailable, setInsightsAvailable] = useState(false);
  const [anomaliesAvailable, setAnomaliesAvailable] = useState(false);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState('');

  const loadSnapshot = useCallback(async () => {
    try {
      const s = await api.snapshot();
      setSnapshot(s);
    } catch { setSnapshot(null); }
  }, []);

  // Real trend data from snapshot history
  // Sources LOGOS actually polled, with their measured latency — the snapshot
  // carries `status` and `_elapsed_ms` per source, which is what the 3D scene draws.
  const observedSources = (() => {
    const snap = snapshot as any;
    if (!snap) return [] as Array<{name:string;status:string;elapsedMs:number | null;magnitude:number}>;
    const out: Array<{name:string;status:string;elapsedMs:number | null;magnitude:number}> = [];
    if (snap.status) {
      out.push({ name: 'hub', status: String(snap.status),
        elapsedMs: snap.status === 'ok' && snap._elapsed_ms != null ? Number(snap._elapsed_ms) : null,
        magnitude: Number(snap.total_capabilities || 0) });
    }
    const f = snap.findings;
    if (f && f.status) {
      out.push({ name: 'momus', status: String(f.status),
        elapsedMs: f.status === 'ok' && f._elapsed_ms != null ? Number(f._elapsed_ms) : null,
        magnitude: Number(f.total_findings || 0) });
    }
    const tr = snap.treasury;
    if (tr && tr.status) {
      out.push({ name: 'treasury', status: String(tr.status),
        elapsedMs: tr.status === 'ok' && tr._elapsed_ms != null ? Number(tr._elapsed_ms) : null,
        magnitude: Number(tr.available_usd || 0) });
    }
    return out;
  })();

  const [trendPoints, setTrendPoints] = useState<Array<{ts:string;v:number}>>([]);
  const loadTrend = useCallback(async () => {
    try {
      const r = await fetch('/api/v1/trend?metric=total_capabilities&limit=24');
      if (!r.ok) { setTrendPoints([]); return; }
      const data = await r.json();
      setTrendPoints(data.points || []);
    } catch { setTrendPoints([]); }
  }, []);

  const loadAnomalies = useCallback(async () => {
    try {
      // 'all' — the alert strip filters to open ones, the heatmap needs history
      const a = await api.anomalies('all');
      const hasCritical = a.anomalies.some((an: Anomaly) => an.severity === 'critical' && !an.acknowledged);
      setAnomalies(a.anomalies);
      setAnomaliesAvailable(true);
      if (hasCritical) playAlertSound();
    } catch { setAnomalies([]); setAnomaliesAvailable(false); }
  }, []);

  const loadReport = useCallback(async () => {
    try {
      const r = await api.dailyReport();
      setReport(r);
    } catch { setReport(null); }
  }, []);

  const loadInsights = useCallback(async () => {
    try {
      const r = await api.insights();
      setInsights(r.insights);
      setInsightsAvailable(true);
    } catch { setInsights([]); setInsightsAvailable(false); }
  }, []);

  useEffect(() => {
    loadSnapshot();
    loadAnomalies();
    loadTrend();
    loadInsights();
    const iv = setInterval(() => {
      loadSnapshot();
      loadAnomalies();
      loadTrend();
    }, 300_000); // 5 min
    return () => clearInterval(iv);
  }, [loadSnapshot, loadAnomalies, loadReport, loadTrend, loadInsights]);

  const handleAsk = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    try {
      const resp = await api.ask(q);
      setInsights(resp.insights);
      setInsightsAvailable(true);
      if (resp.insights.length === 0) {
        setError(t('query.noInsights', undefined, 'No insights returned — try a different query.'));
      }
    } catch {
      setError(t('query.requestFailed', undefined, 'Request failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleAsk();
  };

  // Chat state
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Voice input
  const [voiceActive, setVoiceActive] = useState(false);
  const toggleVoice = () => {
    if (voiceActive) { setVoiceActive(false); return; }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const rec = new SpeechRecognition();
    rec.lang = locale === 'zh' ? 'zh-CN' : locale === 'ru' ? 'ru-RU' : locale === 'es' ? 'es-ES' : locale === 'fr' ? 'fr-FR' : 'en-US';
    rec.interimResults = false;
    rec.onresult = (e: any) => { setChatInput(e.results[0][0].transcript); setVoiceActive(false); };
    rec.onerror = () => setVoiceActive(false);
    rec.onend = () => setVoiceActive(false);
    setVoiceActive(true);
    rec.start();
  };

  const handleChat = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatMessages(prev => [...prev, { role: 'user', content: msg }]);
    setChatInput('');
    setChatLoading(true);
    try {
      const r = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${r.status}`);
      }
      if (!r.body) throw new Error('Streaming is not supported by this browser');
      setChatMessages(prev => [...prev, { role: 'assistant', content: '' }]);
      const reader = r.body.getReader(), decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const event of events) {
          const data = event.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
          if (!data || data === '[DONE]') continue;
          setChatMessages(prev => {
            const next = [...prev], last = next[next.length - 1];
            if (last?.role === 'assistant') next[next.length - 1] = { ...last, content: last.content + data };
            return next;
          });
        }
        if (done) break;
      }
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: t('chat.offline', undefined, 'Unable to reach the LOGOS assistant. Is the backend running?') }]);
    } finally {
      setChatLoading(false);
    }
  };

  // NEXUS state
  const [caps, setCaps] = useState<CapInfo[]>([]);
  const [nexusCap, setNexusCap] = useState('');
  const [nexusInput, setNexusInput] = useState('{}');
  const [nexusResult, setNexusResult] = useState<any>(null);
  const [nexusLoading, setNexusLoading] = useState(false);
  const [nexusError, setNexusError] = useState('');
  const [catalogState, setCatalogState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');

  const loadCaps = async () => {
    setCatalogState('loading');
    try {
      const r = await fetch('/api/v1/federation/capabilities');
      if (!r.ok) throw new Error(String(r.status));
      const data = await r.json();
      setCaps(data.capabilities || []);
      setCatalogState('ready');
    } catch {
      setCaps([]);
      setCatalogState('error');
    }
  };

  useEffect(() => { if (view === 'nexus') loadCaps(); }, [view]);

  const handleNexusInvoke = async () => {
    if (!nexusCap) return;
    let input: unknown;
    try { input = JSON.parse(nexusInput); } catch { setNexusError(t('nexus.invalidJson', undefined, 'Invalid JSON input')); return; }
    setNexusLoading(true); setNexusError(''); setNexusResult(null);
    try {
      const r = await fetch('/api/v1/federation/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability_id: nexusCap, input }),
      });
      const data = await r.json();
      setNexusResult(data);
      if (data.status === 'error') setNexusError(data.error || t('nexus.invokeFailed', undefined, 'Invoke failed'));
    } catch { setNexusError(t('nexus.networkError', undefined, 'Network error')); }
    finally { setNexusLoading(false); }
  };

  // Consumption state
  const [consData, setConsData] = useState<ConsData | null>(null);
  const [consState, setConsState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  // Keyboard shortcut: / focuses query
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement === document.body) {
        e.preventDefault(); setView('query');
        setTimeout(() => document.querySelector<HTMLInputElement>('.query-bar input')?.focus(), 50);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const loadConsumption = async () => {
    setConsState('loading');
    try {
      const r = await fetch('/api/v1/consumption');
      if (!r.ok) throw new Error(String(r.status));
      setConsData(await r.json());
      setConsState('ready');
    } catch {
      setConsData(null);
      setConsState('error');
    }
  };
  useEffect(() => { if (view === 'consumption') loadConsumption(); }, [view]);

  const chatEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  // Sound alert on critical anomalies
  const playAlertSound = () => {
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
    } catch { /* audio not supported */ }
  };

  const handleAcknowledge = async (id: string) => {
    try {
      await api.acknowledgeAnomaly(id);
      setAnomalies((prev) => prev.filter((a) => a.anomaly_id !== id));
    } catch { /* silent */ }
  };

  const suggestions = [
    t('query.suggestions.general', undefined, 'Give me a federation overview'),
    t('query.suggestions.economy', undefined, 'How long will the Treasury last?'),
    t('query.suggestions.security', undefined, 'Are there any critical findings?'),
    t('query.suggestions.latency', undefined, 'Which hubs are slow right now?'),
    t('query.suggestions.reputation', undefined, 'Who is the most trusted hub?'),
  ];

  return (
    <>
      <header className="header">
        <div className="brand">
          <h1>{t('app.title', undefined, 'LOGOS')}</h1>
          <span className="sub">{t('app.subtitle', undefined, 'Federation Analytics Engine')}</span>
        </div>
        <button
          type="button"
          className="mobile-menu-toggle"
          aria-expanded={mobileNavOpen}
          aria-controls="primary-navigation"
          aria-label={mobileNavOpen ? t('nav.menuClose', undefined, 'Close menu') : t('nav.menuOpen', undefined, 'Open menu')}
          onClick={() => setMobileNavOpen(open => !open)}
        >
          <span aria-hidden="true" className="mobile-menu-icon"><i /><i /><i /></span>
        </button>
        <nav id="primary-navigation" className={`nav-actions${mobileNavOpen ? ' mobile-open' : ''}`} aria-label={t('nav.primary', undefined, 'Primary navigation')}>
          <span className="system-state" title={snapshot?.status === 'ok' ? t('nav.telemetryConnected', undefined, 'Federation telemetry connected') : snapshot?.status === 'partial' ? t('nav.telemetryPartial', undefined, 'Federation telemetry is partial') : t('nav.telemetryWaiting', undefined, 'Waiting for federation telemetry')}>
            <i className={snapshot?.status === 'ok' ? 'online' : ''} />{snapshot?.status === 'ok' ? t('nav.live', undefined, 'LIVE') : snapshot?.status === 'partial' ? t('nav.partial', undefined, 'PARTIAL') : t('nav.connecting', undefined, 'CONNECTING')}
          </span>
          <button
            className={view === 'query' ? 'pill' : 'pill'}
            style={view === 'query' ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
            onClick={() => { setView('query'); setMobileNavOpen(false); }}
          >
            {t('insight.title', undefined, 'Insights')}
          </button>
          <button
            className="pill"
            style={view === 'report' ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
            onClick={() => { setView('report'); setMobileNavOpen(false); loadReport(); }}
          >
            {t('report.title', undefined, 'Daily Briefing')}
          </button>
          <button
            className="pill"
            style={view === 'chat' ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
            onClick={() => { setView('chat'); setMobileNavOpen(false); }}
          >
            🤖 {t('nav.ai', undefined, 'AI')}
          </button>
          <button
            className="pill"
            style={view === 'nexus' ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'rgba(0,229,255,0.1)' } : {}}
            onClick={() => { setView('nexus'); setMobileNavOpen(false); }}
          >
            🧿 {t('nav.nexus', undefined, 'NEXUS')}
          </button>
          <button
            className="pill"
            style={view === 'consumption' ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'rgba(0,229,255,0.1)' } : {}}
            onClick={() => { setView('consumption'); setMobileNavOpen(false); }}
          >
            💰 {t('nav.consumption', undefined, 'Consumption')}
          </button>
          <button
            className="pill"
            style={view === 'analytics' ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'rgba(0,229,255,0.1)' } : {}}
            onClick={() => { setView('analytics'); setMobileNavOpen(false); }}
          >
            📊 {t('nav.analytics', undefined, 'Analytics')}
          </button>
          <button
            onClick={() => { setTheme(t => t === 'dark' ? 'light' : 'dark'); setMobileNavOpen(false); }}
            className="pill"
            title={theme === 'dark' ? t('nav.themeLight', undefined, 'Light mode') : t('nav.themeDark', undefined, 'Dark mode')}
            aria-label={theme === 'dark' ? t('nav.themeLight', undefined, 'Light mode') : t('nav.themeDark', undefined, 'Dark mode')}
          >
            {theme === 'dark' ? '☀' : '☾'}{' '}
            <span className="pill-label">
              {theme === 'dark' ? t('nav.themeLight', undefined, 'Light mode') : t('nav.themeDark', undefined, 'Dark mode')}
            </span>
          </button>
          <div className="lang-sw">
            {(['en','ru','es','fr','zh'] as const).map((l) => (
              <button key={l} className={locale === l ? 'on' : ''} onClick={() => { setLocale(l); setMobileNavOpen(false); }} aria-label={`${t('nav.language', undefined, 'Language')}: ${l === 'zh' ? '中文' : l.toUpperCase()}`}>
                {l === 'zh' ? '中文' : l.toUpperCase()}
              </button>
            ))}
          </div>
        </nav>
      </header>

      <main className="main">
        {view === 'query' ? (
          <>
            {/* Query bar */}
            <div className="query-bar">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('query.placeholder', undefined, 'Ask about the federation…')}
                disabled={loading}
              />
              <button onClick={handleAsk} disabled={loading || !query.trim()}>
                {loading ? '…' : t('query.submit', undefined, 'Analyze')}
              </button>
            </div>

            {/* Suggestions */}
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} className="pill" onClick={() => { setQuery(s); }}>
                  {s}
                </button>
              ))}
            </div>

            {/* Loading */}
            {loading && (
              <div className="loading">
                <div className="spinner" />
                {t('query.executing', undefined, 'Gathering data…')}
              </div>
            )}

            {/* Error */}
            {error && <div className="empty" style={{ color: 'var(--bad)' }}>{error}</div>}

            {/* Insights */}
            {insights.length > 0 && (
              <section>
                <h2 style={{ fontSize: 12, color: 'var(--ink-dim)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 12 }}>
                  {t('insight.title', undefined, 'Insights')}
                  {loading && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--accent)' }}>{t('common.updating', undefined, 'updating…')}</span>}
                </h2>
                {insights.map((ins) => (
                  <InsightCard key={ins.insight_id} insight={ins} t={t} />
                ))}
              </section>
            )}

            {!loading && insights.length === 0 && !error && (
              <div className="empty">{t('insight.empty', undefined, 'No insights yet. Ask a question above.')}</div>
            )}

            {/* KPI snapshot strip */}
            {snapshot?.status === 'ok' && <SnapshotKPI snapshot={snapshot} t={t} />}
            {snapshot && snapshot.status !== 'ok' && (
              <div className="empty">{snapshot.status === 'partial' ? t('app.partialData', undefined, 'Some federation sources are unavailable; withheld values remain blank.') : t('app.dataUnavailable', undefined, 'Federation telemetry is unavailable. No zeroes were inferred.')}</div>
            )}

            {/* 3D Data Constellation */}
            {snapshot && (
              <div className="card constellation-card" style={{ marginBottom: 16 }}>
                <Suspense fallback={<div className="skeleton" style={{ height: 340, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink-dim)', fontSize: 12 }}>{t('common.loading3d', undefined, 'Loading 3D constellation…')}</div>}>
                  <DataConstellation
                    peers={snapshot.peers || []}
                    anomaly_count={anomaliesAvailable ? anomalies.filter(a => !a.acknowledged).length : undefined}
                    theme={theme}
                    sources={observedSources}
                    capabilityCount={snapshot.total_capabilities ?? undefined}
                    t={t}
                  />
                </Suspense>
              </div>
            )}

            {/* Federation charts */}
            {snapshot && snapshot.peers && snapshot.peers.length > 0 && snapshot.healthy_hubs != null && snapshot.total_hubs != null && snapshot.total_capabilities != null && snapshot.federated_capabilities != null && (
              <div className="card" style={{ marginBottom: 16 }}>
                <h2>{t('federation.title', undefined, 'Federation')}</h2>
                <FederationChart peers={snapshot.peers} theme={theme} t={t} />
                <div style={{ display: 'flex', gap: 16, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <DonutGauge pct={snapshot.healthy_hubs / Math.max(snapshot.total_hubs, 1)} label={t('analytics.healthy', undefined, 'healthy')} size={70} theme={theme} />
                  <div style={{ fontSize: 11, color: 'var(--ink-dim)' }}>
                    {t('federation.hubHealth', { healthy: snapshot.healthy_hubs, total: snapshot.total_hubs }, `${snapshot.healthy_hubs}/${snapshot.total_hubs} healthy`)} · {' '}
                    {t('federation.capabilities', { n: snapshot.total_capabilities }, `${snapshot.total_capabilities} capabilities`)} · {' '}
                    {t('report.kpi.federated', { n: snapshot.federated_capabilities }, `${snapshot.federated_capabilities} federated`)}
                  </div>
                </div>
              </div>
            )}

            {/* Anomalies */}
            {anomalies.filter(a => !a.acknowledged).length > 0 && (
              <section style={{ marginTop: 24 }}>
                <h2 style={{ fontSize: 12, color: 'var(--warn)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>
                  {t('anomalies.title', undefined, 'Anomalies')} ({anomalies.filter(a => !a.acknowledged).length})
                </h2>
                {anomalies.filter(a => !a.acknowledged).slice(0, 5).map((a) => (
                  <div key={a.anomaly_id} className="anom">
                    <span className="z" style={{ color: a.severity === 'critical' ? 'var(--bad)' : 'var(--warn)' }}>
                      {a.z_score.toFixed(1)}σ
                    </span>
                    <span style={{ flex: 1 }}>{a.description}</span>
                    <button onClick={() => handleAcknowledge(a.anomaly_id)}>
                      {t('anomalies.acknowledge', undefined, 'Acknowledge')}
                    </button>
                  </div>
                ))}
              </section>
            )}
          </>
        ) : view === 'chat' ? (
          /* AI chat view */
          <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '60vh', minHeight: 400 }}>
            <h2>🤖 {t('chat.title', undefined, 'LOGOS Assistant')}</h2>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {chatMessages.length === 0 && (
                <div className="empty" style={{ padding: 20 }}>
                  {t('chat.intro', undefined, 'Ask the LOGOS assistant anything about the federation. It has read-only access to all analytics data.')}
                </div>
              )}
              {chatMessages.map((m, i) => (
                <div key={i} style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  padding: '10px 14px',
                  borderRadius: 12,
                  fontSize: 13,
                  lineHeight: 1.5,
                  background: m.role === 'user' ? 'rgba(0,229,255,0.12)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${m.role === 'user' ? 'rgba(0,229,255,0.25)' : 'rgba(255,255,255,0.06)'}`,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  {m.content}
                </div>
              ))}
              {chatLoading && <div className="loading"><div className="spinner" /></div>}
              <div ref={chatEndRef} />
            </div>
            <div className="query-bar" style={{ marginBottom: 0, marginTop: 8 }}>
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleChat()}
                placeholder={t('query.placeholder', undefined, 'Ask about the federation…')}
                disabled={chatLoading}
              />
              <button onClick={toggleVoice} title={t('chat.voice', undefined, 'Voice input')} style={{ width: 34, height: 34, flex: 'none', borderRadius: '50%', border: '1px solid var(--border)', background: voiceActive ? 'rgba(255,47,176,0.15)' : 'transparent', color: voiceActive ? 'var(--mag)' : 'var(--ink-dim)', cursor: 'pointer', fontSize: 14, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {voiceActive ? '⏹' : '🎤'}
              </button>
              <button onClick={handleChat} disabled={chatLoading || !chatInput.trim()}>
                {t('query.submit', undefined, 'Send')}
              </button>
            </div>
          </div>
        ) : view === 'consumption' ? (
          /* Consumption — measured settlement activity + catalog pricing */
          <div>
            <div className="card" style={{ marginBottom: 16 }}>
              <h2>💰 {t('consumption.header', undefined, 'Federation Consumption')}</h2>
              <p style={{ fontSize: 11, color: 'var(--ink-dim)', marginBottom: 14 }}>
                {t('consumption.intro', undefined, 'Measured settlement activity and catalog pricing from Hub manifest + stats.')}
              </p>
              {consState === 'loading' || consState === 'idle' ? (
                <div className="loading"><div className="spinner" /></div>
              ) : consState === 'error' || !consData ? (
                <div className="empty">{t('consumption.unreachable', undefined, 'Consumption telemetry is unreachable. No values were inferred.')}</div>
              ) : (
                <>
                  {/* Big numbers */}
                  <div className="kpi-row">
                    <div className="kpi ok">
                      <div className="val">{consData.settled_volume_usd == null ? '—' : <>$<AnimatedNumber value={consData.settled_volume_usd} locale={locale} /></>}</div>
                      <div className="lbl">{t('consumption.settledVolume', undefined, 'Settled volume')}</div>
                    </div>
                    <div className="kpi ok">
                      <div className="val">{consData.invocations_24h == null ? '—' : <AnimatedNumber value={consData.invocations_24h} locale={locale} />}</div>
                      <div className="lbl">{t('consumption.invocations24h', undefined, 'Invocations (24h)')}</div>
                    </div>
                    <div className="kpi ok">
                      <div className="val">{consData.estimated_monthly_spend_usd == null ? '—' : <>$<AnimatedNumber value={consData.estimated_monthly_spend_usd} locale={locale} /></>}</div>
                      <div className="lbl">{t('consumption.projection30d', undefined, '30-day projection')}</div>
                    </div>
                    <div className="kpi ok">
                      <div className="val">{consData.active_channels ?? '—'}</div>
                      <div className="lbl">{t('consumption.activeChannels', undefined, 'Active channels')}</div>
                    </div>
                  </div>

                  {/* Capability breakdown */}
                  <div className="grid2" style={{ marginTop: 16 }}>
                    <div className="card">
                      <h2>{t('consumption.capabilities', undefined, 'Capabilities')}</h2>
                      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                        <span className="pill" style={{ background: 'rgba(0,229,255,0.1)', borderColor: 'var(--accent)' }}>
                          {consData.total_capabilities == null ? '—' : t('consumption.total', { n: consData.total_capabilities }, `${consData.total_capabilities} total`)}
                        </span>
                        <span className="pill" style={{ background: 'rgba(74,222,128,0.1)', borderColor: 'var(--good)' }}>
                          {consData.paid_capabilities == null ? '—' : t('consumption.paid', { n: consData.paid_capabilities }, `${consData.paid_capabilities} paid`)}
                        </span>
                        <span className="pill" style={{ background: 'rgba(142,166,192,0.1)', borderColor: 'rgba(142,166,192,0.3)' }}>
                          {consData.free_capabilities == null ? '—' : t('consumption.free', { n: consData.free_capabilities }, `${consData.free_capabilities} free`)}
                        </span>
                      </div>
                      <div style={{ fontSize: 13 }}>
                        <div>{t('consumption.maxPrice', undefined, 'Max price per call')}: <strong>{consData.max_price_per_call == null ? '—' : `$${consData.max_price_per_call.toFixed(4)}`}</strong></div>
                        <div style={{ marginTop: 4 }}>{t('consumption.measured24h', undefined, 'Measured 24h volume')}: <strong>{consData.volume_24h_usd == null ? t('consumption.unavailable', undefined, 'unavailable') : `$${consData.volume_24h_usd.toFixed(2)}`}</strong></div>
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--ink-dim)', marginTop: 8, fontStyle: 'italic' }}>
                        {consData.spend_basis === 'measured_24h_settlement_volume' ? t('consumption.noteMeasured', undefined, '30-day projection from measured 24h settlement volume.') : t('consumption.noteUnavailable', undefined, 'Spend unavailable: the hub did not publish measured settlement volume.')}
                      </div>
                    </div>

                    {/* Per-hub breakdown */}
                    <div className="card">
                      <h2>{t('consumption.perHub', undefined, 'Per Hub')}</h2>
                      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                        <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                          <thead>
                            <tr style={{ color: 'var(--ink-dim)', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '4px 8px' }}>{t('consumption.colHub', undefined, 'Hub')}</th>
                              <th style={{ padding: '4px 8px', textAlign: 'right' }}>{t('consumption.colCaps', undefined, 'Caps')}</th>
                              <th style={{ padding: '4px 8px', textAlign: 'right' }}>{t('consumption.colPaid', undefined, 'Paid')}</th>
                              <th style={{ padding: '4px 8px', textAlign: 'right' }}>{t('consumption.colMax', undefined, 'Max $')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {consData.by_hub.map(h => (
                              <tr key={h.url} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                <td style={{ padding: '6px 8px', color: 'var(--ink)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={h.url}>
                                  {h.url.replace(/^https?:\/\//, '').split('/')[0]}
                                </td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'ui-monospace,monospace' }}>{h.capabilities}</td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'ui-monospace,monospace' }}>{h.paid_capabilities}</td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'ui-monospace,monospace', color: 'var(--good)' }}>${h.max_price.toFixed(4)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  {/* Spend projection bar */}
                  <div className="card" style={{ marginTop: 16 }}>
                    <h2>{t('consumption.spendProjection', undefined, 'Spend Projection')}</h2>
                    <div style={{ display: 'flex', gap: 24, alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'ui-monospace,monospace', color: 'var(--good)' }}>
                          {consData.estimated_daily_spend_usd == null ? '—' : `$${consData.estimated_daily_spend_usd.toFixed(2)}`}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--ink-dim)' }}>{t('consumption.measured24h', undefined, 'measured / 24h')}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'ui-monospace,monospace' }}>
                          {consData.estimated_monthly_spend_usd == null ? '—' : `$${consData.estimated_monthly_spend_usd.toFixed(2)}`}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--ink-dim)' }}>{t('consumption.projection30d', undefined, '30-day projection')}</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 9, color: 'var(--ink-dim)', marginTop: 8 }}>
                      {t('consumption.source', undefined, 'Source')}: {t('consumption.sourceHubManifestStats', undefined, 'Hub manifest + stats')}
                    </div>
                    <button onClick={() => {
                      const csv = `${t('consumption.colHub')},${t('consumption.capabilities')},${t('consumption.colPaid')},${t('consumption.colMax')}\n` + consData.by_hub.map(h => `"${h.url}",${h.capabilities},${h.paid_capabilities},${h.max_price}`).join('\n');
                      const b = new Blob([csv], { type: 'text/csv' });
                      const u = URL.createObjectURL(b);
                      const a = document.createElement('a'); a.href = u; a.download = 'logos-consumption.csv'; a.click();
                      URL.revokeObjectURL(u);
                    }} style={{ marginTop: 8, fontSize: 10, background: 'none', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--ink-dim)', cursor: 'pointer', padding: '4px 10px' }}>
                      📥 {t('consumption.exportCsv', undefined, 'Export CSV')}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : view === 'nexus' ? (
          /* NEXUS — federation playground */
          <div className="nexus-shell">
            <div className="card nexus-card">
              <div className="nexus-hero">
                <div>
                  <p className="nexus-kicker">{t('nexus.kicker', undefined, 'FEDERATION PLAYGROUND')}</p>
                  <h2>🧿 {t('nexus.title', undefined, 'NEXUS')}</h2>
                  <p className="nexus-intro">
                    {t('nexus.intro', undefined, 'Pick a live federation capability, edit the JSON input, then invoke it through the hub. The route stays visible — nothing is invented.')}
                  </p>
                </div>
                <div className="nexus-steps" aria-label={t('nexus.stepsLabel', undefined, 'How to use NEXUS')}>
                  <div><b>1</b><span>{t('nexus.step1', undefined, 'Choose')}</span></div>
                  <div><b>2</b><span>{t('nexus.step2', undefined, 'Edit input')}</span></div>
                  <div><b>3</b><span>{t('nexus.step3', undefined, 'Invoke')}</span></div>
                </div>
              </div>

              <div className="nexus-field">
                <div className="nexus-field-label">
                  <span>{t('nexus.capabilityLabel', undefined, 'Capability')}</span>
                  <HintTip text={t('nexus.capabilityTip', undefined, 'Open the searchable catalog. Type a name like platon.random to filter hundreds of live federation tools.')} />
                </div>
                <div className="nexus-picker-row">
                  <NexusCapPicker
                    caps={caps}
                    value={nexusCap}
                    catalogLoading={catalogState === 'loading' || catalogState === 'idle'}
                    busy={nexusLoading}
                    disabled={nexusLoading}
                    t={t}
                    onSelect={(id) => {
                      setNexusCap(id);
                      setNexusResult(null);
                      setNexusError('');
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => void loadCaps()}
                    className="nexus-refresh"
                    disabled={catalogState === 'loading'}
                    title={t('nexus.refresh', undefined, 'Refresh capabilities from the hub')}
                  >
                    {catalogState === 'loading'
                      ? <i className="nexus-cap-spinner" aria-hidden />
                      : '↻'}
                    <span>{t('nexus.refreshShort', undefined, 'Refresh')}</span>
                  </button>
                </div>
                {(catalogState === 'loading' || catalogState === 'idle') && (
                  <div className="nexus-inline-busy" aria-live="polite">
                    <i className="nexus-cap-spinner" />
                    <span>{t('nexus.loadingCatalog', undefined, 'Loading federation catalog…')}</span>
                  </div>
                )}
                {caps.length === 0 && catalogState !== 'loading' && catalogState !== 'idle' && (
                  <div className="nexus-warn">
                    {t('nexus.noCapabilities', undefined, 'No capabilities found — is the hub reachable?')}
                  </div>
                )}
                {nexusCap && (
                  <div className="nexus-selected-card">
                    <div>
                      <small>{t('nexus.selected', undefined, 'Selected')}</small>
                      <strong>{nexusCap}</strong>
                      <p>{(caps.find((c) => c.capability_id === nexusCap)?.description) || t('nexus.noDescription', undefined, 'No description published for this capability.')}</p>
                    </div>
                    <HintTip text={t('nexus.selectedTip', undefined, 'Next: edit the JSON input if needed, then press Invoke. LOGOS only proxies read-only capabilities.')} />
                  </div>
                )}
              </div>

              <div className="nexus-field">
                <div className="nexus-field-label">
                  <span>{t('nexus.inputJson', undefined, 'Input (JSON)')}</span>
                  <HintTip text={t('nexus.inputTip', undefined, 'Must be valid JSON. Start with {} for capabilities that need no fields. Invalid JSON blocks invoke.')} />
                </div>
                <textarea
                  className="nexus-textarea"
                  value={nexusInput}
                  onChange={e => setNexusInput(e.target.value)}
                  rows={5}
                  spellCheck={false}
                  placeholder='{}'
                  aria-label={t('nexus.inputJson', undefined, 'Input (JSON)')}
                />
              </div>

              <button
                type="button"
                onClick={handleNexusInvoke}
                disabled={nexusLoading || !nexusCap}
                className="nexus-invoke"
                title={!nexusCap ? t('nexus.invokeNeedCap', undefined, 'Choose a capability first') : t('nexus.invokeTip', undefined, 'Send the request through the hub')}
              >
                {nexusLoading && <i className="nexus-cap-spinner is-on-accent" aria-hidden />}
                {nexusLoading ? t('nexus.invoking', undefined, 'Invoking…') : `▶ ${t('nexus.invoke', undefined, 'INVOKE')}`}
              </button>
              {!nexusCap && (
                <p className="nexus-coach">{t('nexus.coachPick', undefined, 'Start by choosing a capability above. Search works — try “platon” or “sortes”.')}</p>
              )}
              {nexusError && <div className="nexus-error" role="alert">{nexusError}</div>}
            </div>

            {nexusResult && (
              <div className="card nexus-result-card">
                <div className="nexus-field-label">
                  <h2>{t('nexus.result', undefined, 'Result')}</h2>
                  <HintTip text={t('nexus.resultTip', undefined, 'This payload came from the live hub route. Price and routed-via badges are measured, not decorative.')} />
                </div>
                <div className="nexus-result-meta">
                  {nexusResult.price_usd != null && (
                    <span className="pill" title={t('nexus.priceTip', undefined, 'Measured call price')}>${String(nexusResult.price_usd)}</span>
                  )}
                  {nexusResult.source && (
                    <span className="pill">{t('nexus.via', undefined, 'via')} {String(nexusResult.source)}</span>
                  )}
                  {nexusResult.routed_via && (
                    <span className="pill nexus-pill-accent">
                      {t('nexus.routedVia', undefined, 'routed via')} {String(nexusResult.routed_via)}
                    </span>
                  )}
                </div>
                <pre className="nexus-result-pre">
                  {JSON.stringify((nexusResult as Record<string,unknown>).result || nexusResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : view === 'analytics' ? (
          <Suspense fallback={<div className="loading"><div className="spinner" /></div>}>
            <AnalyticsPanel
              snapshot={snapshot}
              anomalies={anomalies}
              insights={insights}
              consData={consData}
              theme={theme}
              t={t}
              trendPoints={trendPoints}
              anomaliesAvailable={anomaliesAvailable}
              insightsAvailable={insightsAvailable}
            />
          </Suspense>
        ) : (
          /* Daily report view */
          <ReportView report={report} anomalies={anomalies} anomaliesAvailable={anomaliesAvailable} t={t} onAcknowledge={handleAcknowledge} />
        )}
      </main>

      <footer className="footer">
        LOGOS v0.1 · {t('app.tagline', undefined, 'One node. Every insight.')}
      </footer>
    </>
  );
}

/* ── InsightCard ── */
function InsightCard({ insight, t }: { insight: Insight; t: (k: string, v?: Record<string, string | number>, d?: string) => string }) {
  const [open, setOpen] = useState(false);
  const sev = insight.severity || 'info';
  return (
    <div className="insight">
      <div className="insight-head" onClick={() => setOpen(!open)}>
        <span className={`sev ${sev}`}>{t(`insight.severity.${sev}`, undefined, sev.toUpperCase())}</span>
        <span className="title">{insight.title}</span>
        <span className="meta">{insight.generated_by}</span>
      </div>
      {/* Always show the one-line summary — collapsed cards used to look like empty duplicates. */}
      {insight.summary && <div className="insight-summary">{insight.summary}</div>}
      {open && (
        <div className="insight-body">
          {insight.explanation ? <div className="explanation">{insight.explanation}</div> : null}
          {insight.recommendations && insight.recommendations.length > 0 && (
            <>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-dim)', marginBottom: 6, textTransform: 'uppercase' }}>
                {t('insight.recommendations', undefined, 'Recommendations')}
              </div>
              {insight.recommendations.map((r, i) => (
                <div key={i} className="rec">
                  <strong>{r.priority}. {r.action}</strong>
                  <div style={{ fontSize: 11, marginTop: 2 }}>{r.impact}</div>
                </div>
              ))}
            </>
          )}
          <div style={{ fontSize: 10, color: 'rgba(142,166,192,.5)', marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              {t('insight.generatedBy', { source: insight.generated_by }, `Generated by ${insight.generated_by}`)}
              {insight.sources && insight.sources.length > 0 && (
                <> · {t('insight.sources')}: {insight.sources.map(s => s.name).join(', ')}</>
              )}
            </span>
            <button onClick={async (e) => {
              const md = `## ${insight.title}\n\n**${insight.severity.toUpperCase()}** · ${insight.kind}\n\n${insight.summary}\n\n${insight.explanation || ''}`;
              try { await navigator.clipboard.writeText(md); (e.target as HTMLElement).textContent = '✓'; setTimeout(() => { (e.target as HTMLElement).textContent = '📋'; }, 1500); } catch {}
            }} title={t('chat.copyMarkdown', undefined, 'Copy as Markdown')} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--ink-dim)', cursor: 'pointer', fontSize: 12, padding: '2px 6px' }}>📋</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Snapshot KPI strip ── */
function SnapshotKPI({ snapshot, t }: { snapshot: Snapshot; t: (k: string, v?: Record<string, string | number>, d?: string) => string }) {
  const hubOk = snapshot.healthy_hubs != null && snapshot.total_hubs != null && snapshot.healthy_hubs === snapshot.total_hubs;
  const caps = snapshot.total_capabilities;
  const fed = snapshot.federated_capabilities;
  return (
    <div className="kpi-row">
      <div className={`kpi ${hubOk ? 'ok' : 'warn'}`}>
        <div className="val">{snapshot.healthy_hubs == null || snapshot.total_hubs == null ? '—' : `${snapshot.healthy_hubs}/${snapshot.total_hubs}`}</div>
        <div className="lbl">{t('report.kpi.hubsOnline', undefined, 'Hubs online')}</div>
      </div>
      <div className="kpi ok">
        <div className="val">{caps ?? '—'}</div>
        <div className="lbl">{t('report.kpi.capabilities', undefined, 'Capabilities')}{fed != null && fed > 0 ? ` (${t('report.kpi.federated', { n: fed }, `${fed} fed`)})` : ''}</div>
      </div>
    </div>
  );
}

/* ── Report view ── */
function ReportView({ report, anomalies, anomaliesAvailable, t, onAcknowledge }: {
  report: DailyReport | null;
  anomalies: Anomaly[];
  anomaliesAvailable: boolean;
  t: (k: string, v?: Record<string, string | number>, d?: string) => string;
  onAcknowledge: (id: string) => void;
}) {
  if (!report) return <div className="empty">{t('app.connecting', undefined, 'Connecting to LOGOS…')}</div>;
  const kpiLabelKey: Record<string, string> = {
    'Hubs online': 'report.kpi.hubsOnline',
    'Capabilities': 'report.kpi.capabilities',
    'Findings': 'report.kpi.findings',
    'Treasury': 'report.kpi.treasury',
  };

  return (
    <>
      <div className="grid2">
        <div className="card">
          <h2>{t('report.title', undefined, 'Daily Briefing')}</h2>
          <div style={{ fontSize: 13, marginBottom: 14, lineHeight: 1.5 }}>
            {report.kpis.length === 0
              ? t('app.dataUnavailable', undefined, 'Federation telemetry is unavailable. No zeroes were inferred.')
              : t(`report.overall.${report.overall_status}`, undefined, report.summary)}
          </div>
          <div className="kpi-row">
            {report.kpis.map((k) => (
              <div key={k.label} className={`kpi ${k.status}`}>
                <div className="val">{k.value}</div>
                <div className="lbl">{kpiLabelKey[k.label] ? t(kpiLabelKey[k.label], undefined, k.label) : k.label}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10, color: 'rgba(142,166,192,.4)' }}>
            {t('report.generated', { time: report.generated_at?.slice(11, 19) || '?' }, `Generated at ${report.generated_at}`)}
          </div>
        </div>

        <div className="card">
          <h2>{t('anomalies.title', undefined, 'Anomalies')}</h2>
          {!anomaliesAvailable ? (
            <div className="empty" style={{ padding: 20 }}>{t('anomalies.unavailable', undefined, 'Anomaly telemetry is unavailable.')}</div>
          ) : anomalies.filter(a => !a.acknowledged).length === 0 ? (
            <div className="empty" style={{ padding: 20 }}>{t('anomalies.empty', undefined, 'No active anomalies.')}</div>
          ) : (
            anomalies.filter(a => !a.acknowledged).slice(0, 5).map((a) => (
              <div key={a.anomaly_id} className="anom">
                <span className="z" style={{ color: a.severity === 'critical' ? 'var(--bad)' : 'var(--warn)' }}>
                  {a.z_score.toFixed(1)}σ
                </span>
                <span style={{ flex: 1, fontSize: 11 }}>{a.description}</span>
                <button onClick={() => onAcknowledge(a.anomaly_id)}>
                  {t('anomalies.acknowledge', undefined, 'Ack')}
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {report.insights && report.insights.length > 0 && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 12, color: 'var(--ink-dim)', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 12 }}>
            {t('insight.title', undefined, 'Insights')}
          </h2>
          {report.insights.slice(0, 5).map((ins) => (
            <InsightCard key={ins.insight_id} insight={ins} t={t} />
          ))}
        </section>
      )}
    </>
  );
}
