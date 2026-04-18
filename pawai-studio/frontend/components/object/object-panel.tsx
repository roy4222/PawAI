"use client"

import { Package } from "lucide-react"
import { PanelCard } from "@/components/shared/panel-card"
import { MetricChip } from "@/components/shared/metric-chip"
import { useStateStore } from "@/stores/state-store"
import { useEventStore } from "@/stores/event-store"
import type { ObjectState, PawAIEvent } from "@/contracts/types"
import { cn } from "@/lib/utils"

// ══════════════════════════════════════════════════════════════════
// 白名單（OBJECT_WHITELIST）
// ──────────────────────────────────────────────────────────────────
// 決策依據（object-wu.md）：
//   - 只保留 COCO 80-class 中室內穩定、Go2 視角可辨識的物品
//   - 瓶子（bottle, id=39）已驗證失敗 → 排除
//   - 椅子（chair, id=56）太普遍，不觸發任何提醒 → 排除
//   - 人（person, id=0）由人臉模組處理，不在這裡重複觸發
//   - 遙控器（remote, id=65）、剪刀（scissors, id=76）太小 → 排除
//
// 最終白名單選定 6 個 class（5-8 個範圍內）：
//   cup(41), cell phone(67), book(73), laptop(63), backpack(24), clock(74)
//
// 情境設計原則：
//   「PawAI 對物體的關心應該是情境式的，不是念名字」（object-wu.md）
//   每個 TTS 都應帶使用者情境推測 + 行動建議，而非單純報告偵測結果。
//
// 冷卻機制（cooldown）：
//   每個 class 獨立 5 秒冷卻，避免重複觸發（Backend 邏輯，此處只顯示 icon）
// ══════════════════════════════════════════════════════════════════

export interface ObjectEntry {
  /** COCO class id */
  classId: number
  /** COCO 英文 class name（和 Jetson 上傳來的 class_name 必須完全一致） */
  className: string
  /** 中文顯示名稱 */
  zh: string
  /** 情境說明（在 Studio 顯示，方便 demo 時確認） */
  situation: string
  /** Go2 TTS 語音（交給盧柏宇填入 state_machine.py） */
  tts: string
  /** Go2 動作（預設無動作，後續擴充） */
  action: string | null
  /** Emoji（UI 用，讓 panel 一眼辨識） */
  emoji: string
  /** 實測狀態备注 */
  testNote: string
}

/**
 * 情境化白名單 — 完整映射表
 *
 * 此表同步交給盧柏宇（Roy）填入 Jetson 的
 * `interaction_executive/interaction_executive/state_machine.py`
 */
export const OBJECT_WHITELIST: ObjectEntry[] = [
  {
    classId: 41,
    className: "cup",
    zh: "杯子",
    situation: "人坐著 + 杯子在旁 → 可能忘記喝水",
    tts: "你要喝水嗎？",
    action: null,
    emoji: "☕",
    testNote: "✅ 已驗證穩定，直立 cup 辨識率高",
  },
  {
    classId: 67,
    className: "cell phone",
    zh: "手機",
    situation: "人拿著 / 看著手機 → 可能正在使用或剛放下",
    tts: "你在用手機嗎？如果需要提醒或鬧鐘，叫我一聲！",
    action: null,
    emoji: "📱",
    testNote: "✅ 已驗證可偵測，需手持展示效果最佳",
  },
  {
    classId: 73,
    className: "book",
    zh: "書本",
    situation: "書翻開了 → 使用者正在閱讀",
    tts: "你在看書嗎？需要我安靜陪伴你，或是幫你計時休息眼睛嗎？",
    action: null,
    emoji: "📖",
    testNote: "⚠️ 翻開時可辨識，平放時失敗；Demo 請翻開展示",
  },
  {
    classId: 63,
    className: "laptop",
    zh: "筆電",
    situation: "筆電開著 → 工作或學習中",
    tts: "你在工作或學習嗎？記得每隔一小時起來伸展喔！",
    action: null,
    emoji: "💻",
    testNote: "✅ 正面辨識率高，側面略差",
  },
  {
    classId: 24,
    className: "backpack",
    zh: "背包",
    situation: "背包出現在視野 → 使用者可能準備出門",
    tts: "你要出門嗎？需要我提醒你帶傘或確認門有沒有鎖嗎？",
    action: null,
    emoji: "🎒",
    testNote: "✅ 體積大，辨識容易；放桌上或背著都可",
  },
  {
    classId: 74,
    className: "clock",
    zh: "時鐘",
    situation: "看到時鐘 → 可能在確認時間",
    tts: "需要我幫你設定提醒或鬧鐘嗎？",
    action: null,
    emoji: "🕐",
    testNote: "✅ 掛牆式大時鐘辨識良好；小桌鐘挑戰較大",
  },
]

