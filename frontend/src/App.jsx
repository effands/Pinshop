import { useState, useEffect, useRef } from 'react'
import { LayoutDashboard, Settings, Wand2, Shield, Zap, XCircle, Key, RefreshCw, Cookie } from 'lucide-react'
import './index.css'

const API_BASE = 'http://127.0.0.1:8001/api'
const WS_URL = 'ws://127.0.0.1:8001/ws/logs'

function App() {
  const [activeTab, setActiveTab] = useState('prompt')
  const [logs, setLogs] = useState([])
  const [cookieStatus, setCookieStatus] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [nicheInput, setNicheInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [cookieInput, setCookieInput] = useState('')
  const [accountNameInput, setAccountNameInput] = useState('')
  const [accountsList, setAccountsList] = useState([])
  const [isTestingKeys, setIsTestingKeys] = useState(false)
  const [toast, setToast] = useState({ show: false, message: '', type: 'info' })

  const showToast = (message, type = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => setToast({ show: false, message: '', type: 'info' }), 4000)
  }
  
  const [config, setConfig] = useState({
    startTime: '',
    stopTime: '',
    targetPost: 0,
    mediaType: 'image',
    spintaxLinks: '',
    geminiApiKeys: '',
    subject: '',
    detail: '',
    background: '',
    quality: ''
  })

  useEffect(() => {
    fetch(`${API_BASE}/get-config`)
      .then(res => res.json())
      .then(data => {
        if(Object.keys(data).length > 0) {
          setConfig(prev => ({...prev, ...data}))
        }
      })
      .catch(err => console.error(err))

    fetchAccounts()

    const ws = new WebSocket(WS_URL)
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'log') {
        setLogs(prev => [...prev, data.message])
      }
    }
    return () => ws.close()
  }, [])

  const logsEndRef = useRef(null)
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const saveConfig = async () => {
    try {
      await fetch(`${API_BASE}/save-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      showToast('Konfigurasi berhasil disimpan!', 'success')
    } catch(e) {
      showToast('Gagal menyimpan konfigurasi', 'error')
    }
  }

  const autoSaveConfig = async () => {
    try {
      await fetch(`${API_BASE}/save-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
    } catch(e) {
      console.error('Auto-save failed:', e)
    }
  }

  const handleAuth = async () => {
    try {
      await fetch(`${API_BASE}/auth-setup`, { method: 'POST' })
    } catch(e) {
      showToast('Gagal membuka auth', 'error')
    }
  }

  const fetchAccounts = async () => {
    try {
      const res = await fetch(`${API_BASE}/accounts`)
      const data = await res.json()
      if (data.success) {
        setAccountsList(data.accounts)
      }
    } catch(e) {
      console.error(e)
    }
  }

  const handleInjectCookie = async () => {
    if (!accountNameInput.trim()) return showToast('Masukkan Nama Akun terlebih dahulu!', 'error')
    if (!cookieInput) return showToast('Masukkan JSON cookie terlebih dahulu!', 'error')
    
    setCookieStatus('Menyuntikkan & Memvalidasi Cookies...')
    try {
      const res = await fetch(`${API_BASE}/auth-cookie`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookies: cookieInput, accountName: accountNameInput })
      })
      const data = await res.json()
      if (data.success) {
        if(data.status === 'valid') {
            setCookieStatus(`✅ ${data.count || 'Beberapa'} Cookies aktif dan valid untuk akun '${accountNameInput}'.`)
            showToast('Cookies berhasil disuntikkan & valid!', 'success')
        } else {
            setCookieStatus(`⚠️ Cookies terinjeksi tapi terdeteksi Invalid/Expired!`)
            showToast('Cookies invalid/expired!', 'error')
        }
        setCookieInput('')
        setAccountNameInput('')
        fetchAccounts()
      } else {
        const errorMsg = data.error || (data.detail && JSON.stringify(data.detail)) || 'Gagal inject cookie';
        showToast('Gagal: ' + errorMsg, 'error')
        setCookieStatus(null)
      }
    } catch (e) {
      showToast('Error saat menghubungi server', 'error')
      setCookieStatus(null)
    }
  }

  const handleDeleteAccount = async (name) => {
    if(!confirm(`Hapus akun ${name}?`)) return
    try {
      await fetch(`${API_BASE}/accounts/${name}`, { method: 'DELETE' })
      showToast(`Akun ${name} dihapus.`, 'success')
      fetchAccounts()
    } catch(e) {
      showToast('Gagal menghapus akun', 'error')
    }
  }

  const handleCheckAccount = async (name) => {
    showToast(`Mengecek status akun ${name}...`, 'info')
    try {
      const res = await fetch(`${API_BASE}/accounts/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountName: name })
      })
      const data = await res.json()
      if (data.success) {
        showToast(`Status ${name}: ${data.status.toUpperCase()}`, data.status === 'valid' ? 'success' : 'error')
        fetchAccounts()
      }
    } catch(e) {
      showToast('Gagal mengecek akun', 'error')
    }
  }

  const toggleAutopilot = async () => {
    const endpoint = isRunning ? 'stop-autopilot' : 'start-autopilot'
    try {
      await fetch(`${API_BASE}/${endpoint}`, { method: 'POST' })
      setIsRunning(!isRunning)
    } catch(e) {
      showToast('Gagal mengontrol Autopilot', 'error')
    }
  }

  const testGeminiKeys = async () => {
    if (!config.geminiApiKeys) return showToast('Masukkan API Key terlebih dahulu!', 'error')
    setIsTestingKeys(true)
    try {
      const res = await fetch(`${API_BASE}/test-gemini-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: config.geminiApiKeys })
      })
      const data = await res.json()
      if (data.success) {
        setConfig({...config, geminiApiKeys: data.sortedKeys})
        showToast(`Test Selesai!\nAktif: ${data.activeCount}\nMati/Limit: ${data.invalidCount}\n\nKey mati otomatis dipindah ke bawah.`, 'success')
      } else {
        const errorMsg = data.error || (data.detail && JSON.stringify(data.detail)) || 'Endpoint Error / Not Found';
        showToast('Gagal: ' + errorMsg, 'error')
      }
    } catch (e) {
      showToast('Terjadi kesalahan koneksi.', 'error')
    }
    setIsTestingKeys(false)
  }

  const generatePromptsWithAI = async () => {
    if (!nicheInput) return showToast('Masukkan niche atau topik Pinterest Anda!', 'error')
    setIsGenerating(true)
    
    await fetch(`${API_BASE}/save-config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })

    try {
      const res = await fetch(`${API_BASE}/generate-prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: nicheInput })
      })
      const data = await res.json()
      if (data.success) {
        setConfig({
          ...config,
          subject: data.data.subject || '',
          detail: data.data.detail || '',
          background: data.data.background || '',
          quality: data.data.quality || ''
        })
        showToast('Prompt berhasil di-generate!', 'success')
      } else {
        const errorMsg = data.error || (data.detail && JSON.stringify(data.detail)) || 'Gagal generate prompt';
        showToast('Gagal: ' + errorMsg, 'error')
      }
    } catch (e) {
      showToast('Terjadi kesalahan koneksi.', 'error')
    }
    setIsGenerating(false)
  }

  return (
    <div className="app-container">
      {/* Top Floating Navbar */}
      <div className="top-nav">
        <div className="brand">
          <img src="/logo.png" alt="PinShop Logo" />
          <span>PINSHOP</span>
        </div>

        <div className="nav-links">
          <div className={`nav-item ${activeTab === 'prompt' ? 'active' : ''}`} onClick={() => setActiveTab('prompt')}>
            <Wand2 size={18} /> Studio
          </div>
          <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
            <Settings size={18} /> Settings
          </div>
          <div className={`nav-item ${activeTab === 'auth' ? 'active' : ''}`} onClick={() => setActiveTab('auth')}>
            <Shield size={18} /> Auth
          </div>
          <div className={`nav-item ${activeTab === 'activity' ? 'active' : ''}`} onClick={() => setActiveTab('activity')}>
            <LayoutDashboard size={18} /> Monitor
          </div>
        </div>

        <div style={{display: 'flex', gap: '16px', alignItems: 'center'}}>
          <div className="status-badge">
            <span className="pulse-dot" style={{backgroundColor: isRunning ? 'var(--success)' : 'var(--text-muted)', animation: isRunning ? 'pulse 2s infinite' : 'none'}}></span> 
            <span style={{color: isRunning ? 'var(--success)' : 'var(--text-muted)'}}>{isRunning ? 'ONLINE' : 'STANDBY'}</span>
          </div>

          {!isRunning ? (
            <button className="btn btn-primary" onClick={toggleAutopilot}>
              <Zap size={16} /> START
            </button>
          ) : (
            <button className="btn btn-danger" onClick={toggleAutopilot}>
              <XCircle size={16} /> STOP
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="content-area">
        {activeTab === 'activity' && (
          <div className="panel">
            <h3><LayoutDashboard size={20} /> Activity Log</h3>
            <div className="terminal">
              {logs.length === 0 ? (
                <div style={{color: 'var(--text-muted)', textAlign: 'center', marginTop: '10vh'}}>
                  Sistem dalam keadaan standby. Log akan muncul di sini saat berjalan.
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="log-line">
                    <span className="log-arrow">&rarr;</span> {log}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div>
            <div className="panel">
              <h3><Settings size={20} /> Jadwal Operasional Pintar</h3>
              <div className="grid-3">
                <div className="form-group">
                  <label>Jam Mulai</label>
                  <input type="time" className="form-control" value={config.startTime} onChange={e => setConfig({...config, startTime: e.target.value})} />
                </div>
                <div className="form-group">
                  <label>Jam Berhenti</label>
                  <input type="time" className="form-control" value={config.stopTime} onChange={e => setConfig({...config, stopTime: e.target.value})} />
                </div>
                <div className="form-group">
                  <label>Tipe Media (Google Flow)</label>
                  <div className="radio-group">
                    <label className="radio-label">
                      <input type="radio" name="mediaType" value="image" checked={config.mediaType === 'image'} onChange={e => setConfig({...config, mediaType: e.target.value})} /> Foto
                    </label>
                    <label className="radio-label">
                      <input type="radio" name="mediaType" value="video" checked={config.mediaType === 'video'} onChange={e => setConfig({...config, mediaType: e.target.value})} /> Video
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label>Akun Pinterest Target</label>
                  <select 
                    className="form-control" 
                    value={config.targetAccount || ''} 
                    onChange={e => setConfig({...config, targetAccount: e.target.value})}
                  >
                    <option value="">Pilih Akun...</option>
                    {accountsList.filter(a => a.status === 'valid').map((acc, i) => (
                      <option key={i} value={acc.name}>{acc.name} (Valid)</option>
                    ))}
                  </select>
                  <small style={{color: 'var(--text-muted)'}}>Akun yang akan digunakan saat Autopilot (Upload).</small>
                </div>
              </div>
            </div>

            <div className="grid-2">
              <div className="panel">
                <h3>Injeksi Link Pinterest (Spintax)</h3>
                <textarea 
                  className="form-control" 
                  style={{height: '250px'}}
                  value={config.spintaxLinks}
                  onChange={e => setConfig({...config, spintaxLinks: e.target.value})}
                  onBlur={autoSaveConfig}
                  placeholder="https://s.shopee.co.id/xxx"
                ></textarea>
              </div>

              <div className="panel">
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                  <h3 style={{margin: 0}}>Gemini API Keys</h3>
                  <button className="btn btn-outline" style={{padding: '6px 16px', fontSize: '13px'}} onClick={testGeminiKeys} disabled={isTestingKeys}>
                    {isTestingKeys ? <RefreshCw size={14} className="spin"/> : <Key size={14} />} Test & Sort Keys
                  </button>
                </div>
                <textarea 
                  className="form-control" 
                  style={{height: '250px'}}
                  value={config.geminiApiKeys}
                  onChange={e => setConfig({...config, geminiApiKeys: e.target.value})}
                  onBlur={autoSaveConfig}
                  placeholder="AIzaSy..."
                ></textarea>
              </div>
            </div>

            <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: '10px'}}>
              <button className="btn btn-primary" onClick={saveConfig}>Simpan Konfigurasi</button>
            </div>
          </div>
        )}

        {activeTab === 'auth' && (
          <div>
            <div className="grid-2">
              <div className="panel">
              <h3><Shield size={20} /> Login Manual</h3>
              <p style={{fontSize: '14px', color: 'var(--text-muted)', marginBottom: '24px', lineHeight: '1.6'}}>
                Buka browser khusus untuk melakukan login manual ke akun Pinterest Anda. Lakukan ini jika Anda belum memiliki Cookies.
              </p>
              <button className="btn btn-outline" style={{width: '100%'}} onClick={handleAuth}>
                Buka Browser Auth
              </button>
            </div>
            
            <div className="panel">
              <h3><Cookie size={20} /> Inject Cookies (Bypass Login)</h3>
              <p style={{fontSize: '14px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: '1.6'}}>
                Paste JSON cookies Pinterest Anda di bawah ini agar sistem otomatis masuk tanpa verifikasi manual.
              </p>
              <input 
                type="text" 
                className="form-control" 
                placeholder="Nama Akun (misal: Toko Baju 1)"
                value={accountNameInput}
                onChange={e => setAccountNameInput(e.target.value)}
                style={{marginBottom: '10px'}}
              />
              <textarea 
                className="form-control" 
                style={{height: '140px', marginBottom: '16px', fontSize: '12px', fontFamily: 'monospace'}}
                placeholder='[{"domain": ".pinterest.com", "name": "_pinterest_sess", ...}]'
                value={cookieInput}
                onChange={e => setCookieInput(e.target.value)}
              ></textarea>
              {cookieStatus && (
                <div style={{marginTop: '15px', padding: '12px', backgroundColor: 'rgba(34, 197, 94, 0.1)', color: 'var(--success)', borderRadius: '8px', border: '1px solid var(--success)', fontSize: '14px', fontWeight: '500'}}>
                  {cookieStatus}
                </div>
              )}
              <br/>
              <button className="btn btn-primary" style={{width: '100%', marginTop: '10px'}} onClick={handleInjectCookie} disabled={!cookieInput || !accountNameInput.trim()}>
                Inject Cookies Sekarang
              </button>
            </div>
          </div>
          
          <div className="panel" style={{marginTop: '20px'}}>
            <h3><Key size={20} /> Daftar Akun Pinterest</h3>
            <p style={{fontSize: '14px', color: 'var(--text-muted)', marginBottom: '16px'}}>
              Daftar akun yang berhasil diinject cookiesnya.
            </p>
            {accountsList.length === 0 ? (
              <div style={{padding: '20px', textAlign: 'center', color: 'var(--text-muted)', border: '1px dashed var(--border)', borderRadius: '8px'}}>
                Belum ada akun yang terdaftar.
              </div>
            ) : (
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Nama Akun</th>
                    <th>Status Cookies</th>
                    <th>Last Checked</th>
                    <th style={{textAlign: 'right'}}>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {accountsList.map((acc, idx) => (
                    <tr key={idx}>
                      <td style={{fontWeight: '500'}}>{acc.name}</td>
                      <td>
                        {acc.status === 'valid' ? 
                          <span style={{color: 'var(--success)', fontWeight: '600'}}>✅ Valid</span> : 
                          <span style={{color: 'var(--error)', fontWeight: '600'}}>⚠️ Expired</span>
                        }
                      </td>
                      <td style={{fontSize: '13px', color: 'var(--text-muted)'}}>
                        {acc.last_checked ? new Date(acc.last_checked).toLocaleString() : '-'}
                      </td>
                      <td style={{textAlign: 'right'}}>
                        <button className="btn btn-outline" style={{padding: '6px 12px', fontSize: '12px', marginRight: '8px'}} onClick={() => handleCheckAccount(acc.name)}>
                          Cek Status
                        </button>
                        <button className="btn btn-outline" style={{padding: '6px 12px', fontSize: '12px', borderColor: 'var(--error)', color: 'var(--error)'}} onClick={() => handleDeleteAccount(acc.name)}>
                          Hapus
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          </div>
        )}

        {activeTab === 'prompt' && (
          <div>
            <div className="panel" style={{border: '1px solid var(--primary)', background: 'var(--bg-app)'}}>
              <div style={{display: 'flex', gap: '20px', alignItems: 'flex-end'}}>
                <div className="form-group" style={{flex: 1, marginBottom: 0}}>
                  <label style={{color: 'var(--primary)'}}>✨ AI Prompt Generator</label>
                  <input type="text" className="form-control" value={nicheInput} onChange={e => setNicheInput(e.target.value)} placeholder="Ide dekorasi kamar estetik..." />
                </div>
                <button className="btn btn-primary" style={{padding: '14px 24px'}} onClick={generatePromptsWithAI} disabled={isGenerating}>
                  {isGenerating ? <RefreshCw size={16} className="spin" /> : <Wand2 size={16} />} 
                  {isGenerating ? 'Meracik Prompt...' : 'Buat Master Prompt'}
                </button>
              </div>
            </div>

            <div className="grid-2">
              <div className="panel">
                <h3 style={{color: 'var(--primary)'}}>Subjek Utama</h3>
                <textarea className="form-control" rows="5" value={config.subject} onChange={e => setConfig({...config, subject: e.target.value})}></textarea>
              </div>
              <div className="panel">
                <h3 style={{color: 'var(--primary)'}}>Variasi 1 (Detail)</h3>
                <textarea className="form-control" rows="5" value={config.detail} onChange={e => setConfig({...config, detail: e.target.value})}></textarea>
              </div>
              <div className="panel">
                <h3 style={{color: 'var(--primary)'}}>Variasi 2 (Latar)</h3>
                <textarea className="form-control" rows="5" value={config.background} onChange={e => setConfig({...config, background: e.target.value})}></textarea>
              </div>
              <div className="panel">
                <h3 style={{color: 'var(--primary)'}}>Variasi 3 (Nuansa)</h3>
                <textarea className="form-control" rows="5" value={config.quality} onChange={e => setConfig({...config, quality: e.target.value})}></textarea>
              </div>
            </div>

            <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: '10px'}}>
              <button className="btn btn-primary" onClick={saveConfig}>Simpan Konfigurasi</button>
            </div>
          </div>
        )}
      </div>

      {/* Toast Container */}
      {toast.show && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>
            {toast.message}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
