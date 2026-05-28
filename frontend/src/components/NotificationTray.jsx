import React, { useEffect } from 'react';
import { useNotifications } from '../contexts';

export default function NotificationTray() {
  const { notifications, removeNotification } = useNotifications();

  useEffect(() => {
    const timers = [];
    notifications.forEach((n) => {
      if (!n.autoDismiss === false) return;
      const t = setTimeout(() => removeNotification(n.id), n.ttl || 5000);
      timers.push(t);
    });
    return () => timers.forEach(clearTimeout);
  }, [notifications, removeNotification]);

  if (!notifications || notifications.length === 0) return null;

  return (
    <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 2000, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {notifications.map((n) => (
        <div key={n.id} style={{ minWidth: 260, maxWidth: 420, background: n.type === 'success' ? '#ecfdf5' : n.type === 'error' ? '#fff1f2' : '#f0f9ff', color: n.type === 'error' ? '#991b1b' : '#064e3b', padding: '12px 14px', borderRadius: 8, boxShadow: '0 8px 20px rgba(2,6,23,0.08)', border: '1px solid rgba(2,6,23,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{n.message}</div>
            <button onClick={() => removeNotification(n.id)} style={{ marginLeft: 12, background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}>✕</button>
          </div>
        </div>
      ))}
    </div>
  );
}
