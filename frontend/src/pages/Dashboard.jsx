import { useState, useEffect } from 'react';
import { getSummary, getClients } from '../api/client';
import { StatCard, Card, LoadingPage, Badge } from '../components/UI';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

const fmt = (n) => {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n?.toFixed(1) ?? '0';
};

const SCOPE_COLORS = ['var(--scope1)', 'var(--scope2)', 'var(--scope3)'];
const SOURCE_COLORS = { SAP: 'var(--amber)', UTILITY: 'var(--blue)', TRAVEL: 'var(--scope3)' };

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 8, padding: '0.625rem 0.875rem', fontSize: '0.8rem' }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontFamily: 'var(--font-mono)' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontWeight: 600 }}>{p.name}: {fmt(p.value)} tCO₂e</div>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getClients().then(r => {
      setClients(r.data.results || r.data);
      if ((r.data.results || r.data).length > 0) {
        setClientId((r.data.results || r.data)[0].id);
      }
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = clientId ? { client: clientId } : {};
    getSummary(params).then(r => {
      setSummary(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [clientId]);

  if (loading && !summary) return <LoadingPage />;

  const totalCO2e = ((summary?.scope1_co2e || 0) + (summary?.scope2_co2e || 0) + (summary?.scope3_co2e || 0));

  const scopeData = [
    { name: 'Scope 1', value: summary?.scope1_co2e || 0 },
    { name: 'Scope 2', value: summary?.scope2_co2e || 0 },
    { name: 'Scope 3', value: summary?.scope3_co2e || 0 },
  ];

  const sourceData = [
    { name: 'SAP', tCO2e: summary?.by_source?.SAP || 0 },
    { name: 'Utility', tCO2e: summary?.by_source?.UTILITY || 0 },
    { name: 'Travel', tCO2e: summary?.by_source?.TRAVEL || 0 },
  ];

  const reviewData = [
    { name: 'Pending', value: summary?.pending || 0, color: 'var(--amber)' },
    { name: 'Approved', value: summary?.approved || 0, color: 'var(--green)' },
    { name: 'Rejected', value: summary?.rejected || 0, color: 'var(--red)' },
  ];

  return (
    <div style={{ padding: '2rem', maxWidth: 1200, margin: '0 auto' }} className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>Emissions Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Aggregated view across all Scope 1, 2, and 3 sources</p>
        </div>
        <select
          value={clientId}
          onChange={e => setClientId(e.target.value)}
          style={{ width: 'auto', minWidth: 200 }}
        >
          <option value="">All clients</option>
          {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
        <StatCard label="Total tCO₂e" value={fmt(totalCO2e)} sub="All scopes" accentColor="var(--accent)" />
        <StatCard label="Scope 1" value={fmt(summary?.scope1_co2e)} sub="Direct combustion" accentColor="var(--scope1)" />
        <StatCard label="Scope 2" value={fmt(summary?.scope2_co2e)} sub="Purchased electricity" accentColor="var(--scope2)" />
        <StatCard label="Scope 3" value={fmt(summary?.scope3_co2e)} sub="Value chain travel" accentColor="var(--scope3)" />
        <StatCard label="Pending Review" value={summary?.pending ?? 0} sub={`${summary?.total ?? 0} total rows`} accentColor="var(--amber)" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.75rem' }}>
        {/* Scope breakdown pie */}
        <Card style={{ padding: '1.5rem' }}>
          <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: '1.25rem', fontSize: '0.95rem' }}>Scope Breakdown (tCO₂e)</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={scopeData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value">
                {scopeData.map((_, i) => <Cell key={i} fill={SCOPE_COLORS[i]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend formatter={(v) => <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* Source bar */}
        <Card style={{ padding: '1.5rem' }}>
          <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: '1.25rem', fontSize: '0.95rem' }}>Emissions by Source (tCO₂e)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sourceData} barSize={32}>
              <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="tCO2e" radius={[4, 4, 0, 0]}>
                {sourceData.map((d, i) => <Cell key={i} fill={SOURCE_COLORS[d.name] || 'var(--accent)'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Review status */}
      <Card style={{ padding: '1.5rem' }}>
        <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: '1.25rem', fontSize: '0.95rem' }}>Review Status</div>
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
          {reviewData.map(({ name, value, color }) => (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-display)', color }}>{value}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{name}</div>
              </div>
            </div>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Review completion:</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 600 }}>
              {summary?.total ? Math.round(((summary.approved + summary.rejected) / summary.total) * 100) : 0}%
            </span>
          </div>
        </div>
        {/* Progress bar */}
        <div style={{ height: 6, background: 'var(--surface3)', borderRadius: 999, marginTop: '1rem', overflow: 'hidden' }}>
          {summary?.total > 0 && (
            <div style={{
              height: '100%',
              width: `${Math.round(((summary.approved + summary.rejected) / summary.total) * 100)}%`,
              background: 'linear-gradient(90deg, var(--accent), var(--accent-dim))',
              borderRadius: 999, transition: 'width 0.5s ease',
            }} />
          )}
        </div>
      </Card>
    </div>
  );
}
