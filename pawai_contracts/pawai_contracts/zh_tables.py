"""zh_tables — single source of truth for object recognition Chinese labels.

Plan C3, 2026-06-10 (Roy ruling). Supersedes the old "three copies on purpose"
regime (brain_node.py:37-40, conversation_graph_node.py:78-81).

Producer canon: object_perception/coco_classes.py COLOR_ZH (the classifier that
actually assigns colour names). Studio TS copy guarded by parity test
(test_zh_parity.py:test_studio_ts_copy_matches_contracts).

Consumers: interaction_executive.brain_node, pawai_brain.conversation_graph_node.
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
