"use client"

// whitelist-view.tsx — ✅ 白名單對照表（PR #40 port）
import { OBJECT_WHITELIST, EXCLUDED_ITEMS } from "./object-config"
import { cn } from "@/lib/utils"

export function WhitelistSection() {
  return (
    <div className="flex flex-col gap-5">
      {/* 白名單 */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 px-0.5">
          <span className="text-xs font-semibold text-amber-400">✅ 情境化白名單</span>
          <span className="text-[10px] text-muted-foreground">— 偵測到會觸發 Go2 TTS</span>
        </div>
        <div className="rounded-xl border border-border/30 overflow-hidden">
          <div className="grid grid-cols-[36px_52px_60px_1fr_1fr] bg-surface/60 border-b border-border/20">
            {["", "ID", "中文", "TTS 語音", "備注"].map((h) => (
              <div key={h} className="px-2.5 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{h}</div>
            ))}
          </div>
          {OBJECT_WHITELIST.map((entry) => (
            <div
              key={entry.className}
              className="grid grid-cols-[36px_52px_60px_1fr_1fr] items-start border-b border-border/10 last:border-0 hover:bg-amber-400/5 transition-colors"
            >
              <div className="px-2.5 py-2.5 text-xl leading-none select-none">{entry.emoji}</div>
              <div className="px-2.5 py-2.5 text-[10px] font-mono text-muted-foreground/60 pt-3">{entry.classId}</div>
              <div className="px-2.5 py-2.5 text-xs font-medium text-foreground pt-3">{entry.zh}</div>
              <div className="px-2.5 py-2.5 text-[11px] text-emerald-400/80 italic leading-relaxed">「{entry.tts}」</div>
              <div
                className={cn(
                  "px-2.5 py-2.5 text-[10px] leading-relaxed",
                  entry.testNote.startsWith("✅") ? "text-emerald-400/70" :
                    entry.testNote.startsWith("⚠️") ? "text-amber-400/70" :
                      "text-muted-foreground/60"
                )}
              >
                {entry.testNote}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 排除清單 */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 px-0.5">
          <span className="text-xs font-semibold text-muted-foreground">❌ 已排除</span>
          <span className="text-[10px] text-muted-foreground">— 不觸發任何反應</span>
        </div>
        <div className="rounded-xl border border-border/20 overflow-hidden opacity-70">
          <div className="grid grid-cols-[36px_52px_60px_1fr] bg-surface/40 border-b border-border/20">
            {["", "ID", "中文", "排除原因"].map((h) => (
              <div key={h} className="px-2.5 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{h}</div>
            ))}
          </div>
          {EXCLUDED_ITEMS.map((item) => (
            <div
              key={item.className}
              className="grid grid-cols-[36px_52px_60px_1fr] items-center border-b border-border/10 last:border-0"
            >
              <div className="px-2.5 py-2 text-lg leading-none select-none opacity-50">{item.emoji}</div>
              <div className="px-2.5 py-2 text-[10px] font-mono text-muted-foreground/50">{item.classId}</div>
              <div className="px-2.5 py-2 text-xs text-muted-foreground">{item.zh}</div>
              <div className="px-2.5 py-2 text-[10px] text-rose-400/60">{item.reason}</div>
            </div>
          ))}
        </div>
      </div>
      <p className="text-[10px] text-muted-foreground/40 px-0.5">冷卻機制：每個 class 5 秒冷卻，避免重複觸發（Backend 控制）</p>
    </div>
  )
}
