import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../components/Toast.jsx'

const statConfig = [
  { key: 'total_jobs',    label: 'Total Jobs',   icon: SearchIcon    },
  { key: 'new_jobs',      label: 'Unseen',        icon: StarIcon      },
  { key: 'today_scraped', label: 'Today',         icon: CalIcon       },
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
  const [jobs, setJobs] = useState([])
  const [scrapeStatus, setScrapeStatus] = useState({ running: false, message: 'Idle' })
  const [loading, setLoading] = useState(true)
  const toast = useToast()
  const navigate = useNavigate()

  const loadData = async () => {
    try {
      const [sRes, jRes] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/jobs?per_page=8'),
      ])
      const s = await sRes.json()
      const j = await jRes.json()
      setStats(s)
      setJobs(j.jobs || [])
    } catch (e) {
      toast.error('Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const pollScrape = async () => {
    try {
      const r = await fetch('/api/scrape/status')
      const d = await r.json()
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
        toast.info('Scrape started — check the Scan page for live output')
        setScrapeStatus({ running: true, message: 'Scraping portals…' })
      } else {
        toast.error(d.message || 'Scrape already running')
      }
    } catch {
      toast.error('Failed to start scrape')
    }
  }

  const formatDate = (s) => {
    if (!s) return '—'
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Kerala IT Parks job pipeline overview</p>
      </div>

      {/* Scrape status banner */}
      {scrapeStatus.running && (
        <motion.div
          className="scrape-banner"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
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

      {/* Stats */}
      {loading ? <SkeletonStats /> : (
        <div className="stats-grid">
          {statConfig.map((s, i) => (
            <motion.div
              key={s.key}
              className="stat-card"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
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

      {/* Quick actions */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
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
          Review Applications
        </button>
      </div>

      {/* Recent jobs */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Recent Jobs</span>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/jobs')}>
            See all →
          </button>
        </div>
        <div className="card-body table-wrap">
          {loading ? (
            <div style={{ padding: 16 }}><SkeletonRows n={6} /></div>
          ) : jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-title">No jobs yet</div>
              <p className="empty-desc">Click "Scan Now" to scrape the IT parks portals</p>
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
                {jobs.map(job => (
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
    </div>
  )
}
