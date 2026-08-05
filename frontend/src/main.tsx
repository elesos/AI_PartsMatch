import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './i18n'
import { loadPublicRuntimeConfig } from './services/runtimeConfig'
import './styles/tokens.css'
import './styles/app.css'

void loadPublicRuntimeConfig().finally(() => {
  createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
})
