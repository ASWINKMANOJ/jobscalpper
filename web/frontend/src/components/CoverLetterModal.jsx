import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

export default function CoverLetterModal({ appId, title, onClose }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/applications/${appId}/cover_letter`)
      .then(r => r.json())
      .then(d => { setContent(d.cover_letter || '— No cover letter generated —'); setLoading(false) })
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
          <span className="modal-title">Cover Letter Preview</span>
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
