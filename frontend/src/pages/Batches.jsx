import { useState, useEffect } from 'react';
import { getBatches, getClients } from '../api/client';
import { Card, Btn, Badge, LoadingPage, Empty } from '../components/UI';
import { RefreshCw, Package, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';

const statusColor = { pending: 'amber', processing: 'blue', done: 'green', failed: 'red' };
const sourceColor = { SAP: 'amber', UTILITY: 'blue', TRAVEL: 'scope3' };

export default function Batches() {
  const [batches, setBatches] = useState([]);
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getClients().then(r => setClients(r.data.results || r.data));
  }, []);

  const load = () => {
    setLoading(true);
    const params = clientId ? { client: clientId } : {};
    getBatches(params)
      .then(r => setBatches(r.data.results || r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [clientId]);

  if (loading && batches.length === 0) return <LoadingPage />;

  return (
    <div style={{ padding: '2rem' }} className="animate-in">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>Ingestion Log</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>History of all file uploads and their parsing results</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <select style={{ width: 'auto', minWidth: 180 }} value={clientId} onChange={e => setClientId(e.target.value)}>
            <option value="">All clients</option>
            {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Btn variant="ghost" size="sm" icon={RefreshCw} onClick={load}>Refresh</Btn>
        </div>
      </div>

      {batches.length === 0 ? (
        <Empty icon={Package} title="No ingestion batches yet" sub="Upload a file to see it appear here" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {batches.map(b => (
            <Card key={b.id} style={{ padding: '1.25rem 1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
                {/* Icon */}
                <div style={{
                  width: 40, height: 40, borderRadius: 8, flexShrink: 0,
                  background: b.status === 'failed' ? 'var(--red-dim)' : 'var(--accent-subtle)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {b.status === 'failed'
                    ? <AlertCircle size={18} color="var(--red)" />
                    : <Package size={18} color="var(--accent)" />}
                </div>

                {/* Main info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap', marginBottom: '0.3rem' }}>
                    <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280 }}>
                      {b.file_name}
                    </span>
                    <Badge label={b.source_type} color={sourceColor[b.source_type] || 'default'} />
                    <Badge label={b.status} color={statusColor[b.status] || 'default'} />
                  </div>
                  <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    <span>Client: <strong style={{ color: 'var(--text)' }}>{b.client_name}</strong></span>
                    <span>By: <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{b.uploaded_by_email}</span></span>
                    <span>{format(new Date(b.ingested_at), 'dd MMM yyyy HH:mm')}</span>
                  </div>
                  {b.status === 'failed' && b.error_summary && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--red)', fontFamily: 'var(--font-mono)', background: 'var(--red-dim)', borderRadius: 6, padding: '0.4rem 0.6rem' }}>
                      {b.error_summary}
                    </div>
                  )}
                </div>

                {/* Row stats */}
                {b.status === 'done' && (
                  <div style={{ display: 'flex', gap: '1.25rem', flexShrink: 0, alignItems: 'center' }}>
                    <Stat label="Total" value={b.total_rows} color="var(--text)" />
                    <Stat label="OK" value={b.ok_rows} color="var(--green)" />
                    {b.warn_rows > 0 && <Stat label="Warn" value={b.warn_rows} color="var(--amber)" />}
                    {b.error_rows > 0 && <Stat label="Errors" value={b.error_rows} color="var(--red)" />}
                  </div>
                )}
              </div>

              {/* Hash footer */}
              <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)', fontSize: '0.72rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                SHA-256: {b.file_hash}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-display)', color }}>{value}</div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
    </div>
  );
}
