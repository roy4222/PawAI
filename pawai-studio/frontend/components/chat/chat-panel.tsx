"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { ArrowUp, PawPrint, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { EventItem } from "@/components/shared/event-item"
import { cn } from "@/lib/utils"
import type { PawAIEvent } from "@/contracts/types"

interface UserMessage {
  id: string
  type: "user"
  text: string
  timestamp: string
}

interface AIMessage {
  id: string
  type: "ai"
  text: string
  timestamp: string
}

interface EventMessage {
  id: string
  type: "event"
  event: PawAIEvent
}

type ChatMessage = UserMessage | AIMessage | EventMessage

function formatTime(date: Date): string {
  return date.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
}

interface ChatPanelProps {
  events?: PawAIEvent[]
}

export function ChatPanel({ events = [] }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState("")
  const [isThinking, setIsThinking] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevEventsLenRef = useRef(0)

  const hasMessages = messages.length > 0

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isThinking])

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = "auto"
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
  }, [])

  useEffect(() => {
    adjustTextareaHeight()
  }, [inputText, adjustTextareaHeight])

  // Inject incoming events as inline event cards
  useEffect(() => {
    if (events.length > prevEventsLenRef.current) {
      const newEvents = events.slice(prevEventsLenRef.current)
      prevEventsLenRef.current = events.length
      setMessages((prev) => [
        ...prev,
        ...newEvents.map((e) => ({
          id: `event-${e.id}`,
          type: "event" as const,
          event: e,
        })),
      ])
    }
  }, [events])

  async function handleSend() {
    const text = inputText.trim()
    if (!text || isThinking) return

    const userMsg: UserMessage = {
      id: `user-${Date.now()}`,
      type: "user",
      text,
      timestamp: formatTime(new Date()),
    }
    setMessages((prev) => [...prev, userMsg])
    setInputText("")
    setIsThinking(true)

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    try {
      const gatewayUrl = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000"
      const res = await fetch(`${gatewayUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          command_type: "chat",
          text,
          session_id: "studio-session",
        }),
      })
      const json = await res.json()
      const aiMsg: AIMessage = {
        id: `ai-${Date.now()}`,
        type: "ai",
        text: json.reply ?? "（無回應）",
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      const errMsg: AIMessage = {
        id: `ai-err-${Date.now()}`,
        type: "ai",
        text: "連線失敗，請確認 Gateway 是否啟動。",
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setIsThinking(false)
      textareaRef.current?.focus()
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Composer input ──
  const composerInput = (
    <div className={cn(
      "relative rounded-2xl border border-border/60 bg-surface transition-all duration-200",
      "focus-within:border-primary/40 focus-within:shadow-[0_0_0_1px_rgba(124,107,255,0.15)]",
      hasMessages ? "mx-4 mb-4" : "w-full"
    )}>
      <Textarea
        ref={textareaRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="傳送訊息給 PawAI…"
        disabled={isThinking}
        rows={1}
        className={cn(
          "min-h-[48px] max-h-[200px] resize-none border-0 bg-transparent pr-14",
          "text-foreground placeholder:text-muted-foreground/50",
          "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-transparent",
          "px-4 py-3 text-[15px] leading-relaxed"
        )}
      />
      <Button
        onClick={handleSend}
        disabled={isThinking || !inputText.trim()}
        size="icon"
        className={cn(
          "absolute right-2.5 bottom-2.5 h-8 w-8 rounded-lg transition-all duration-200",
          inputText.trim()
            ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
            : "bg-muted text-muted-foreground cursor-not-allowed"
        )}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </div>
  )

  // ── Welcome view (no messages yet) ──
  if (!hasMessages) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6">
        <div className="flex flex-col items-center gap-6 w-full max-w-2xl -mt-20">
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-primary/10 border border-primary/20">
              <PawPrint className="h-6 w-6 text-primary" />
            </div>
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">
              PawAI Studio
            </h1>
            <p className="text-sm text-muted-foreground">
              你的 AI 機器狗控制中樞
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 w-full max-w-md mt-2">
            {[
              { label: "打個招呼", desc: "讓 PawAI 揮手問好" },
              { label: "查看狀態", desc: "系統健康與模組狀態" },
              { label: "開始巡邏", desc: "啟動自主巡邏模式" },
              { label: "拍張照片", desc: "拍攝當前場景照片" },
            ].map((item) => (
              <button
                key={item.label}
                onClick={() => {
                  setInputText(item.label)
                  textareaRef.current?.focus()
                }}
                className={cn(
                  "flex flex-col items-start gap-0.5 rounded-xl border border-border/50 px-4 py-3",
                  "bg-surface/50 hover:bg-surface-hover hover:border-border",
                  "transition-all duration-150 cursor-pointer text-left group"
                )}
              >
                <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                  {item.label}
                </span>
                <span className="text-xs text-muted-foreground">
                  {item.desc}
                </span>
              </button>
            ))}
          </div>

          <div className="w-full mt-4">
            {composerInput}
          </div>
        </div>
      </div>
    )
  }

  // ── Conversation view ──
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
          {messages.map((msg) => {
            if (msg.type === "user") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%]">
                    <div className="rounded-2xl rounded-br-md bg-primary/10 px-4 py-2.5 text-[15px] text-foreground leading-relaxed">
                      {msg.text}
                    </div>
                  </div>
                </div>
              )
            }

            if (msg.type === "ai") {
              return (
                <div key={msg.id} className="flex gap-3">
                  <div className="flex items-start pt-0.5 shrink-0">
                    <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10">
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[15px] text-foreground leading-relaxed">
                      {msg.text}
                    </p>
                  </div>
                </div>
              )
            }

            const e = msg.event
            const summary = typeof e.data === "object" && e.data !== null
              ? Object.entries(e.data).map(([k, v]) => `${k}=${v}`).join(" ")
              : ""
            return (
              <div key={msg.id} className="rounded-xl border border-border/50 bg-surface/30 overflow-hidden">
                <EventItem
                  timestamp={new Date(e.timestamp).toLocaleTimeString("zh-TW", { hour12: false })}
                  eventType={e.event_type}
                  source={e.source}
                  summary={summary}
                />
              </div>
            )
          })}

          {isThinking && (
            <div className="flex gap-3">
              <div className="flex items-start pt-0.5 shrink-0">
                <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                </div>
              </div>
              <div className="flex items-center gap-1 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="max-w-3xl mx-auto w-full">
        {composerInput}
      </div>
    </div>
  )
}
