'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Mic, Square, Bot, User, Home, Activity, Zap, Clock, MessageSquare, ServerCrash, Trash2 } from 'lucide-react'
import { useAudioRecorder } from '@/hooks/use-audio-recorder'
import { PanelCard } from '@/components/shared/panel-card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useStateStore } from '@/stores/state-store'

// ============================================================================
// 🐾 1. 首頁專用版面
// ============================================================================
function CompactSpeechWidget() {
  const { isRecording, isProcessing, lastResult, startRecording, stopRecording } = useAudioRecorder()
  const speechState = useStateStore((s) => s.speechState)
  const audioRef = useRef<HTMLAudioElement>(null) // ✨ 實體播放器參考

  useEffect(() => {
    // ✨ 終極防回音：只有當網址真的改變時，才指派給 audio 標籤並播放
    if (lastResult?.audio_url && audioRef.current) {
      if (audioRef.current.src !== lastResult.audio_url) {
        audioRef.current.src = lastResult.audio_url;
        audioRef.current.play().catch(e => console.log("播放被攔截:", e));
      }
    }
  }, [lastResult?.audio_url]);

  return (
    <PanelCard title="語音互動" icon={<Mic className="h-4 w-4" />} status={speechState ? "active" : "loading"} href="/studio/speech">
      {/* ✨ 隱藏的唯一播放器，保證絕對不會有雙重聲音 */}
      <audio ref={audioRef} className="hidden" />
      
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 p-3 rounded-lg border border-sky-500/30 bg-sky-500/5 shadow-md">
          <div className="flex items-center justify-between border-b border-sky-500/20 pb-2">
            <div className="flex flex-col">
              <span className="text-sm font-bold text-sky-400">語音互動區</span>
              <span className="text-[10px] text-muted-foreground italic">請對著麥克風說話</span>
            </div>
            <Button
              type="button"
              onClick={() => isRecording ? stopRecording() : startRecording()}
              className={cn("h-10 w-10 rounded-full transition-all shadow-md", isRecording ? "bg-red-500 hover:bg-red-600 animate-pulse" : "bg-sky-500 hover:bg-sky-600")}
            >
              {isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>
          </div>
          {lastResult && (
            <div className="flex flex-col gap-2 py-1">
              <div className="flex flex-col gap-1 items-end">
                <span className="text-[9px] text-sky-400 font-bold flex items-center gap-1">YOU <User className="h-2.5 w-2.5" /></span>
                <div className="bg-sky-500 text-white px-3 py-1.5 rounded-2xl rounded-tr-none max-w-[85%] text-xs">{lastResult.asr || '(辨識中...)'}</div>
              </div>
              {lastResult.reply_text && (
                <div className="flex flex-col gap-1 items-start">
                  <span className="text-[9px] text-primary font-bold flex items-center gap-1"><Bot className="h-2.5 w-2.5" /> PawAI</span>
                  <div className="bg-primary/10 border border-primary/30 px-3 py-1.5 rounded-2xl rounded-tl-none max-w-[85%] text-xs text-primary">{lastResult.reply_text}</div>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Link href="/studio/speech" className="w-full"><Button variant="outline" size="sm" className="w-full text-[11px] h-7">開啟戰情室</Button></Link>
          <Button variant="outline" size="sm" className="w-full text-[11px] h-7">事件歷史</Button>
        </div>
      </div>
    </PanelCard>
  )
}

// ============================================================================
// 🚀 2. 專屬頁面版面
// ============================================================================
function FullScreenSpeechDashboard() {
  const { isRecording, isProcessing, lastResult, startRecording, stopRecording } = useAudioRecorder()
  const [chatHistory, setChatHistory] = useState<any[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null) // ✨ 實體播放器參考

  const isGpuOffline = lastResult?.intent === 'offline_fallback';

  useEffect(() => {
    if (lastResult?.asr && lastResult?.reply_text) {
      setChatHistory(prev => {
        if (prev.some(item => item.audio_url === lastResult.audio_url)) return prev;
        const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        const displayAsr = lastResult.asr ? lastResult.asr : "(未辨識到清晰語音)";
        
        return [...prev, { ...lastResult, asr: displayAsr, timestamp: timeString }]
      })
    }
  }, [lastResult])

  useEffect(() => {
    // ✨ 終極防回音：只有當網址真的改變時，才指派給 audio 標籤並播放
    if (lastResult?.audio_url && audioRef.current) {
      if (audioRef.current.src !== lastResult.audio_url) {
        audioRef.current.src = lastResult.audio_url;
        audioRef.current.play().catch(e => console.log("播放被攔截:", e));
      }
    }
  }, [lastResult?.audio_url]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [chatHistory.length, isProcessing])

  return (
    <div className="w-[95vw] max-w-[800px] mx-auto h-auto md:h-[60vh] min-h-[500px] flex flex-col md:flex-row gap-4 justify-center relative md:-translate-x-30">
      
      {/* ✨ 隱藏的唯一播放器，保證絕對不會有雙重聲音 */}
      <audio ref={audioRef} className="hidden" />

      {/* 👈 左欄：主控台 */}
      <div className="w-full md:w-[35%] flex flex-col gap-3">
        <div className={cn(
          "flex-1 border rounded-xl p-5 flex flex-col items-center justify-center relative shadow-md overflow-hidden transition-colors duration-500",
          isGpuOffline ? "bg-red-950/20 border-red-500/40" : "bg-slate-900/40 border-sky-500/20"
        )}>
          
          <div className="absolute top-3 left-3 flex items-center gap-1.5">
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", isGpuOffline ? "bg-red-500 shadow-red-500/50" : (isRecording ? "bg-sky-400" : "bg-emerald-500"))} />
            <span className={cn("text-[9px] font-bold uppercase tracking-wider", isGpuOffline ? "text-red-400" : "text-emerald-400")}>
              {isGpuOffline ? "GPU OFFLINE" : "SYSTEM ONLINE"}
            </span>
          </div>

          <div className="my-4 flex flex-col items-center gap-4 relative">
            {isRecording && !isGpuOffline && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-28 h-28 bg-sky-500/20 rounded-full animate-ping" />
            )}

            <Button
              type="button"
              onClick={() => isRecording ? stopRecording() : startRecording()}
              className={cn(
                "h-20 w-20 rounded-full transition-all duration-300 z-10",
                isRecording 
                  ? "bg-sky-400 hover:bg-sky-500 scale-105 shadow-[0_0_30px_rgba(56,189,248,0.5)]" 
                  : (isGpuOffline ? "bg-red-500 hover:bg-red-400 shadow-[0_0_15px_rgba(239,68,68,0.3)]" : "bg-sky-600 hover:bg-sky-500 shadow-[0_0_15px_rgba(2,132,199,0.3)] hover:scale-105")
              )}
            >
              {isRecording ? <Square className="h-6 w-6 text-white" /> : <Mic className="h-6 w-6 text-white" />}
            </Button>
            
            <div className="flex flex-col items-center gap-1 mt-1">
              <span className="text-[11px] text-slate-300 font-medium whitespace-nowrap">
                {isRecording ? "🔴 錄音中 (點擊發送)..." : "點擊麥克風說話"}
              </span>
              {isGpuOffline && <span className="text-[9px] text-red-400 font-bold whitespace-nowrap">⚠️ 離線守護模式</span>}
            </div>
          </div>
        </div>

        {/* 數據看板 */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 flex flex-col gap-2.5 shadow-sm">
          <h3 className="text-[10px] text-slate-400 font-bold uppercase flex items-center gap-1.5"><Activity className="w-3 h-3 text-sky-400" /> 分析數據</h3>
          <div className="flex flex-col gap-1.5">
            <div className="bg-slate-950/50 rounded-md px-2.5 py-1.5 border border-slate-800/50 flex justify-between items-center">
              <div className="text-[10px] text-slate-500 flex items-center gap-1.5"><Zap className="w-3 h-3 text-yellow-400"/> 意圖分類</div>
              <div className={cn("text-[11px] font-bold", isGpuOffline ? "text-red-400" : "text-slate-200")}>
                {lastResult?.intent || '--'}
              </div>
            </div>
            <div className="bg-slate-950/50 rounded-md px-2.5 py-1.5 border border-slate-800/50 flex justify-between items-center">
              <div className="text-[10px] text-slate-500 flex items-center gap-1.5"><Activity className="w-3 h-3 text-green-400"/> 信心度</div>
              <div className="text-[11px] font-bold text-slate-200">
                {lastResult?.confidence ? `${(lastResult.confidence * 100).toFixed(0)}%` : '--'}
              </div>
            </div>
          </div>
        </div>

        {/* 下方按鈕區 */}
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={() => setChatHistory([])}
            className="w-10 h-8 bg-transparent border-slate-700 hover:bg-red-900/50 hover:text-red-400 text-slate-400 text-xs px-0 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
          <Link href="/studio" className="flex-1">
            <Button variant="outline" className="w-full h-8 bg-transparent border-slate-700 hover:bg-slate-800 text-slate-300 text-[11px]">
              <Home className="w-3.5 h-3.5 mr-1.5" /> 返回控制首頁
            </Button>
          </Link>
        </div>
      </div>

      {/* 👉 右欄：通訊歷史日誌 */}
      <div className="w-full md:w-[65%] bg-slate-900/40 border border-slate-800 rounded-xl flex flex-col overflow-hidden shadow-md relative">
        <div className="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 p-3.5 flex items-center gap-2.5 z-10">
          <MessageSquare className="w-3.5 h-3.5 text-sky-400" />
          <h2 className="text-[11px] font-bold text-slate-200 tracking-wide">互動通訊日誌</h2>
          <Badge variant="outline" className={cn("ml-auto text-[9px] px-1.5 py-0", isGpuOffline ? "bg-red-500/10 text-red-400 border-red-500/20" : "bg-sky-500/10 text-sky-400 border-sky-500/20")}>
            {isGpuOffline ? "Fallback Mode" : "Live Session"}
          </Badge>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 scroll-smooth bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950">
          
          {chatHistory.length === 0 && !isProcessing ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-2.5">
              <Bot className="w-8 h-8 opacity-50" />
              <p className="text-[11px]">系統待命中。請點擊左側發送指令。</p>
            </div>
          ) : (
            chatHistory.map((chat, index) => (
              <div key={index} className="flex flex-col gap-2 animate-in fade-in slide-in-from-bottom-2 duration-500">
                <div className="flex flex-col items-end gap-1">
                  <span className="text-[9px] text-sky-400/80 font-bold flex items-center gap-1 px-1">
                    {chat.timestamp} · YOU <User className="w-2.5 h-2.5" />
                  </span>
                  <div className="bg-sky-600 text-white px-3.5 py-2 rounded-2xl rounded-tr-none max-w-[85%] shadow-sm text-[13px]">{chat.asr}</div>
                </div>
                <div className="flex flex-col items-start gap-1">
                  <span className={cn("text-[9px] font-bold flex items-center gap-1 px-1", isGpuOffline ? "text-red-400/80" : "text-purple-400/80")}>
                    {isGpuOffline ? <ServerCrash className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />} PawAI · {chat.timestamp}
                  </span>
                  <div className="bg-slate-800 border border-slate-700 text-slate-200 px-3.5 py-2 rounded-2xl rounded-tl-none max-w-[85%] shadow-sm text-[13px] leading-relaxed">{chat.reply_text}</div>
                </div>
              </div>
            ))
          )}

          {isProcessing && (
             <div className="flex flex-col items-start gap-1 mt-1 animate-in fade-in duration-300">
                <span className="text-[9px] text-sky-400/80 font-bold flex items-center gap-1 px-1">
                  <Activity className="w-2.5 h-2.5 animate-bounce" /> System
                </span>
                <div className="bg-slate-800/80 border border-slate-700 text-slate-400 px-3.5 py-2 rounded-2xl rounded-tl-none shadow-sm text-[11px] flex items-center gap-2">
                  <span className="flex gap-0.5">
                    <span className="w-1 h-1 bg-sky-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                    <span className="w-1 h-1 bg-sky-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="w-1 h-1 bg-sky-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </span>
                  分析中...
                </div>
             </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// 🧠 3. 主輸出
// ============================================================================
export function SpeechPanel() {
  const pathname = usePathname();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => { setIsMounted(true) }, []);
  if (!isMounted) return null;

  if (pathname === '/studio/speech') return <FullScreenSpeechDashboard />
  return <CompactSpeechWidget />
}