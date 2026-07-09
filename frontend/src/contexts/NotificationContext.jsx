import React, { createContext, useCallback, useContext, useState } from 'react'

const NotificationContext = createContext(null)

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])

  const addNotification = useCallback((payload) => {
    const id = String(Date.now())
    const note = { id, ...payload }
    setNotifications((s) => [...s, note])
    return id
  }, [])

  const removeNotification = useCallback((id) => {
    setNotifications((s) => s.filter((n) => n.id !== id))
  }, [])

  const clearNotifications = useCallback(() => setNotifications([]), [])

  return (
    <NotificationContext.Provider
      value={{ notifications, addNotification, removeNotification, clearNotifications }}
    >
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotifications() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotifications must be used within NotificationProvider')
  return ctx
}

export default NotificationContext
