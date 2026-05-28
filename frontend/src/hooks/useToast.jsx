import { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertTriangle, X } from 'lucide-react';

const ToastCtx = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((msg, type = 'success') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  }, []);

  const remove = useCallback((id) => setToasts(t => t.filter(x => x.id !== id)), []);

  const icons = { success: CheckCircle, error: XCircle, warn: AlertTriangle };
  const colors = { success: 'var(--accent)', error: 'var(--red)', warn: 'var(--amber)' };

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-container">
        {toasts.map(({ id, msg, type }) => {
          const Icon = icons[type] || CheckCircle;
          return (
            <div key={id} className={`toast ${type}`}>
              <Icon size={16} color={colors[type]} style={{ flexShrink: 0, marginTop: 2 }} />
              <span style={{ flex: 1, fontSize: '0.875rem' }}>{msg}</span>
              <button
                onClick={() => remove(id)}
                style={{ background: 'none', color: 'var(--text-dim)', padding: 0, lineHeight: 1 }}
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
