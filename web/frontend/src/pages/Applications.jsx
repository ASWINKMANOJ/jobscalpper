import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useToast } from '../components/Toast.jsx'

const TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'rejected', label: 'Rejected' },
]

function CoverLetterModal({ appId, title, onClose }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/applications/${appId}/cover_letter`)
      .then(r => r.json())
      .then(d => { setContent(d.cover_letter || '— No cover letter —'); setLoading(false) })
      .catch(() => { setContent('Failed to load.'); setLoading(false) })
  }, [appId])

  return (
    <motion.div
      className="modal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        className="modal"
        initial={{ scale: 0.95, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 8 }}
        transition={{ duration: 0.18 }}
      >
        <div className="modal-header">
          <span className="modal-title">Cover Letter</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>{title}</p>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
            <div className="spinner spinner-lg" />
          </div>
        ) : (
          <pre>{content}</pre>
        )}
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function AppRow({ app, onAction, index = 0 }) {
  const [busy, setBusy] = useState(null)
  const [showCover, setShowCover] = useState(false)
  const toast = useToast()

  const doAction = async (action) => {
    setBusy(action)
    try {
      const r = await fetch(`/api/applications/${app.id}/${action}`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`Application ${action}d`)
        onAction(app.id, action === 'send' ? 'sent' : action + 'd')
      } else {
        toast.error(d.error || `Failed to ${action}`)
      }
    } catch {
      toast.error(`Network error`)
    } finally {
      setBusy(null)
    }
  }

  const formatDate = (s) => {
    if (!s) return '—'
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  }

  return (
    <>
      <tr>
        <td>
          <div className="td-title">
            <a href={app.url} target="_blank" rel="noopener noreferrer">{app.title}</a>
          </div>
          <div className="td-sub">{app.company || app.park}</div>
        </td>
        <td><span className="park-pill">{app.park}</span></td>
        <td>
          <span className={`badge badge-${app.status}`}>{app.status}</span>
        </td>
        <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          {formatDate(app.created_at)}
        </td>
        <td>
          <div className="action-group">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowCover(true)}
              title="Preview cover letter"
            >
              Letter
            </button>
            {app.status === 'pending' && (
              <>
                <button
                  className="btn btn-approve btn-sm"
                  disabled={busy === 'approve'}
                  onClick={() => doAction('approve')}
                >
                  {busy === 'approve' ? <div className="spinner" /> : '✓ Approve'}
                </button>
                <button
                  className="btn btn-danger btn-sm"
                  disabled={busy === 'reject'}
                  onClick={() => doAction('reject')}
                >
                  {busy === 'reject' ? <div className="spinner" /> : '✕ Reject'}
                </button>
              </>
            )}
            {app.status === 'approved' && (
              <button
                className="btn btn-send btn-sm"
                disabled={busy === 'send'}
                onClick={() => doAction('send')}
              >
                {busy === 'send' ? <><div className="spinner" /> Sending…</> : '↑ Send'}
              </button>
            )}
          </div>
        </td>
      </tr>
      <AnimatePresence>
        {showCover && (
          <CoverLetterModal
            appId={app.id}
            title={app.title}
            onClose={() => setShowCover(false)}
          />
        )}
      </AnimatePresence>
    </>
  )
}

function SkeletonRows({ n = 6 }) {
  return Array(n).fill(0).map((_, i) => (
    <tr key={i}>
      <td colSpan={5}>
        <div className="skeleton skeleton-text" style={{ width: `${50 + Math.random() * 40}%` }} />
      </td>
    </tr>
  ))
}

export default function Applications() {
  const [tab, setTab] = useState('')
  const [appList, setAppList] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const load = async (status = tab) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      const r = await fetch(`/api/applications?${params}`)
      const d = await r.json()
      setAppList(d.applications || [])
      setCounts(d.counts || {})
    } catch {
      toast.error('Failed to load applications')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [tab])

  const handleAction = (id, newStatus) => {
    // Remove from list if filtering by a specific status and status changed
    if (tab && newStatus !== tab) {
      setAppList(prev => prev.filter(a => a.id !== id))
    } else {
      setAppList(prev => prev.map(a => a.id === id ? { ...a, status: newStatus } : a))
    }
    load(tab)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Applications</h1>
        <p className="page-subtitle">
          {Object.values(counts).reduce((a, b) => a + b, 0)} total applications
        </p>
      </div>

      {/* Status tabs */}
      <div className="status-tabs">
        {TABS.map(t => (
          <button
            key={t.value}
            className={`status-tab${tab === t.value ? ' active' : ''}`}
            onClick={() => setTab(t.value)}
          >
            {t.label}
            {t.value && counts[t.value] !== undefined && (
              <span className="tab-count">{counts[t.value]}</span>
            )}
            {!t.value && (
              <span className="tab-count">
                {Object.values(counts).reduce((a, b) => a + b, 0)}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job Title</th>
                <th>Park</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonRows />
              ) : appList.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <div className="empty-state" style={{ padding: '48px 24px' }}>
                      <div className="empty-title">No applications {tab ? `with status "${tab}"` : 'yet'}</div>
                      <p className="empty-desc">
                        {tab
                          ? 'Try a different filter tab'
                          : 'Scan for jobs first, then applications will appear here after processing'
                        }
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                appList.map((app, i) => (
                  <AppRow key={app.id} app={app} onAction={handleAction} index={i} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
