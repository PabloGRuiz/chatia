import { useState, useEffect, useRef } from 'react'
import { Send, Folder, Database, Settings, ShieldAlert, Bot, LogOut, Lock, Mail, Users, FileText, Plus, Trash2, ChevronRight, ChevronDown, Sun, Moon, Edit2, XCircle, CheckSquare, Square, Key, Search, Eye, Download } from 'lucide-react'

// Intercept all fetch requests to auto-logout on expired/invalid JWT token
const originalFetch = window.fetch;
window.fetch = async (input, init) => {
  const response = await originalFetch(input, init);
  if (response.status === 401) {
    const headers = init?.headers;
    let hasAuth = false;
    if (headers) {
      if (headers instanceof Headers) {
        hasAuth = headers.has('Authorization');
      } else if (Array.isArray(headers)) {
        hasAuth = headers.some(([key]) => key.toLowerCase() === 'authorization');
      } else if (typeof headers === 'object') {
        hasAuth = Object.keys(headers).some(key => key.toLowerCase() === 'authorization');
      }
    }
    if (hasAuth) {
      localStorage.removeItem('chatia_user');
      window.location.reload();
    }
  }
  return response;
};

const renderMessageContent = (text) => {
  if (!text) return null;

  const lines = text.split('\n');
  const renderedElements = [];
  
  let inCodeBlock = false;
  let codeBlockLines = [];

  for (let idx = 0; idx < lines.length; idx++) {
    const line = lines[idx];

    // Check for code block boundary
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        // Close code block
        renderedElements.push(
          <pre key={`code-${idx}`}>
            <code>{codeBlockLines.join('\n')}</code>
          </pre>
        );
        codeBlockLines = [];
        inCodeBlock = false;
      } else {
        // Open code block
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      continue;
    }

    // Parse normal/list/blockquote line
    const bulletMatch = line.match(/^(\s*)[*\-]\s+(.*)$/);
    const numMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    const quoteMatch = line.match(/^>\s+(.*)$/);

    let content = line;
    let isBullet = false;
    let isNumbered = false;
    let isQuote = false;
    let indent = 0;

    if (bulletMatch) {
      isBullet = true;
      indent = bulletMatch[1].length;
      content = bulletMatch[2];
    } else if (numMatch) {
      isNumbered = true;
      indent = numMatch[1].length;
      content = numMatch[2];
    } else if (quoteMatch) {
      isQuote = true;
      content = quoteMatch[1];
    }

    // Parse inline markdown elements (bold, italic, code)
    const parts = [];
    let keyIdx = 0;
    const regex = /(\*\*.*?\*\*|__.*?__|`.*?`|\*.*?\*|_.*?_)/g;
    const splitParts = content.split(regex);

    splitParts.forEach((part) => {
      if (!part) return;
      if (part.startsWith('**') && part.endsWith('**')) {
        parts.push(<strong key={keyIdx++}>{part.slice(2, -2)}</strong>);
      } else if (part.startsWith('__') && part.endsWith('__')) {
        parts.push(<strong key={keyIdx++}>{part.slice(2, -2)}</strong>);
      } else if (part.startsWith('`') && part.endsWith('`')) {
        parts.push(<code key={keyIdx++}>{part.slice(1, -1)}</code>);
      } else if ((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_'))) {
        parts.push(<em key={keyIdx++}>{part.slice(1, -1)}</em>);
      } else {
        parts.push(part);
      }
    });

    const style = { 
      marginLeft: `${indent * 8}px`,
      minHeight: '1.2em'
    };

    if (isBullet) {
      renderedElements.push(
        <div key={idx} style={{ ...style, display: 'flex', gap: '8px', margin: '4px 0', alignItems: 'flex-start' }}>
          <span style={{ color: 'var(--primary-color)', userSelect: 'none' }}>•</span>
          <span>{parts}</span>
        </div>
      );
    } else if (isNumbered) {
      const numPrefix = line.match(/^(\s*)(\d+\.)\s+/)[2];
      renderedElements.push(
        <div key={idx} style={{ ...style, display: 'flex', gap: '8px', margin: '4px 0', alignItems: 'flex-start' }}>
          <span style={{ color: 'var(--primary-color)', fontWeight: 'bold', userSelect: 'none' }}>{numPrefix}</span>
          <span>{parts}</span>
        </div>
      );
    } else if (isQuote) {
      renderedElements.push(
        <blockquote key={idx}>
          {parts}
        </blockquote>
      );
    } else {
      renderedElements.push(
        <div key={idx} style={{ margin: '6px 0', minHeight: '1em', lineHeight: '1.5' }}>
          {parts.length > 0 ? parts : <br />}
        </div>
      );
    }
  }

  if (inCodeBlock && codeBlockLines.length > 0) {
    renderedElements.push(
      <pre key="code-final">
        <code>{codeBlockLines.join('\n')}</code>
      </pre>
    );
  }

  return <div>{renderedElements}</div>;
};

