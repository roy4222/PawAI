'use client'

import { useState, useEffect, useRef } from 'react' // ✨ 1. 這裡加了 useRef
import Link from 'next/link'
import { Mic, Square, Bot, User, Home, FileText, History } from 'lucide-react'
import { useAudioRecorder } from '@/hooks/use-audio-recorder'
import { PanelCard } from '@/components/shared/panel-card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useStateStore } from '@/stores/state-store'

function VoiceRecorderSection() {
  const { isRecording, isProcessing, lastResult, error, startRecording, stopRecording } = useAudioRecorder()

  // ✨ 2. 新增一個記憶體，用來記住「最後一次播放的音檔網址」
  const lastPlayedUrl = useRef<string | null>(null)

  // ✨ 3. 更新播放邏輯：確保 React 重新渲染時不會重複播放（徹底消滅回音）
  useEffect(() => {
    // 只有當網址存在，且「跟上次播的不一樣」時，才准播放！
    if (lastResult?.audio_url && lastResult.audio_url !== lastPlayedUrl.current) {
      lastPlayedUrl.current = lastResult.audio_url; // 把這次的網址寫入記憶體
      const audio = new Audio(lastResult.audio_url);
      audio.play().catch(e => console.log("等待互動才能播放音檔", e));
    }
  }, [lastResult?.audio_url]);

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
          {/* 👤 使用者說的話 */}
          <div className="flex flex-col gap-1 items-end">
            <span className="text-[10px] text-sky-400 font-bold flex items-center gap-1">
              YOU <User className="h-3 w-3" />
            </span>
            <div className="bg-sky-500 text-white px-4 py-2 rounded-2xl rounded-tr-none max-w-[85%] shadow-sm">
              <p className="text-sm font-medium">{lastResult.asr || '(辨識中或無聲音)'}</p>
            </div>
          </div>

          {/* 🐶 機器狗回覆 */}
          {lastResult.reply_text && (
            <div className="flex flex-col gap-1 items-start">
              <span className="text-[10px] text-primary font-bold flex items-center gap-1">
                <Bot className="h-3 w-3" /> PawAI
              </span>
              <div className="bg-primary/10 border border-primary/30 px-4 py-2 rounded-2xl rounded-tl-none max-w-[85%] shadow-sm">
                <p className="text-sm text-primary font-bold">{lastResult.reply_text}</p>
              </div>
              {/* 這裡已經確認沒有 <audio autoPlay> 標籤了 */}
            </div>
          )}
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
    <PanelCard 
      title="語音互動" 
      icon={<Mic className="h-4 w-4" />} 
      status={speechState ? "active" : "loading"}
      href="/studio/speech"
    >
      <div className="flex flex-col gap-6">
        {/* 1. 互動區置頂 */}
        <VoiceRecorderSection />

        {/* 2. 歷史狀態 */}
        {speechState?.last_asr_text && (
          <div className="flex flex-col gap-2 p-3 bg-surface-hover rounded-lg border border-border/30 opacity-60">
            <span className="text-[9px] text-muted-foreground uppercase font-bold">上次互動歷史</span>
            <p className="text-[11px]">👤 {speechState.last_asr_text}</p>
            <p className="text-[11px] text-primary italic">🐶 {speechState.last_tts_text}</p>
          </div>
        )}

        {/* 3. 底部按鈕 */}
        <div className="grid grid-cols-2 gap-2">
          <Link href="/studio/speech" className="w-full">
            <Button variant="outline" size="sm" className="w-full text-xs py-4">對話詳情</Button>
          </Link>
          <Button variant="outline" size="sm" className="w-full text-xs py-4">事件歷史</Button>
        </div>

        {/* 返回首頁按鈕 */}
        <Link href="/studio" className="w-full mt-1 block">
          <Button variant="ghost" size="sm" className="w-full text-xs text-muted-foreground hover:text-foreground">
            <Home className="w-4 h-4 mr-2" /> 返回控制首頁
          </Button>
        </Link>
      </div>
    </PanelCard>
  )
}