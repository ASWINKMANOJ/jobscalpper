import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useToast } from '../components/Toast.jsx'

const FIELDS = [
  {
    key: 'GMAIL_ADDRESS',
    label: 'Gmail Address',
    type: 'email',
    placeholder: 'you@gmail.com',
    help: 'The Gmail account used to send applications',
  },
  {
    key: 'GMAIL_APP_PASSWORD',
    label: 'Gmail App Password',
    type: 'password',
    placeholder: '16-character app password',
    help: 'Not your regular password — must be a Google App Password',
    sensitive: true,
  },
  {
    key: 'APPLICANT_NAME',
    label: 'Your Full Name',
    type: 'text',
    placeholder: 'Your Name',
    help: 'Used in the email subject and cover letter signature',
  },
]

function OnboardingGuide() {
  return (
    <div className="settings-card" style={{ marginBottom: 24 }}>
      <div className="alert alert-warning" style={{ marginBottom: 0, borderRadius: 'var(--radius-sm)' }}>
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 1 }}>
          <circle cx="8" cy="8" r="6.5"/><line x1="8" y1="5" x2="8" y2="8.5"/><circle cx="8" cy="11" r="0.5" fill="currentColor"/>
        </svg>
        <span>No credentials found. Follow these steps to get started.</span>
      </div>

      <div style={{ marginTop: 16 }}>
        {[
          {
            n: 1,
            title: 'Use a Gmail account',
            body: <>Make sure you have a Gmail account you want to send job applications from.</>,
          },
          {
            n: 2,
            title: 'Enable 2-Step Verification',
            body: <>Go to{' '}<a href="https://myaccount.google.com/security" target="_blank" rel="noopener noreferrer">Google Account → Security</a>{' '}and enable 2-Step Verification if you haven't already.</>,
          },
          {
            n: 3,
            title: 'Create an App Password',
            body: <>Visit{' '}<a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">myaccount.google.com/apppasswords</a>, set App name to <code>JobScalpper</code>, and click <strong>Create</strong>. Copy the 16-character password shown.</>,
          },
          {
            n: 4,
            title: 'Enter credentials below',
            body: <>Paste your Gmail address and the 16-character app password into the form below, then click <strong>Save Configuration</strong>.</>,
          },
        ].map(step => (
          <div key={step.n} className="onboarding-step">
            <div className="onboarding-num">{step.n}</div>
            <div className="onboarding-content">
              <h4>{step.title}</h4>
              <p>{step.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Settings() {
  const [config, setConfig] = useState({})
  const [form, setForm]     = useState({})
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [testing, setTesting]   = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [hasCredentials, setHasCredentials] = useState(false)
  const toast = useToast()

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/config')
      const d = await r.json()
      setConfig(d)
      setHasCredentials(d.has_credentials || false)
      // Initialise form — clear password placeholder
      const f = {}
      FIELDS.forEach(field => {
        f[field.key] = field.sensitive ? '' : (d[field.key] || '')
      })
      setForm(f)
    } catch {
      toast.error('Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleSave = async () => {
    setSaving(true)
    setTestResult(null)
    try {
      const r = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const d = await r.json()
      if (d.ok) {
        toast.success('Configuration saved successfully')
        await load()
      } else {
        toast.error(d.error || 'Failed to save')
      }
    } catch {
      toast.error('Network error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await fetch('/api/config/test', { method: 'POST' })
      const d = await r.json()
      setTestResult(d)
      if (d.ok) toast.success('SMTP connection successful!')
      else toast.error(d.error || 'Connection failed')
    } catch {
      toast.error('Network error')
      setTestResult({ ok: false, error: 'Network error' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="page" style={{ maxWidth: 680 }}>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Manage your credentials and application configuration</p>
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: 72, borderRadius: 'var(--radius)' }} />
          ))}
        </div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {/* Onboarding guide when no credentials */}
          {!hasCredentials && <OnboardingGuide />}

          {/* Status badge */}
          {hasCredentials && (
            <div className="alert alert-success" style={{ marginBottom: 24 }}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ flexShrink: 0 }}>
                <polyline points="2.5,8.5 6,12 13.5,4"/>
              </svg>
              <span>Credentials configured — email sending is active</span>
            </div>
          )}

          {/* Form */}
          <div className="settings-section">
            <div className="settings-title">Email Configuration</div>
            <p className="settings-desc">
              These credentials are stored locally in your <code style={{ fontSize: 11 }}>.env</code> file and never leave your machine.
            </p>

            <div className="settings-card">
              {FIELDS.map(field => (
                <div key={field.key} className="input-group">
                  <label className="input-label" htmlFor={field.key}>{field.label}</label>
                  <input
                    id={field.key}
                    type={field.type}
                    className="input"
                    placeholder={field.sensitive && config[field.key]
                      ? '••••••••••••••••'
                      : field.placeholder
                    }
                    value={form[field.key] || ''}
                    onChange={e => setForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                    autoComplete={field.sensitive ? 'new-password' : 'off'}
                  />
                  <p style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{field.help}</p>
                </div>
              ))}

              {/* Test result */}
              {testResult && (
                <div className={`alert ${testResult.ok ? 'alert-success' : 'alert-error'}`}>
                  {testResult.ok ? testResult.message : testResult.error}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  className="btn btn-primary"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? <><div className="spinner" style={{ borderTopColor: 'var(--bg)' }} /> Saving…</> : 'Save Configuration'}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={handleTest}
                  disabled={testing || !hasCredentials}
                  title={!hasCredentials ? 'Save credentials first' : 'Test SMTP connection'}
                >
                  {testing ? <><div className="spinner" /> Testing…</> : 'Test Connection'}
                </button>
              </div>
            </div>
          </div>

          {/* Info section */}
          <div className="divider" />
          <div className="settings-section">
            <div className="settings-title">About</div>
            <div className="settings-card">
              <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>
                <p style={{ marginBottom: 10 }}>
                  <strong>JobScalpper</strong> scrapes job postings from Kerala IT park portals (Infopark, Technopark, Cyberpark), 
                  tailors your resume and cover letter, and sends job applications automatically via Gmail.
                </p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Credentials are stored in <code>.env</code> at the project root. 
                  App passwords are never sent to any external service.
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
