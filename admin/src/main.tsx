import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { AuthProvider } from './contexts/AuthProvider'
import { loadPublicConfig } from './services/runtimeConfig'
import './styles.css'
void loadPublicConfig().finally(() => createRoot(document.getElementById('root')!).render(<StrictMode><AuthProvider><App /></AuthProvider></StrictMode>))
