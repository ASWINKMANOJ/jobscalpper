import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import { ToastProvider } from './components/Toast.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Jobs from './pages/Jobs.jsx'
import Applications from './pages/Applications.jsx'
import Scan from './pages/Scan.jsx'
import Settings from './pages/Settings.jsx'

// ── Icons (inline SVG) ────────────────────────────────────────────────────
const icons = {
  dashboard: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="1" y="1" width="6" height="6" rx="1.5" />
      <rect x="9" y="1" width="6" height="6" rx="1.5" />
      <rect x="1" y="9" width="6" height="6" rx="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="1.5" />
    </svg>
  ),
  jobs: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="6" cy="6" r="4.5" />
      <line x1="9.5" y1="9.5" x2="14.5" y2="14.5" />
    </svg>
  ),
  applications: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="2" y="1.5" width="12" height="13" rx="2" />
      <line x1="5" y1="5.5" x2="11" y2="5.5" />
      <line x1="5" y1="8.5" x2="11" y2="8.5" />
      <line x1="5" y1="11.5" x2="8" y2="11.5" />
    </svg>
  ),
  scan: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M1.5 5.5V3a1.5 1.5 0 011.5-1.5H5.5" />
      <path d="M10.5 1.5H13a1.5 1.5 0 011.5 1.5v2.5" />
      <path d="M14.5 10.5V13a1.5 1.5 0 01-1.5 1.5H10.5" />
      <path d="M5.5 14.5H3A1.5 1.5 0 011.5 13v-2.5" />
      <line x1="1.5" y1="8" x2="14.5" y2="8" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3m10 0h1.5M3.4 3.4l1 1m7.2 7.2 1 1M12.6 3.4l-1 1M4.4 11.6l-1 1" />
    </svg>
  ),
  bolt: (
    <svg viewBox="0 0 16 16" fill="currentColor">
      <path d="M9 1L2 9h6l-1 6 7-8H8l1-6z" />
    </svg>
  ),
}

const navItems = [
  { path: '/',             label: 'Dashboard',    icon: 'dashboard'    },
  { path: '/jobs',         label: 'Job Board',    icon: 'jobs'         },
  { path: '/applications', label: 'Applications', icon: 'applications' },
  { path: '/scan',         label: 'Scan',         icon: 'scan'         },
  { path: '/settings',     label: 'Settings',     icon: 'settings'     },
]

const pageVariants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -6 },
}

export default function App() {
  const [scrapeRunning, setScrapeRunning] = useState(false)

  // Poll scrape status globally
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/scrape/status')
        const d = await r.json()
        setScrapeRunning(d.running)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  return (
    <ToastProvider>
      <div className="app-layout">
        {/* Sidebar */}
        <nav className="sidebar">
          <div className="logo">
            <div className="logo-mark">
              {icons.bolt}
            </div>
            <span className="logo-name">JobScalpper</span>
          </div>

          <p className="nav-section">Menu</p>
          <ul className="nav-list">
            {navItems.map(item => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                >
                  <span className="nav-icon">{icons[item.icon]}</span>
                  {item.label}
                  {item.path === '/scan' && scrapeRunning && (
                    <span style={{ marginLeft: 'auto' }}>
                      <span className="pulse-dot" style={{ width: 6, height: 6 }} />
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="sidebar-bottom">
            <div style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              padding: '0 10px',
            }}>
              Kerala IT Parks
            </div>
          </div>
        </nav>

        {/* Main */}
        <main className="main-content">
          <AnimatePresence mode="wait">
            <Routes>
              <Route path="/" element={
                <motion.div key="dashboard" {...pageVariants} transition={{ duration: 0.2 }}>
                  <Dashboard />
                </motion.div>
              } />
              <Route path="/jobs" element={
                <motion.div key="jobs" {...pageVariants} transition={{ duration: 0.2 }}>
                  <Jobs />
                </motion.div>
              } />
              <Route path="/applications" element={
                <motion.div key="applications" {...pageVariants} transition={{ duration: 0.2 }}>
                  <Applications />
                </motion.div>
              } />
              <Route path="/scan" element={
                <motion.div key="scan" {...pageVariants} transition={{ duration: 0.2 }}>
                  <Scan />
                </motion.div>
              } />
              <Route path="/settings" element={
                <motion.div key="settings" {...pageVariants} transition={{ duration: 0.2 }}>
                  <Settings />
                </motion.div>
              } />
            </Routes>
          </AnimatePresence>
        </main>
      </div>
    </ToastProvider>
  )
}
