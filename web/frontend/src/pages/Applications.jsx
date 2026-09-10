import { useState, useEffect, useMemo } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useToast } from '../components/Toast.jsx'
import CoverLetterModal from '../components/CoverLetterModal.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'

const TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'rejected', label: 'Rejected' },
]

function AppRow({ app, onAction, selected, onSelect }) {
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
      <tr className={selected ? 'row-selected' : ''}>
        <td style={{ width: 36, paddingRight: 0 }}>
          <label className="row-checkbox-label">
            <input
              type="checkbox"
              className="row-checkbox"
              checked={selected}
              onChange={() => onSelect(app.id)}
            />
          </label>
        </td>
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
      <td colSpan={6}>
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
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [batchBusy, setBatchBusy] = useState(null)
  const [confirmModal, setConfirmModal] = useState(null)
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
      setSelectedIds(new Set())
    } catch {
      toast.error('Failed to load applications')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [tab])

  const handleAction = (id, newStatus) => {
    if (tab && newStatus !== tab) {
      setAppList(prev => prev.filter(a => a.id !== id))
    } else {
      setAppList(prev => prev.map(a => a.id === id ? { ...a, status: newStatus } : a))
    }
    load(tab)
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === appList.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(appList.map(a => a.id)))
    }
  }

  // Derive what batch actions are available based on selection
  const selectedApps = useMemo(() =>
    appList.filter(a => selectedIds.has(a.id)),
  [appList, selectedIds])

  const selectedPending = selectedApps.filter(a => a.status === 'pending')
  const selectedApproved = selectedApps.filter(a => a.status === 'approved')

  const doBatchAction = async (action, ids) => {
    setBatchBusy(action)
    try {
      const r = await fetch(`/api/applications/batch/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
      })
      const d = await r.json()
      if (d.ok) {
        const label = action === 'send' ? 'sent' : `${action}d`
        toast.success(`${d.count || d.sent_count || ids.length} application(s) ${label}`)
        await load(tab)
      } else {
        toast.error(d.error || `Batch ${action} failed`)
      }
    } catch {
      toast.error('Network error')
    } finally {
      setBatchBusy(null)
      setConfirmModal(null)
    }
  }

  const handleApproveAllPending = async () => {
    setBatchBusy('approve-all')
    try {
      const r = await fetch('/api/applications/approve-all-pending', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`${d.count} application(s) approved`)
        await load(tab)
      } else {
        toast.error(d.message || 'Failed')
      }
    } catch {
      toast.error('Network error')
    } finally {
      setBatchBusy(null)
    }
  }

  const handleSendAllApproved = async () => {
    setBatchBusy('send-all')
    try {
      const r = await fetch('/api/applications/send-all-approved', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`${d.sent_count} application(s) sent`)
        if (d.failed_count > 0) toast.error(`${d.failed_count} failed to send`)
        await load(tab)
      } else {
        toast.error(d.message || 'Failed')
      }
    } catch {
      toast.error('Network error')
    } finally {
      setBatchBusy(null)
      setConfirmModal(null)
    }
  }

  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <div className="page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 className="page-title">Applications</h1>
          <p className="page-subtitle">{totalCount} total applications</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {(counts.pending || 0) > 0 && (
            <button
              className="btn btn-approve btn-sm"
              disabled={!!batchBusy}
              onClick={handleApproveAllPending}
            >
              {batchBusy === 'approve-all' ? <><div className="spinner" /> Approving…</> : `✓ Approve All Pending (${counts.pending})`}
            </button>
          )}
          {(counts.approved || 0) > 0 && (
            <button
              className="btn btn-send btn-sm"
              disabled={!!batchBusy}
              onClick={() => setConfirmModal({
                title: 'Send All Approved',
                message: `This will send ${counts.approved} application email(s) to the respective companies. This action cannot be undone.`,
                confirmLabel: `Send ${counts.approved} Email(s)`,
                confirmClass: 'btn-send',
                onConfirm: handleSendAllApproved,
              })}
            >
              ↑ Send All Approved ({counts.approved})
            </button>
          )}
        </div>
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
              <span className="tab-count">{totalCount}</span>
            )}
          </button>
        ))}
      </div>

      {/* Batch action toolbar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <div className="batch-bar">
            <span className="batch-bar-label">{selectedIds.size} selected</span>
            <div className="batch-bar-actions">
              {selectedPending.length > 0 && (
                <>
                  <button
                    className="btn btn-approve btn-sm"
                    disabled={!!batchBusy}
                    onClick={() => doBatchAction('approve', selectedPending.map(a => a.id))}
                  >
                    {batchBusy === 'approve' ? <div className="spinner" /> : `✓ Approve (${selectedPending.length})`}
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={!!batchBusy}
                    onClick={() => setConfirmModal({
                      title: 'Reject Selected',
                      message: `Reject ${selectedPending.length} pending application(s)?`,
                      confirmLabel: `Reject ${selectedPending.length}`,
                      confirmClass: 'btn-danger',
                      onConfirm: () => doBatchAction('reject', selectedPending.map(a => a.id)),
                    })}
                  >
                    ✕ Reject ({selectedPending.length})
                  </button>
                </>
              )}
              {selectedApproved.length > 0 && (
                <button
                  className="btn btn-send btn-sm"
                  disabled={!!batchBusy}
                  onClick={() => setConfirmModal({
                    title: 'Send Selected',
                    message: `Send ${selectedApproved.length} approved application(s) via email? This cannot be undone.`,
                    confirmLabel: `Send ${selectedApproved.length} Email(s)`,
                    confirmClass: 'btn-send',
                    onConfirm: () => doBatchAction('send', selectedApproved.map(a => a.id)),
                  })}
                >
                  ↑ Send ({selectedApproved.length})
                </button>
              )}
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setSelectedIds(new Set())}
              >
                Clear
              </button>
            </div>
          </div>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="card">
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 36, paddingRight: 0 }}>
                  <label className="row-checkbox-label">
                    <input
                      type="checkbox"
                      className="row-checkbox"
                      checked={appList.length > 0 && selectedIds.size === appList.length}
                      onChange={toggleSelectAll}
                      disabled={loading || appList.length === 0}
                    />
                  </label>
                </th>
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
                  <td colSpan={6}>
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
                appList.map((app) => (
                  <AppRow
                    key={app.id}
                    app={app}
                    onAction={handleAction}
                    selected={selectedIds.has(app.id)}
                    onSelect={toggleSelect}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confirm Modal */}
      <AnimatePresence>
        {confirmModal && (
          <ConfirmModal
            title={confirmModal.title}
            message={confirmModal.message}
            confirmLabel={confirmModal.confirmLabel}
            confirmClass={confirmModal.confirmClass}
            onConfirm={confirmModal.onConfirm}
            onCancel={() => setConfirmModal(null)}
            busy={!!batchBusy}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
