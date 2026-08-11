import { useState, useEffect, useRef } from 'react'
import { LayoutDashboard, Settings, Wand2, Shield, Zap, XCircle, Key, RefreshCw, Cookie, Trash2, Edit3, UploadCloud, Copy, Check, Image as ImageIcon, Film, Download, FolderHeart, AlertTriangle } from 'lucide-react'
import './index.css'

const API_BASE = 'http://127.0.0.1:8015/api'
const WS_URL = 'ws://127.0.0.1:8015/ws/logs'

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
  const [flowCount, setFlowCount] = useState(0)
  const [isLogsCopied, setIsLogsCopied] = useState(false)
  const [toast, setToast] = useState({ show: false, message: '', type: 'info' })

  const copyLogsToClipboard = () => {
    if (logs.length === 0) return showToast('Log masih kosong!', 'info')
    navigator.clipboard.writeText(logs.join('\n'))
    setIsLogsCopied(true)
    showToast('Log berhasil disalin ke clipboard!', 'success')
    setTimeout(() => setIsLogsCopied(false), 2000)
  }

  const showToast = (message, type = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => setToast({ show: false, message: '', type: 'info' }), 4000)
  }
  
  const [galleryFiles, setGalleryFiles] = useState([])
  const [selectedGalleryItems, setSelectedGalleryItems] = useState([])
  const [isLoadingGallery, setIsLoadingGallery] = useState(false)
  const [previewIndex, setPreviewIndex] = useState(null)

  useEffect(() => {
    if (previewIndex === null) return
    const handleKeyDown = (e) => {
      if (e.key === 'ArrowLeft') {
        if (previewIndex > 0) setPreviewIndex(previewIndex - 1)
      } else if (e.key === 'ArrowRight') {
        if (previewIndex < galleryFiles.length - 1) setPreviewIndex(previewIndex + 1)
      } else if (e.key === 'Escape') {
        setPreviewIndex(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [previewIndex, galleryFiles.length])

  const [confirmModal, setConfirmModal] = useState({
    show: false,
    message: '',
    onConfirm: null
  })

  const askConfirmation = (message, onConfirmAction) => {
    setConfirmModal({
      show: true,
      message,
      onConfirm: () => {
        onConfirmAction()
        setConfirmModal({ show: false, message: '', onConfirm: null })
      }
    })
  }

  const [copiedField, setCopiedField] = useState(null)
  const [editingQueueItemId, setEditingQueueItemId] = useState(null)

  const handleEditQueueItem = (item) => {
    setEditingQueueItemId(item.id)
    setManualBasicTitle(item.basicTitle || '')
    setManualImages(item.referenceImages || [])
    setConfig(prev => ({
      ...prev,
      spintaxLinks: item.spintaxLinks || '',
      seoTitle: item.seoTitle || '',
      seoDesc: item.seoDesc || '',
      masterPrompt: item.masterPrompt || ''
    }))
    window.scrollTo({ top: 0, behavior: 'smooth' })
    showToast("Data antrean dimuat ke editor utama di atas!", "info")
  }

  const cancelEditQueueItem = () => {
    setEditingQueueItemId(null)
    setManualBasicTitle('')
    setManualImages([])
    setConfig(prev => ({
      ...prev,
      spintaxLinks: '',
      seoTitle: '',
      seoDesc: '',
      masterPrompt: ''
    }))
    showToast("Edit antrean dibatalkan.", "info")
  }

  const saveEditedQueueItemDirect = async () => {
    if (!manualBasicTitle) {
      showToast("Judul Dasar wajib diisi!", "error")
      return
    }
    try {
      const res = await fetch(`${API_BASE}/queue/${editingQueueItemId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: editingQueueItemId,
          basicTitle: manualBasicTitle,
          spintaxLinks: config.spintaxLinks || '',
          referenceImages: manualImages || [],
          status: 'pending',
          seoTitle: config.seoTitle || '',
          seoDesc: config.seoDesc || '',
          masterPrompt: config.masterPrompt || ''
        })
      })
      const data = await res.json()
      if (data.success) {
        showToast("Item antrean berhasil diperbarui!", "success")
        setEditingQueueItemId(null)
        setManualBasicTitle('')
        setManualImages([])
        setConfig(prev => ({
          ...prev,
          spintaxLinks: '',
          seoTitle: '',
          seoDesc: '',
          masterPrompt: ''
        }))
        fetchQueue()
      } else {
        showToast("Gagal memperbarui item antrean", "error")
      }
    } catch (e) {
      showToast("Koneksi gagal", "error")
    }
  }

  const [bulkTheme, setBulkTheme] = useState('')
  const [bulkShopeeLink, setBulkShopeeLink] = useState('')
  const [bulkCount, setBulkCount] = useState(5)
  const [isGeneratingBulk, setIsGeneratingBulk] = useState(false)

  const generateBulkQueueItems = async () => {
    if (!bulkTheme.trim()) {
      showToast("Tema utama wajib diisi!", "error")
      return
    }
    if (!bulkShopeeLink.trim()) {
      showToast("Link affiliate Shopee wajib diisi!", "error")
      return
    }

    setIsGeneratingBulk(true)
    try {
      const res = await fetch(`${API_BASE}/generate-bulk-ideas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          theme: bulkTheme,
          shopeeLink: bulkShopeeLink,
          count: bulkCount
        })
      })
      const data = await res.json()
      if (data.success) {
        showToast(`AI Berhasil menambahkan ${data.count} ide postingan baru ke antrean!`, "success")
        setBulkTheme('')
        fetchQueue()
      } else {
        showToast(data.error || "Gagal men-generate ide bulk", "error")
      }
    } catch (e) {
      showToast("Koneksi ke backend gagal", "error")
    } finally {
      setIsGeneratingBulk(false)
    }
  }
  
  const handleCopyText = (text, fieldName) => {
    if (!text) {
      showToast(`${fieldName} masih kosong!`, 'info')
      return
    }
    navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    showToast(`${fieldName} disalin ke clipboard!`, 'success')
    setTimeout(() => setCopiedField(null), 2000)
  }

  const fetchGallery = async () => {
    setIsLoadingGallery(true)
    setSelectedGalleryItems([]) // Reset selection on refresh/reload
    try {
      const res = await fetch(`${API_BASE}/gallery`)
      const data = await res.json()
      if (data.files) {
        setGalleryFiles(data.files)
      }
    } catch (e) {
      console.error(e)
    }
    setIsLoadingGallery(false)
  }

  const toggleSelectGalleryItem = (filename) => {
    setSelectedGalleryItems(prev => {
      if (prev.includes(filename)) {
        return prev.filter(f => f !== filename)
      } else {
        return [...prev, filename]
      }
    })
  }

  const selectAllGalleryItems = () => {
    if (!Array.isArray(galleryFiles) || galleryFiles.length === 0) {
      setSelectedGalleryItems([])
      return
    }
    const allNames = galleryFiles.filter(f => f && f.filename).map(f => f.filename)
    if (selectedGalleryItems && selectedGalleryItems.length === allNames.length) {
      setSelectedGalleryItems([])
    } else {
      setSelectedGalleryItems(allNames)
    }
  }

  const deleteSelectedGalleryItems = async () => {
    if (selectedGalleryItems.length === 0) return
    askConfirmation(`Hapus ${selectedGalleryItems.length} item terpilih dari Gallery?`, async () => {
      try {
        const res = await fetch(`${API_BASE}/gallery/delete-batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filenames: selectedGalleryItems })
        })
        const data = await res.json()
        if (data.success) {
          showToast(`${data.deleted} item berhasil dihapus`, 'success')
          setSelectedGalleryItems([])
          fetchGallery()
        } else {
          showToast('Gagal menghapus item', 'error')
        }
      } catch (e) {
        showToast('Error koneksi', 'error')
      }
    })
  }

  const deleteGalleryItem = async (filename) => {
    askConfirmation("Hapus file ini dari Gallery?", async () => {
      try {
        const res = await fetch(`${API_BASE}/gallery/${filename}`, { method: 'DELETE' })
        const data = await res.json()
        if (data.success) {
          showToast("Item berhasil dihapus dari Gallery", "success")
          fetchGallery()
        } else {
          showToast("Gagal menghapus item", "error")
        }
      } catch (e) {
        showToast("Error saat menghapus item", "error")
      }
    })
  }

  const [queueItems, setQueueItems] = useState([])
  const [isAddingToQueue, setIsAddingToQueue] = useState(false)

  const fetchQueue = async () => {
    try {
      const res = await fetch(`${API_BASE}/queue`)
      const data = await res.json()
      if (data.queue) {
        setQueueItems(data.queue)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const addToQueue = async () => {
    if (!manualBasicTitle) {
      showToast("Judul Dasar wajib diisi!", "error")
      return
    }
    setIsAddingToQueue(true)
    const newItem = {
      id: 'q_' + Date.now(),
      basicTitle: manualBasicTitle,
      spintaxLinks: config.spintaxLinks || "",
      referenceImages: manualImages,
      status: "pending",
      seoTitle: config.seoTitle || null,
      seoDesc: config.seoDesc || null,
      masterPrompt: config.masterPrompt || null
    }
    
    try {
      const res = await fetch(`${API_BASE}/queue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newItem)
      })
      const data = await res.json()
      if (data.success) {
        showToast("Item berhasil ditambahkan ke Antrean!", "success")
        fetchQueue()
        // Clear input inputs and config textareas so the user can quickly add more products
        setManualBasicTitle('')
        setManualImages([])
        setConfig(prev => ({
          ...prev,
          seoTitle: '',
          seoDesc: '',
          masterPrompt: ''
        }))
      } else {
        showToast("Gagal menambahkan ke antrean", "error")
      }
    } catch (e) {
      showToast("Koneksi gagal", "error")
    }
    setIsAddingToQueue(false)
  }

  const deleteQueueItem = async (itemId) => {
    try {
      const res = await fetch(`${API_BASE}/queue/${itemId}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.success) {
        showToast("Item dihapus dari antrean", "success")
        fetchQueue()
      }
    } catch (e) {
      showToast("Gagal menghapus item", "error")
    }
  }

  const clearQueue = async () => {
    askConfirmation("Hapus seluruh isi antrean?", async () => {
      try {
        const res = await fetch(`${API_BASE}/queue/clear`, { method: 'POST' })
        const data = await res.json()
        if (data.success) {
          showToast("Antrean berhasil dikosongkan", "success")
          fetchQueue()
        }
      } catch (e) {
        showToast("Gagal mengosongkan antrean", "error")
      }
    })
  }
  const [manualImages, setManualImages] = useState([])
  const [manualBasicTitle, setManualBasicTitle] = useState('')
  const [isGeneratingSEO, setIsGeneratingSEO] = useState(false)

  const handleManualPaste = (e) => {
    const items = e.clipboardData.items
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const blob = items[i].getAsFile()
        const reader = new FileReader()
        reader.onload = (event) => setManualImages(prev => [...prev, event.target.result])
        reader.readAsDataURL(blob)
      }
    }
  }

  const handleManualFile = (e) => {
    const files = Array.from(e.target.files)
    files.forEach(file => {
      const reader = new FileReader()
      reader.onload = (event) => setManualImages(prev => [...prev, event.target.result])
      reader.readAsDataURL(file)
    })
  }
  
  const [config, setConfig] = useState({
    startTime: '',
    stopTime: '',
    targetPost: 0,
    mediaType: 'image',
    generateCount: 1,
    spintaxLinks: '',
    geminiApiKeys: '',
    masterPrompt: '',
    seoTitle: '',
    seoDesc: '',
    referenceImages: []
  })

  useEffect(() => {
    fetch(`${API_BASE}/get-config`)
      .then(res => res.json())
      .then(data => {
        if(Object.keys(data).length > 0) {
          setConfig(prev => ({...prev, ...data}))
          if (data.spintaxLinks) {
            setBulkShopeeLink(data.spintaxLinks)
          }
        }
      })
      .catch(err => console.error(err))

    fetchAccounts()
    fetchQueue()

    const ws = new WebSocket(WS_URL)
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'log') {
        setLogs(prev => [...prev, data.message])
      }
    }

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/status`)
        const data = await res.json()
        setFlowCount(data.flowCount || 0)
        if (data.autopilotRunning !== undefined) {
          setIsRunning(data.autopilotRunning)
        }
      } catch(e) {}
      // Poll queue updates in real-time
      fetchQueue()
    }
    checkStatus()
    const intv = setInterval(checkStatus, 5000)

    return () => {
      ws.close()
      clearInterval(intv)
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'prompt') return

    const handleGlobalPaste = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
        return
      }
      const items = e.clipboardData?.items
      if (!items) return
      let hasImage = false
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          hasImage = true
          const blob = items[i].getAsFile()
          const reader = new FileReader()
          reader.onload = (event) => {
            setManualImages(prev => [...prev, event.target.result])
          }
          reader.readAsDataURL(blob)
        }
      }
      if (hasImage) {
        showToast('Gambar referensi berhasil ditempel!', 'success')
      }
    }

    window.addEventListener('paste', handleGlobalPaste)
    return () => {
      window.removeEventListener('paste', handleGlobalPaste)
    }
  }, [activeTab])

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
    askConfirmation(`Hapus akun ${name}?`, async () => {
      try {
        await fetch(`${API_BASE}/accounts/${name}`, { method: 'DELETE' })
        showToast(`Akun ${name} dihapus.`, 'success')
        fetchAccounts()
      } catch(e) {
        showToast('Gagal menghapus akun', 'error')
      }
    })
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

  const generateSEO = async () => {
    if (!manualBasicTitle) return showToast('Harap masukkan Judul Dasar Produk terlebih dahulu!', 'error')
    setIsGeneratingSEO(true)
    try {
      const res = await fetch(`${API_BASE}/generate-seo-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imagesBase64: manualImages, basicTitle: manualBasicTitle })
      })
      const data = await res.json()
      if (data.success) {
        setConfig(prev => ({
          ...prev,
          seoTitle: data.data.seo_title || '',
          seoDesc: data.data.seo_desc || '',
          masterPrompt: data.data.master_prompt || '',
          referenceImages: data.data.reference_images || []
        }))
        showToast('SEO & Master Prompt berhasil diracik!', 'success')
      } else {
        showToast('Gagal: ' + data.error, 'error')
      }
    } catch (e) {
      showToast('Error koneksi ke API', 'error')
    }
    setIsGeneratingSEO(false)
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
          <div className={`nav-item ${activeTab === 'gallery' ? 'active' : ''}`} onClick={() => { setActiveTab('gallery'); fetchGallery(); }}>
            <FolderHeart size={18} /> Gallery
          </div>
          <div className={`nav-item ${activeTab === 'auth' ? 'active' : ''}`} onClick={() => setActiveTab('auth')}>
            <Shield size={18} /> Auth
          </div>
          <div className={`nav-item ${activeTab === 'activity' ? 'active' : ''}`} onClick={() => setActiveTab('activity')}>
            <LayoutDashboard size={18} /> Monitor
          </div>
        </div>

        <div style={{display: 'flex', gap: '16px', alignItems: 'center'}}>
          <div style={{display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: isRunning ? 'var(--success-light)' : 'var(--bg-card)', borderRadius: '20px', fontSize: '12px', fontWeight: 'bold'}}>
            <div style={{width: '8px', height: '8px', borderRadius: '50%', background: isRunning ? 'var(--success)' : 'var(--text-muted)'}}></div>
            <span style={{color: isRunning ? 'var(--success)' : 'var(--text-muted)'}}>{isRunning ? 'ONLINE' : 'STANDBY'}</span>
            <span style={{marginLeft: '4px', paddingLeft: '8px', borderLeft: '1px solid var(--border-color)', color: 'var(--primary)'}}>({flowCount} Flow)</span>
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
          <div>
            <div className="terminal-card">
              <div className="terminal-header">
                <div className="terminal-dots">
                  <span className="dot dot-red"></span>
                  <span className="dot dot-yellow"></span>
                  <span className="dot dot-green"></span>
                </div>
                <div className="terminal-title">live_engine_logs.sh</div>
                <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                  <button className="terminal-clear-btn" onClick={copyLogsToClipboard} title="Salin semua log">
                    {isLogsCopied ? <Check size={13} style={{color: '#22c55e'}} /> : <Copy size={13} />}
                    {isLogsCopied ? 'Copied!' : 'Copy'}
                  </button>
                  <button className="terminal-clear-btn" onClick={() => setLogs([])} title="Hapus Log">
                    <Trash2 size={13} /> Clear
                  </button>
                </div>
              </div>
              <div className="terminal-body">
                {logs.length === 0 ? (
                  <div className="terminal-empty">
                    Sistem dalam keadaan standby. Log akan muncul di sini saat berjalan.
                  </div>
                ) : (
                  logs.map((log, i) => {
                    const match = log.match(/^(\[\d{2}:\d{2}:\d{2}\])\s*(.*)$/)
                    let time = ''
                    let rest = log
                    if (match) {
                      time = match[1]
                      rest = match[2]
                    }

                    const getLogColor = (text) => {
                      const t = text.toLowerCase()
                      if (t.includes('merender') || t.includes('standby')) return '#d97706' // rich amber
                      if (t.includes('download') || t.includes('berhasil') || t.includes('sukses') || t.includes('terbit')) return '#059669' // emerald green
                      if (t.includes('error') || t.includes('gagal') || t.includes('crash')) return '#dc2626' // vivid red
                      if (t.includes('warning')) return '#d97706' // amber
                      if (t.includes('google flow') || t.includes('project id')) return '#0284c7' // cyan blue
                      if (t.includes('sleep engine') || t.includes('menyuntikkan') || t.includes('mengupload') || t.includes('generate judul') || t.includes('watermark') || t.includes('checking schedule')) return '#0284c7' // sky blue
                      if (t.includes('[system]')) return '#2563eb' // royal blue
                      return '#334155' // dark slate
                    }

                    return (
                      <div key={i} className="terminal-row">
                        {time && <span className="terminal-time">{time}</span>}
                        <span style={{ color: getLogColor(rest) }}>{rest}</span>
                      </div>
                    )
                  })
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div>
            <div className="panel">
              <h3><Settings size={20} /> Jadwal Operasional Pintar</h3>
              <div style={{display: 'flex', gap: '20px', flexWrap: 'wrap'}}>
                <div className="form-group" style={{flex: '1 1 200px'}}>
                  <label style={{color: 'var(--primary)', fontWeight: 'bold'}}>Pilih Akun</label>
                  <select 
                    className="form-control" 
                    style={{borderColor: 'var(--primary)', borderWidth: '2px'}}
                    value={config.targetAccount || ''} 
                    onChange={e => setConfig({...config, targetAccount: e.target.value})}
                  >
                    <option value="">Pilih Akun...</option>
                    {accountsList.filter(a => a.status === 'valid').map((acc, i) => (
                      <option key={i} value={acc.name}>{acc.name} (Valid)</option>
                    ))}
                  </select>
                </div>
                 
                 <div className="form-group" style={{flex: '1 1 180px'}}>
                   <label>Browser Pinterest</label>
                   <select 
                     className="form-control" 
                     value={config.pinterestBrowserMode || 'visible'} 
                     onChange={e => {
                       const val = e.target.value;
                       setConfig({...config, pinterestBrowserMode: val});
                       fetch(`${API_BASE}/api/save-config`, {
                         method: 'POST',
                         headers: { 'Content-Type': 'application/json' },
                         body: JSON.stringify({...config, pinterestBrowserMode: val})
                       });
                     }}
                   >
                     <option value="visible">Tampilkan (Visible)</option>
                     <option value="headless">Latar Belakang (Headless)</option>
                   </select>
                 </div>

                 <div className="form-group" style={{flex: '1 1 120px'}}>
                  <label>Jam Mulai</label>
                  <input type="time" className="form-control" value={config.startTime} onChange={e => setConfig({...config, startTime: e.target.value})} />
                </div>
                <div className="form-group" style={{flex: '1 1 120px'}}>
                  <label>Jam Berhenti</label>
                  <input type="time" className="form-control" value={config.stopTime} onChange={e => setConfig({...config, stopTime: e.target.value})} />
                </div>
                 <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Type Media</label>
                  <div className="radio-group">
                    <label className="radio-label">
                      <input type="radio" name="mediaType" value="image" checked={config.mediaType === 'image'} onChange={e => setConfig({...config, mediaType: e.target.value})} /> Foto
                    </label>
                    <label className="radio-label">
                      <input type="radio" name="mediaType" value="video" checked={config.mediaType === 'video'} onChange={e => setConfig({...config, mediaType: e.target.value})} /> Video
                    </label>
                  </div>
                </div>
                <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Jumlah Gambar (FOTO)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    min="1"
                    max="1000"
                    value={config.generateCount || 1} 
                    onChange={e => {
                      const val = parseInt(e.target.value) || 1;
                      setConfig({...config, generateCount: val});
                      fetch(`${API_BASE}/api/save-config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({...config, generateCount: val})
                      });
                    }} 
                  />
                </div>
                 <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Jeda Posting (Detik)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    min="1"
                    value={config.sleepInterval || 10} 
                    onChange={e => {
                      const val = parseInt(e.target.value) || 10;
                      setConfig({...config, sleepInterval: val});
                      fetch(`${API_BASE}/api/save-config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({...config, sleepInterval: val})
                      });
                    }} 
                  />
                </div>

                <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Ratio Gambar (FOTO)</label>
                  <select 
                    className="form-control" 
                    value={config.imageRatio || '9:16'} 
                    onChange={e => {
                      const val = e.target.value;
                      setConfig({...config, imageRatio: val});
                      fetch(`${API_BASE}/api/save-config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({...config, imageRatio: val})
                      });
                    }}
                  >
                    <option value="9:16">9:16 (Pinterest/TikTok Reel)</option>
                    <option value="1:1">1:1 (Square)</option>
                    <option value="16:9">16:9 (Landscape)</option>
                  </select>
                </div>

                <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Ratio Video (VIDEO)</label>
                  <select 
                    className="form-control" 
                    value={config.videoRatio || '9:16'} 
                    onChange={e => {
                      const val = e.target.value;
                      setConfig({...config, videoRatio: val});
                      fetch(`${API_BASE}/api/save-config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({...config, videoRatio: val})
                      });
                    }}
                  >
                    <option value="9:16">9:16 (Vertical)</option>
                    <option value="16:9">16:9 (Landscape)</option>
                  </select>
                </div>

                <div className="form-group" style={{flex: '1 1 150px'}}>
                  <label>Durasi Video (VIDEO)</label>
                  <select 
                    className="form-control" 
                    value={config.videoDuration || '10s'} 
                    onChange={e => {
                      const val = e.target.value;
                      setConfig({...config, videoDuration: val});
                      fetch(`${API_BASE}/api/save-config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({...config, videoDuration: val})
                      });
                    }}
                  >
                    <option value="4s">4 detik</option>
                    <option value="6s">6 detik</option>
                    <option value="8s">8 detik</option>
                    <option value="10s">10 detik</option>
                  </select>
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
                    <th style={{width: '50px'}}>No.</th>
                    <th>Nama Akun</th>
                    <th>Status Cookies</th>
                    <th>Last Checked</th>
                    <th style={{textAlign: 'right'}}>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {accountsList.map((acc, idx) => (
                    <tr key={idx}>
                      <td style={{color: 'var(--text-muted)'}}>{idx + 1}</td>
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
                        <button className="btn btn-outline" style={{padding: '6px 12px', fontSize: '12px', borderColor: 'var(--error)', color: 'var(--error)'}} onClick={() => handleDeleteAccount(acc.name)} title="Hapus Akun">
                          <Trash2 size={14} />
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
            <div className="grid-2">
              <div className="panel" style={{border: '1px solid var(--primary)', background: 'var(--bg-app)', margin: 0}}>
                <h3 style={{color: 'var(--primary)', marginBottom: '16px'}}>✨ Image Reference to Master Prompt (SEO Optimized)</h3>
              <div style={{display: 'flex', flexDirection: 'column', gap: '20px'}}>
                {/* Drag and Drop / Paste Area - Now Full Width and Sleeker */}
                <div 
                  style={{
                    width: '100%', 
                    minHeight: '120px', 
                    border: '2px dashed var(--primary)', 
                    borderRadius: '12px', 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    position: 'relative',
                    overflow: 'hidden',
                    backgroundColor: 'rgba(92, 102, 242, 0.05)',
                    padding: '20px',
                    transition: 'all 0.3s ease',
                    cursor: 'pointer'
                  }}
                  onPaste={handleManualPaste}
                  onClick={() => document.getElementById('hiddenFileInput').click()}
                >
                  {manualImages.length > 0 ? (
                    <div style={{display: 'flex', flexWrap: 'wrap', gap: '12px', width: '100%', justifyContent: 'center', alignItems: 'center'}}>
                      {manualImages.map((img, idx) => (
                        <div key={idx} style={{position: 'relative', height: '90px', width: '90px', flexShrink: 0, borderRadius: '8px', overflow: 'hidden', boxShadow: '0 4px 10px rgba(0,0,0,0.15)'}}>
                          <img src={img} alt={`Ref ${idx}`} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
                          <button 
                            onClick={(e) => {
                              e.stopPropagation();
                              const newImgs = [...manualImages];
                              newImgs.splice(idx, 1);
                              setManualImages(newImgs);
                            }}
                            style={{position: 'absolute', top: '4px', right: '4px', background: 'rgba(239, 35, 60, 0.9)', color: 'white', border: 'none', borderRadius: '50%', width: '18px', height: '18px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 'bold'}}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <div 
                        style={{
                          height: '90px', 
                          width: '90px', 
                          display: 'flex', 
                          flexDirection: 'column',
                          alignItems: 'center', 
                          justifyContent: 'center', 
                          border: '2px dashed var(--primary)', 
                          borderRadius: '8px', 
                          cursor: 'pointer',
                          backgroundColor: 'rgba(92, 102, 242, 0.1)',
                          color: 'var(--primary)'
                        }}
                        title="Tambah Foto"
                      >
                        <UploadCloud size={24} />
                        <span style={{fontSize: '10px', marginTop: '4px', fontWeight: '600'}}>Tambah</span>
                      </div>
                    </div>
                  ) : (
                    <div style={{textAlign: 'center', color: 'var(--text-muted)'}}>
                      <UploadCloud size={40} style={{color: 'var(--primary)', marginBottom: '8px', opacity: 0.8}} />
                      <p style={{fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px'}}>Klik untuk Unggah atau Paste (Ctrl+V) Gambar Referensi</p>
                      <p style={{fontSize: '12px', opacity: 0.7}}>Mendukung banyak gambar produk sekaligus</p>
                    </div>
                  )}
                  <input id="hiddenFileInput" type="file" multiple accept="image/*" style={{display: 'none'}} onChange={handleManualFile} />
                </div>
                
                {/* Form Inputs Flex Row - Sleek & Fully Responsive */}
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '16px',
                  alignItems: 'end'
                }}>
                  <div className="form-group" style={{margin: 0, flex: '3 1 300px'}}>
                    <label style={{fontWeight: '600', fontSize: '12px'}}>Judul Dasar (Shopee dll)</label>
                    <input type="text" className="form-control" value={manualBasicTitle} onChange={e => setManualBasicTitle(e.target.value)} placeholder="Contoh: Meja Kerja Minimalis Gaya Industrial..." />
                  </div>
                  
                  <div className="form-group" style={{margin: 0, flex: '2 1 200px'}}>
                    <label style={{fontWeight: '600', fontSize: '12px'}}>Link Affiliate (Shopee/TikTok)</label>
                    <input type="text" className="form-control" value={config.spintaxLinks} onChange={e => setConfig({...config, spintaxLinks: e.target.value})} placeholder="https://shope.ee/..." />
                  </div>

                  <button 
                    className="btn btn-primary" 
                    style={{
                      height: '42px', 
                      padding: '0 24px', 
                      fontSize: '14px', 
                      fontWeight: 'bold', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '8px', 
                      flex: '1 1 140px',
                      whiteSpace: 'nowrap'
                    }} 
                    onClick={generateSEO} 
                    disabled={isGeneratingSEO}
                  >
                    {isGeneratingSEO ? <RefreshCw size={16} className="spin" /> : <Wand2 size={16} />} 
                    {isGeneratingSEO ? 'Generating...' : 'Generate SEO'}
                  </button>

                  <button 
                    className="btn btn-outline" 
                    style={{
                      height: '42px', 
                      padding: '0 24px', 
                      fontSize: '14px', 
                      fontWeight: 'bold', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      gap: '8px', 
                      flex: '1 1 140px',
                      whiteSpace: 'nowrap',
                      borderColor: 'var(--primary)',
                      color: 'var(--primary)'
                    }} 
                    onClick={addToQueue} 
                    disabled={isAddingToQueue}
                  >
                    {isAddingToQueue ? <RefreshCw size={16} className="spin" /> : <UploadCloud size={16} />} 
                    Queue Posting
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: AI Auto-Generate Bulk Ideas */}
              <div className="panel" style={{border: '1px solid var(--success)', background: 'var(--bg-app)', margin: 0, display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>
                <div>
                  <h3 style={{color: 'var(--success)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <span>💡</span> AI Auto-Generate Antrean dari Tema
                  </h3>
                  <p style={{fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px', lineHeight: '1.5'}}>
                    AI akan otomatis memikirkan beberapa ide judul produk unik berdasarkan tema utama Bos, lalu merancang SEO pinterest & prompt visualnya secara bulk untuk dimasukkan ke antrean.
                  </p>
                  <div style={{display: 'flex', flexDirection: 'column', gap: '16px'}}>
                    <div>
                      <label style={{display: 'block', fontSize: '11px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px'}}>TEMA UTAMA (TOPIK)</label>
                      <input 
                        type="text" 
                        className="form-control" 
                        placeholder="Contoh: meja belajar estetik dan kokoh" 
                        style={{width: '100%', boxSizing: 'border-box'}}
                        value={bulkTheme}
                        onChange={e => setBulkTheme(e.target.value)}
                      />
                    </div>
                    
                    <div style={{display: 'flex', gap: '16px'}}>
                      <div style={{flex: 3}}>
                        <label style={{display: 'block', fontSize: '11px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px'}}>LINK AFFILIATE SHOPEE</label>
                        <input 
                          type="text" 
                          className="form-control" 
                          placeholder="Link affiliate Shopee..." 
                          style={{width: '100%', boxSizing: 'border-box'}}
                          value={bulkShopeeLink}
                          onChange={e => setBulkShopeeLink(e.target.value)}
                        />
                      </div>

                      <div style={{flex: 1}}>
                        <label style={{display: 'block', fontSize: '11px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', whiteSpace: 'nowrap'}}>JUMLAH POSTINGAN</label>
                        <input 
                          type="number" 
                          min="1" 
                          max="20" 
                          className="form-control" 
                          style={{width: '100%', boxSizing: 'border-box'}}
                          value={bulkCount}
                          onChange={e => setBulkCount(parseInt(e.target.value) || 5)}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div style={{marginTop: '20px'}}>
                  <button 
                    type="button"
                    className="btn btn-primary" 
                    style={{
                      width: '100%', 
                      height: '42px', 
                      fontSize: '14px', 
                      fontWeight: 'bold',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      background: 'linear-gradient(135deg, #06d6a0 0%, #2ec4b6 100%)',
                      boxShadow: '0 4px 15px rgba(46, 196, 182, 0.35)',
                      border: 'none'
                    }}
                    onClick={generateBulkQueueItems}
                    disabled={isGeneratingBulk}
                  >
                    {isGeneratingBulk ? <RefreshCw size={16} className="spin" /> : <Zap size={16} />}
                    {isGeneratingBulk ? 'AI sedang merancang promosi...' : 'AI Auto-Generate ke Antrean'}
                  </button>
                </div>
              </div>
            </div>

            {/* Bulk Queue Panel */}
            <div className="panel" style={{
              marginTop: '24px', 
              border: '1px solid var(--panel-border)',
              background: 'var(--panel-bg)',
              borderRadius: '16px',
              padding: '20px'
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px'}}>
                <h3 style={{margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 'bold'}}>
                  <span>📋</span> Antrean Posting Massal ({queueItems.length} Produk)
                </h3>
                {queueItems.length > 0 && (
                  <button className="btn btn-action-delete" style={{padding: '4px 12px', fontSize: '12px'}} onClick={clearQueue}>
                    Kosongkan Antrean
                  </button>
                )}
              </div>
              
              {queueItems.length === 0 ? (
                <div style={{textAlign: 'center', padding: '30px 20px', color: 'var(--text-muted)'}}>
                  <p style={{fontSize: '13px', margin: 0}}>Belum ada produk dalam antrean massal.</p>
                  <p style={{fontSize: '12px', marginTop: '6px', opacity: 0.8}}>Masukkan foto dan judul di atas, lalu klik "Queue Posting" untuk menumpuk antrean.</p>
                </div>
              ) : (
                <div style={{display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px'}}>
                  {queueItems.map((item, idx) => {
                    let statusColor = 'var(--text-muted)';
                    let statusBg = 'rgba(0,0,0,0.05)';
                    if (item.status === 'running') {
                      statusColor = '#8b5cf6';
                      statusBg = 'rgba(139, 92, 246, 0.1)';
                    } else if (item.status === 'success') {
                      statusColor = 'var(--success)';
                      statusBg = 'rgba(46, 196, 182, 0.1)';
                    } else if (item.status === 'failed') {
                      statusColor = 'var(--danger)';
                      statusBg = 'rgba(239, 35, 60, 0.1)';
                    }
                    
                    return (
                      <div key={item.id} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid var(--panel-border)',
                        borderRadius: '10px',
                        gap: '12px'
                      }}>
                        <div style={{display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0}}>
                          {/* Mini Thumbnail Grid */}
                          <div style={{display: 'flex', gap: '4px', flexShrink: 0}}>
                            {item.referenceImages && item.referenceImages.slice(0, 3).map((img, i) => (
                              <img key={i} src={img} alt="" style={{width: '28px', height: '28px', borderRadius: '4px', objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)'}} />
                            ))}
                            {item.referenceImages && item.referenceImages.length > 3 && (
                              <div style={{width: '28px', height: '28px', borderRadius: '4px', background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '9px', fontWeight: 'bold'}}>
                                +{item.referenceImages.length - 3}
                              </div>
                            )}
                          </div>
                          
                          <div style={{minWidth: 0, flex: 1}}>
                            <p style={{fontSize: '13px', fontWeight: '600', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                              {item.basicTitle}
                            </p>
                            <p style={{fontSize: '11px', color: 'var(--text-muted)', margin: '2px 0 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                              {item.spintaxLinks || "Tanpa Link Affiliate"}
                            </p>
                          </div>
                        </div>
                        
                        <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
                          <span style={{
                            padding: '4px 10px',
                            borderRadius: '20px',
                            fontSize: '10px',
                            fontWeight: 'bold',
                            color: statusColor,
                            background: statusBg,
                            textTransform: 'uppercase'
                          }}>
                            {item.status}
                          </span>
                          <button 
                            className="btn btn-action-edit" 
                            style={{padding: '6px', borderRadius: '50%', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center'}}
                            onClick={() => handleEditQueueItem(item)}
                            title="Edit"
                          >
                            <Edit3 size={12} />
                          </button>
                          <button 
                            className="btn btn-action-delete" 
                            style={{padding: '6px', borderRadius: '50%', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center'}}
                            onClick={() => deleteQueueItem(item.id)}
                            title="Hapus"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* AI Master Prompt Luxury Panel */}
            <div className="panel" style={{
              marginTop: '24px', 
              border: '1px solid rgba(139, 92, 246, 0.25)', 
              background: 'linear-gradient(135deg, var(--panel-bg), rgba(139, 92, 246, 0.03))',
              position: 'relative',
              borderRadius: '16px',
              padding: '20px'
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px'}}>
                <h3 style={{color: 'rgb(139, 92, 246)', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 'bold'}}>
                  <span style={{display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#8b5cf6', boxShadow: '0 0 8px #8b5cf6'}}></span>
                  AI Master Prompt (Kirim ke Flow)
                </h3>
                <button 
                  className="btn btn-outline" 
                  style={{padding: '4px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px'}}
                  onClick={() => handleCopyText(config.masterPrompt, 'Master Prompt')}
                >
                  {copiedField === 'Master Prompt' ? <Check size={14} style={{color: 'var(--success)'}} /> : <Copy size={14} />}
                  {copiedField === 'Master Prompt' ? 'Disalin' : 'Salin Prompt'}
                </button>
              </div>
              <textarea 
                className="form-control" 
                rows="6" 
                value={config.masterPrompt} 
                onChange={e => setConfig({...config, masterPrompt: e.target.value})} 
                placeholder="Master prompt utuh dari AI..."
                style={{
                  fontFamily: '"Fira Code", "JetBrains Mono", source-code-pro, Menlo, Monaco, Consolas, monospace',
                  fontSize: '13px',
                  lineHeight: '1.6',
                  background: 'rgba(255,255,255,0.03)',
                  borderColor: 'rgba(139, 92, 246, 0.2)',
                  color: 'var(--text-primary)',
                  boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)'
                }}
              />
            </div>

            {/* Pinterest SEO Metadata Luxury Panel */}
            <div className="panel" style={{
              marginTop: '24px', 
              borderLeft: '4px solid #E60023',
              borderTop: '1px solid rgba(230, 0, 35, 0.1)',
              borderRight: '1px solid rgba(230, 0, 35, 0.1)',
              borderBottom: '1px solid rgba(230, 0, 35, 0.1)',
              background: 'linear-gradient(135deg, var(--panel-bg), rgba(230, 0, 35, 0.02))',
              borderRadius: '16px',
              padding: '20px'
            }}>
              <h3 style={{color: '#E60023', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 'bold'}}>
                <span>📌</span> Pinterest SEO Metadata
              </h3>
              
              <div className="form-group" style={{position: 'relative'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px'}}>
                  <label style={{margin: 0, fontWeight: '600', fontSize: '12px'}}>Judul SEO Pinterest</label>
                  <button 
                    className="btn btn-outline" 
                    style={{padding: '2px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px', border: 'none', background: 'transparent'}}
                    onClick={() => handleCopyText(config.seoTitle, 'Judul SEO')}
                  >
                    {copiedField === 'Judul SEO' ? <Check size={12} style={{color: 'var(--success)'}} /> : <Copy size={12} />}
                    {copiedField === 'Judul SEO' ? 'Disalin' : 'Salin'}
                  </button>
                </div>
                <input 
                  type="text" 
                  className="form-control" 
                  value={config.seoTitle} 
                  onChange={e => setConfig({...config, seoTitle: e.target.value})} 
                  style={{
                    fontWeight: '500',
                    fontSize: '14px',
                    borderColor: 'rgba(230, 0, 35, 0.15)',
                    background: 'rgba(255,255,255,0.02)'
                  }}
                />
              </div>
              
              <div className="form-group" style={{marginBottom: 0, position: 'relative'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px'}}>
                  <label style={{margin: 0, fontWeight: '600', fontSize: '12px'}}>Deskripsi SEO Pinterest (dengan hashtag)</label>
                  <button 
                    className="btn btn-outline" 
                    style={{padding: '2px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px', border: 'none', background: 'transparent'}}
                    onClick={() => handleCopyText(config.seoDesc, 'Deskripsi SEO')}
                  >
                    {copiedField === 'Deskripsi SEO' ? <Check size={12} style={{color: 'var(--success)'}} /> : <Copy size={12} />}
                    {copiedField === 'Deskripsi SEO' ? 'Disalin' : 'Salin'}
                  </button>
                </div>
                <textarea 
                  className="form-control" 
                  rows="4" 
                  value={config.seoDesc} 
                  onChange={e => setConfig({...config, seoDesc: e.target.value})}
                  style={{
                    lineHeight: '1.5',
                    borderColor: 'rgba(230, 0, 35, 0.15)',
                    background: 'rgba(255,255,255,0.02)'
                  }}
                />
              </div>
            </div>

            <div style={{display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px'}}>
              {editingQueueItemId ? (
                <>
                  <button 
                    type="button"
                    className="btn btn-action-delete" 
                    onClick={cancelEditQueueItem}
                    style={{
                      padding: '12px 24px',
                      fontSize: '14px',
                      fontWeight: 'bold',
                      borderRadius: '30px'
                    }}
                  >
                    Batal Edit
                  </button>
                  <button 
                    type="button"
                    className="btn btn-primary" 
                    onClick={saveEditedQueueItemDirect}
                    style={{
                      padding: '12px 28px',
                      fontSize: '14px',
                      fontWeight: 'bold',
                      boxShadow: '0 4px 15px rgba(139, 92, 246, 0.35)',
                      borderRadius: '30px'
                    }}
                  >
                    Update Antrean
                  </button>
                </>
              ) : (
                <button 
                  className="btn btn-primary" 
                  onClick={saveConfig}
                  style={{
                    padding: '12px 28px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    boxShadow: '0 4px 15px rgba(99, 102, 241, 0.35)',
                    borderRadius: '30px'
                  }}
                >
                  Simpan Konfigurasi
                </button>
              )}
            </div>
          </div>
        )}

        {activeTab === 'gallery' && (
          <div>
            <div className="panel" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px'}}>
              <h3 style={{margin: 0}}>🎨 Gallery Hasil Render ({galleryFiles.length} item)</h3>
              
              <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
                {galleryFiles.length > 0 && (
                  <>
                    <button 
                      type="button"
                      className="btn btn-outline" 
                      style={{padding: '10px 20px', fontSize: '13px'}}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        selectAllGalleryItems()
                      }}
                    >
                      {selectedGalleryItems.length === galleryFiles.length ? 'Batal Pilih' : 'Pilih Semua'}
                    </button>
                    
                    {selectedGalleryItems.length > 0 && (
                      <button 
                        type="button"
                        className="btn btn-danger" 
                        style={{padding: '10px 20px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px'}}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          deleteSelectedGalleryItems()
                        }}
                      >
                        <Trash2 size={14} /> Hapus Terpilih ({selectedGalleryItems.length})
                      </button>
                    )}
                  </>
                )}
                
                <button 
                  type="button"
                  className="btn btn-outline" 
                  style={{padding: '10px 20px', fontSize: '13px'}} 
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    fetchGallery()
                  }} 
                  disabled={isLoadingGallery}
                >
                  <RefreshCw size={14} className={isLoadingGallery ? "spin" : ""} /> Refresh Gallery
                </button>
              </div>
            </div>
            
            {galleryFiles.length === 0 ? (
              <div className="panel" style={{textAlign: 'center', padding: '50px 20px', color: 'var(--text-muted)'}}>
                <ImageIcon size={48} style={{opacity: 0.3, marginBottom: '16px'}} />
                <p>Belum ada foto atau video hasil render di Gallery.</p>
                <p style={{fontSize: '13px', marginTop: '8px'}}>Mulai autopilot untuk merender media baru!</p>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: '20px',
                marginBottom: '24px'
              }}>
                {galleryFiles.map((file, idx) => (
                  <div key={idx} className="panel" style={{
                    padding: '12px',
                    margin: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                    overflow: 'hidden',
                    background: 'var(--panel-bg)',
                    borderRadius: '16px',
                    border: selectedGalleryItems.includes(file.filename) ? '1px solid var(--primary)' : '1px solid var(--panel-border)',
                    boxShadow: selectedGalleryItems.includes(file.filename) ? '0 0 10px rgba(99, 102, 241, 0.15)' : 'var(--panel-shadow)',
                    transition: 'all 0.2s ease'
                  }}>
                    <div 
                      onClick={(e) => {
                        if (e.target.type === 'checkbox') return
                        setPreviewIndex(idx)
                      }}
                      style={{
                        width: '100%',
                        height: '240px',
                        borderRadius: '12px',
                        overflow: 'hidden',
                        backgroundColor: 'rgba(0,0,0,0.05)',
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'zoom-in'
                      }}
                    >
                      {/* Floating Checkbox */}
                      <input 
                        type="checkbox" 
                        checked={selectedGalleryItems.includes(file.filename)}
                        onChange={(e) => {
                          e.stopPropagation()
                          toggleSelectGalleryItem(file.filename)
                        }}
                        style={{
                          position: 'absolute',
                          top: '10px',
                          right: '10px',
                          width: '18px',
                          height: '18px',
                          cursor: 'pointer',
                          zIndex: 10,
                          accentColor: 'var(--primary)',
                          boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                        }}
                      />
                      {file.type === 'video' ? (
                        <div style={{width: '100%', height: '100%', position: 'relative'}}>
                          <video 
                            src={`http://127.0.0.1:8015${file.url}`} 
                            style={{width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none'}}
                          />
                          {/* Floating Play Indicator */}
                          <div style={{
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                            background: 'rgba(0, 0, 0, 0.6)',
                            borderRadius: '50%',
                            padding: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'white',
                            boxShadow: '0 4px 10px rgba(0,0,0,0.3)'
                          }}>
                            <Film size={18} />
                          </div>
                        </div>
                      ) : (
                        <img 
                          src={`http://127.0.0.1:8015${file.url}`} 
                          alt={file.filename} 
                          style={{width: '100%', height: '100%', objectFit: 'cover'}} 
                        />
                      )}
                      
                      {/* Floating type indicator */}
                      <span style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        padding: '4px 8px',
                        background: 'rgba(0,0,0,0.6)',
                        color: 'white',
                        borderRadius: '20px',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        zIndex: 5
                      }}>
                        {file.type === 'video' ? <Film size={10} /> : <ImageIcon size={10} />}
                        {file.type.toUpperCase()}
                      </span>

                      {/* Floating Posted Badge */}
                      {file.meta && file.meta.posted && (
                        <span style={{
                          position: 'absolute',
                          top: '8px',
                          left: '75px',
                          padding: '4px 8px',
                          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                          color: 'white',
                          borderRadius: '20px',
                          fontSize: '10px',
                          fontWeight: 'bold',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          boxShadow: '0 2px 5px rgba(0,0,0,0.3)',
                          zIndex: 5
                        }}>
                          🏆 Posted
                        </span>
                      )}
                    </div>
                    
                    <div style={{marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                      <div style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '8px', flex: 1}}>
                        <p style={{fontSize: '13px', fontWeight: '600', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis'}} title={file.meta && file.meta.posted_title ? file.meta.posted_title : file.filename}>
                          {file.meta && file.meta.posted_title ? file.meta.posted_title : file.filename}
                        </p>
                        <p style={{fontSize: '11px', color: 'var(--text-muted)', margin: '4px 0 0 0'}}>
                          {(file.size / (1024 * 1024)).toFixed(2)} MB • {new Date(file.created_at * 1000).toLocaleDateString()}
                        </p>
                      </div>
                      
                      <div style={{display: 'flex', gap: '4px'}}>
                        <a 
                          href={`http://127.0.0.1:8015${file.url}`} 
                          download={file.filename} 
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-outline"
                          style={{
                            padding: '8px',
                            borderRadius: '50%',
                            width: '32px',
                            height: '32px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                          title="Download"
                        >
                          <Download size={14} />
                        </a>
                        <button 
                          className="btn btn-danger" 
                          onClick={() => deleteGalleryItem(file.filename)}
                          style={{
                            padding: '8px',
                            borderRadius: '50%',
                            width: '32px',
                            height: '32px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'rgba(239, 35, 60, 0.1)',
                            color: 'var(--danger)'
                          }}
                          title="Hapus"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Lightbox Preview Modal */}
      {previewIndex !== null && galleryFiles[previewIndex] && (() => {
        const file = galleryFiles[previewIndex];
        return (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.95)',
            zIndex: 10000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(8px)',
            transition: 'all 0.3s ease'
          }}>
            {/* Close Button */}
            <button 
              onClick={() => setPreviewIndex(null)}
              style={{
                position: 'absolute',
                top: '24px',
                right: '24px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'white',
                borderRadius: '50%',
                width: '42px',
                height: '42px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s',
                zIndex: 10010
              }}
              title="Close (Esc)"
            >
              <XCircle size={22} />
            </button>

            {/* Split Screen Container */}
            <div style={{
              display: 'flex',
              width: '90%',
              maxWidth: '1200px',
              height: '80vh',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '40px'
            }}>
              
              {/* Media Content Box (Left Side) */}
              <div style={{
                flex: '1 1 50%',
                maxHeight: '80vh',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative'
              }}>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%' }}>
                  {/* Left Nav Arrow */}
                  {previewIndex > 0 && (
                    <button 
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setPreviewIndex(previewIndex - 1)
                      }}
                      style={{
                        position: 'absolute',
                        left: '-60px',
                        background: 'rgba(15, 23, 42, 0.85)',
                        border: '1px solid rgba(255,255,255,0.15)',
                        color: 'white',
                        borderRadius: '50%',
                        width: '44px',
                        height: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        zIndex: 10020,
                        backdropFilter: 'blur(4px)',
                        boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                        transition: 'all 0.2s'
                      }}
                      title="Previous (Left Arrow)"
                    >
                      <span style={{fontSize: '24px', fontWeight: 'bold', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>‹</span>
                    </button>
                  )}

                  {/* Right Nav Arrow */}
                  {previewIndex < galleryFiles.length - 1 && (
                    <button 
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setPreviewIndex(previewIndex + 1)
                      }}
                      style={{
                        position: 'absolute',
                        right: '-60px',
                        background: 'rgba(15, 23, 42, 0.85)',
                        border: '1px solid rgba(255,255,255,0.15)',
                        color: 'white',
                        borderRadius: '50%',
                        width: '44px',
                        height: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        zIndex: 10020,
                        backdropFilter: 'blur(4px)',
                        boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                        transition: 'all 0.2s'
                      }}
                      title="Next (Right Arrow)"
                    >
                      <span style={{fontSize: '24px', fontWeight: 'bold', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>›</span>
                    </button>
                  )}

                  {file.type === 'video' ? (
                    <video 
                      src={`http://127.0.0.1:8001${file.url}`} 
                      controls 
                      autoPlay
                      style={{
                        maxWidth: '100%',
                        maxHeight: '65vh',
                        borderRadius: '16px',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        objectFit: 'contain'
                      }}
                    />
                  ) : (
                    <img 
                      src={`http://127.0.0.1:8001${file.url}`} 
                      alt={file.filename} 
                      style={{
                        maxWidth: '100%',
                        maxHeight: '65vh',
                        borderRadius: '16px',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        objectFit: 'contain'
                      }}
                    />
                  )}
                </div>

                <div style={{marginTop: '15px', color: 'rgba(255,255,255,0.4)', fontSize: '12px'}}>
                  Item {previewIndex + 1} dari {galleryFiles.length}
                </div>
              </div>

              {/* Detail Info Panel (Right Side) */}
              <div style={{
                flex: '1 1 50%',
                background: 'rgba(30, 41, 59, 0.4)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '24px',
                padding: '30px',
                maxHeight: '80vh',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '24px',
                boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
                backdropFilter: 'blur(10px)',
                textAlign: 'left'
              }}>
                <div>
                  <h3 style={{margin: '0 0 10px 0', fontSize: '20px', fontWeight: 'bold', color: '#fff'}}>
                    {file.meta && file.meta.posted_title ? file.meta.posted_title : file.filename}
                  </h3>
                  <p style={{margin: 0, fontSize: '12px', color: 'rgba(255,255,255,0.4)'}}>
                    File: {file.filename} • {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>

                <hr style={{border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)', margin: 0}} />

                {/* Status Badge */}
                <div>
                  <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Status Posting</label>
                  {file.meta && file.meta.posted ? (
                    <div style={{display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', padding: '8px 16px', borderRadius: '50px', fontSize: '13px', fontWeight: 'bold', border: '1px solid rgba(16, 185, 129, 0.2)'}}>
                      🏆 Terposting ke Pinterest
                    </div>
                  ) : (
                    <div style={{display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', padding: '8px 16px', borderRadius: '50px', fontSize: '13px', fontWeight: 'bold', border: '1px solid rgba(245, 158, 11, 0.2)'}}>
                      ⏳ Belum Terposting / Render Only
                    </div>
                  )}
                </div>

                {/* Pinterest Details if Posted */}
                {file.meta && file.meta.posted && (
                  <>
                    <div>
                      <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Akun Pinterest</label>
                      <p style={{margin: 0, fontSize: '14px', color: '#fff', fontWeight: '500'}}>{file.meta.posted_account || '-'}</p>
                    </div>

                    <div>
                      <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Tanggal Posting</label>
                      <p style={{margin: 0, fontSize: '14px', color: '#fff'}}>{new Date(file.meta.posted_at * 1000).toLocaleString('id-ID')}</p>
                    </div>

                    <div>
                      <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Deskripsi Pin</label>
                      <p style={{margin: 0, fontSize: '13px', color: 'rgba(255,255,255,0.7)', lineHeight: '1.6', background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.04)', whiteSpace: 'pre-wrap'}}>{file.meta.posted_desc || '-'}</p>
                    </div>

                    {file.meta.posted_link && (
                      <div>
                        <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Link Tujuan (Affiliate)</label>
                        <div>
                          <a 
                            href={file.meta.posted_link} 
                            target="_blank" 
                            rel="noreferrer"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              color: 'var(--primary)',
                              fontSize: '13px',
                              fontWeight: '600',
                              textDecoration: 'none',
                              background: 'rgba(99, 102, 241, 0.1)',
                              padding: '8px 14px',
                              borderRadius: '8px',
                              border: '1px solid rgba(99, 102, 241, 0.2)',
                              transition: 'all 0.2s'
                            }}
                          >
                            Buka Link Produk ➔
                          </a>
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* AI Prompt */}
                <div>
                  <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Master Prompt AI</label>
                  <p style={{
                    margin: 0, 
                    fontSize: '13px', 
                    color: 'rgba(255,255,255,0.7)', 
                    lineHeight: '1.6', 
                    fontFamily: 'monospace',
                    background: 'rgba(0,0,0,0.2)', 
                    padding: '12px', 
                    borderRadius: '12px',
                    border: '1px solid rgba(255,255,255,0.04)',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {file.meta && file.meta.prompt ? file.meta.prompt : 'Tidak ada catatan prompt.'}
                  </p>
                </div>

                <div>
                  <label style={{display: 'block', fontSize: '12px', fontWeight: 'bold', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Waktu Render File</label>
                  <p style={{margin: 0, fontSize: '13px', color: 'rgba(255,255,255,0.5)'}}>{new Date(file.created_at * 1000).toLocaleString('id-ID')}</p>
                </div>
              </div>

            </div>
          </div>
        );
      })()}

      {/* Premium Confirm Modal */}
      {confirmModal.show && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(10px)',
          zIndex: 20000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{
            background: '#151c2c',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '24px',
            width: '420px',
            padding: '30px',
            textAlign: 'center',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px'
          }}>
            <div style={{
              background: 'rgba(239, 35, 60, 0.1)',
              borderRadius: '50%',
              width: '64px',
              height: '64px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--danger)'
            }}>
              <AlertTriangle size={32} />
            </div>

            <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
              <h3 style={{margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#fff'}}>Konfirmasi Tindakan</h3>
              <p style={{margin: 0, fontSize: '14px', color: '#cbd5e1', lineHeight: '1.5'}}>{confirmModal.message}</p>
            </div>

            <div style={{display: 'flex', gap: '12px', width: '100%', marginTop: '10px'}}>
              <button 
                type="button"
                className="btn" 
                onClick={() => setConfirmModal({ show: false, message: '', onConfirm: null })}
                style={{
                  flex: 1, 
                  padding: '12px', 
                  borderRadius: '12px', 
                  fontSize: '14px', 
                  fontWeight: 'bold', 
                  color: '#fff', 
                  background: 'rgba(255,255,255,0.08)', 
                  border: '1px solid rgba(255,255,255,0.15)',
                  cursor: 'pointer'
                }}
              >
                Batal
              </button>
              <button 
                type="button"
                className="btn btn-danger" 
                onClick={confirmModal.onConfirm}
                style={{
                  flex: 1, 
                  padding: '12px', 
                  borderRadius: '12px', 
                  fontSize: '14px', 
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Ya, Lanjutkan
              </button>
            </div>
          </div>
        </div>
      )}

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
