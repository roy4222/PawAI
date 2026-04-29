"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { ArrowUp, PawPrint, Sparkles, HandMetal, Activity, Mic, Square, Camera, User, Hand, Brain } from "lucide-react"
import { useStateStore } from "@/stores/state-store"
import { useAudioRecorder } from "@/hooks/use-audio-recorder"
import { useTextCommand } from "@/hooks/use-text-command"
import { AudioVisualizer } from "@/components/chat/audio-visualizer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

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

interface VoiceMessage {
  id: string
  type: "voice"
  text: string
  intent: string
  confidence: number
  timestamp: string
}

type ChatMessage = UserMessage | AIMessage | VoiceMessage

function formatTime(date: Date): string {
  return date.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
}

const MODULE_STATUS = [
  { name: "Face", icon: User, key: "faceState" as const },
  { name: "Speech", icon: Mic, key: "speechState" as const },
  { name: "Gesture", icon: Hand, key: "gestureState" as const },
  { name: "Pose", icon: Activity, key: "poseState" as const },
  { name: "Brain", icon: Brain, key: "brainState" as const },
]

const QUICK_ACTIONS = [
  { label: "打個招呼", desc: "讓 PawAI 揮手問好", Icon: HandMetal },
  { label: "查看狀態", desc: "系統健康與模組狀態", Icon: Activity },
  { label: "語音對話", desc: "開啟語音互動模式", Icon: Mic },
  { label: "拍張照片", desc: "拍攝當前場景照片", Icon: Camera },
]

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState("")
  const [isThinking, setIsThinking] = useState(false)
  const faceState = useStateStore((s) => s.faceState)
  const speechState = useStateStore((s) => s.speechState)
  const gestureState = useStateStore((s) => s.gestureState)
  const poseState = useStateStore((s) => s.poseState)
  const brainState = useStateStore((s) => s.brainState)
  const stateMap = { faceState, speechState, gestureState, poseState, brainState }
  const { isRecording, isProcessing, audioLevels, lastResult: voiceResult, error: voiceError, startRecording, stopRecording } = useAudioRecorder()
  const { sendText } = useTextCommand()
  const lastTtsText = useStateStore((s) => s.lastTtsText)
  const lastTtsAt = useStateStore((s) => s.lastTtsAt)
  const pendingRequestIdRef = useRef<string | null>(null)
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevVoiceResultRef = useRef(voiceResult)

  const hasMessages = messages.length > 0

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isThinking])

  // Cleanup pending timeout on unmount
  useEffect(() => {
    return () => {
      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current)
    }
  }, [])

  // TTS reply → AI bubble (only when pending)
  useEffect(() => {
    if (lastTtsAt && lastTtsText && pendingRequestIdRef.current) {
      pendingRequestIdRef.current = null
      if (pendingTimeoutRef.current) {
        clearTimeout(pendingTimeoutRef.current)
        pendingTimeoutRef.current = null
      }

      setIsThinking(false)

      const aiMsg: AIMessage = {
        id: `ai-${Date.now()}`,
        type: "ai",
        text: lastTtsText,
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, aiMsg])
    }
  }, [lastTtsAt, lastTtsText])

  // Voice result → add as voice message + enter pending
  useEffect(() => {
    if (voiceResult && voiceResult !== prevVoiceResultRef.current) {
      prevVoiceResultRef.current = voiceResult
      const voiceMsg: VoiceMessage = {
        id: `voice-${Date.now()}`,
        type: "voice",
        text: voiceResult.asr,
        intent: voiceResult.intent,
        confidence: voiceResult.confidence,
        timestamp: formatTime(new Date()),
      }

      setMessages((prev) => [...prev, voiceMsg])

      // Enter pending for TTS reply
      const requestId = `voice-${Date.now()}`
      pendingRequestIdRef.current = requestId
      setIsThinking(true)

      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current)
      pendingTimeoutRef.current = setTimeout(() => {
        if (pendingRequestIdRef.current === requestId) {
          pendingRequestIdRef.current = null
          setIsThinking(false)
        }
      }, 8000)
    }
  }, [voiceResult])

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

  function handleSend() {
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

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    // Send via /ws/text
    const sent = sendText(text)
    if (!sent) {
      const errMsg: AIMessage = {
        id: `ai-err-${Date.now()}`,
        type: "ai",
        text: "文字通道未連線，請確認 Gateway 是否啟動。",
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, errMsg])
      return
    }

    // Enter pending — wait for TTS reply
    setIsThinking(true)
    const requestId = `req-${Date.now()}`
    pendingRequestIdRef.current = requestId

    if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current)
    pendingTimeoutRef.current = setTimeout(() => {
      if (pendingRequestIdRef.current === requestId) {
        pendingRequestIdRef.current = null
        setIsThinking(false)
        const errMsg: AIMessage = {
          id: `ai-timeout-${Date.now()}`,
          type: "ai",
          text: "回應逾時，請確認 LLM 是否在線。",
          timestamp: formatTime(new Date()),
        }
        setMessages((prev) => [...prev, errMsg])
      }
    }, 8000)

    textareaRef.current?.focus()
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
      "relative rounded-2xl border transition-all duration-200",
      isRecording
        ? "border-red-500/40 shadow-[0_0_0_1px_rgba(239,68,68,0.15)] bg-surface"
        : "border-border/60 bg-surface focus-within:border-primary/40 focus-within:shadow-[0_0_0_1px_rgba(124,107,255,0.15)]",
      hasMessages ? "mx-4 mb-4" : "w-full"
    )}>
      <Textarea
        ref={textareaRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isRecording ? "錄音中..." : "傳送訊息給 PawAI…"}
        disabled={isThinking || isRecording}
        rows={1}
        className={cn(
          "min-h-[48px] max-h-[200px] resize-none border-0 bg-transparent pr-24",
          "text-foreground placeholder:text-muted-foreground/50",
          "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-transparent",
          "px-4 py-3 text-[15px] leading-relaxed"
        )}
      />
      {/* Mic button — expands to pill with audio bars when recording */}
      <Button
        onClick={() => isRecording ? stopRecording() : startRecording()}
        disabled={isThinking || isProcessing}
        size={isRecording && audioLevels.length > 0 ? "default" : "icon"}
        className={cn(
          "absolute bottom-2.5 transition-all duration-200",
          isRecording
            ? "right-12 h-8 px-3 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-sm flex items-center gap-2"
            : isProcessing
              ? "right-12 h-8 w-8 rounded-lg bg-amber-500 text-white cursor-wait"
              : "right-12 h-8 w-8 rounded-lg bg-muted text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground"
        )}
        title={isRecording ? "停止錄音" : isProcessing ? "辨識中..." : "語音輸入"}
      >
        {isRecording ? (
          <>
            <AudioVisualizer levels={audioLevels} isActive={isRecording} />
            {audioLevels.length === 0 && <Mic className="h-3.5 w-3.5 animate-pulse" />}
            <Square className="h-3 w-3 shrink-0" />
          </>
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>
      {/* Send button */}
      <Button
        onClick={handleSend}
        disabled={isThinking || isRecording || !inputText.trim()}
        size="icon"
        className={cn(
          "absolute right-2.5 bottom-2.5 h-8 w-8 rounded-lg transition-all duration-200",
          inputText.trim() && !isRecording
            ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
            : "bg-muted text-muted-foreground cursor-not-allowed"
        )}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
      {voiceError && (
        <div className="absolute -top-7 left-0 right-0 text-center">
          <span className="text-[11px] text-destructive bg-background/90 px-2 py-0.5 rounded">
            {voiceError}
          </span>
        </div>
      )}
    </div>
  )

  // ── Welcome view (no messages yet) — Mission Control ──
  if (!hasMessages) {
    return (
      <div className="relative flex flex-col items-center justify-center h-full px-6 control-grid control-glow">
        <div className="flex flex-col items-center gap-8 w-full max-w-2xl -mt-16">
          {/* Hero */}
          <div className="flex flex-col items-center gap-4">
            <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-sky-500/10 border border-sky-400/20 hud-ring">
              <PawPrint className="h-8 w-8 text-sky-400" />
              <div className="absolute inset-0 rounded-2xl hud-pulse" />
            </div>
            <h1 className="text-3xl font-bold text-foreground tracking-tighter">
              PawAI Studio
            </h1>
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground/60">
              Embodied AI Control Center
            </p>
          </div>

          {/* Module Status Strip */}
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-border/30 bg-surface/30 backdrop-blur-sm">
            {MODULE_STATUS.map(({ name, icon: Icon, key }) => {
              const active = stateMap[key] != null
              return (
                <div key={name} className="flex items-center gap-1.5 px-2">
                  <Icon className={cn(
                    "h-3.5 w-3.5 transition-colors duration-300",
                    active ? "text-emerald-400" : "text-muted-foreground/40"
                  )} />
                  <span className={cn(
                    "text-[11px] font-mono transition-colors duration-300",
                    active ? "text-foreground/80" : "text-muted-foreground/40"
                  )}>
                    {name}
                  </span>
                  <div className={cn(
                    "w-1.5 h-1.5 rounded-full transition-all duration-300",
                    active ? "bg-emerald-400 motion-safe:animate-pulse" : "bg-muted-foreground/20"
                  )} />
                </div>
              )
            })}
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-2.5 w-full max-w-md">
            {QUICK_ACTIONS.map(({ label, desc, Icon }) => (
              <button
                key={label}
                onClick={() => {
                  setInputText(label)
                  textareaRef.current?.focus()
                }}
                className={cn(
                  "relative flex items-center gap-3 rounded-xl border border-border/30 px-4 py-3",
                  "bg-surface/30 backdrop-blur-sm overflow-hidden",
                  "hover:bg-surface-hover hover:border-sky-400/20",
                  "hover:shadow-[0_0_20px_rgba(56,189,248,0.06)]",
                  "transition-all duration-200 cursor-pointer text-left group"
                )}
              >
                {/* Left accent bar */}
                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-sky-400/30 group-hover:bg-sky-400/60 transition-colors" />
                <Icon className="h-4 w-4 text-muted-foreground group-hover:text-sky-400 transition-colors shrink-0" />
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-foreground group-hover:text-foreground transition-colors">
                    {label}
                  </span>
                  <span className="text-[11px] text-muted-foreground/60">
                    {desc}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Composer */}
          <div className="w-full mt-2">
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

            if (msg.type === "voice") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%]">
                    <div className="rounded-2xl rounded-br-md bg-sky-500/10 border border-sky-400/20 px-4 py-2.5 text-[15px] text-foreground leading-relaxed">
                      <div className="flex items-center gap-2 mb-1">
                        <Mic className="h-3 w-3 text-sky-400" />
                        <span className="text-[10px] text-sky-400 font-mono">語音輸入</span>
                        <Badge className="text-[9px] px-1.5 py-0 h-4 rounded-full bg-emerald-500/10 text-emerald-400 border-transparent font-normal">
                          已發佈
                        </Badge>
                      </div>
                      {msg.text}
                      {msg.intent && (
                        <div className="mt-1.5 text-[10px] text-muted-foreground font-mono">
                          intent: {msg.intent} · {Math.round(msg.confidence * 100)}%
                        </div>
                      )}
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
