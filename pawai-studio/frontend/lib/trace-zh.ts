export const TRACE_GATE_ZH: Record<string, string> = {
  active_plan: "已有行動計畫",
  alert_active: "警戒中",
  attention_engaged: "注意力已佔用",
  capability_health: "能力健康檢查",
  confirm_pending: "等待確認",
  conversation_gate: "對話閘門",
  dedup: "重複事件",
  demo_phase: "demo 場景遮罩",
  depth_clear: "深度安全",
  emergency: "緊急狀態",
  executing: "正在執行",
  gesture_enabled: "手勢啟用",
  greet_cooldown: "問候冷卻",
  greet_gate: "問候閘門",
  greet_sitting_window: "坐姿問候視窗",
  ism_shadow: "ISM 影子判斷",
  llm_allowlist: "LLM 白名單",
  nav_paused: "導航暫停",
  nav_ready: "導航就緒",
  object_remark_dedup: "物件評論重複",
  pending_confirm: "等待確認",
  safety: "安全限制",
  safety_hold: "安全暫停",
  skill_cooldown: "技能冷卻",
  speaking: "正在說話",
  stranger_alert_enabled: "陌生人警戒啟用",
  tts_playing: "語音播放中",
};

export const TRACE_REASON_PREFIX_ZH: Record<string, string> = {
  cooldown: "冷卻中",
  phase: "demo 場景遮罩",
  watchdog_timeout: "逾時自癒",
  banned_api: "禁用指令",
  gate: "被閘門擋下",
  identity: "身份",
};

export const ISM_VERDICT_ZH: Record<string, string> = {
  accept: "接受",
  suppress: "抑制",
  queue: "排隊",
  preempt: "搶佔",
};

export const ISM_TRIGGER_ZH: Record<string, string> = {
  skill_result: "技能結果",
  confirm_result: "確認結果",
  tts_ack: "語音確認",
  operator: "操作者",
  safety: "安全",
};

export const ISM_STATE_ZH: Record<string, string> = {
  idle: "閒置",
  listening: "聆聽中",
  speaking: "說話中",
  confirm_pending: "等待確認",
  executing: "執行中",
  alert_active: "警戒中",
  safety_hold: "安全暫停",
  error_recovery: "錯誤復原",
};

export function gateZh(gate: string): string {
  const label = TRACE_GATE_ZH[gate];
  return label ? `${label}（${gate}）` : gate;
}

export function reasonZh(reason: string): string {
  const prefix = reason.split(":", 1)[0];
  const label = TRACE_REASON_PREFIX_ZH[prefix];
  return label ? `${label}（${reason}）` : reason;
}
