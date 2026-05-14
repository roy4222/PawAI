"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Hand, Lock, Octagon, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import type { SkillRegistryEntry, SkillRegistryResponse } from "@/contracts/types";

// Friendly Chinese labels for known active skills. Anything not in this map
// falls back to the raw skill name (still shown).
const SKILL_LABELS: Record<string, string> = {
  stop_move: "停",
  system_pause: "暫停",
  show_status: "狀態",
  chat_reply: "聊天",
  say_canned: "罐頭回",
  self_introduce: "自我介紹",
  wave_hello: "打招呼",
  wiggle: "扭屁股",
  stretch: "伸懶腰",
  sit_along: "陪坐",
  careful_remind: "提醒小心",
  greet_known_person: "歡迎熟人",
  stranger_alert: "陌生人警報",
  object_remark: "物體評論",
  nav_demo_point: "Nav demo",
  approach_person: "靠近人",
  fallen_alert: "跌倒警報",
};

// Default args for skills that need them (Studio button trigger context).
const DEFAULT_ARGS: Record<string, Record<string, unknown>> = {
  greet_known_person: { name: "Studio" },
  fallen_alert: { name: "有人" },
  object_remark: { label: "cup", color: "red" },
  approach_person: { name: "Studio" },
};

async function postSkill(skill: string, args: Record<string, unknown> = {}) {
  await fetch(`${getGatewayHttpUrl()}/api/skill_request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skill, args, request_id: `btn-${Date.now()}` }),
  });
}

function iconFor(entry: SkillRegistryEntry) {
  if (entry.ui_style === "safety") return Octagon;
  if (entry.ui_style === "alert") return AlertTriangle;
  if (entry.requires_confirmation) return Shield;
  return Hand;
}

export function SkillButtons() {
  const [registry, setRegistry] = useState<SkillRegistryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${getGatewayHttpUrl()}/api/skill_registry`)
      .then((r) => r.json())
      .then((data: SkillRegistryResponse) => {
        if (!cancelled) setRegistry(data);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    if (!registry?.skills) return { active: [], hidden: [], disabled: [] };
    return {
      active: registry.skills.filter((s) => s.bucket === "active"),
      hidden: registry.skills.filter((s) => s.bucket === "hidden"),
      disabled: registry.skills.filter((s) => s.bucket === "disabled"),
      // retired: not rendered
    };
  }, [registry]);

  if (error) {
    return (
      <div className="border-t border-border/50 bg-surface/50 px-4 py-2 text-xs text-destructive">
        skill_registry fetch failed: {error}
      </div>
    );
  }
  if (!registry) {
    return (
      <div className="border-t border-border/50 bg-surface/50 px-4 py-2 text-xs text-muted-foreground">
        loading skill registry…
      </div>
    );
  }

  return (
    <div className="space-y-1 border-t border-border/50 bg-surface/50 px-4 py-2">
      <SkillRow
        title={`Active · ${grouped.active.length}`}
        skills={grouped.active}
        variant="enabled"
      />
      {grouped.hidden.length > 0 && (
        <SkillRow
          title={`Hidden · ${grouped.hidden.length}`}
          skills={grouped.hidden}
          variant="grayed"
        />
      )}
      {grouped.disabled.length > 0 && (
        <SkillRow
          title={`Disabled · ${grouped.disabled.length}`}
          skills={grouped.disabled}
          variant="locked"
        />
      )}
    </div>
  );
}

interface SkillRowProps {
  title: string;
  skills: SkillRegistryEntry[];
  variant: "enabled" | "grayed" | "locked";
}

function SkillRow({ title, skills, variant }: SkillRowProps) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">
        {title}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((s) => {
          const Icon = variant === "locked" ? Lock : iconFor(s);
          const label = SKILL_LABELS[s.name] ?? s.name;
          const args = DEFAULT_ARGS[s.name] ?? {};
          const isInteractive = variant === "enabled" && s.static_enabled && !s.enabled_when_blocked;
          const tooltip = [
            s.description,
            s.requires_confirmation ? "需要 OK 二次確認" : null,
            s.cooldown_s > 0 ? `cooldown ${s.cooldown_s}s` : null,
            s.safety_requirements.length ? `safety: ${s.safety_requirements.join(", ")}` : null,
            s.enabled_when_blocked ? "目前被 enabled_when 卡住" : null,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <Button
              key={s.name}
              type="button"
              variant={s.ui_style === "safety" ? "destructive" : "secondary"}
              size="sm"
              disabled={!isInteractive}
              title={tooltip}
              className={
                "h-8 gap-1 rounded-md text-xs " +
                (variant === "grayed" ? "opacity-50" : "") +
                (variant === "locked" ? " opacity-30" : "")
              }
              onClick={isInteractive ? () => postSkill(s.name, args) : undefined}
            >
              <Icon className="h-3 w-3" />
              {label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
