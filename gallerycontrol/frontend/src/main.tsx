// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PollStatusProvider } from './context/PollStatusContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PollStatusProvider>
      <App />
    </PollStatusProvider>
  </StrictMode>,
)
