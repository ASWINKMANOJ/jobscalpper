import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useToast } from '../components/Toast.jsx'

function SkeletonRows({ n = 8 }) {
  return Array(n).fill(0).map((_, i) => (
    <tr key={i}>
      <td colSpan={5}>
        <div className="skeleton skeleton-text" style={{ width: `${60 + Math.random() * 30}%` }} />
      </td>
    </tr>
  ))
}

export default function Jobs() {
  const [data, setData] = useState({ jobs: [], total: 0, total_pages: 1, parks: [] })
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [park, setPark] = useState('')
  const [loading, setLoading] = useState(true)
  const [searchInput, setSearchInput] = useState('')
  const toast = useToast()

  const load = async (p = 1, q = search, pk = park) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: p, per_page: 50 })
      if (q) params.set('q', q)
      if (pk) params.set('park', pk)
      const r = await fetch(`/api/jobs?${params}`)
      const d = await r.json()
      setData(d)
      setPage(p)
    } catch {
      toast.error('Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(1) }, [])

  // Debounced search
  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(searchInput)
      load(1, searchInput, park)
    }, 350)
    return () => clearTimeout(id)
  }, [searchInput])

  const handleParkChange = (e) => {
    setPark(e.target.value)
    load(1, search, e.target.value)
  }

  const formatDate = (s) => {
    if (!s) return '—'
    return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  }

  const pageRange = () => {
    const { total_pages } = data
    const delta = 2
    const range = []
    for (let i = Math.max(1, page - delta); i <= Math.min(total_pages, page + delta); i++) {
      range.push(i)
    }
    return range
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Job Board</h1>
        <p className="page-subtitle">{data.total.toLocaleString()} total jobs scraped</p>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <input
          className="input search-input"
          placeholder="Search jobs…"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
        />
        <select className="input" value={park} onChange={handleParkChange} style={{ minWidth: 160 }}>
          <option value="">All Parks</option>
          {data.parks.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        {(search || park) && (
          <button className="btn btn-ghost btn-sm" onClick={() => {
            setSearchInput(''); setPark(''); setSearch('')
            load(1, '', '')
          }}>
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Park</th>
                <th>Status</th>
                <th>Scraped</th>
                <th>Times seen</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonRows />
              ) : data.jobs.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <div className="empty-state" style={{ padding: '48px 24px' }}>
                      <div className="empty-title">No jobs found</div>
                      <p className="empty-desc">Try adjusting your filters or scan for new jobs</p>
                    </div>
                  </td>
                </tr>
              ) : (
                data.jobs.map((job, i) => (
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
                      <div className="td-sub">{new URL(job.url).hostname}</div>
                    </td>
                    <td><span className="park-pill">{job.park}</span></td>
                    <td>
                      {job.app_status
                        ? <span className={`badge badge-${job.app_status}`}>{job.app_status}</span>
                        : <span className="badge badge-new">new</span>
                      }
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {formatDate(job.scraped_at)}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {job.seen_count}×
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data.total_pages > 1 && (
          <div className="pagination">
            <button
              className="page-btn"
              disabled={page === 1 || loading}
              onClick={() => load(page - 1)}
            >
              ←
            </button>
            {page > 3 && (
              <>
                <button className="page-btn" onClick={() => load(1)}>1</button>
                {page > 4 && <span style={{ color: 'var(--text-muted)', padding: '0 4px' }}>…</span>}
              </>
            )}
            {pageRange().map(p => (
              <button
                key={p}
                className={`page-btn${p === page ? ' current' : ''}`}
                onClick={() => load(p)}
              >
                {p}
              </button>
            ))}
            {page < data.total_pages - 2 && (
              <>
                {page < data.total_pages - 3 && <span style={{ color: 'var(--text-muted)', padding: '0 4px' }}>…</span>}
                <button className="page-btn" onClick={() => load(data.total_pages)}>{data.total_pages}</button>
              </>
            )}
            <button
              className="page-btn"
              disabled={page === data.total_pages || loading}
              onClick={() => load(page + 1)}
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
