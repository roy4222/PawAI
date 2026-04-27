/**
 * object-config.ts
 * ─────────────────────────────────────────────────────────────────
 * 物體辨識功能層（純資料 + 工具函式，無 React 相依）
 *
 * 包含：
 *   - OBJECT_WHITELIST  — 情境化白名單（6 個 COCO class）
 *   - EXCLUDED_ITEMS    — 排除清單（說明排除原因）
 *   - isWhitelisted()   — 判斷是否在白名單
 *   - getObjectEntry()  — 取得完整 ObjectEntry
 *   - getLabel()        — 取得中文顯示名稱
 *
 * 決策依據（object-wu.md）：
 *   - 只保留 COCO 80-class 中室內穩定、Go2 視角可辨識的物品
 *   - 瓶子（bottle, id=39）已驗證偵測失敗 → 排除
 *   - 椅子（chair, id=56）太普遍，不觸發任何提醒 → 排除
 *   - 人（person, id=0）由人臉模組處理，不重複觸發 → 排除
 *   - 遙控器/剪刀 太小，辨識率低 → 排除
 *
 * 最終白名單：6 個 class（符合 object-wu.md 的 5-8 個規範）
 *   cup(41)、cell phone(67)、book(73)、laptop(63)、backpack(24)、clock(74)
 *
 * 情境設計原則：
 *   「PawAI 對物體的關心應該是情境式的，不是念名字」—— object-wu.md
 *
 * TTS 語音：
 *   此處的 tts 欄位同步交給盧柏宇，
 *   填入 Jetson 的 interaction_executive/state_machine.py
 *
 * 冷卻機制：
 *   每個 class 5 秒冷卻（於 Backend state_machine.py 控制，Frontend 不重複實作）
 */

// ══════════════════════════════════════════════════════════════════
// 型別定義
// ══════════════════════════════════════════════════════════════════

export interface ObjectEntry {
  /** COCO class id（和 Jetson YOLO 輸出一致） */
  classId: number
  /** COCO 英文 class name（和 Jetson YOLO 輸出一致） */
  className: string
  /** 中文顯示名稱 */
  zh: string
  /** 情境說明（Studio 顯示，幫助 demo 說明） */
  situation: string
  /** Go2 TTS 語音 → 交給盧柏宇填入 state_machine.py */
  tts: string
  /** Go2 動作（預留，目前皆為 null） */
  action: string | null
  /** Emoji（UI 顯示用） */
  emoji: string
  /** 實測備注（對應 object-wu.md 測試結果欄） */
  testNote: string
}

export interface ExcludedItem {
  className: string
  zh: string
  classId: number
  reason: string
  emoji: string
}

// ══════════════════════════════════════════════════════════════════
// 情境化白名單（6 個 class）
// ══════════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════════
// 排除清單（不會觸發任何 TTS，列出供 Studio 說明用）
// ══════════════════════════════════════════════════════════════════

export const EXCLUDED_ITEMS: ExcludedItem[] = [
  { className: "bottle",   zh: "水瓶",   classId: 39, reason: "已驗證偵測失敗",   emoji: "🍼" },
  { className: "chair",    zh: "椅子",   classId: 56, reason: "太常見，不觸發",   emoji: "🪑" },
  { className: "person",   zh: "人",     classId: 0,  reason: "由人臉模組處理",   emoji: "🧑" },
  { className: "remote",   zh: "遙控器", classId: 65, reason: "太小，辨識率低",   emoji: "📺" },
  { className: "scissors", zh: "剪刀",   classId: 76, reason: "太小，辨識率低",   emoji: "✂️" },
]

// ══════════════════════════════════════════════════════════════════
// 快查表（由白名單建立，避免 O(n) 線性搜尋）
// ══════════════════════════════════════════════════════════════════

const WHITELIST_MAP: Record<string, ObjectEntry> = Object.fromEntries(
  OBJECT_WHITELIST.map((e) => [e.className, e])
)

// ══════════════════════════════════════════════════════════════════
// COCO 中文對照 Fallback（非白名單物品的中文名）
// ══════════════════════════════════════════════════════════════════

const COCO_ZH_FALLBACK: Record<string, string> = {
  person: "人", bicycle: "腳踏車", car: "汽車", dog: "狗", cat: "貓",
  chair: "椅子", bottle: "瓶子", cup: "杯子", book: "書",
  "dining table": "餐桌", dining_table: "餐桌",
  "cell phone": "手機", cell_phone: "手機",
  laptop: "筆電", backpack: "背包", umbrella: "雨傘", handbag: "手提包",
  couch: "沙發", remote: "遙控器", clock: "時鐘",
}

// ══════════════════════════════════════════════════════════════════
// 工具函式（供 UI 層呼叫）
// ══════════════════════════════════════════════════════════════════

/**
 * 判斷 class_name 是否在白名單內
 * （白名單外的物品在偵測到時會被靜默過濾，不觸發 TTS）
 */
export function isWhitelisted(className: string): boolean {
  return className in WHITELIST_MAP
}

/**
 * 取得完整 ObjectEntry（含 TTS、情境、emoji）
 * 若不在白名單內回傳 undefined
 */
export function getObjectEntry(className: string): ObjectEntry | undefined {
  return WHITELIST_MAP[className]
}

/**
 * 取得中文顯示名稱
 * 白名單優先 → COCO fallback → 原始英文 class name
 */
export function getLabel(className: string): string {
  return WHITELIST_MAP[className]?.zh ?? COCO_ZH_FALLBACK[className] ?? className
}

// ── YOLO 模型輸入解析度（Jetson 上使用 640x480）────────────────────
// bbox 格式：[x1, y1, x2, y2]，座標對應此解析度
export const YOLO_MODEL_W = 640
export const YOLO_MODEL_H = 480
