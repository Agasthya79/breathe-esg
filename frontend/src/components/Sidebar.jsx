import { NavLink } from 'react-router-dom';
import { LayoutDashboard, UploadCloud, ClipboardList, History, LogOut, Leaf } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: UploadCloud, label: 'Upload Data' },
  { to: '/review', icon: ClipboardList, label: 'Review Queue' },
  { to: '/batches', icon: History, label: 'Ingestion Log' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside style={{
      width: 220,
      minHeight: '100vh',
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '1.5rem 1.25rem 1rem', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-dim))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Leaf size={16} color="#000" strokeWidth={2.5} />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '0.95rem', color: 'var(--text)', lineHeight: 1.1 }}>Breathe</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--accent)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase' }}>ESG</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '0.75rem 0.75rem' }}>
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: '0.625rem',
              padding: '0.55rem 0.75rem', borderRadius: 'var(--radius)',
              textDecoration: 'none', fontSize: '0.875rem', fontWeight: 500,
              color: isActive ? 'var(--accent)' : 'var(--text-muted)',
              background: isActive ? 'var(--accent-subtle)' : 'transparent',
              transition: 'all 0.15s', marginBottom: '0.125rem',
            })}
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div style={{ padding: '1rem', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginBottom: '0.125rem', fontFamily: 'var(--font-mono)' }}>
          {user?.username}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: user?.role === 'admin' ? 'var(--amber)' : 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {user?.role}
          </span>
          <button
            onClick={logout}
            style={{ background: 'none', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', padding: '0.25rem' }}
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
