"use client";

import { Hand, MapPinOff, Octagon, UserRound, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getGatewayHttpUrl } from "@/lib/gateway-url";

const BUTTONS = [
  { skill: "self_introduce", label: "自我介紹", icon: Wand2 },
  { skill: "stop_move", label: "停", icon: Octagon, destructive: true },
  { skill: "acknowledge_gesture", label: "OK 手勢", icon: Hand, args: { gesture: "ok" } },
  { skill: "greet_known_person", label: "打招呼", icon: UserRound, args: { name: "Studio" } },
  {
    skill: "go_to_named_place",
    label: "去地點",
    icon: MapPinOff,
    disabled: true,
    title: "Phase B 才整合 nav_capability",
  },
];

async function postSkill(skill: string, args: Record<string, unknown> = {}) {
  await fetch(`${getGatewayHttpUrl()}/api/skill_request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skill, args, request_id: `btn-${Date.now()}` }),
  });
}

export function SkillButtons() {
  return (
    <div className="flex flex-wrap gap-2 border-t border-border/50 bg-surface/50 px-4 py-2">
      {BUTTONS.map(({ skill, label, icon: Icon, args, disabled, destructive, title }) => (
        <Button
          key={skill}
          type="button"
          variant={destructive ? "destructive" : "secondary"}
          size="sm"
          disabled={disabled}
          title={title}
          className="h-9 gap-1.5 rounded-lg text-xs"
          onClick={() => postSkill(skill, args)}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </Button>
      ))}
    </div>
  );
}