// ──────────────────────────────────────────────────────────────────
// 快速查詢表（由白名單建立）
//   key: COCO class_name（字串，動態 YOLO 傳來）
//   value: ObjectEntry
// ──────────────────────────────────────────────────────────────────

const WHITELIST_MAP: Record<string, ObjectEntry> = Object.fromEntries(
  OBJECT_WHITELIST.map((e) => [e.className, e])
)

/**
 * 判斷一個 class_name 是否在白名單內
 * （Jetson 傳來的 class_name 用空格，COCO 標準；前端 key 也用原始 class_name）
 */
export function isWhitelisted(className: string): boolean {
  return className in WHITELIST_MAP
}

/**
 * 取得該物品的情境入口（包含 TTS、emoji 等）
 * 若不在白名單內回傳 undefined（表示不觸發任何反應）
 */
export function getObjectEntry(className: string): ObjectEntry | undefined {
  return WHITELIST_MAP[className]
}

// ──────────────────────────────────────────────────────────────────
// 舊版 label（向下相容，給其他地方還在用 getLabel() 的程式）
// ──────────────────────────────────────────────────────────────────

const COCO_ZH_FALLBACK: Record<string, string> = {
  person: "人",
  bicycle: "腳踏車",
  car: "汽車",
  dog: "狗",
  cat: "貓",
  chair: "椅子",
  bottle: "瓶子",
  cup: "杯子",
  book: "書",
  dining_table: "餐桌",
  "dining table": "餐桌",
  cell_phone: "手機",
  "cell phone": "手機",
  laptop: "筆電",
  backpack: "背包",
  umbrella: "雨傘",
  handbag: "手提包",
  couch: "沙發",
  remote: "遙控器",
  clock: "時鐘",
}

/** 取得中文顯示名稱；白名單優先，其次 fallback，最後回傳原名 */
export function getLabel(className: string): string {
  return (
    WHITELIST_MAP[className]?.zh ??
    COCO_ZH_FALLBACK[className] ??
    className
  )
}

// ──────────────────────────────────────────────────────────────────
// 常數
// ──────────────────────────────────────────────────────────────────

const MAX_HISTORY = 10

// ══════════════════════════════════════════════════════════════════
// 子元件：事件歷史列
// ══════════════════════════════════════════════════════════════════

