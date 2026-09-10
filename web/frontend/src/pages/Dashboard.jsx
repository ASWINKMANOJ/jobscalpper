import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../components/Toast.jsx'
import CoverLetterModal from '../components/CoverLetterModal.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'

const statConfig = [
  { key: 'total_jobs',    label: 'Total Jobs',   icon: SearchIcon    },
  { key: 'new_jobs',      label: 'Unseen/New',    icon: StarIcon      },
  { key: 'today_scraped', label: 'Scraped Today', icon: CalIcon       },
  { key: 'pending',       label: 'Pending',       icon: ClockIcon     },
  { key: 'approved',      label: 'Approved',      icon: CheckIcon     },
  { key: 'sent',          label: 'Sent',          icon: SendIcon      },
  { key: 'rejected',      label: 'Rejected',      icon: XIcon         },
]

function SearchIcon() { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="6" cy="6" r="4.5"/><line x1="9.5" y1="9.5" x2="14.5" y2="14.5"/></svg> }
function StarIcon()   { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="8,1.5 10,6 14.5,6.5 11,10 12,14.5 8,12 4,14.5 5,10 1.5,6.5 6,6"/></svg> }
function CalIcon()    { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="1.5" y="2.5" width="13" height="12" rx="2"/><line x1="1.5" y1="6.5" x2="14.5" y2="6.5"/><line x1="5" y1="1.5" x2="5" y2="3.5"/><line x1="11" y1="1.5" x2="11" y2="3.5"/></svg> }
function ClockIcon()  { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6.5"/><polyline points="8,4.5 8,8 10.5,10.5"/></svg> }
function CheckIcon()  { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="2.5,8.5 6,12 13.5,4"/></svg> }
function SendIcon()   { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="14.5" y1="1.5" x2="1.5" y2="6.5"/><line x1="14.5" y1="1.5" x2="9" y2="14.5"/><line x1="14.5" y1="1.5" x2="6" y2="9"/></svg> }
function XIcon()      { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg> }
function WandIcon()   { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M11.5 1.5l3 3-9 9-3-3 9-9z"/><line x1="11.5" y1="4.5" x2="8.5" y2="1.5"/><line x1="14.5" y1="7.5" x2="11.5" y2="4.5"/><path d="M2.5 13.5l-1 1"/></svg> }

function AnimatedNumber({ target }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    if (target === 0) { setDisplay(0); return }
    let start = 0
    const duration = 800
    const step = target / (duration / 16)
    const timer = setInterval(() => {
      start += step
      if (start >= target) { setDisplay(target); clearInterval(timer) }
      else setDisplay(Math.floor(start))
    }, 16)
    return () => clearInterval(timer)
  }, [target])
  return <>{display}</>
}

function SkeletonStats() {
  return (
    <div className="stats-grid">
      {Array(7).fill(0).map((_, i) => (
        <div key={i} className="skeleton skeleton-stat" />
      ))}
    </div>
  )
}

