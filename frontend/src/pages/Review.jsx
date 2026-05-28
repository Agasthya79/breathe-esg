import { useState, useEffect, useCallback } from 'react';
import { getActivities, getClients, approveActivity, rejectActivity, unlockActivity, getHistory } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { Card, Btn, Spinner, Modal, ReviewBadge, ScopeBadge, SourceBadge, LoadingPage, Empty } from '../components/UI';
import { CheckCircle2, XCircle, Unlock, ChevronDown, ChevronRight, History, Filter, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';

const PAGE_SIZE = 50;

export default function Review() {
  const { user } = useAuth();
  const toast = useToast();

  const [clients, setClients] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  // Filters
  const [filters, setFilters] = useState({ client: '', review_status: 'pending', source_type: '', scope: '' });

  // Modal states
  const [rejectModal, setRejectModal] = useState(null);
  const [unlockModal, setUnlockModal] = useState(null);
  const [historyModal, setHistoryModal] = useState(null);
  const [historyLogs, setHistoryLogs] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [modalNote, setModalNote] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  // Expanded rows
  const [expanded, setExpanded] = useState(new Set());

  useEffect(() => {
    getClients().then(r => setClients(r.data.results || r.data));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) };
      const { data } = await getActivities(params);
      setActivities(data.results || data);
      setTotal(data.count ?? (data.results || data).length);
    } catch {
      toast('Failed to load activities', 'error');
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const handleFilter = (k, v) => { setFilters(f => ({ ...f, [k]: v })); setPage(1); };

  const doApprove = async (id) => {
    setActionLoading(id + '-approve');
    try {
      await approveActivity(id);
      toast('Activity approved', 'success');
      load();
    } catch (e) {
      toast(e.response?.data?.error || 'Failed to approve', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const doReject = async () => {
    if (!rejectModal) return;
    setActionLoading(rejectModal + '-reject');
    try {
      await rejectActivity(rejectModal, modalNote);
      toast('Activity rejected', 'success');
      setRejectModal(null); setModalNote('');
      load();
    } catch (e) {
      toast(e.response?.data?.error || 'Failed to reject', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const doUnlock = async () => {
    if (!unlockModal || !modalNote.trim()) {
      toast('A note is required to unlock', 'warn');
      return;
    }
    setActionLoading(unlockModal + '-unlock');
    try {
      await unlockActivity(unlockModal, modalNote);
      toast('Row unlocked and reset to pending', 'success');
      setUnlockModal(null); setModalNote('');
      load();
    } catch (e) {
      toast(e.response?.data?.error || 'Failed to unlock', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const openHistory = async (id) => {
    setHistoryModal(id);
    setHistoryLoading(true);
    try {
      const { data } = await getHistory(id);
      setHistoryLogs(data);
    } catch { toast('Failed to load history', 'error'); }
    finally { setHistoryLoading(false); }
  };

  const toggleExpand = (id) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div style={{ padding: '2rem' }} className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>Review Queue</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            {loading ? '…' : total} {filters.review_status || 'total'} activit{total === 1 ? 'y' : 'ies'}
          </p>
        </div>
        <Btn variant="ghost" size="sm" icon={RefreshCw} onClick={load}>Refresh</Btn>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <Filter size={14} color="var(--text-dim)" />
        <select style={{ width: 'auto', minWidth: 160 }} value={filters.client} onChange={e => handleFilter('client', e.target.value)}>
          <option value="">All clients</option>
          {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select style={{ width: 'auto', minWidth: 140 }} value={filters.review_status} onChange={e => handleFilter('review_status', e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <select style={{ width: 'auto', minWidth: 120 }} value={filters.source_type} onChange={e => handleFilter('source_type', e.target.value)}>
          <option value="">All sources</option>
          <option value="SAP">SAP</option>
          <option value="UTILITY">Utility</option>
          <option value="TRAVEL">Travel</option>
        </select>
        <select style={{ width: 'auto', minWidth: 110 }} value={filters.scope} onChange={e => handleFilter('scope', e.target.value)}>
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>
      </div>

      {/* Table */}
      <Card style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}><Spinner /></div>
        ) : activities.length === 0 ? (
          <Empty icon={CheckCircle2} title="Queue is empty" sub="No activities match the current filters" />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['', 'Date', 'Source', 'Scope', 'Category', 'Facility', 'Quantity', 'CO₂e (t)', 'Status', 'Actions'].map((h, i) => (
                    <th key={i} style={{ padding: '0.75rem 1rem', textAlign: 'left', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activities.map(act => (
                  <>
                    <tr
                      key={act.id}
                      style={{ borderBottom: '1px solid var(--border)', background: expanded.has(act.id) ? 'var(--surface2)' : 'transparent', cursor: 'pointer' }}
                      onClick={() => toggleExpand(act.id)}
                    >
                      <td style={{ padding: '0.7rem 0.5rem 0.7rem 1rem', width: 24 }}>
                        {expanded.has(act.id) ? <ChevronDown size={14} color="var(--text-dim)" /> : <ChevronRight size={14} color="var(--text-dim)" />}
                      </td>
                      <td style={{ padding: '0.7rem 1rem', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        {act.activity_date}
                      </td>
                      <td style={{ padding: '0.7rem 1rem' }}><SourceBadge source={act.source_type} /></td>
                      <td style={{ padding: '0.7rem 1rem' }}><ScopeBadge scope={act.scope} /></td>
                      <td style={{ padding: '0.7rem 1rem', color: 'var(--text)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {act.category?.replace(/_/g, ' ')}
                      </td>
                      <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                        {act.facility_code || '—'}
                      </td>
                      <td style={{ padding: '0.7rem 1rem', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}>
                        {parseFloat(act.quantity_value).toLocaleString()} {act.quantity_unit}
                      </td>
                      <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: act.quantity_co2e ? 'var(--text)' : 'var(--text-dim)' }}>
                        {act.quantity_co2e ? parseFloat(act.quantity_co2e).toFixed(3) : '—'}
                      </td>
                      <td style={{ padding: '0.7rem 1rem' }}>
                        <ReviewBadge status={act.review_status} />
                        {act.is_locked && <span style={{ marginLeft: 4, fontSize: '0.7rem', color: 'var(--text-dim)' }}>🔒</span>}
                        {act.parse_status === 'warn' && <span style={{ marginLeft: 4, fontSize: '0.7rem', color: 'var(--amber)' }}>⚠</span>}
                      </td>
                      <td style={{ padding: '0.7rem 1rem' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                          {act.review_status === 'pending' && !act.is_locked && (
                            <>
                              <Btn
                                variant="success" size="sm"
                                loading={actionLoading === act.id + '-approve'}
                                onClick={() => doApprove(act.id)}
                                title="Approve"
                              >
                                <CheckCircle2 size={13} />
                              </Btn>
                              <Btn
                                variant="danger" size="sm"
                                onClick={() => { setRejectModal(act.id); setModalNote(''); }}
                                title="Reject"
                              >
                                <XCircle size={13} />
                              </Btn>
                            </>
                          )}
                          {act.is_locked && user?.role === 'admin' && (
                            <Btn
                              variant="amber" size="sm"
                              onClick={() => { setUnlockModal(act.id); setModalNote(''); }}
                              title="Unlock (admin)"
                            >
                              <Unlock size={13} />
                            </Btn>
                          )}
                          <Btn variant="ghost" size="sm" onClick={() => openHistory(act.id)} title="View history">
                            <History size={13} />
                          </Btn>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded row */}
                    {expanded.has(act.id) && (
                      <tr key={act.id + '-expanded'} style={{ background: 'var(--surface2)', borderBottom: '1px solid var(--border)' }}>
                        <td colSpan={10} style={{ padding: '0.75rem 1rem 1rem 3rem' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem 2rem' }}>
                            {act.description && <Detail label="Description" value={act.description} />}
                            {act.reviewed_by_email && <Detail label="Reviewed by" value={act.reviewed_by_email} />}
                            {act.reviewed_at && <Detail label="Reviewed at" value={format(new Date(act.reviewed_at), 'dd MMM yyyy HH:mm')} />}
                            {act.emission_factor_value && <Detail label="Emission factor" value={`${act.emission_factor_value} kgCO₂e/unit`} />}
                            {act.parse_errors?.length > 0 && (
                              <div>
                                <div style={detailLabelStyle}>Parse warnings</div>
                                {act.parse_errors.map((e, i) => (
                                  <div key={i} style={{ fontSize: '0.78rem', color: 'var(--amber)', fontFamily: 'var(--font-mono)' }}>⚠ {e}</div>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.25rem', alignItems: 'center' }}>
          <Btn variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</Btn>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {page} / {totalPages}
          </span>
          <Btn variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</Btn>
        </div>
      )}

      {/* Reject Modal */}
      <Modal open={!!rejectModal} onClose={() => setRejectModal(null)} title="Reject Activity">
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Optionally add a note explaining why this row is being rejected.
        </p>
        <textarea
          rows={3}
          placeholder="Rejection reason (optional)…"
          value={modalNote}
          onChange={e => setModalNote(e.target.value)}
          style={{ resize: 'vertical', marginBottom: '1.25rem' }}
        />
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <Btn variant="ghost" onClick={() => setRejectModal(null)}>Cancel</Btn>
          <Btn variant="danger" loading={actionLoading?.includes('-reject')} onClick={doReject}>Reject</Btn>
        </div>
      </Modal>

      {/* Unlock Modal */}
      <Modal open={!!unlockModal} onClose={() => setUnlockModal(null)} title="Unlock Row (Admin)">
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Unlocking resets this row to <strong>pending</strong> and records the action in the audit trail.
          A note is <strong>required</strong>.
        </p>
        <textarea
          rows={3}
          placeholder="Reason for unlock (required)…"
          value={modalNote}
          onChange={e => setModalNote(e.target.value)}
          style={{ resize: 'vertical', marginBottom: '1.25rem' }}
        />
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <Btn variant="ghost" onClick={() => setUnlockModal(null)}>Cancel</Btn>
          <Btn variant="amber" loading={actionLoading?.includes('-unlock')} onClick={doUnlock}>Unlock</Btn>
        </div>
      </Modal>

      {/* History Modal */}
      <Modal open={!!historyModal} onClose={() => { setHistoryModal(null); setHistoryLogs([]); }} title="Audit History" width={580}>
        {historyLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><Spinner /></div>
        ) : historyLogs.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>No audit history yet</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {historyLogs.map(log => (
              <div key={log.id} style={{ padding: '0.875rem', background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: actionColor(log.action) }}>{log.action.toUpperCase()}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {format(new Date(log.created_at), 'dd MMM yyyy HH:mm')}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>by {log.actor_email}</div>
                {log.note && <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--text)', fontStyle: 'italic' }}>"{log.note}"</div>}
                {log.diff?.before && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {JSON.stringify(log.diff.before)} → {JSON.stringify(log.diff.after)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}

const detailLabelStyle = { fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.2rem' };

function Detail({ label, value }) {
  return (
    <div>
      <div style={detailLabelStyle}>{label}</div>
      <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  );
}

function actionColor(action) {
  const map = { approve: 'var(--green)', reject: 'var(--red)', unlock: 'var(--amber)', edit: 'var(--blue)', create: 'var(--accent)' };
  return map[action] || 'var(--text-muted)';
}
