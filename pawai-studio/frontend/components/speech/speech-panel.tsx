'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Mic, Square, History, ArrowLeft, FileText, Bot, Home, User } from 'lucide-react'
import { useAudioRecorder } from '@/hooks/use-audio-recorder'
import { PanelCard } from '@/components/shared/panel-card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useStateStore } from '@/stores/state-store'

function VoiceRecorderSection() {
  const { isRecording, isProcessing, lastResult, error, startRecording, stopRecording } = useAudioRecorder()

  return (
    <div className="flex flex-col gap-4 p-4 rounded-lg border border-sky-500/30 bg-sky-500/5 shadow-md">
      <div className="flex items-center justify-between border-b border-sky-500/20 pb-3">
        <div className="flex flex-col">
          <span className="text-sm font-bold text-sky-400">語音互動區</span>
          <span className="text-[10px] text-muted-foreground italic">請對著麥克風說話</span>
        </div>
        <Button
          type="button"
          onClick={() => isRecording ? stopRecording() : startRecording()}
          disabled={isProcessing}
          className={cn(
            "h-12 w-12 rounded-full transition-all active:scale-90 shadow-lg",
            isRecording ? "bg-red-500 hover:bg-red-600 animate-pulse" : "bg-sky-500 hover:bg-sky-600"
          )}
        >
          {isRecording ? <Square className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </Button>
      </div>

      {lastResult && (
        <div className="flex flex-col gap-4 py-2 animate-in fade-in slide-in-from-top-4 duration-500">
          {/* 👤 使用者說的話 (放在最上面) */}
          <div className="flex flex-col gap-1 items-end">
            <span className="text-[10px] text-sky-400 font-bold flex items-center gap-1">
              YOU <User className="h-3 w-3" />
            </span>
            <div className="bg-sky-500 text-white px-4 py-2 rounded-2xl rounded-tr-none max-w-[85%] shadow-sm">
              <p className="text-sm font-medium">{lastResult.asr || '(辨識失敗，請再試一次)'}</p>
            </div>
          </div>

          {/* 🐶 機器狗回覆 (緊跟在下) */}
          {lastResult.reply_text && (
            <div className="flex flex-col gap-1 items-start">
              <span className="text-[10px] text-primary font-bold flex items-center gap-1">
                <Bot className="h-3 w-3" /> PawAI
              </span>
              <div className="bg-primary/10 border border-primary/30 px-4 py-2 rounded-2xl rounded-tl-none max-w-[85%] shadow-sm">
                <p className="text-sm text-primary font-bold">{lastResult.reply_text}</p>
              </div>
              <audio src={lastResult.audio_url} autoPlay className="hidden" />
            </div>
          )}
          
          <div className="flex justify-center">
             <Badge variant="outline" className="text-[8px] opacity-40 italic">
               Intent: {lastResult.intent}
             </Badge>
          </div>
        </div>
      )}
    </div>
  )
}

export function SpeechPanel() {
  const [isMounted, setIsMounted] = useState(false)
  useEffect(() => { setIsMounted(true) }, [])

  const speechState = useStateStore((s) => s.speechState)
  if (!isMounted) return null

  return (
    <PanelCard title="語音互動" icon={<Mic className="h-4 w-4" />} status={speechState ? "active" : "loading"}>
      <div className="flex flex-col gap-6">
        {/* 1. 互動區置頂 */}
        <VoiceRecorderSection />

        {/* 2. 歷史狀態 (縮小放在下面) */}
        {speechState?.last_asr_text && (
          <div className="flex flex-col gap-2 p-3 bg-surface-hover rounded-lg border border-border/30 opacity-60">
            <span className="text-[9px] text-muted-foreground uppercase font-bold">上次互動歷史</span>
            <p className="text-[11px]">👤 {speechState.last_asr_text}</p>
            <p className="text-[11px] text-primary italic">🐶 {speechState.last_tts_text}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" size="sm" className="text-xs py-4">對話詳情</Button>
          <Button variant="outline" size="sm" className="text-xs py-4">事件歷史</Button>
        </div>

        <Link href="/studio">
          <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground py-4">返回控制首頁</Button>
        </Link>
      </div>
    </PanelCard>
  )
}