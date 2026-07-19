import { useState } from 'react'
import {
  User,
  FileText,
  Scan,
  CalendarDays,
  MessageSquare,
  Clock,
  Settings,
} from 'lucide-react'

const navItems = [
  { icon: User, label: 'Profile', id: 'profile' },
  { icon: FileText, label: 'Analyze', id: 'analyze' },
  { icon: Scan, label: 'X-Ray', id: 'xray' },
  { icon: CalendarDays, label: 'Appointments', id: 'appointments' },
  { icon: MessageSquare, label: 'Chat', id: 'chat' },
  { icon: Clock, label: 'History', id: 'history' },
]

export default function LeftSidebar() {
  const [active, setActive] = useState('chat')

  return (
    <nav
      className="flex flex-col items-center py-6 gap-2"
      style={{
        width: '80px',
        minWidth: '80px',
        height: '100vh',
        background: 'var(--bg-base)',
        boxShadow: 'inset -4px 0 8px rgba(209, 209, 214, 0.3), inset 4px 0 8px rgba(255, 255, 255, 0.5)',
        position: 'relative',
        zIndex: 10,
      }}
    >
      {/* Logo */}
      <button
        className="neu-convex flex items-center justify-center mb-8 transition-all duration-150 hover:scale-105 active:scale-95"
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          padding: '10px',
        }}
        title="DocTalk AI"
      >
        <img
          src="/logo-icon.png"
          alt="DocTalk"
          style={{ width: '28px', height: '28px', objectFit: 'contain' }}
        />
      </button>

      {/* Nav Icons */}
      <div className="flex flex-col items-center gap-3 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = active === item.id
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={isActive ? 'neu-active' : 'neu-flat-sm'}
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 150ms ease-in-out',
                border: 'none',
              }}
              title={item.label}
            >
              <Icon
                size={22}
                style={{
                  color: isActive ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  transition: 'color 150ms ease-in-out',
                }}
              />
            </button>
          )
        })}
      </div>

      {/* Bottom: Avatar + Settings */}
      <div className="flex flex-col items-center gap-3 mt-auto">
        <button
          className="neu-flat-sm"
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            padding: '3px',
            cursor: 'pointer',
            border: 'none',
            overflow: 'hidden',
            transition: 'all 150ms ease-in-out',
          }}
          title="My Profile"
        >
          <img
            src="/avatar.jpg"
            alt="User"
            style={{
              width: '100%',
              height: '100%',
              borderRadius: '50%',
              objectFit: 'cover',
            }}
          />
        </button>

        <button
          className="neu-flat-sm"
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            border: 'none',
            transition: 'all 150ms ease-in-out',
          }}
          title="Settings"
        >
          <Settings size={18} style={{ color: 'var(--text-secondary)' }} />
        </button>
      </div>
    </nav>
  )
}