function SkeletonRows({ n = 5 }) {
  return Array(n).fill(0).map((_, i) => (
    <div key={i} className="skeleton skeleton-row" style={{ margin: '0 0 1px' }} />
  ))
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [unappliedJobs, setUnappliedJobs] = useState([])
  const [recentJobs, setRecentJobs] = useState([])
  const [scrapeStatus, setScrapeStatus] = useState({ running: false, message: 'Idle' })
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [preparingHash, setPreparingHash] = useState(null)
  const [preparingAll, setPreparingAll] = useState(false)
  const [busyAppId, setBusyAppId] = useState(null)
  const [batchBusy, setBatchBusy] = useState(null)
  const [coverModal, setCoverModal] = useState(null)
  const [confirmModal, setConfirmModal] = useState(null)

  const toast = useToast()
  const navigate = useNavigate()

  const loadData = async () => {
    try {
      const [sRes, rRes, uRes] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/jobs?per_page=6'),
        fetch('/api/jobs/unapplied?limit=100'),
      ])
      const s = await sRes.json()
      const r = await rRes.json()
      const u = await uRes.json()
      setStats(s)
      setRecentJobs(r.jobs || [])
      setUnappliedJobs(u.jobs || [])
    } catch (e) {
      toast.error('Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const pollScrape = async () => {
    try {
      const res = await fetch('/api/scrape/status')
      const d = await res.json()
      setScrapeStatus(d)
    } catch {}
  }

  useEffect(() => {
    loadData()
    pollScrape()
  }, [])

  useEffect(() => {
    if (!scrapeStatus.running) return
    const id = setInterval(async () => {
      await pollScrape()
      await loadData()
    }, 3000)
    return () => clearInterval(id)
  }, [scrapeStatus.running])

  const handleScrape = async () => {
    try {
      const r = await fetch('/api/scrape', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.info('Scrape started — monitoring IT parks...')
        setScrapeStatus({ running: true, message: 'Scraping portals…' })
      } else {
        toast.error(d.message || 'Scrape already running')
      }
    } catch {
      toast.error('Failed to start scrape')
    }
  }

  const handlePrepareSingle = async (job) => {
    setPreparingHash(job.hash)
    try {
      const r = await fetch(`/api/jobs/${job.hash}/prepare`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`Application prepared for "${job.title}"`)
        await loadData()
      } else {
        toast.error(d.error || 'Failed to prepare application')
      }
    } catch {
      toast.error('Network error during application preparation')
    } finally {
      setPreparingHash(null)
    }
  }

  const handlePrepareAll = async () => {
    setPreparingAll(true)
    try {
      const r = await fetch('/api/jobs/prepare-all', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`Prepared ${d.prepared_count} application(s) successfully!`)
        await loadData()
      } else {
        toast.error(d.message || 'Preparation encountered issues')
      }
    } catch {
      toast.error('Network error during batch preparation')
    } finally {
      setPreparingAll(false)
    }
  }

  const handleAppAction = async (appId, action) => {
    setBusyAppId(`${appId}-${action}`)
    try {
      const r = await fetch(`/api/applications/${appId}/${action}`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`Application ${action === 'send' ? 'sent' : action + 'd'}`)
        await loadData()
      } else {
        toast.error(d.error || `Failed to ${action}`)
      }
    } catch {
      toast.error('Network error')
    } finally {
      setBusyAppId(null)
    }
  }

  const handleApproveAllPending = async () => {
    setBatchBusy('approve-all')
    try {
      const r = await fetch('/api/applications/approve-all-pending', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.success(`${d.count} application(s) approved`)
        await loadData()
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
        await loadData()
      }
    } catch {
      toast.error('Network error')
    } finally {
      setBatchBusy(null)
      setConfirmModal(null)
    }
  }

  const formatDate = (s) => {
    if (!s) return '—'
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  }

  // Filter unapplied jobs
  const newCount = unappliedJobs.filter(j => !j.app_status || j.app_status === 'new').length
  const pendingCount = unappliedJobs.filter(j => j.app_status === 'pending').length
  const approvedCount = unappliedJobs.filter(j => j.app_status === 'approved').length

  const filteredUnapplied = unappliedJobs.filter(j => {
    if (filter === 'new') return !j.app_status || j.app_status === 'new'
    if (filter === 'pending') return j.app_status === 'pending'
    if (filter === 'approved') return j.app_status === 'approved'
    return true
  })

  return (
    <div className="page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Kerala IT Parks job pipeline & quick action dashboard</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-primary"
            onClick={handleScrape}
            disabled={scrapeStatus.running}
          >
            {scrapeStatus.running ? (
              <><div className="spinner" style={{ borderTopColor: 'var(--bg)' }} /> Scanning…</>
            ) : (
              <>
                <svg className="btn-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M1.5 5.5V3a1.5 1.5 0 011.5-1.5H5.5M10.5 1.5H13A1.5 1.5 0 0114.5 3v2.5M14.5 10.5V13A1.5 1.5 0 0113 14.5H10.5M5.5 14.5H3A1.5 1.5 0 011.5 13v-2.5"/>
                  <line x1="1.5" y1="8" x2="14.5" y2="8"/>
                </svg>
                Scan Now
              </>
            )}
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/applications')}>
            All Applications →
          </button>
        </div>
      </div>

      {/* Scrape status banner */}
      {scrapeStatus.running && (
        <motion.div
          className="scrape-banner"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: 20 }}
        >
          <div className="pulse-dot" />
          <span>{scrapeStatus.message}</span>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: 'auto' }}
            onClick={() => navigate('/scan')}
          >
            View logs →
          </button>
        </motion.div>
      )}

      {/* Stats Cards */}
      {loading ? <SkeletonStats /> : (
        <div className="stats-grid" style={{ marginBottom: 24 }}>
          {statConfig.map((s, i) => (
            <motion.div
              key={s.key}
              className="stat-card"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <div className="stat-icon"><s.icon /></div>
              <div className="stat-value">
                <AnimatedNumber target={stats?.[s.key] ?? 0} />
              </div>
              <div className="stat-label">{s.label}</div>
            </motion.div>
          ))}
        </div>
      )}

      {/* ── TOP SECTION: NEW & UNAPPLIED JOBS — ACTION PANEL ────────────────── */}
      <div className="card" style={{ marginBottom: 28, border: '1px solid var(--border-bright)' }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="card-title" style={{ fontSize: 16, fontWeight: 700 }}>
                ⚡ New & Unapplied Jobs
              </span>
              <span className="badge badge-new" style={{ fontSize: 11 }}>
                {unappliedJobs.length} Ready
              </span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Apply to newly scraped jobs or review generated application letters
            </p>
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Filter Pills */}
            <div className="tab-pill-group">
              <button
                className={`tab-pill${filter === 'all' ? ' active' : ''}`}
                onClick={() => setFilter('all')}
              >
                All ({unappliedJobs.length})
              </button>
              <button
                className={`tab-pill${filter === 'new' ? ' active' : ''}`}
                onClick={() => setFilter('new')}
              >
                New ({newCount})
              </button>
              <button
                className={`tab-pill${filter === 'pending' ? ' active' : ''}`}
                onClick={() => setFilter('pending')}
              >
                Pending ({pendingCount})
              </button>
              <button
                className={`tab-pill${filter === 'approved' ? ' active' : ''}`}
                onClick={() => setFilter('approved')}
              >
                Approved ({approvedCount})
              </button>
            </div>

            {/* Batch action buttons */}
            <div style={{ display: 'flex', gap: 6 }}>
              {newCount > 0 && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handlePrepareAll}
                  disabled={preparingAll || !!batchBusy}
                >
                  {preparingAll ? (
                    <><div className="spinner" /> Preparing ({newCount})…</>
                  ) : (
                    <><WandIcon /> Prepare All ({newCount})</>
                  )}
                </button>
              )}
              {pendingCount > 0 && (
                <button
                  className="btn btn-approve btn-sm"
                  onClick={handleApproveAllPending}
                  disabled={!!batchBusy}
                >
                  {batchBusy === 'approve-all' ? <><div className="spinner" /> Approving…</> : `✓ Approve All (${pendingCount})`}
                </button>
              )}
              {approvedCount > 0 && (
                <button
                  className="btn btn-send btn-sm"
                  onClick={() => setConfirmModal({
                    title: 'Send All Approved',
                    message: `This will send ${approvedCount} application email(s). This action cannot be undone.`,
                    confirmLabel: `Send ${approvedCount} Email(s)`,
                    confirmClass: 'btn-send',
                    onConfirm: handleSendAllApproved,
                  })}
                  disabled={!!batchBusy}
                >
                  ↑ Send All ({approvedCount})
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="card-body table-wrap">
          {loading ? (
            <div style={{ padding: 16 }}><SkeletonRows n={6} /></div>
          ) : filteredUnapplied.length === 0 ? (
            <div className="empty-state" style={{ padding: '36px 20px' }}>
              <div className="empty-title">
                {filter === 'all'
                  ? 'All caught up!'
                  : `No jobs matching "${filter}" status`}
              </div>
              <p className="empty-desc">
                {filter === 'all'
                  ? 'All current jobs have been applied to or rejected. Run "Scan Now" to fetch new listings!'
                  : 'Try selecting a different filter tab above.'}
              </p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Job Title & Company</th>
                  <th>Park</th>
                  <th>Status</th>
                  <th>Scraped</th>
                  <th style={{ textAlign: 'right' }}>Direct Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredUnapplied.map((job, i) => {
                  const isNew = !job.app_status || job.app_status === 'new'
                  const isPending = job.app_status === 'pending'
                  const isApproved = job.app_status === 'approved'
                  const isPreparingThis = preparingHash === job.hash

                  return (
                    <motion.tr
                      key={job.hash}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.02 }}
                    >
                      <td>
                        <div className="td-title">
                          <a href={job.url} target="_blank" rel="noopener noreferrer">
                            {job.title}
                          </a>
                        </div>
                        <div className="td-sub">
                          {job.app_company || job.park}
                          {job.app_email ? ` • ${job.app_email}` : ''}
                        </div>
                      </td>
                      <td><span className="park-pill">{job.park}</span></td>
                      <td>
                        {isNew && <span className="badge badge-new">new</span>}
                        {isPending && <span className="badge badge-pending">pending</span>}
                        {isApproved && <span className="badge badge-approved">approved</span>}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                        {formatDate(job.scraped_at)}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="action-group" style={{ justifyContent: 'flex-end' }}>
                          {/* NEW JOB: Prepare Application Button */}
                          {isNew && (
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={isPreparingThis || preparingAll}
                              onClick={() => handlePrepareSingle(job)}
                            >
                              {isPreparingThis ? (
                                <><div className="spinner" /> Preparing…</>
                              ) : (
                                <>⚡ Prepare App</>
                              )}
                            </button>
                          )}

                          {/* PENDING APPLICATION: Letter, Approve, Reject */}
                          {isPending && (
                            <>
                              {job.app_id && (
                                <button
                                  className="btn btn-ghost btn-sm"
                                  onClick={() => setCoverModal({ appId: job.app_id, title: job.title })}
                                >
                                  Letter
                                </button>
                              )}
                              <button
                                className="btn btn-approve btn-sm"
                                disabled={busyAppId === `${job.app_id}-approve`}
                                onClick={() => handleAppAction(job.app_id, 'approve')}
                              >
                                {busyAppId === `${job.app_id}-approve` ? <div className="spinner" /> : '✓ Approve'}
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                disabled={busyAppId === `${job.app_id}-reject`}
                                onClick={() => handleAppAction(job.app_id, 'reject')}
                              >
                                {busyAppId === `${job.app_id}-reject` ? <div className="spinner" /> : '✕ Reject'}
                              </button>
                            </>
                          )}

                          {/* APPROVED APPLICATION: Letter, Send, Reject */}
                          {isApproved && (
                            <>
                              {job.app_id && (
                                <button
                                  className="btn btn-ghost btn-sm"
                                  onClick={() => setCoverModal({ appId: job.app_id, title: job.title })}
                                >
                                  Letter
                                </button>
                              )}
                              <button
                                className="btn btn-send btn-sm"
                                disabled={busyAppId === `${job.app_id}-send`}
                                onClick={() => handleAppAction(job.app_id, 'send')}
                              >
                                {busyAppId === `${job.app_id}-send` ? <><div className="spinner" /> Sending…</> : '↑ Send App'}
                              </button>
                              <button
                                className="btn btn-danger btn-sm"
                                disabled={busyAppId === `${job.app_id}-reject`}
                                onClick={() => handleAppAction(job.app_id, 'reject')}
                              >
                                {busyAppId === `${job.app_id}-reject` ? <div className="spinner" /> : '✕'}
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── BOTTOM SECTION: RECENT JOBS OVERVIEW ─────────────────────────── */}
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="card-title">Recent Scraped Jobs</span>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/jobs')}>
            See all jobs →
          </button>
        </div>
        <div className="card-body table-wrap">
          {loading ? (
            <div style={{ padding: 16 }}><SkeletonRows n={5} /></div>
          ) : recentJobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-title">No scraped jobs yet</div>
              <p className="empty-desc">Click "Scan Now" to fetch the latest job listings</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Park</th>
                  <th>Scraped</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map(job => (
                  <tr key={job.hash}>
                    <td>
                      <div className="td-title">
                        <a href={job.url} target="_blank" rel="noopener noreferrer">
                          {job.title}
                        </a>
                      </div>
                    </td>
                    <td><span className="park-pill">{job.park}</span></td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {formatDate(job.scraped_at)}
                    </td>
                    <td>
                      {job.app_status
                        ? <span className={`badge badge-${job.app_status}`}>{job.app_status}</span>
                        : <span className="badge badge-new">new</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Cover Letter Modal */}
      <AnimatePresence>
        {coverModal && (
          <CoverLetterModal
            appId={coverModal.appId}
            title={coverModal.title}
            onClose={() => setCoverModal(null)}
          />
        )}
      </AnimatePresence>

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
