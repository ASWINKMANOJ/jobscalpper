import { motion } from 'framer-motion'

export default function ConfirmModal({ title, message, confirmLabel = 'Confirm', confirmClass = 'btn-primary', onConfirm, onCancel, busy = false }) {
  return (
    <motion.div
      className="modal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={e => e.target === e.currentTarget && !busy && onCancel()}
    >
      <motion.div
        className="modal confirm-modal"
        initial={{ scale: 0.95, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 8 }}
        transition={{ duration: 0.18 }}
      >
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button className="modal-close" onClick={onCancel} disabled={busy}>✕</button>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6, marginBottom: 8 }}>{message}</p>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={`btn ${confirmClass}`} onClick={onConfirm} disabled={busy}>
            {busy ? <><div className="spinner" /> Processing…</> : confirmLabel}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
