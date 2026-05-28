import { useState, useRef, useEffect } from 'react';
import { uploadFile, getClients } from '../api/client';
import { useToast } from '../hooks/useToast';
import { Card, Btn, Spinner, Badge } from '../components/UI';
import { UploadCloud, FileText, CheckCircle2, XCircle, AlertTriangle, Download } from 'lucide-react';

const SOURCE_TYPES = [
  { value: 'SAP', label: 'SAP — Fuel & Procurement', scope: 'Scope 1/2', hint: 'Flat file CSV with MBLNR, WERKS, MATNR, MEINS, MENGE, BUDAT columns' },
  { value: 'UTILITY', label: 'Utility — Electricity', scope: 'Scope 2', hint: 'Green Button CSV with TYPE, START DATE, END DATE, USAGE, UNITS, COST columns' },
  { value: 'TRAVEL', label: 'Travel — Concur', scope: 'Scope 3', hint: 'Concur CSV with trip_id, segment_type, origin, destination, travel_class, distance_km, nights columns' },
];

// Sample CSV content for each source type
const SAMPLES = {
  SAP: `MBLNR,WERKS,MATNR,MEINS,MENGE,BUDAT,KOSTL,LIFNR
5000012345,1001,DIESEL-B7,L,2450.00,20240115,CC-MFG-01,V-SHELL-001
5000012346,1002,NATGAS-MED,M3,8920.50,20240116,CC-UTIL-02,V-GASNET-007
5000012347,1001,PETROL-95,L,1200.00,20240117,CC-FLEET-03,V-BP-003`,
  UTILITY: `# Green Button Data
# Account: ACME Corp | Meter: 1234567890
TYPE,START DATE,END DATE,USAGE,UNITS,COST,NOTES
Electric usage,2024-01-01 00:00,2024-01-31 23:59,48250,kWh,5790.00,
Electric usage,2024-02-01 00:00,2024-02-29 23:59,44100,kWh,5292.00,
Electric usage,2024-03-01 00:00,2024-03-31 23:59,51800,kWh,6216.00,`,
  TRAVEL: `trip_id,employee_id,segment_type,travel_date,origin,destination,travel_class,distance_km,nights,vendor
TRP-2024-001,EMP-042,air,2024-01-10,LHR,JFK,economy,,0,British Airways
TRP-2024-002,EMP-107,air,2024-01-15,BOM,SIN,business,,0,Singapore Air
TRP-2024-003,EMP-042,hotel,2024-01-11,,,,,3,Marriott NYC
TRP-2024-004,EMP-203,ground,2024-01-20,,,,,0,Uber`,
};

