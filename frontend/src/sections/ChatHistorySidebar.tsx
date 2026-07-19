import { useState } from 'react'
import { Plus, ChevronLeft, MoreHorizontal, Sparkles } from 'lucide-react'

interface ChatSession {
  id: string
  title: string
  date: string
}

const mockSessions: ChatSession[] = [
  { id: '1', title: 'Blood Report Analysis', date: 'Today, 10:23 AM' },
  { id: '2', title: 'Headache & Migraine', date: 'Yesterday, 4:15 PM' },
  { id: '3', title: 'Vitamin D Deficiency', date: 'Jun 15, 2:30 PM' },
  { id: '4', title: 'X-Ray Interpretation', date: 'Jun 14, 11:00 AM' },
  { id: '5', title: 'Diet Recommendations', date: 'Jun 12, 9:45 AM' },
  { id: '6', title: 'Sleep Disorder Consult', date: 'Jun 10, 6:20 PM' },
  { id: '7', title: 'Allergy Symptoms', date: 'Jun 8, 3:10 PM' },
  { id: '8', title: 'Annual Checkup Review', date: 'Jun 5, 10:00 AM' },
]

export default function ChatHistorySidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [activeChat, setActiveChat] = useState('1')

  if (collapsed) {
    return (
      <div
        className="flex items-start justify-center pt-6"
        style={{
          width: '48px',
          minWidth: '48px',
          height: '100vh',
          background: 'var(--bg-base)',
          boxShadow: 'inset -4px 0 8px rgba(209, 209, 214, 0.2)',
          position: 'relative',
          zIndex: 5,
        }}
      >
        <button
          onClick={() => setCollapsed(false)}
          className="neu-convex-sm flex items-center justify-center"
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 150ms ease-in-out',
          }}
          title="Expand sidebar"
        >
          <ChevronLeft size={16} style={{ color: 'var(--text-secondary)', transform: 'rotate(180deg)' }} />
        </button>
      </div>
    )
  }

  return (
    <aside
      className="flex flex-col"
      style={{
        width: '280px',
        minWidth: '280px',
        height: '100vh',
        background: 'var(--bg-base)',
        boxShadow: 'inset -4px 0 8px rgba(209, 209, 214, 0.2), 4px 0 12px rgba(209, 209, 214, 0.1)',
        position: 'relative',
        zIndex: 5,
        padding: '20px 16px',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '22px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            letterSpacing: '-0.02em',
          }}
        >
          DocTalk
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCollapsed(true)}
            className="neu-convex-sm flex items-center justify-center"
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 150ms ease-in-out',
            }}
            title="Collapse sidebar"
          >
            <ChevronLeft size={14} style={{ color: 'var(--text-secondary)' }} />
          </button>
          <button
            className="neu-btn-accent flex items-center justify-center gap-1.5"
            style={{
              height: '32px',
              padding: '0 14px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: 'var(--font-body)',
            }}
          >
            <Plus size={14} />
            New Chat
          </button>
        </div>
      </div>

      {/* Chat List */}
      <div
        className="flex flex-col gap-2 flex-1 overflow-y-auto"
        style={{ paddingRight: '4px', marginRight: '-4px' }}
      >
        {mockSessions.map((session, index) => {
          const isActive = activeChat === session.id
          return (
            <button
              key={session.id}
              onClick={() => setActiveChat(session.id)}
              className={isActive ? 'neu-pressed-sm' : 'neu-flat-sm'}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 14px',
                borderRadius: '14px',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 150ms ease-in-out',
                animationDelay: `${index * 0.1}s`,
              }}
            >
              <div className="flex-1 min-w-0">
                <p
                  style={{
                    fontSize: '13px',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? 'var(--text-primary)' : 'var(--text-primary)',
                    fontFamily: 'var(--font-body)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    marginBottom: '2px',
                  }}
                >
                  {session.title}
                </p>
                <p
                  style={{
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-body)',
                  }}
                >
                  {session.date}
                </p>
              </div>
              <MoreHorizontal
                size={16}
                style={{
                  color: 'var(--text-secondary)',
                  flexShrink: 0,
                  marginLeft: '8px',
                }}
              />
            </button>
          )
        })}
      </div>

      {/* Pro Plan Pill */}
      <div
        className="neu-convex mt-4 flex items-center gap-3"
        style={{
          padding: '14px 16px',
          borderRadius: '16px',
          cursor: 'pointer',
          transition: 'all 150ms ease-in-out',
        }}
      >
        <div
          className="flex items-center justify-center"
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'linear-gradient(145deg, #7B61FF, #9B85FF)',
          }}
        >
          <Sparkles size={18} style={{ color: 'white' }} />
        </div>
        <div>
          <p
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
            }}
          >
            Pro Plan
          </p>
          <p
            style={{
              fontSize: '11px',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-body)',
            }}
          >
            Unlock all features
          </p>
        </div>
      </div>
    </aside>
  )
}
