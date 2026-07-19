import { useState, useRef, useEffect } from 'react'
import { Plus, Send, Globe } from 'lucide-react'
import DNAHelix from './DNAHelix'

interface Message {
  id: string
  role: 'user' | 'ai'
  content: string
  timestamp: string
}

const mockMessages: Message[] = [
  {
    id: '1',
    role: 'user',
    content: 'I have been experiencing headaches for the past 3 days. Should I be concerned?',
    timestamp: '10:23 AM',
  },
  {
    id: '2',
    role: 'ai',
    content: 'I understand your concern. Persistent headaches can have various causes ranging from tension and dehydration to more serious conditions.\n\nTo better assess your situation, could you tell me:\n\n1. Where is the pain located (forehead, temples, back of head)?\n2. How would you rate the intensity on a scale of 1-10?\n3. Any accompanying symptoms like nausea, vision changes, or sensitivity to light?\n4. Have you been under unusual stress or changed your sleep patterns recently?\n\nIf the pain is severe (8+), sudden onset, or accompanied by confusion, please seek immediate medical attention.',
    timestamp: '10:24 AM',
  },
]

function TypingIndicator() {
  return (
    <div
      className="neu-flat"
      style={{
        alignSelf: 'flex-start',
        padding: '16px 20px',
        borderRadius: '20px 20px 20px 6px',
        maxWidth: '80px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: 'var(--text-secondary)',
            display: 'inline-block',
            animation: `typingBounce 1.4s ease-in-out ${i * 0.16}s infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes typingBounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  )
}

export default function MainChatArea() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [hasStartedChat, setHasStartedChat] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto demo: start with hero, then show messages after 2 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setMessages(mockMessages)
      setHasStartedChat(true)
      setIsTyping(true)
      setTimeout(() => setIsTyping(false), 3000)
    }, 2500)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isTyping])

  const handleSend = () => {
    if (!inputValue.trim()) return

    const newMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, newMsg])
    setInputValue('')
    setHasStartedChat(true)
    setIsTyping(true)
    setTimeout(() => setIsTyping(false), 2500)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <main
      className="flex flex-col"
      style={{
        flex: 1,
        height: '100vh',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Header */}
      <header
        className="flex items-center justify-between"
        style={{
          padding: '20px 28px',
          flexShrink: 0,
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '24px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.01em',
            }}
          >
            AI Health Assistant
          </h1>
          <p
            style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-body)',
              marginTop: '2px',
            }}
          >
            *Not a substitute for professional medical advice*
          </p>
        </div>

        {/* Language Selector */}
        <button
          className="neu-convex-pill flex items-center gap-2"
          style={{
            padding: '8px 16px',
            border: 'none',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-body)',
            transition: 'all 150ms ease-in-out',
          }}
        >
          <Globe size={15} style={{ color: 'var(--text-secondary)' }} />
          English
        </button>
      </header>

      {/* Chat Content Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        style={{
          padding: '0 28px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {!hasStartedChat && messages.length === 0 ? (
          /* Hero State with 3D DNA */
          <div
            className="flex flex-col items-center justify-center"
            style={{ minHeight: '100%' }}
          >
            <DNAHelix />
            <div className="text-center" style={{ marginTop: '-20px' }}>
              <h2
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '36px',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.02em',
                  marginBottom: '8px',
                }}
              >
                Welcome back, Sarah
              </h2>
              <p
                style={{
                  fontSize: '16px',
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-body)',
                  lineHeight: 1.6,
                }}
              >
                How can I assist your health today?
              </p>
            </div>
          </div>
        ) : (
          /* Active Chat Messages */
          <div className="flex flex-col gap-4" style={{ paddingBottom: '16px' }}>
            {messages.map((msg) =>
              msg.role === 'user' ? (
                <div
                  key={msg.id}
                  className="neu-pressed-sm"
                  style={{
                    alignSelf: 'flex-end',
                    maxWidth: '70%',
                    padding: '14px 18px',
                    borderRadius: '20px 20px 6px 20px',
                  }}
                >
                  <p
                    style={{
                      fontSize: '14px',
                      lineHeight: 1.6,
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-body)',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {msg.content}
                  </p>
                  <p
                    style={{
                      fontSize: '11px',
                      color: 'var(--text-secondary)',
                      marginTop: '6px',
                      textAlign: 'right',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {msg.timestamp}
                  </p>
                </div>
              ) : (
                <div
                  key={msg.id}
                  className="neu-flat"
                  style={{
                    alignSelf: 'flex-start',
                    maxWidth: '75%',
                    padding: '16px 20px',
                    borderRadius: '20px 20px 20px 6px',
                    background: 'var(--bg-elevated)',
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: 'linear-gradient(145deg, #7B61FF, #9B85FF)',
                      }}
                    >
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          color: 'white',
                          fontFamily: 'var(--font-display)',
                        }}
                      >
                        AI
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-body)',
                      }}
                    >
                      DocTalk Assistant
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: '14px',
                      lineHeight: 1.7,
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-body)',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {msg.content}
                  </p>
                  <p
                    style={{
                      fontSize: '11px',
                      color: 'var(--text-secondary)',
                      marginTop: '8px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {msg.timestamp}
                  </p>
                </div>
              )
            )}
            {isTyping && <TypingIndicator />}
          </div>
        )}
      </div>

      {/* Input Area */}
      <div
        style={{
          padding: '16px 28px 24px',
          flexShrink: 0,
        }}
      >
        <div
          className="neu-pressed-pill flex items-center gap-3"
          style={{
            padding: '6px 6px 6px 20px',
            maxWidth: '800px',
            margin: '0 auto',
          }}
        >
          {/* Attachment Button */}
          <button
            className="neu-convex-sm flex items-center justify-center flex-shrink-0"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 150ms ease-in-out',
            }}
            title="Attach file"
          >
            <Plus size={18} style={{ color: 'var(--text-secondary)' }} />
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask AI Health Assistant..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: '14px',
              fontFamily: 'var(--font-body)',
              color: 'var(--text-primary)',
              padding: '10px 0',
            }}
          />

          {/* Send Button */}
          <button
            onClick={handleSend}
            className="neu-btn-accent flex items-center justify-center flex-shrink-0"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 150ms ease-in-out',
            }}
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </main>
  )
}