export default function Upload() {
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [sourceType, setSourceType] = useState('SAP');
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef();
  const toast = useToast();

  useEffect(() => {
    getClients().then(r => {
      const list = r.data.results || r.data;
      setClients(list);
      if (list.length) setClientId(list[0].id);
    });
  }, []);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const onFileChange = (e) => {
    if (e.target.files[0]) setFile(e.target.files[0]);
  };

  const submit = async () => {
    if (!file || !clientId) {
      toast('Please select a client and file', 'warn');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('client_id', clientId);
      fd.append('source_type', sourceType);
      const { data } = await uploadFile(fd);
      setResult({ ok: true, data });
      toast(`Ingested ${data.total_rows} rows — ${data.ok_rows} OK, ${data.warn_rows} warnings, ${data.error_rows} errors`, 'success');
      setFile(null);
    } catch (err) {
      const msg = err.response?.data?.error || 'Upload failed';
      const isDup = err.response?.data?.duplicate;
      setResult({ ok: false, msg });
      toast(isDup ? 'Duplicate file — already ingested' : msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const downloadSample = () => {
    const content = SAMPLES[sourceType];
    const blob = new Blob([content], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sample_${sourceType.toLowerCase()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const selected = SOURCE_TYPES.find(s => s.value === sourceType);

  return (
    <div style={{ padding: '2rem', maxWidth: 720, margin: '0 auto' }} className="animate-in">
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>Upload Data</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Ingest SAP, Utility, or Travel CSV files for emissions accounting</p>
      </div>

      <Card style={{ padding: '1.75rem', marginBottom: '1rem' }}>
        {/* Client + source selectors */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
          <div>
            <label style={labelStyle}>Client</label>
            <select value={clientId} onChange={e => setClientId(e.target.value)}>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Source Type</label>
            <select value={sourceType} onChange={e => { setSourceType(e.target.value); setResult(null); }}>
              {SOURCE_TYPES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        </div>

        {/* Source hint */}
        <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '0.75rem 1rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text)' }}>{selected?.label}</span>
              <Badge label={selected?.scope} color={sourceType === 'SAP' ? 'amber' : sourceType === 'UTILITY' ? 'blue' : 'scope3'} />
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{selected?.hint}</p>
          </div>
          <Btn variant="ghost" size="sm" icon={Download} onClick={downloadSample}>Sample CSV</Btn>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? 'var(--accent)' : file ? 'var(--accent-dim)' : 'var(--border2)'}`,
            borderRadius: 'var(--radius-lg)',
            padding: '2.5rem 1.5rem',
            textAlign: 'center',
            cursor: 'pointer',
            background: dragging ? 'var(--accent-subtle)' : file ? 'rgba(0,212,170,0.04)' : 'var(--surface2)',
            transition: 'all 0.2s ease',
          }}
        >
          <input ref={fileRef} type="file" accept=".csv,.txt" onChange={onFileChange} style={{ display: 'none' }} />
          {file ? (
            <>
              <FileText size={32} color="var(--accent)" style={{ margin: '0 auto 0.75rem' }} />
              <div style={{ fontWeight: 600, color: 'var(--text)' }}>{file.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                {(file.size / 1024).toFixed(1)} KB — click to replace
              </div>
            </>
          ) : (
            <>
              <UploadCloud size={32} color="var(--text-dim)" style={{ margin: '0 auto 0.75rem' }} />
              <div style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Drop CSV file here or click to browse</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '0.25rem' }}>Accepts .csv files</div>
            </>
          )}
        </div>

        <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
          <Btn variant="primary" size="lg" loading={loading} onClick={submit} style={{ minWidth: 160, justifyContent: 'center' }}>
            {loading ? 'Ingesting…' : 'Ingest File'}
          </Btn>
        </div>
      </Card>

      {/* Result */}
      {result && (
        <Card style={{ padding: '1.25rem 1.5rem', borderColor: result.ok ? 'var(--accent)' : 'var(--red)', background: result.ok ? 'rgba(0,212,170,0.04)' : 'rgba(239,68,68,0.04)' }} className="animate-in">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {result.ok
              ? <CheckCircle2 size={20} color="var(--accent)" />
              : <XCircle size={20} color="var(--red)" />}
            <div>
              {result.ok ? (
                <>
                  <div style={{ fontWeight: 700, color: 'var(--text)' }}>Ingestion complete</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem', display: 'flex', gap: '1rem' }}>
                    <span style={{ color: 'var(--green)' }}>✓ {result.data.ok_rows} ok</span>
                    {result.data.warn_rows > 0 && <span style={{ color: 'var(--amber)' }}>⚠ {result.data.warn_rows} warn</span>}
                    {result.data.error_rows > 0 && <span style={{ color: 'var(--red)' }}>✗ {result.data.error_rows} errors</span>}
                    <span style={{ color: 'var(--text-dim)' }}>{result.data.total_rows} total rows</span>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontWeight: 700, color: 'var(--red)' }}>Ingestion failed</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>{result.msg}</div>
                </>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

const labelStyle = {
  display: 'block', fontSize: '0.78rem', fontWeight: 600,
  color: 'var(--text-muted)', marginBottom: '0.4rem',
  textTransform: 'uppercase', letterSpacing: '0.05em',
};
