'use client'

import { useState, useEffect } from 'react'
import { Mic, History, ArrowLeft, FileText, Clock, Tag, Zap, Bot, Home } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { EventItem } from '@/components/shared/event-item'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
// 🛡️ 修正：只留下真的有使用到的 SpeechState，刪除沒用到的型別避免 Lint 報錯
import type { SpeechState } from '@/contracts/types'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'

const MOCK_SPEECH_STATE: SpeechState = {
  stamp: 1773561602.123,
  phase: 'speaking',
  last_asr_text: '幫我打開客廳的燈',
  last_intent: 'turn_on_light',
  last_tts_text: '好的，已經為您打開客廳的燈。',
  models_loaded: ['kws', 'asr', 'tts'],
}

const MOCK_SPEECH_EVENTS = [
  {
    id: 'evt-speech-001',
    timestamp: '2026-03-18T13:24:35.000Z',
    source: 'speech',
    event_type: 'wake_word',
    data: {},
  },
  {
    id: 'evt-speech-002',
    timestamp: '2026-03-18T13:24:38.000Z',
    source: 'speech',
    event_type: 'asr_result',
    data: { text: '你好，很高興認識你！' },
  },
  {
    id: 'evt-speech-003',
    timestamp: '2026-03-18T13:24:39.000Z',
    source: 'speech',
    event_type: 'intent_recognized',
    data: {
      intent: 'greet',
      text: '你好，很高興認識你！',
      confidence: 0.99,
      provider: 'whisper_local',
    },
  },
  {
    id: 'evt-speech-004',
    timestamp: '2026-03-18T13:24:52.000Z',
    source: 'speech',
    event_type: 'wake_word',
    data: {},
  },
  {
    id: 'evt-speech-005',
    timestamp: '2026-03-18T13:24:57.000Z',
    source: 'speech',
    event_type: 'asr_result',
    data: { text: '幫我打開客廳的燈' },
  },
  {
    id: 'evt-speech-006',
    timestamp: '2026-03-18T13:25:00.000Z',
    source: 'speech',
    event_type: 'intent_recognized',
    data: {
      intent: 'turn_on_light',
      text: '幫我打開客廳的燈',
      confidence: 0.98,
      provider: 'whisper_local',
    },
  }
]

const PHASE_CONFIG: Record<string, { label: string; colorClass: string }> = {
  idle_wakeword: { label: '等待喚醒', colorClass: 'bg-muted-foreground' },
  wake_ack: { label: '喚醒確認', colorClass: 'bg-warning' },
  loading_local_stack: { label: '載入模型中', colorClass: 'bg-warning' },
  listening: { label: '聆聽中', colorClass: 'bg-success' },
  transcribing: { label: '轉寫中', colorClass: 'bg-primary' },
  local_asr_done: { label: 'ASR 完成', colorClass: 'bg-primary' },
  cloud_brain_pending: { label: '等待大腦', colorClass: 'bg-warning' },
  speaking: { label: '播放中', colorClass: 'bg-success' },
  keep_alive: { label: '保持連線', colorClass: 'bg-muted-foreground' },
  unloading: { label: '卸載中', colorClass: 'bg-muted-foreground' },
}

const EXPECTED_MODELS = ['kws', 'asr', 'tts']
const USE_MOCK_DATA = true