function App() {
  const [user, setUser] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('chatia_theme') || 'light')

  useEffect(() => {
    if (theme === 'dark') {
      document.body.classList.add('dark-theme')
    } else {
      document.body.classList.remove('dark-theme')
    }
    localStorage.setItem('chatia_theme', theme)
  }, [theme])
  
  // Login Form State
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  // Title edit state
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editSessionTitle, setEditSessionTitle] = useState('')

  // Tabs
  const [activeTab, setActiveTab] = useState('consultas') // 'consultas' | 'administracion' | 'usuarios'

  // Folders State
  const [folders, setFolders] = useState([])
  const [activeFolder, setActiveFolder] = useState(null)

  // Document management state
  const [documents, setDocuments] = useState([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [selectedDocsForChat, setSelectedDocsForChat] = useState([])
  const [expandedFolders, setExpandedFolders] = useState({})
  const [docsByFolder, setDocsByFolder] = useState({})

  // New folder form
  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderDesc, setNewFolderDesc] = useState('')

  // New document form
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  // Chat State
  const [messages, setMessages] = useState([
    { id: 1, role: 'assistant', content: 'Hola. Soy tu Asistente Jurídico Inteligente. Selecciona una carpeta a la izquierda si deseas acotar la consulta, y escribe tu duda aquí.' }
  ])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // Chat History
  const [chatSessions, setChatSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [sidebarView, setSidebarView] = useState('folders') // 'folders' or 'history'

  // User Management State
  const [systemUsers, setSystemUsers] = useState([])
  const [newAuthEmail, setNewAuthEmail] = useState('')
  const [newAuthPassword, setNewAuthPassword] = useState('')
  const [newAuthRole, setNewAuthRole] = useState('user')
  const [passwordChangeOld, setPasswordChangeOld] = useState('')
  const [passwordChangeNew, setPasswordChangeNew] = useState('')
  const [passwordChangeMessage, setPasswordChangeMessage] = useState('')

  // Settings State (Military Glossary)
  const [militaryGlossary, setMilitaryGlossary] = useState('')
  const [savingGlossary, setSavingGlossary] = useState(false)
  const [glossaryMessage, setGlossaryMessage] = useState('')

  // Semantic Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')

  // Document administration pagination and local filter states
  const [docSearchQuery, setDocSearchQuery] = useState('')
  const [docCurrentPage, setDocCurrentPage] = useState(1)

  // Load user from localStorage
  useEffect(() => {
    const storedUser = localStorage.getItem('chatia_user')
    if (storedUser) {
      const parsed = JSON.parse(storedUser)
      setUser(parsed)
    }
  }, [])

  // Load folders from backend
  const fetchFolders = async () => {
    try {
      const res = await fetch('http://localhost:8000/folders')
      if (res.ok) {
        const data = await res.json()
        setFolders(data)
        if (data.length > 0 && !activeFolder) {
          setActiveFolder(data[0])
        }
      }
    } catch (err) {
      console.error("Error al cargar carpetas:", err)
    }
  }

  // Load documents for active folder
  const fetchDocuments = async () => {
    if (!activeFolder) return
    setLoadingDocs(true)
    try {
      const res = await fetch(`http://localhost:8000/folders/${activeFolder.id}/documents`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
        setDocCurrentPage(1)
        setDocSearchQuery('')
      }
    } catch (err) {
      console.error("Error al cargar documentos:", err)
    } finally {
      setLoadingDocs(false)
    }
  }

  const fetchDocumentsForFolder = async (folderId) => {
    try {
      const res = await fetch(`http://localhost:8000/folders/${folderId}/documents`)
      if (res.ok) {
        const data = await res.json()
        setDocsByFolder(prev => ({ ...prev, [folderId]: data }))
      }
    } catch (err) {
      console.error("Error al cargar documentos:", err)
    }
  }

  const fetchChatSessions = async () => {
    if (!user) return
    try {
      const res = await fetch('http://localhost:8000/chat/sessions', {
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setChatSessions(data)
      }
    } catch (err) {
      console.error("Error al cargar historial de chats:", err)
    }
  }

  const loadChatSession = async (sessionId) => {
    try {
      const res = await fetch(`http://localhost:8000/chat/sessions/${sessionId}`, {
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setCurrentSessionId(data.id)
        
        let msgs = data.messages || [];
        if (msgs.length === 0 || msgs[0].role !== 'assistant') {
          msgs = [{ id: -1, role: 'assistant', content: 'Hola. Soy tu Asistente Jurídico Inteligente. Selecciona una carpeta a la izquierda si deseas acotar la consulta, y escribe tu duda aquí.' }, ...msgs];
        }
        
        setMessages(msgs.map((m, i) => ({ ...m, id: i })))
        if (data.folder_id) {
          const folder = folders.find(f => f.id === data.folder_id)
          if (folder) setActiveFolder(folder)
        } else {
          setActiveFolder(null)
        }
        setSelectedDocsForChat([])
      }
    } catch (err) {
      console.error("Error al cargar la sesión de chat:", err)
    }
  }

  const handleNewChat = () => {
    setCurrentSessionId(null)
    setMessages([{ id: 1, role: 'assistant', content: 'Hola. Soy tu Asistente Jurídico Inteligente. Selecciona una carpeta a la izquierda si deseas acotar la consulta, y escribe tu duda aquí.' }])
    setActiveFolder(folders.length > 0 ? folders[0] : null)
    setSelectedDocsForChat([])
  }

  const handleUpdateSessionTitle = async (e, sessionId) => {
    e.preventDefault()
    e.stopPropagation()
    if (!editSessionTitle.trim()) {
      setEditingSessionId(null)
      return
    }
    try {
      const res = await fetch(`http://localhost:8000/chat/sessions/${sessionId}/title`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ title: editSessionTitle })
      })
      if (res.ok) {
        setChatSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title: editSessionTitle } : s))
      }
    } catch (err) {
      console.error("Error al actualizar título:", err)
    } finally {
      setEditingSessionId(null)
    }
  }

  const handleDeleteChatSession = async (e, sessionId) => {
    e.stopPropagation()
    if (!confirm("¿Desea borrar este historial de chat?")) return
    try {
      const res = await fetch(`http://localhost:8000/chat/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        setChatSessions(prev => prev.filter(s => s.id !== sessionId))
        if (currentSessionId === sessionId) {
          handleNewChat()
        }
      } else {
        alert("Error al borrar historial")
      }
    } catch (err) {
      console.error(err)
    }
  }

  const fetchSystemUsers = async () => {
    if (!user || user.role !== 'admin') return
    try {
      const res = await fetch('http://localhost:8000/users/', {
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setSystemUsers(data)
      }
    } catch (err) {
      console.error("Error al cargar usuarios:", err)
    }
  }

  const fetchMilitaryGlossary = async () => {
    if (!user) return
    try {
      const res = await fetch('http://localhost:8000/settings/glossary', {
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setMilitaryGlossary(data.content || '')
      }
    } catch (err) {
      console.error("Error al cargar glosario:", err)
    }
  }

  const handleSaveGlossary = async (e) => {
    e.preventDefault()
    setSavingGlossary(true)
    setGlossaryMessage('')
    try {
      const res = await fetch('http://localhost:8000/settings/glossary', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ content: militaryGlossary })
      })
      if (res.ok) {
        setGlossaryMessage('Glosario actualizado correctamente.')
        setTimeout(() => setGlossaryMessage(''), 3000)
      } else {
        setGlossaryMessage('Error al actualizar.')
      }
    } catch (err) {
      console.error(err)
      setGlossaryMessage('Error de conexión.')
    } finally {
      setSavingGlossary(false)
    }
  }

  const handleSemanticSearch = async (e) => {
    if (e) e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearchError('')
    try {
      const res = await fetch(`http://localhost:8000/search/?query=${encodeURIComponent(searchQuery)}`, {
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data)
      } else {
        const errData = await res.json()
        setSearchError(errData.detail || 'Error al realizar la búsqueda semántica')
      }
    } catch (err) {
      console.error(err)
      setSearchError('Error de conexión con el servidor')
    } finally {
      setSearching(false)
    }
  }

  useEffect(() => {
    if (user) {
      fetchFolders()
      fetchChatSessions()
      if (user.role === 'admin') {
        fetchSystemUsers()
        fetchMilitaryGlossary()
      }
    }
  }, [user])

  useEffect(() => {
    if (user && activeFolder) {
      fetchDocuments()
    }
  }, [user, activeFolder])

  const handleCreateUser = async (e) => {
    e.preventDefault()
    if (!newAuthEmail || !newAuthPassword) return
    try {
      const res = await fetch('http://localhost:8000/users/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ email: newAuthEmail, password: newAuthPassword, role: newAuthRole })
      })
      if (res.ok) {
        setNewAuthEmail('')
        setNewAuthPassword('')
        fetchSystemUsers()
      } else {
        const errData = await res.json()
        alert(errData.detail || "Error al crear usuario")
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleDeleteUser = async (id) => {
    if (!confirm("¿Seguro que deseas eliminar este usuario?")) return
    try {
      const res = await fetch(`http://localhost:8000/users/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        fetchSystemUsers()
      } else {
        const errData = await res.json()
        alert(errData.detail)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleResetUserPassword = async (id) => {
    const newPassword = prompt("Ingresa la nueva contraseña para este usuario:")
    if (!newPassword) return
    try {
      const res = await fetch(`http://localhost:8000/users/${id}/reset-password`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}` 
        },
        body: JSON.stringify({ new_password: newPassword })
      })
      if (res.ok) {
        alert("Contraseña actualizada exitosamente.")
      } else {
        const errData = await res.json()
        alert(errData.detail || "Error al actualizar contraseña")
      }
    } catch (err) {
      console.error(err)
      alert("Error de conexión al actualizar contraseña.")
    }
  }

  const handleChangeRole = async (id, newRole) => {
    try {
      const res = await fetch(`http://localhost:8000/users/${id}/role`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ role: newRole })
      })
      if (res.ok) {
        fetchSystemUsers()
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setPasswordChangeMessage('')
    if (!passwordChangeOld || !passwordChangeNew) return
    try {
      const res = await fetch('http://localhost:8000/users/me/password', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ old_password: passwordChangeOld, new_password: passwordChangeNew })
      })
      const data = await res.json()
      if (res.ok) {
        setPasswordChangeMessage('Contraseña actualizada correctamente.')
        setPasswordChangeOld('')
        setPasswordChangeNew('')
      } else {
        setPasswordChangeMessage(`Error: ${data.detail}`)
      }
    } catch (err) {
      setPasswordChangeMessage('Error de conexión.')
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!loginEmail || !loginPassword) return
    setLoginError('')
    setLoginLoading(true)

    try {
      const res = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Error al iniciar sesión')
      }

      const data = await res.json()
      const loggedUser = {
        email: data.email,
        token: data.access_token,
        role: data.role
      }
      localStorage.setItem('chatia_user', JSON.stringify(loggedUser))
      setUser(loggedUser)
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('chatia_user')
    setUser(null)
    setFolders([])
    setDocuments([])
    setChatSessions([])
    setCurrentSessionId(null)
    setActiveFolder(null)
    setMessages([{ id: 1, role: 'assistant', content: 'Hola. Soy tu Asistente Jurídico Inteligente. Selecciona una carpeta a la izquierda si deseas acotar la consulta, y escribe tu duda aquí.' }])
    setActiveTab('consultas')
  }

  const abortControllerRef = useRef(null)

  const handleSendChat = async () => {
    if (!input.trim()) return

    const userMsg = { id: Date.now(), role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setChatLoading(true)

    // Create a new AbortController for this request
    abortControllerRef.current = new AbortController()

    try {
      const res = await fetch('http://localhost:8000/chat/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({
          query: userMsg.content,
          folder_id: activeFolder ? activeFolder.id : null,
          filenames: selectedDocsForChat.length > 0 ? selectedDocsForChat : [],
          session_id: currentSessionId
        }),
        signal: abortControllerRef.current.signal
      })

      const data = await res.json()
      const asstMsg = { 
        id: Date.now() + 1, 
        role: 'assistant', 
        content: data.response,
        folder_name: data.folder_name,
        filenames: data.filenames
      }
      setMessages(prev => [...prev, asstMsg])
      
      if (data.session_id && data.session_id !== currentSessionId) {
        setCurrentSessionId(data.session_id)
        fetchChatSessions()
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log("Petición abortada por el usuario")
      } else {
        console.error(error)
        const errorMsg = { id: Date.now() + 1, role: 'assistant', content: 'Error al procesar consulta. Verifica que el backend esté disponible.' }
        setMessages(prev => [...prev, errorMsg])
      }
    } finally {
      setChatLoading(false)
      abortControllerRef.current = null
    }
  }

  const handleStopChat = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const handleEditMessage = async (msgIndex, text) => {
    if (!currentSessionId) return
    if (!confirm("Editar este mensaje reescribirá el historial a partir de este punto. ¿Deseas continuar?")) return
    
    // 1. Put text back in input
    setInput(text)
    
    // 2. Truncate array in UI
    setMessages(prev => prev.slice(0, msgIndex))
    
    // 3. Truncate in backend
    try {
      await fetch(`http://localhost:8000/chat/sessions/${currentSessionId}/truncate`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ index: msgIndex }) // Keep messages before msgIndex
      })
    } catch (err) {
      console.error("Error truncando sesión:", err)
    }
  }

  // Folder Admin actions
  const handleCreateFolder = async (e) => {
    e.preventDefault()
    if (!newFolderName.trim()) return
    try {
      const res = await fetch('http://localhost:8000/folders/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({ name: newFolderName, description: newFolderDesc })
      })
      if (res.ok) {
        const data = await res.json()
        setFolders(prev => [...prev, data])
        if (!activeFolder) setActiveFolder(data)
        setNewFolderName('')
        setNewFolderDesc('')
      }
    } catch (err) {
      console.error("Error al crear carpeta:", err)
    }
  }

  const handleDeleteFolder = async (id) => {
    if (!confirm("¿Está seguro de que desea eliminar esta carpeta? Se borrarán todos sus documentos e índices vectoriales.")) return
    try {
      const res = await fetch(`http://localhost:8000/folders/${id}`, { 
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        setFolders(prev => prev.filter(f => f.id !== id))
        if (activeFolder && activeFolder.id === id) {
          setActiveFolder(folders.find(f => f.id !== id) || null)
        }
      }
    } catch (err) {
      console.error("Error al borrar carpeta:", err)
    }
  }

  // Document Upload/Delete actions
  const handleUploadDocument = async (e) => {
    e.preventDefault()
    if (!selectedFile || !activeFolder) return
    setUploading(true)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const res = await fetch(`http://localhost:8000/folders/${activeFolder.id}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${user.token}` },
        body: formData
      })
      
      if (!res.ok) {
        const errData = await res.json()
        alert(errData.detail || "Error subiendo archivo")
      } else {
        setSelectedFile(null)
        // Reset file input UI
        const fileInput = document.getElementById('file-input')
        if (fileInput) fileInput.value = ''
        fetchDocuments()
      }
    } catch (err) {
      console.error("Error subiendo archivo:", err)
      alert("Error de conexión al subir el archivo.")
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDocument = async (id) => {
    if (!confirm("¿Desea borrar este documento y sus vectores?")) return
    try {
      const res = await fetch(`http://localhost:8000/folders/documents/${id}`, { 
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${user.token}` }
      })
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.id !== id))
      }
    } catch (err) {
      console.error("Error al borrar documento:", err)
    }
  }

  // Filter documents in folder admin view
  const filteredDocuments = documents.filter(doc => {
    const query = docSearchQuery.toLowerCase().trim();
    if (!query) return true;
    
    const filenameMatch = doc.filename && doc.filename.toLowerCase().includes(query);
    const tagsMatch = doc.tags && doc.tags.some(tag => tag.toLowerCase().includes(query));
    
    return filenameMatch || tagsMatch;
  });

  const docsPerPage = 2;
  const totalDocPages = Math.ceil(filteredDocuments.length / docsPerPage);
  const activeDocPage = Math.min(docCurrentPage, Math.max(1, totalDocPages));
  const paginatedDocuments = filteredDocuments.slice(
    (activeDocPage - 1) * docsPerPage,
    (activeDocPage - 1) * docsPerPage + docsPerPage
  );

  // LOGIN SCREEN
  if (!user) {
    return (
      <div className="login-screen">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="login-logo">
            <ShieldAlert size={48} />
          </div>
          <h2 className="login-title">Asistente IA - Ejercito Argentino</h2>
          <p className="login-subtitle">Departamento de Planeamiento - Ejército Argentino</p>
          
          {loginError && <div className="login-error">{loginError}</div>}
          
          <div className="form-group">
            <label className="form-label"><Mail size={12} style={{marginRight: 4}}/> Correo electrónico</label>
            <input 
              type="email" 
              className="form-input" 
              placeholder="correo@ejercito.mil.ar"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label"><Lock size={12} style={{marginRight: 4}}/> Contraseña</label>
            <input 
              type="password" 
              className="form-input" 
              placeholder="••••••••"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="login-btn" disabled={loginLoading}>
            {loginLoading ? 'Ingresando...' : 'Iniciar Sesión'}
          </button>
        </form>
      </div>
    )
  }

  // MAIN APPLICATION SCREEN
  return (
    <div className="app-container">
      {/* TOPBAR HEADER */}
      <div className="topbar">
        <div className="topbar-left">
          <img src="/logo.png" alt="Ejército Argentino Logo" style={{ height: '38px', width: 'auto', objectFit: 'contain' }} />
          <div>
            <span className="topbar-title">Asistente IA - Ejercito Argentino</span>
            <span className="topbar-subtitle">{user.email}</span>
          </div>
        </div>
        <div className="topbar-right">
          {user.role === 'admin' && (
            <span className="admin-badge">Administrador</span>
          )}
          <button 
            onClick={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
            style={{ 
              background: 'transparent', 
              border: '1px solid rgba(255,255,255,0.2)', 
              color: 'var(--text-main)', 
              padding: '8px', 
              borderRadius: '6px', 
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
              marginRight: '8px'
            }}
            title={theme === 'light' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro'}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>
          <button className="logout-button" onClick={handleLogout}>
            <LogOut size={16} />
            Salir
          </button>
        </div>
      </div>

      {/* TABS (VISIBLE FOR ALL, SOME TABS RESTRICTED) */}
      <div className="tabs-container">
        <div 
          className={`tab-item ${activeTab === 'consultas' ? 'active' : ''}`}
          onClick={() => setActiveTab('consultas')}
        >
          <Bot size={18} /> Consultas
        </div>
        {user.role === 'admin' && (
          <>
            <div 
              className={`tab-item ${activeTab === 'administracion' ? 'active' : ''}`}
              onClick={() => setActiveTab('administracion')}
            >
              <Folder size={18} /> Administración
            </div>
            <div 
              className={`tab-item ${activeTab === 'usuarios' ? 'active' : ''}`}
              onClick={() => setActiveTab('usuarios')}
            >
              <Users size={18} /> Usuarios
            </div>
            <div 
              className={`tab-item ${activeTab === 'glosario' ? 'active' : ''}`}
              onClick={() => setActiveTab('glosario')}
            >
              <Database size={18} /> Glosario Base
            </div>
            <div 
              className={`tab-item ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
            >
              <Search size={18} /> Buscador Semántico
            </div>
          </>
        )}
        <div 
          className={`tab-item ${activeTab === 'perfil' ? 'active' : ''}`}
          onClick={() => setActiveTab('perfil')}
        >
          <Settings size={18} /> Mi Perfil
        </div>
      </div>

      {/* CONTENT LAYOUT */}
      <div className="main-content">
        
        {/* VIEW: CONSULTAS (CHATBOT) */}
        {activeTab === 'consultas' && (
          <>
            {/* Sidebar with Folders and History */}
            <div className="sidebar">
              <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.1)', marginBottom: '10px' }}>
                <div 
                  onClick={() => setSidebarView('folders')}
                  style={{ flex: 1, padding: '10px', textAlign: 'center', cursor: 'pointer', borderBottom: sidebarView === 'folders' ? '2px solid var(--primary-color)' : '2px solid transparent', color: sidebarView === 'folders' ? 'var(--primary-color)' : 'rgba(255,255,255,0.7)', fontWeight: sidebarView === 'folders' ? 600 : 400 }}
                >
                  Carpetas
                </div>
                <div 
                  onClick={() => setSidebarView('history')}
                  style={{ flex: 1, padding: '10px', textAlign: 'center', cursor: 'pointer', borderBottom: sidebarView === 'history' ? '2px solid var(--primary-color)' : '2px solid transparent', color: sidebarView === 'history' ? 'var(--primary-color)' : 'rgba(255,255,255,0.7)', fontWeight: sidebarView === 'history' ? 600 : 400 }}
                >
                  Historial
                </div>
              </div>

              {sidebarView === 'folders' && (
                <div className="folder-list">
                {folders.map(folder => {
                  const isExpanded = expandedFolders[folder.id];
                  const isFolderActive = activeFolder?.id === folder.id && selectedDocsForChat.length === 0;
                  
                  return (
                    <div key={folder.id} className="folder-container" style={{ marginBottom: '4px' }}>
                      <div 
                        className={`folder-item ${isFolderActive ? 'active' : ''}`}
                        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                      >
                        <div 
                          style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}
                          onClick={() => {
                            setActiveFolder(folder);
                            setSelectedDocsForChat([]);
                          }}
                        >
                          <Folder size={16} fill={isFolderActive ? 'currentColor' : 'none'} />
                          <span style={{ fontWeight: isFolderActive ? 600 : 400 }}>{folder.name}</span>
                        </div>
                        <div 
                          onClick={(e) => {
                            e.stopPropagation();
                            const willExpand = !isExpanded;
                            setExpandedFolders(prev => ({ ...prev, [folder.id]: willExpand }));
                            if (willExpand && !docsByFolder[folder.id]) {
                                fetchDocumentsForFolder(folder.id);
                            }
                          }}
                          style={{ padding: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                        >
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </div>
                      </div>
                      
                      {isExpanded && (
                        <div className="document-list" style={{ paddingLeft: '24px', marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          {docsByFolder[folder.id] === undefined ? (
                            <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', padding: '4px 0' }}>Cargando...</div>
                          ) : docsByFolder[folder.id].length === 0 ? (
                            <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', padding: '4px 0' }}>Sin documentos</div>
                          ) : (
                            docsByFolder[folder.id].map(doc => {
                              const isDocActive = activeFolder?.id === folder.id && selectedDocsForChat.includes(doc.filename);
                              return (
                                <div 
                                  key={doc.id}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (activeFolder?.id !== folder.id) {
                                      setActiveFolder(folder);
                                      setSelectedDocsForChat([doc.filename]);
                                    } else {
                                      setSelectedDocsForChat(prev => 
                                        prev.includes(doc.filename) 
                                          ? prev.filter(name => name !== doc.filename) 
                                          : [...prev, doc.filename]
                                      );
                                    }
                                  }}
                                  style={{ 
                                    padding: '6px 8px', 
                                    fontSize: '0.85rem', 
                                    cursor: 'pointer',
                                    borderRadius: '4px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    color: isDocActive ? '#fff' : 'rgba(255,255,255,0.7)',
                                    background: isDocActive ? 'rgba(255,255,255,0.1)' : 'transparent',
                                    fontWeight: isDocActive ? 500 : 400
                                  }}
                                  onMouseEnter={(e) => { if(!isDocActive) e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                                  onMouseLeave={(e) => { if(!isDocActive) e.currentTarget.style.background = 'transparent' }}
                                >
                                  <input 
                                    type="checkbox" 
                                    checked={isDocActive} 
                                    readOnly 
                                    style={{ accentColor: 'var(--primary-color)', cursor: 'pointer', margin: 0 }} 
                                  />
                                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.filename}</span>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {folders.length === 0 && (
                  <div style={{ color: 'rgba(255,255,255,0.4)', padding: '15px', fontSize: '0.85rem' }}>
                    No hay carpetas creadas.
                  </div>
                )}
              </div>
              )}
              
              {sidebarView === 'history' && (
                <div className="history-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button onClick={handleNewChat} style={{ width: '100%', padding: '8px', background: 'var(--primary-color)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', marginBottom: '10px' }}>
                    <Plus size={16} /> Nueva Consulta
                  </button>
                  {chatSessions.length === 0 ? (
                     <div style={{ color: 'rgba(255,255,255,0.4)', padding: '15px', fontSize: '0.85rem', textAlign: 'center' }}>
                       No hay chats previos.
                     </div>
                  ) : (
                    chatSessions.map(session => (
                      <div 
                        key={session.id} 
                        onClick={() => loadChatSession(session.id)}
                        style={{ padding: '10px', borderRadius: '6px', cursor: 'pointer', background: currentSessionId === session.id ? 'rgba(2, 132, 199, 0.2)' : 'rgba(255,255,255,0.05)', border: currentSessionId === session.id ? '1px solid var(--primary-color)' : '1px solid transparent', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', overflow: 'hidden' }}>
                          {editingSessionId === session.id ? (
                            <form onSubmit={(e) => handleUpdateSessionTitle(e, session.id)} style={{ display: 'flex', gap: '4px' }}>
                              <input 
                                autoFocus
                                type="text"
                                value={editSessionTitle}
                                onChange={(e) => setEditSessionTitle(e.target.value)}
                                onClick={e => e.stopPropagation()}
                                style={{ fontSize: '0.85rem', padding: '2px 4px', borderRadius: '4px', border: '1px solid var(--primary-color)', background: 'transparent', color: '#fff', width: '100%' }}
                              />
                            </form>
                          ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: currentSessionId === session.id ? 600 : 400, color: currentSessionId === session.id ? '#fff' : 'rgba(255,255,255,0.8)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session.title}</span>
                              <button 
                                onClick={(e) => { e.stopPropagation(); setEditingSessionId(session.id); setEditSessionTitle(session.title); }}
                                style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', padding: '2px' }}
                                title="Editar título"
                              >
                                <Edit2 size={12} />
                              </button>
                            </div>
                          )}
                          <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)' }}>
                            {session.created_at ? new Date(session.created_at).toLocaleString() : ''}
                          </span>
                        </div>
                        <button 
                          onClick={(e) => handleDeleteChatSession(e, session.id)} 
                          style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}
                          title="Borrar chat"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Chatbot Interface */}
            <div className="chat-area">
              <div className="messages-container">
                {messages.map((msg, index) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    {msg.role === 'assistant' ? (
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: 'var(--primary-color)', fontWeight: 600 }}>
                          <Bot size={18} /> Asistente
                        </div>
                        {msg.folder_name && (
                          <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Database size={10} /> Consultado en: {msg.folder_name} {msg.filenames && msg.filenames.length > 0 ? `> ${msg.filenames.length} archivo(s)` : ''}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '4px' }}>
                        <button 
                          onClick={() => handleEditMessage(index, msg.content)}
                          style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.5)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
                          title="Editar mensaje y borrar historial posterior"
                        >
                          <Edit2 size={12} /> Editar
                        </button>
                      </div>
                    )}
                    <div className="message-content">{renderMessageContent(msg.content)}</div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="message assistant">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Bot size={18} /> <em>Buscando normativas y redactando respuesta...</em>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ padding: '0 20px' }}>
                <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  Tema de Consulta actual: <strong style={{ color: 'var(--primary-color)' }}>{activeFolder ? activeFolder.name : 'General'} {selectedDocsForChat.length > 0 ? `> ${selectedDocsForChat.length} documento(s)` : ''}</strong>
                </div>
              </div>
              <div className="input-container">
                <div className="input-box">
                  <textarea 
                    className="chat-input" 
                    placeholder="Escribe tu consulta o duda jurídica..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSendChat()
                      }
                    }}
                  />
                  <button 
                    className="send-button" 
                    onClick={chatLoading ? handleStopChat : handleSendChat}
                    disabled={!chatLoading && !input.trim()}
                    style={{ background: chatLoading ? '#ef4444' : 'var(--primary-color)' }}
                    title={chatLoading ? "Detener ejecución" : "Enviar consulta"}
                  >
                    {chatLoading ? <XCircle size={20} /> : <Send size={20} />}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* VIEW: BUSCADOR SEMANTICO */}
        {activeTab === 'search' && user.role === 'admin' && (
          <div className="admin-container">
            <div className="admin-card" style={{ maxWidth: '900px', margin: '0 auto' }}>
              <h3 style={{ marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--admin-card-border)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <Search size={20} /> Buscador Semántico de Archivos
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--admin-text-muted)', marginBottom: '20px' }}>
                Busca en todo el sistema utilizando lenguaje natural. La inteligencia artificial convertirá tu consulta en vectores para encontrar los documentos más relevantes por coincidencia semántica, mostrando el porcentaje de similitud y sus etiquetas.
              </p>

              <form onSubmit={handleSemanticSearch} style={{ display: 'flex', gap: '10px', marginBottom: '30px' }}>
                <div style={{ flex: 1, position: 'relative' }}>
                  <input 
                    type="text" 
                    placeholder="Escribe palabras clave o conceptos a buscar (ej: Planes de contingencia, regulaciones militares...)" 
                    style={{ width: '100%', padding: '12px 16px', borderRadius: '8px', border: '1px solid var(--admin-input-border)', backgroundColor: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', transition: 'all 0.3s', fontSize: '0.95rem' }}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" disabled={searching} style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', fontWeight: 600, cursor: searching ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem' }}>
                  {searching ? 'Buscando...' : 'Buscar'}
                </button>
              </form>

              {searchError && (
                <div style={{ padding: '12px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', marginBottom: '20px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  {searchError}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {searching ? (
                  <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '40px' }}>
                    <em style={{ fontSize: '0.95rem' }}>Buscando coincidencias semánticas en Qdrant...</em>
                  </div>
                ) : searchResults.length > 0 ? (
                  searchResults.map((result, idx) => {
                    const matchedFolder = folders.find(f => f.id === result.folder_id);
                    return (
                      <div key={idx} style={{ padding: '16px', border: '1px solid var(--admin-card-border)', borderRadius: '10px', background: 'var(--admin-input-bg)', display: 'flex', flexDirection: 'column', gap: '10px', transition: 'all 0.3s' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '20px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <FileText size={20} color="var(--admin-text-muted)" />
                            <div>
                              <strong style={{ fontSize: '1.05rem', color: 'var(--admin-text-main)' }}>{result.filename}</strong>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: 'var(--admin-text-muted)', marginTop: '2px' }}>
                                <Folder size={12} />
                                <span>Carpeta: {matchedFolder ? matchedFolder.name : 'General'}</span>
                              </div>
                            </div>
                          </div>
                          
                          {/* Match Percentage Badge */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: result.match_percentage >= 80 ? 'rgba(34, 197, 94, 0.15)' : result.match_percentage >= 50 ? 'rgba(234, 179, 8, 0.15)' : 'rgba(100, 116, 139, 0.15)', color: result.match_percentage >= 80 ? '#22c55e' : result.match_percentage >= 50 ? '#eab308' : 'var(--admin-text-muted)', padding: '6px 12px', borderRadius: '20px', fontSize: '0.85rem', fontWeight: 600 }}>
                            <span>{result.match_percentage}% Coincidencia</span>
                          </div>
                        </div>

                        {/* Tags & Actions */}
                        <div className="search-actions-container">
                          {/* Tags */}
                          <div className="search-tags-wrapper">
                            {result.tags && result.tags.length > 0 ? (
                              result.tags.map((tag, tagIdx) => (
                                <span key={tagIdx} style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '4px', background: 'rgba(2, 132, 199, 0.15)', color: 'var(--primary-color)', fontWeight: 500 }}>
                                  {tag}
                                </span>
                              ))
                            ) : (
                              <span style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)' }}>Sin etiquetas</span>
                            )}
                          </div>

                          {/* Actions */}
                          {result.id && (
                            <div className="search-buttons-wrapper">
                              <button 
                                onClick={() => window.open(`http://localhost:8000/folders/documents/${result.id}/download?inline=true`, '_blank')}
                                className="btn-action-view"
                                title="Visualizar documento en nueva pestaña"
                              >
                                <Eye size={14} /> Visualizar
                              </button>
                              <button 
                                onClick={() => window.open(`http://localhost:8000/folders/documents/${result.id}/download`, '_blank')}
                                className="btn-action-download"
                                title="Descargar documento"
                              >
                                <Download size={14} /> Descargar
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : searchQuery && !searching ? (
                  <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '40px', border: '1px dashed var(--admin-card-border)', borderRadius: '8px' }}>
                    No se encontraron documentos con coincidencia semántica para "{searchQuery}".
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '40px', border: '1px dashed var(--admin-card-border)', borderRadius: '8px' }}>
                    Ingresa una consulta arriba para empezar a buscar documentos en la base de datos vectorial.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* VIEW: ADMINISTRACION (CRUD FOR FOLDERS AND DOCUMENTS) */}
        {activeTab === 'administracion' && user.role === 'admin' && (
          <div className="admin-layout">
            
            {/* Column 1: Manage Folders */}
            <div className="admin-card" style={{ flex: 1, maxHeight: '600px', overflowY: 'auto' }}>
              <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--admin-card-border)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <Folder size={20} /> Administrar Carpetas
              </h3>
              
              <form onSubmit={handleCreateFolder} style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '30px' }}>
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px', transition: 'color 0.3s' }}>Nombre de Carpeta</label>
                  <input 
                    type="text" 
                    placeholder="Ej. Leyes Generales" 
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', backgroundColor: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', transition: 'all 0.3s' }}
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px', transition: 'color 0.3s' }}>Descripción</label>
                  <input 
                    type="text" 
                    placeholder="Breve descripción del tema..." 
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', backgroundColor: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', transition: 'all 0.3s' }}
                    value={newFolderDesc}
                    onChange={(e) => setNewFolderDesc(e.target.value)}
                  />
                </div>
                <button type="submit" style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '10px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                  <Plus size={16} /> Crear Carpeta
                </button>
              </form>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {folders.map(f => (
                  <div key={f.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', border: '1px solid var(--admin-card-border)', borderRadius: '8px', background: activeFolder?.id === f.id ? 'rgba(2, 132, 199, 0.15)' : 'transparent', borderLeft: activeFolder?.id === f.id ? '4px solid var(--primary-color)' : '1px solid var(--admin-card-border)', transition: 'all 0.3s' }}>
                    <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => setActiveFolder(f)}>
                      <strong style={{ display: 'block', color: activeFolder?.id === f.id ? 'var(--primary-color)' : 'var(--admin-text-main)', transition: 'color 0.3s' }}>{f.name}</strong>
                      <span style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)', transition: 'color 0.3s' }}>{f.description}</span>
                    </div>
                    <button onClick={() => handleDeleteFolder(f.id)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Column 2: Upload Documents to Selected Folder */}
            <div className="admin-card" style={{ flex: 1.5 }}>
              <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--admin-card-border)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <FileText size={20} /> Documentos de: <span style={{color: 'var(--primary-color)'}}>{activeFolder ? activeFolder.name : 'Ninguna Carpeta Seleccionada'}</span>
              </h3>

              {activeFolder ? (
                <>
                  {/* Upload Form */}
                  <form onSubmit={handleUploadDocument} className="responsive-form" style={{ marginBottom: '20px' }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px', transition: 'color 0.3s' }}>Subir PDF, Word o TXT real</label>
                      <input 
                        id="file-input"
                        type="file" 
                        accept=".pdf,.docx,.doc,.txt"
                        style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', transition: 'all 0.3s' }}
                        onChange={(e) => setSelectedFile(e.target.files[0])}
                        required
                      />
                    </div>
                    <button type="submit" style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '11px 18px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }} disabled={!selectedFile || uploading}>
                      {uploading ? 'Procesando...' : 'Cargar'}
                    </button>
                  </form>

                  {/* Local Search Input */}
                  <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
                    <input 
                      type="text" 
                      placeholder="Buscar por nombre o tag..." 
                      value={docSearchQuery}
                      onChange={(e) => {
                        setDocSearchQuery(e.target.value);
                        setDocCurrentPage(1);
                      }}
                      style={{ flex: 1, padding: '10px 14px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', backgroundColor: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', fontSize: '0.85rem', transition: 'all 0.3s' }}
                    />
                    {docSearchQuery && (
                      <button 
                        onClick={() => {
                          setDocSearchQuery('');
                          setDocCurrentPage(1);
                        }}
                        style={{ padding: '8px 12px', background: 'transparent', border: '1px solid var(--admin-card-border)', color: 'var(--admin-text-muted)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
                      >
                        Limpiar
                      </button>
                    )}
                  </div>
 
                  {/* Document List */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {loadingDocs ? (
                      <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '20px', transition: 'color 0.3s' }}>Cargando listado...</div>
                    ) : (
                      <>
                        {paginatedDocuments.map(doc => (
                          <div key={doc.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', border: '1px solid var(--admin-card-border)', borderRadius: '8px', background: 'var(--admin-input-bg)', transition: 'all 0.3s' }}>
                            <div style={{ display: 'flex', alignItems: 'start', gap: '8px', flex: 1 }}>
                              <FileText size={16} color="var(--admin-text-muted)" style={{ transition: 'color 0.3s', marginTop: '3px' }} />
                              <div style={{ flex: 1 }}>
                                <span style={{ fontWeight: 500, display: 'block' }}>{doc.filename}</span>
                                <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--admin-text-muted)', transition: 'color 0.3s', marginBottom: doc.tags && doc.tags.length > 0 ? '6px' : '0' }}>{doc.chunk_count} fragmentos vectorizados</span>
                                {doc.tags && doc.tags.length > 0 && (
                                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                    {doc.tags.map((tag, tagIdx) => (
                                      <span key={tagIdx} style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(2, 132, 199, 0.15)', color: 'var(--primary-color)', fontWeight: 500 }}>
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                            <button onClick={() => handleDeleteDocument(doc.id)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px', alignSelf: 'start', marginTop: '2px' }}>
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ))}
                        
                        {filteredDocuments.length === 0 && (
                          <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '30px', transition: 'color 0.3s' }}>
                            {docSearchQuery ? 'No se encontraron documentos coincidentes.' : 'No hay documentos cargados en esta carpeta.'}
                          </div>
                        )}
                        
                        {/* Pagination Controls */}
                        {totalDocPages > 1 && (
                          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', marginTop: '20px', padding: '10px 0' }}>
                            <button 
                              disabled={activeDocPage === 1}
                              onClick={() => setDocCurrentPage(prev => Math.max(1, prev - 1))}
                              style={{ 
                                background: activeDocPage === 1 ? 'rgba(0,0,0,0.02)' : 'var(--admin-card-bg)', 
                                border: '1px solid var(--admin-card-border)', 
                                color: activeDocPage === 1 ? 'var(--admin-text-muted)' : 'var(--admin-text-main)', 
                                padding: '6px 12px', 
                                borderRadius: '6px', 
                                cursor: activeDocPage === 1 ? 'not-allowed' : 'pointer',
                                fontSize: '0.8rem',
                                fontWeight: 500,
                                transition: 'all 0.2s'
                              }}
                            >
                              Anterior
                            </button>
                            
                            {Array.from({ length: totalDocPages }, (_, i) => i + 1).map(pageNum => (
                              <button
                                key={pageNum}
                                onClick={() => setDocCurrentPage(pageNum)}
                                style={{
                                  background: activeDocPage === pageNum ? 'var(--primary-color)' : 'var(--admin-card-bg)',
                                  border: '1px solid var(--admin-card-border)',
                                  color: activeDocPage === pageNum ? 'white' : 'var(--admin-text-main)',
                                  width: '30px',
                                  height: '30px',
                                  borderRadius: '6px',
                                  cursor: 'pointer',
                                  fontSize: '0.8rem',
                                  fontWeight: 600,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  transition: 'all 0.2s'
                                }}
                              >
                                {pageNum}
                              </button>
                            ))}

                            <button 
                              disabled={activeDocPage === totalDocPages}
                              onClick={() => setDocCurrentPage(prev => Math.min(totalDocPages, prev + 1))}
                              style={{ 
                                background: activeDocPage === totalDocPages ? 'rgba(0,0,0,0.02)' : 'var(--admin-card-bg)', 
                                border: '1px solid var(--admin-card-border)', 
                                color: activeDocPage === totalDocPages ? 'var(--admin-text-muted)' : 'var(--admin-text-main)', 
                                padding: '6px 12px', 
                                borderRadius: '6px', 
                                cursor: activeDocPage === totalDocPages ? 'not-allowed' : 'pointer',
                                fontSize: '0.8rem',
                                fontWeight: 500,
                                transition: 'all 0.2s'
                              }}
                            >
                              Siguiente
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--admin-text-muted)', padding: '40px', transition: 'color 0.3s' }}>
                  Selecciona o crea una carpeta del listado de la izquierda para administrar sus archivos.
                </div>
              )}
            </div>

          </div>
        )}

        {/* VIEW: USUARIOS (ROLES MANAGEMENT) */}
        {activeTab === 'usuarios' && user.role === 'admin' && (
          <div className="admin-container">
            <div className="admin-card" style={{ maxWidth: '800px', margin: '0 auto' }}>
              <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--admin-card-border)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <Users size={20} /> Control de Usuarios y Roles
              </h3>

              <form onSubmit={handleCreateUser} className="responsive-form">
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px' }}>Correo Electrónico</label>
                  <input type="email" required style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)' }} value={newAuthEmail} onChange={e => setNewAuthEmail(e.target.value)} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px' }}>Contraseña</label>
                  <input type="password" required style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)' }} value={newAuthPassword} onChange={e => setNewAuthPassword(e.target.value)} />
                </div>
                <div style={{ width: '150px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--admin-text-muted)', display: 'block', marginBottom: '4px' }}>Rol</label>
                  <select style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)' }} value={newAuthRole} onChange={e => setNewAuthRole(e.target.value)}>
                    <option value="user">Usuario</option>
                    <option value="admin">Administrador</option>
                  </select>
                </div>
                <button type="submit" style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '9px 18px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer', height: '35px' }}>
                  Añadir
                </button>
              </form>
              
              <div className="table-responsive">
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--admin-table-header-border)', transition: 'border-color 0.3s' }}>
                      <th style={{ padding: '12px' }}>Email</th>
                      <th style={{ padding: '12px' }}>Rol</th>
                      <th style={{ padding: '12px' }}>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {systemUsers.map(sysUser => (
                      <tr key={sysUser.id} style={{ borderBottom: '1px solid var(--admin-table-row-border)', transition: 'border-color 0.3s' }}>
                        <td style={{ padding: '12px' }}>{sysUser.email} {sysUser.email === user.email && <span style={{ color: '#22c55e', fontSize: '0.8rem', marginLeft: '5px' }}>(Tú)</span>}</td>
                        <td style={{ padding: '12px' }}>
                          <select 
                            value={sysUser.role}
                            onChange={(e) => handleChangeRole(sysUser.id, e.target.value)}
                            disabled={sysUser.email === user.email}
                            style={{ padding: '4px', borderRadius: '4px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)' }}
                          >
                            <option value="user">Usuario</option>
                            <option value="admin">Administrador</option>
                          </select>
                        </td>
                        <td style={{ padding: '12px', display: 'flex', gap: '8px' }}>
                          <button 
                            onClick={() => handleResetUserPassword(sysUser.id)} 
                            style={{ background: 'transparent', border: 'none', color: '#3b82f6', cursor: 'pointer' }}
                            title="Cambiar contraseña"
                          >
                            <Key size={16} />
                          </button>
                          {sysUser.email !== user.email && (
                            <button onClick={() => handleDeleteUser(sysUser.id)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                              <Trash2 size={16} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW: GLOSARIO MILITAR BASE */}
        {activeTab === 'glosario' && user.role === 'admin' && (
          <div className="admin-container">
            <div className="admin-card" style={{ maxWidth: '900px', margin: '0 auto' }}>
              <h3 style={{ marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--admin-card-border)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <Database size={20} /> Glosario y Doctrina Base
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--admin-text-muted)', marginBottom: '20px' }}>
                Define aquí términos, siglas, fechas clave o doctrina general. La Inteligencia Artificial leerá este texto <strong>antes</strong> de responder cualquier consulta, lo que ayuda a evitar alucinaciones y mejora la precisión de conceptos militares específicos independientemente del documento consultado.
              </p>

              <form onSubmit={handleSaveGlossary} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {glossaryMessage && (
                  <div style={{ padding: '10px', borderRadius: '6px', background: glossaryMessage.includes('Error') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)', color: glossaryMessage.includes('Error') ? '#ef4444' : '#22c55e' }}>
                    {glossaryMessage}
                  </div>
                )}
                
                <textarea 
                  style={{ width: '100%', minHeight: '350px', padding: '15px', borderRadius: '8px', border: '1px solid var(--admin-input-border)', background: 'var(--admin-input-bg)', color: 'var(--admin-text-main)', fontFamily: 'monospace', fontSize: '0.9rem', resize: 'vertical' }}
                  placeholder="Ejemplo:&#10;JEMGE: Jefe del Estado Mayor General del Ejército&#10;Guerra de Malvinas: Conflicto bélico de 1982..."
                  value={militaryGlossary}
                  onChange={e => setMilitaryGlossary(e.target.value)}
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="submit" disabled={savingGlossary} style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '6px', fontWeight: 600, cursor: savingGlossary ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {savingGlossary ? 'Guardando...' : 'Guardar Glosario'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {activeTab === 'perfil' && (
          <div className="profile-container">
            <div className="glass-card" style={{ maxWidth: '500px', margin: '0 auto' }}>
              <h3 style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '10px', transition: 'border-color 0.3s' }}>
                <Settings size={20} /> Mi Perfil
              </h3>

              <div style={{ marginBottom: '20px' }}>
                <strong>Cuenta:</strong> {user.email} <br />
                <strong>Rol:</strong> {user.role === 'admin' ? 'Administrador' : 'Usuario'}
              </div>

              <h4 style={{ marginBottom: '15px' }}>Cambiar Contraseña</h4>
              <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {passwordChangeMessage && (
                  <div style={{ padding: '10px', borderRadius: '6px', background: passwordChangeMessage.includes('Error') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)', color: passwordChangeMessage.includes('Error') ? '#ef4444' : '#22c55e' }}>
                    {passwordChangeMessage}
                  </div>
                )}
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'rgba(255, 255, 255, 0.7)', display: 'block', marginBottom: '4px' }}>Contraseña Actual</label>
                  <input type="password" required style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.15)', background: 'rgba(9, 13, 22, 0.6)', color: '#f8fafc' }} value={passwordChangeOld} onChange={e => setPasswordChangeOld(e.target.value)} />
                </div>
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'rgba(255, 255, 255, 0.7)', display: 'block', marginBottom: '4px' }}>Nueva Contraseña</label>
                  <input type="password" required style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.15)', background: 'rgba(9, 13, 22, 0.6)', color: '#f8fafc' }} value={passwordChangeNew} onChange={e => setPasswordChangeNew(e.target.value)} />
                </div>
                <button type="submit" style={{ background: 'var(--primary-color)', color: 'white', border: 'none', padding: '10px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}>
                  Actualizar Contraseña
                </button>
              </form>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

export default App
