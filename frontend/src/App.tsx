import { RouterProvider } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import { router } from '@/shared/app/router'
import { ThemeProvider } from '@/shared/app/ThemeProvider'
import { ToastProvider } from '@/shared/app/ToastProvider'

function App() {
  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <RouterProvider router={router} />
        <ToastProvider />
      </ThemeProvider>
    </MotionConfig>
  )
}

export default App
