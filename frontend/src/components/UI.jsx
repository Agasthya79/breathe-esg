import { Loader2 } from 'lucide-react';

// ── Button ─────────────────────────────────────────────────────────────────
export function Btn({ children, variant = 'primary', size = 'md', loading, icon: Icon, ...props }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
    fontWeight: 500, borderRadius: 'var(--radius)', cursor: 'pointer',
    transition: 'all 0.15s ease', border: 'none', fontFamily: 'var(--font-body)',
  };
  const sizes = {
    sm: { padding: '0.3rem 0.7rem', fontSize: '0.8rem' },
    md: { padding: '0.5rem 1rem', fontSize: '0.875rem' },
    lg: { padding: '0.65rem 1.25rem', fontSize: '0.95rem' },
  };
  const variants = {
    primary: { background: 'var(--accent)', color: '#000', fontWeight: 600 },
    ghost: { background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' },
    danger: { background: 'var(--red-dim)', color: 'var(--red)', border: '1px solid rgba(239,68,68,0.3)' },
    success: { background: 'var(--green-dim)', color: 'var(--green)', border: '1px solid rgba(34,197,94,0.3)' },
    amber: { background: 'var(--amber-dim)', color: 'var(--amber)', border: '1px solid rgba(245,158,11,0.3)' },
  };
  return (
    <button style={{ ...base, ...sizes[size], ...variants[variant] }} {...props}>
      {loading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : Icon ? <Icon size={14} /> : null}
      {children}
    </button>
  );
}

// ── Badge ──────────────────────────────────────────────────────────────────
export function Badge({ label, color = 'default' }) {
  const colors = {
    default: { bg: 'var(--surface3)', text: 'var(--text-muted)' },
    green: { bg: 'var(--green-dim)', text: 'var(--green)' },
    red: { bg: 'var(--red-dim)', text: 'var(--red)' },
    amber: { bg: 'var(--amber-dim)', text: 'var(--amber)' },
    blue: { bg: 'var(--blue-dim)', text: 'var(--blue)' },
    accent: { bg: 'var(--accent-subtle)', text: 'var(--accent)' },
    scope1: { bg: 'rgba(249,115,22,0.12)', text: 'var(--scope1)' },
    scope2: { bg: 'rgba(59,158,255,0.12)', text: 'var(--scope2)' },
    scope3: { bg: 'rgba(168,85,247,0.12)', text: 'var(--scope3)' },
  };
  const c = colors[color] || colors.default;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '0.2rem 0.55rem', borderRadius: '999px',
      fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.02em',
      background: c.bg, color: c.text, whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}

// ── Card ───────────────────────────────────────────────────────────────────
export function Card({ children, style, ...props }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      ...style,
    }} {...props}>
      {children}
    </div>
  );
}

// ── Stat Card ──────────────────────────────────────────────────────────────
export function StatCard({ label, value, sub, accentColor }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '1.25rem 1.5rem',
      borderTop: `3px solid ${accentColor || 'var(--accent)'}`,
    }}>
      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>{label}</div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, fontFamily: 'var(--font-display)', color: 'var(--text)' }}>{value}</div>
      {sub && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{sub}</div>}
    </div>
  );
}

// ── Spinner ────────────────────────────────────────────────────────────────
export function Spinner({ size = 24 }) {
  return <Loader2 size={size} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)' }} />;
}

// ── Loading Page ───────────────────────────────────────────────────────────
export function LoadingPage() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: '0.75rem', color: 'var(--text-muted)' }}>
      <Spinner size={20} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>loading…</span>
    </div>
  );
}

// ── Empty State ────────────────────────────────────────────────────────────
export function Empty({ icon: Icon, title, sub }) {
  return (
    <div style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-dim)' }}>
      {Icon && <Icon size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />}
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>{title}</div>
      {sub && <div style={{ fontSize: '0.85rem' }}>{sub}</div>}
    </div>
  );
}

// ── Modal ──────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, width = 520 }) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 500, backdropFilter: 'blur(4px)',
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border2)',
        borderRadius: 'var(--radius-lg)',
        width: `min(${width}px, calc(100vw - 2rem))`,
        maxHeight: 'calc(100vh - 4rem)',
        overflow: 'auto',
        animation: 'fadeIn 0.2s ease',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>{title}</h3>
          <button onClick={onClose} style={{ background: 'none', color: 'var(--text-dim)', padding: '0.25rem', borderRadius: '4px', lineHeight: 1, display: 'flex' }}>✕</button>
        </div>
        <div style={{ padding: '1.5rem' }}>{children}</div>
      </div>
    </div>
  );
}

// ── Status helpers ─────────────────────────────────────────────────────────
export function ReviewBadge({ status }) {
  const map = {
    pending: { color: 'amber', label: 'Pending' },
    approved: { color: 'green', label: 'Approved' },
    rejected: { color: 'red', label: 'Rejected' },
    warn: { color: 'amber', label: 'Warning' },
  };
  const { color, label } = map[status] || { color: 'default', label: status };
  return <Badge label={label} color={color} />;
}

export function ScopeBadge({ scope }) {
  const colors = { 1: 'scope1', 2: 'scope2', 3: 'scope3' };
  return <Badge label={`Scope ${scope}`} color={colors[scope] || 'default'} />;
}

export function SourceBadge({ source }) {
  const colors = { SAP: 'amber', UTILITY: 'blue', TRAVEL: 'scope3' };
  return <Badge label={source} color={colors[source] || 'default'} />;
}