export function SpeechPanel() {
  const [viewMode, setViewMode] = useState<'main' | 'history' | 'latest'>('main')

  const [isMounted, setIsMounted] = useState(false)
  useEffect(() => {
    setIsMounted(true)
  }, [])

  const formatTime = (ts: string | number | undefined) => {
    if (!isMounted || !ts) return '--:--:--'
    return new Date(ts).toLocaleTimeString('zh-TW', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const realSpeechState = useStateStore((s) => s.speechState) as SpeechState | null
  const allEvents = useEventStore((s) => s.events) || []
  const realSpeechEvents = allEvents.filter((e) => e.source === 'speech')

  const speechState = USE_MOCK_DATA ? MOCK_SPEECH_STATE : realSpeechState
  const speechEvents = USE_MOCK_DATA ? MOCK_SPEECH_EVENTS : realSpeechEvents

  const recentEvents = [...speechEvents].reverse().slice(0, 10)
  const latestIntentEvent = [...speechEvents].find(e => e.event_type === 'intent_recognized')

  // 🛡️ 修正：補上嚴格的型別宣告，讓 TypeScript 機器人不再報錯
  const eventData = latestIntentEvent?.data as { confidence?: number; provider?: string } | undefined
  const confidence = eventData?.confidence ? Number(eventData.confidence) : 0

  const latestTimeStr = formatTime(latestIntentEvent?.timestamp)

  let panelStatus: "loading" | "active" | "inactive" | "error" = "loading"
  if (!speechState) {
    panelStatus = "loading"
  } else if (speechState.phase === 'idle_wakeword' && recentEvents.length === 0) {
    panelStatus = "inactive"
  } else {
    panelStatus = "active"
  }

  const phaseStr = speechState?.phase ? String(speechState.phase) : 'idle_wakeword'
  const phaseConfig = PHASE_CONFIG[phaseStr] || { label: phaseStr, colorClass: 'bg-muted-foreground' }

  const isListening = phaseStr === 'listening'
  const isIdleEmpty = phaseStr === 'idle_wakeword' && recentEvents.length === 0

  const titleMap = { main: "語音互動", history: "事件歷史紀錄", latest: "最近對話詳情" }
  const iconMap = {
    main: <Mic className="h-4 w-4" />,
    history: <History className="h-4 w-4" />,
    latest: <FileText className="h-4 w-4" />
  }

  if (!isMounted) {
    return null
  }

  return (
    <PanelCard
      title={titleMap[viewMode]}
      icon={iconMap[viewMode]}
      status={panelStatus}
    >
      {/* 📖 視圖 1：歷史紀錄 */}
      {viewMode === 'history' && (
        <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-right-4 duration-300">
          <Button type="button" variant="ghost" size="sm" className="w-fit -ml-2 text-muted-foreground hover:text-foreground cursor-pointer" onClick={() => setViewMode('main')}>
            <ArrowLeft className="w-4 h-4 mr-1" /> 返回語音面板
          </Button>

          <ScrollArea className="h-[250px] pr-3">
            {recentEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-10">
                <History className="h-8 w-8 mb-2 opacity-20" />
                <span className="text-sm">目前沒有任何紀錄</span>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {/* 🛡️ 修正：明確告知 TypeScript 這個 evt 物件的長相 */}
                {recentEvents.map((evt: { id: string; timestamp: string; event_type: string; source: string; data?: any }) => {
                  let summary = String(evt.event_type)
                  const itemData = evt.data as { intent?: string; text?: string } | undefined

                  if (evt.event_type === 'intent_recognized') summary = `意圖: ${itemData?.intent || ''}`
                  if (evt.event_type === 'asr_result') summary = `轉寫: ${itemData?.text || ''}`
                  if (evt.event_type === 'wake_word') summary = `喚醒詞觸發`

                  const timeStr = formatTime(evt.timestamp)

                  return (
                    <EventItem
                      key={String(evt.id)}
                      timestamp={timeStr}
                      eventType={String(evt.event_type)}
                      source={String(evt.source)}
                      summary={summary}
                    />
                  )
                })}
              </div>
            )}
          </ScrollArea>
        </div>
      )}

      {/* 📄 視圖 2：最近對話詳情 */}
      {viewMode === 'latest' && (
        <div className="flex flex-col gap-3 animate-in fade-in slide-in-from-right-4 duration-300">
          <Button type="button" variant="ghost" size="sm" className="w-fit -ml-2 text-muted-foreground hover:text-foreground cursor-pointer" onClick={() => setViewMode('main')}>
            <ArrowLeft className="w-4 h-4 mr-1" /> 返回語音面板
          </Button>

          {!speechState?.last_asr_text ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
              <FileText className="h-8 w-8 mb-2 opacity-20" />
              <span className="text-sm">尚無對話紀錄</span>
            </div>
          ) : (
            <div className="flex flex-col gap-4 p-4 bg-surface-hover rounded-lg border border-border/50">

              <div className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><Mic className="w-3 h-3" /> 使用者說</span>
                <p className="text-sm font-medium text-foreground">{String(speechState.last_asr_text)}</p>
              </div>

              {Boolean(speechState.last_tts_text) && (
                <div className="flex flex-col gap-1 p-3 bg-primary/10 rounded-md border border-primary/20">
                  <span className="text-xs text-primary flex items-center gap-1"><Bot className="w-3 h-3" /> 機器狗回覆</span>
                  <p className="text-sm font-medium text-foreground">{String(speechState.last_tts_text)}</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4 mt-1">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground flex items-center gap-1"><Tag className="w-3 h-3" /> 意圖判斷</span>
                  <span className="text-sm font-medium text-primary">
                    {speechState.last_intent ? String(speechState.last_intent) : '無意圖'}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground flex items-center gap-1"><Zap className="w-3 h-3" /> 信心度</span>
                  <span className="text-sm font-medium">
                    {confidence > 0 ? `${Math.round(confidence * 100)}%` : 'N/A'}
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-1 pt-3 border-t border-border/50">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" /> 紀錄時間</span>
                <span className="text-xs font-mono text-muted-foreground">{latestTimeStr}</span>
              </div>

            </div>
          )}
        </div>
      )}

      {/* 🎙️ 視圖 3：主畫面 */}
      {viewMode === 'main' && (
        <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-left-4 duration-300">

          {!speechState && (
            <div className="py-6 flex flex-col items-center justify-center text-muted-foreground">
              <Mic className="h-8 w-8 mb-3 opacity-20 motion-safe:animate-pulse" />
              <span className="text-sm font-medium">尚未連線語音模組</span>
              <span className="text-xs mt-1 opacity-50">等待後端伺服器啟動...</span>
            </div>
          )}

          {speechState && isIdleEmpty && (
            <div className="py-6 flex flex-col items-center justify-center text-muted-foreground">
              <Mic className="h-8 w-8 mb-3 opacity-20" />
              <span className="text-sm font-medium">等待喚醒中...</span>
              <span className="text-xs mt-1 opacity-50">目前沒有對話內容</span>
            </div>
          )}

          {speechState && !isIdleEmpty && (
            <>
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${phaseConfig.colorClass} motion-safe:transition-colors motion-safe:duration-150`} />
                <span className="text-sm font-medium text-foreground">{phaseConfig.label}</span>
                {isListening && (
                  <div className="flex gap-1 ml-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-success motion-safe:animate-pulse" style={{ animationDelay: '0ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-success motion-safe:animate-pulse" style={{ animationDelay: '300ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-success motion-safe:animate-pulse" style={{ animationDelay: '600ms' }} />
                  </div>
                )}
              </div>

              {Boolean(speechState.last_asr_text) && (
                <div className="flex flex-col gap-2 p-3 bg-surface-hover rounded-lg border border-border/50">
                  <span className="text-xs text-muted-foreground">最近對話</span>
                  <p className="text-sm text-foreground truncate">👤 {String(speechState.last_asr_text)}</p>
                  {Boolean(speechState.last_tts_text) && (
                    <p className="text-sm text-muted-foreground truncate opacity-80">🐶 {String(speechState.last_tts_text)}</p>
                  )}
                </div>
              )}

              <div className="flex flex-col gap-2">
                <span className="text-xs text-muted-foreground">已載入模型</span>
                <div className="flex gap-2">
                  {EXPECTED_MODELS.map(model => {
                    const isLoaded = Boolean(speechState.models_loaded?.includes(model))
                    return (
                      <span key={model} className={`text-xs px-2 py-1 rounded-sm uppercase ${isLoaded ? 'bg-success/20 text-success' : 'bg-muted/50 text-muted-foreground'}`}>
                        {model}
                      </span>
                    )
                  })}
                </div>
              </div>
            </>
          )}

          <div className="flex flex-col gap-2 mt-2">
            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                variant="outline"
                className="w-full text-xs cursor-pointer"
                onClick={() => setViewMode('latest')}
              >
                <FileText className="w-3.5 h-3.5 mr-1.5" /> 對話詳情
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full text-xs cursor-pointer"
                onClick={() => setViewMode('history')}
              >
                <History className="w-3.5 h-3.5 mr-1.5" /> 事件歷史
              </Button>
            </div>

            <a href="/studio" className="w-full">
              <Button
                type="button"
                variant="ghost"
                className="w-full text-xs text-muted-foreground cursor-pointer hover:text-foreground"
              >
                <Home className="w-3.5 h-3.5 mr-1.5" /> 返回控制首頁
              </Button>
            </a>
          </div>

        </div>
      )}
    </PanelCard>
  )
}