function ObjectEventItem({ event }: { event: PawAIEvent }) {
  const data = event.data as Record<string, unknown>
  const rawObjects = (
    data.objects ?? data.detected_objects ?? []
  ) as Array<{ class_name: string; confidence: number }>

  // 只顯示白名單內的物件
  const objects = rawObjects.filter((o) => isWhitelisted(o.class_name))
  const time = new Date(event.timestamp).toLocaleTimeString("zh-TW", {
    hour12: false,
  })

  if (objects.length === 0) return null

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md px-2.5 py-1.5",
        "bg-surface/40 border border-border/20",
        "text-xs text-muted-foreground"
      )}
    >
      <span className="shrink-0">
        {objects
          .map((o) => getObjectEntry(o.class_name)?.emoji ?? "📦")
          .join("")}
      </span>
      <span className="text-foreground font-medium">
        {objects.map((o) => getLabel(o.class_name)).join("、")}
      </span>
      <span className="ml-auto tabular-nums">{time}</span>
      {objects.length > 0 && (
        <span className="shrink-0 text-[10px]">
          {Math.round((objects[0].confidence ?? 0) * 100)}%
        </span>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════
// 主元件：ObjectPanel
// ══════════════════════════════════════════════════════════════════

export function ObjectPanel() {
  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const allEvents = useEventStore((s) => s.events)

  const objectEvents = allEvents
    .filter((e) => e.source === "object")
    .slice(0, MAX_HISTORY)

  const panelStatus: "active" | "inactive" | "loading" =
    objectState === null
      ? "loading"
      : objectState.active
        ? "active"
        : "inactive"

  // 全部偵測到的物件
  const allObjects = objectState?.detected_objects ?? []

  // 只保留白名單內的物件（其餘無情境意義，不顯示也不觸發 TTS）
  const whitelistedObjects = allObjects.filter((o) =>
    isWhitelisted(o.class_name)
  )

  // 被過濾掉的物件數量（Non-whitelisted，Debug 用）
  const filteredOutCount = allObjects.length - whitelistedObjects.length

  return (
    <PanelCard
      title="物件偵測"
      href="/studio/object"
      icon={<Package className="h-4 w-4" />}
      status={panelStatus}
      // count 只計白名單內的（真正有情境反應的）
      count={whitelistedObjects.length || undefined}
      defaultCollapsed
    >
      <div className="flex flex-col gap-3">

        {/* ── Loading ── */}
        {panelStatus === "loading" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
            <span>正在連線...</span>
          </div>
        )}

        {/* ── Inactive ── */}
        {panelStatus === "inactive" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <Package className="h-8 w-8 opacity-30" />
            <span>尚未偵測到白名單物件</span>
          </div>
        )}

        {/* ── Active：偵測到的白名單物件 ── */}
        {panelStatus === "active" && (
          <>
            {whitelistedObjects.length > 0 ? (
              <div className="flex flex-col gap-2">
                {whitelistedObjects.map((obj, i) => {
                  const entry = getObjectEntry(obj.class_name)
                  return (
                    <div
                      key={`${obj.class_name}-${i}`}
                      className={cn(
                        "rounded-lg border border-border/30 bg-surface/50 px-4 py-3",
                        "flex flex-col gap-1.5",
                        "motion-safe:animate-in motion-safe:slide-in-from-right-4 motion-safe:duration-200",
                        "hover:bg-surface-hover motion-safe:transition-colors motion-safe:duration-150"
                      )}
                    >
                      {/* Row 1：emoji + 名稱 + 信心度 */}
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xl select-none">
                            {entry?.emoji ?? "📦"}
                          </span>
                          <div className="flex flex-col gap-0">
                            <span className="text-sm font-semibold text-foreground">
                              {getLabel(obj.class_name)}
                            </span>
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {obj.class_name} · class_id {entry?.classId ?? "?"}
                            </span>
                          </div>
                        </div>
                        <MetricChip
                          label="信心度"
                          value={Math.round(obj.confidence * 100)}
                          unit="%"
                        />
                      </div>

                      {/* Row 2：情境說明 */}
                      {entry && (
                        <div className="text-[11px] text-muted-foreground bg-surface/60 rounded-md px-2.5 py-1.5 border border-border/10">
                          <span className="text-amber-400/80 font-medium">情境：</span>
                          {entry.situation}
                        </div>
                      )}

                      {/* Row 3：TTS 語音預覽 */}
                      {entry?.tts && (
                        <div className="text-[11px] text-emerald-400/90 flex items-start gap-1.5">
                          <span className="shrink-0">🔊</span>
                          <span className="italic">「{entry.tts}」</span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                偵測到非白名單物件（{filteredOutCount} 個），無情境反應
              </div>
            )}

            {/* 被過濾掉的 debug 提示（只在有過濾時才顯示） */}
            {filteredOutCount > 0 && whitelistedObjects.length > 0 && (
              <p className="text-[10px] text-muted-foreground/50 px-0.5">
                另有 {filteredOutCount} 個非白名單物件已過濾
              </p>
            )}

            {/* 事件歷史（只列白名單內的事件） */}
            {objectEvents.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[11px] text-muted-foreground font-medium px-0.5">
                  偵測記錄
                </span>
                {objectEvents.map((evt, i) => (
                  <ObjectEventItem key={`${evt.id}-${i}`} event={evt} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </PanelCard>
  )
}
