"""zh_tables — single source of truth for object recognition Chinese labels.

Plan C3, 2026-06-10 (Roy ruling). Supersedes the old "three copies on purpose"
regime (brain_node.py:37-40, conversation_graph_node.py:78-81).

Producer canon: object_perception/coco_classes.py COLOR_ZH (the classifier that
actually assigns colour names). Studio TS copy guarded by parity test
(test_zh_parity.py:test_studio_ts_copy_matches_contracts).

Consumers: interaction_executive.brain_node, pawai_brain.conversation_graph_node.

Evidence Center display tables below are additive and best-effort. Consumers
should fall back to the raw code when a display key is absent.
"""

# Mirror of object_perception/coco_classes.py:COCO_CLASSES_ZH (whitelist subset).
OBJECT_CLASS_ZH: dict[str, str] = {
    "cup": "杯子", "bottle": "瓶子", "book": "書",
    "person": "人", "dog": "狗狗", "cat": "貓咪",
    "chair": "椅子", "couch": "沙發", "bed": "床",
    "dining_table": "餐桌", "tv": "電視", "laptop": "筆電",
    "cell_phone": "手機", "remote": "遙控器", "keyboard": "鍵盤",
    "mouse": "滑鼠", "backpack": "背包", "handbag": "手提包",
    "umbrella": "雨傘", "clock": "時鐘", "vase": "花瓶",
    "potted_plant": "盆栽", "teddy_bear": "玩偶", "scissors": "剪刀",
    "wine_glass": "酒杯", "fork": "叉子", "knife": "刀子",
    "spoon": "湯匙", "bowl": "碗", "banana": "香蕉",
    "apple": "蘋果", "orange": "橘子",
}
OBJECT_COLOR_ZH: dict[str, str] = {
    "red": "紅色", "orange": "橘色", "yellow": "黃色", "green": "綠色",
    "cyan": "青色", "blue": "藍色", "purple": "紫色", "pink": "粉紅色",
    "brown": "咖啡色", "black": "黑色", "white": "白色", "gray": "灰色",
}
# Personality phrases — appended AFTER the colour-aware preamble (per 5/6
# user feedback). Never replace the preamble; user wants both colour
# announcement and the playful phrase.
OBJECT_TTS_SPECIAL_SUFFIX: dict[str, str] = {
    "cup": "，你要喝水嗎？今天天氣很熱，要記得補充水分。",
    "bottle": "，喝點水吧",
    "book": "，在看書啊",
}

# Evidence Center trace gate labels. Keep in sync with the trace gate strings
# emitted by interaction_executive and pawai_brain.
TRACE_GATE_ZH: dict[str, str] = {
    "active_plan": "已有行動計畫",
    "alert_active": "警戒中",
    "attention_engaged": "注意力已佔用",
    "capability_health": "能力健康檢查",
    "confirm_pending": "等待確認",
    "conversation_gate": "對話閘門",
    "dedup": "重複事件",
    "demo_phase": "demo 場景遮罩",
    "depth_clear": "深度安全",
    "emergency": "緊急狀態",
    "executing": "正在執行",
    "gesture_enabled": "手勢啟用",
    "greet_cooldown": "問候冷卻",
    "greet_gate": "問候閘門",
    "greet_sitting_window": "坐姿問候視窗",
    "ism_shadow": "ISM 影子判斷",
    "llm_allowlist": "LLM 白名單",
    "nav_paused": "導航暫停",
    "nav_ready": "導航就緒",
    "object_remark_dedup": "物件評論重複",
    "pending_confirm": "等待確認",
    "safety": "安全限制",
    "safety_hold": "安全暫停",
    "skill_cooldown": "技能冷卻",
    "speaking": "正在說話",
    "stranger_alert_enabled": "陌生人警戒啟用",
    "tts_playing": "語音播放中",
}

TRACE_REASON_PREFIX_ZH: dict[str, str] = {
    "cooldown": "冷卻中",
    "phase": "demo 場景遮罩",
    "watchdog_timeout": "逾時自癒",
    "banned_api": "禁用指令",
    "gate": "被閘門擋下",
    "identity": "身份",
}

ISM_VERDICT_ZH: dict[str, str] = {
    "accept": "接受",
    "suppress": "抑制",
    "queue": "排隊",
    "preempt": "搶佔",
}

ISM_TRIGGER_ZH: dict[str, str] = {
    "skill_result": "技能結果",
    "confirm_result": "確認結果",
    "tts_ack": "語音確認",
    "operator": "操作者",
    "safety": "安全",
}

ISM_STATE_ZH: dict[str, str] = {
    "idle": "閒置",
    "listening": "聆聽中",
    "speaking": "說話中",
    "confirm_pending": "等待確認",
    "executing": "執行中",
    "alert_active": "警戒中",
    "safety_hold": "安全暫停",
    "error_recovery": "錯誤復原",
}
