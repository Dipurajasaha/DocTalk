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
        <div key={n.id} className="neu-convex" style={{ minWidth: 260, maxWidth: 420, color: n.type === 'error' ? '#dc2626' : n.type === 'success' ? '#059669' : '#4f46e5', padding: '12px 16px', borderRadius: '16px', borderLeft: n.type === 'error' ? '4px solid #dc2626' : n.type === 'success' ? '4px solid #10b981' : '4px solid #8B7EFF' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{n.message}</div>
            <button onClick={() => removeNotification(n.id)} style={{ marginLeft: 12, background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}>✕</button>
          </div>
        </div>
      ))}
    </div>
  );
}
