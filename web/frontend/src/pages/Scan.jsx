import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useToast } from '../components/Toast.jsx'

export default function Scan() {
  const [status, setStatus] = useState({ running: false, message: 'Idle', log: [] })
  const [starting, setStarting] = useState(false)
  const logRef = useRef(null)
  const toast = useToast()
  const pollRef = useRef(null)

  const poll = async () => {
    try {
      const r = await fetch('/api/scrape/status')
      const d = await r.json()
      setStatus(d)
      if (!d.running && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch {}
  }

  useEffect(() => {
    poll()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [status.log])

  const startScrape = async () => {
    setStarting(true)
    try {
      const r = await fetch('/api/scrape', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        toast.info('Scrape started')
        setStatus(prev => ({ ...prev, running: true, message: 'Scraping portals…' }))
        pollRef.current = setInterval(poll, 2000)
      } else {
        toast.error(d.message || 'Already running')
        // Start polling if already running
        if (!pollRef.current) {
          pollRef.current = setInterval(poll, 2000)
        }
      }
    } catch {
      toast.error('Failed to start scrape')
    } finally {
      setStarting(false)
    }
  }

  const isIdle = !status.running

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Scan</h1>
        <p className="page-subtitle">Scrape Kerala IT Parks portals for new jobs in real time</p>
      </div>

      {/* Control panel */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button
          className="btn btn-primary btn-lg"
          disabled={status.running || starting}
          onClick={startScrape}
        >
          {status.running ? (
            <><div className="spinner" style={{ borderTopColor: 'var(--bg)', width: 16, height: 16 }} /> Scanning…</>
          ) : starting ? (
            <><div className="spinner" style={{ borderTopColor: 'var(--bg)', width: 16, height: 16 }} /> Starting…</>
          ) : (
            <>
              <svg className="btn-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M1.5 5.5V3A1.5 1.5 0 013 1.5h2.5M10.5 1.5H13A1.5 1.5 0 0114.5 3v2.5M14.5 10.5V13A1.5 1.5 0 0113 14.5H10.5M5.5 14.5H3A1.5 1.5 0 011.5 13v-2.5"/>
                <line x1="1.5" y1="8" x2="14.5" y2="8"/>
              </svg>
              Start Scan
            </>
          )}
        </button>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 13,
          color: 'var(--text-muted)',
        }}>
          {status.running ? (
            <><div className="pulse-dot" /><span style={{ color: 'var(--text-2)' }}>{status.message}</span></>
          ) : (
            <span>{status.message}</span>
          )}
        </div>
      </div>

      {/* Terminal */}
      <div className="terminal">
        <div className="terminal-header">
          <div className="terminal-dot terminal-dot-red" />
          <div className="terminal-dot terminal-dot-amber" />
          <div className="terminal-dot terminal-dot-green" />
          <span className="terminal-title" style={{ marginLeft: 8 }}>
            jobscalpper — scraper output
          </span>
          {status.running && (
            <div className="spinner" style={{ marginLeft: 'auto', width: 12, height: 12, borderWidth: 1.5 }} />
          )}
        </div>
        <div className="terminal-body" ref={logRef}>
          {status.log && status.log.length > 0 ? (
            status.log.map((line, i) => (
              <motion.div
                key={i}
                className="terminal-line"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15 }}
              >
                <span className="prefix">$</span>
                <span>{line}</span>
              </motion.div>
            ))
          ) : (
            <div style={{ color: 'var(--text-muted)' }}>
              {isIdle
                ? '— Idle. Press "Start Scan" to begin scraping IT park portals. —'
                : 'Waiting for output…'
              }
            </div>
          )}
          {status.running && (
            <div className="terminal-line" style={{ marginTop: 4 }}>
              <span className="prefix">$</span>
              <span className="terminal-cursor" />
            </div>
          )}
        </div>
      </div>

      {/* Info cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 24 }}>
        {[
          { title: 'Infopark',    desc: 'Kochi IT cluster' },
          { title: 'Technopark',  desc: 'Thiruvananthapuram' },
          { title: 'Cyberpark',   desc: 'Kozhikode' },
        ].map(p => (
          <div key={p.title} className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{p.title}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
