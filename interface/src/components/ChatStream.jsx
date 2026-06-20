import { useEffect, useRef } from 'react'

const senderLabels = {
  user: 'you',
  agent: 'hvra agent',
  system: 'system',
}

export default function ChatStream({ messages }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) {
      return
    }
    containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5" ref={containerRef}>
      <div className="space-y-4">
        {messages.map((message, index) => {
          if (message.role === 'system') {
            return (
              <div key={index} className="flex justify-center">
                <div className="type-level-3 inline-flex items-center gap-2 rounded-pill border border-DEFAULT bg-surface-secondary px-3 py-2">
                  <span>{message.text}</span>
                </div>
              </div>
            )
          }

          const isUser = message.role === 'user'
          const bubbleClasses = isUser
            ? 'rounded-tl-md rounded-tr-sm rounded-br-md rounded-bl-md bg-ink-primary text-surface-primary'
            : 'rounded-tl-sm rounded-tr-md rounded-br-md rounded-bl-md bg-surface-secondary text-ink-primary'
          const alignment = isUser ? 'justify-end' : 'justify-start'

          return (
            <div key={index} className={`flex ${alignment}`}>
              <div className="max-w-[90%]">
                <p className="type-level-3 mb-2">{senderLabels[message.role]}</p>
                <div className={`type-level-2 p-3 leading-[1.65] ${bubbleClasses}`}>
                  {message.text}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
