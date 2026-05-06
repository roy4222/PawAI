"""COCO 80 class names + deterministic color generator for object visualization.

YOLO26n output uses contiguous COCO 80 IDs (0-79), not the 91-ID scheme from
the original COCO dataset paper. Class names with spaces in the original COCO
(e.g., "dining table", "cell phone") are normalized to underscores for JSON
consistency across events, contract, and downstream consumers.

`COCO_CLASSES_ZH` is mirrored (NOT imported) by:
  - `pawai-studio/frontend/components/object/object-config.ts`
  - subset only: `interaction_executive/interaction_executive/brain_node.py`
Keep all three in sync when the table changes.
"""

import cv2
import numpy as np

# COCO 80 classes (YOLO 0-79 contiguous IDs, underscored names)
COCO_CLASSES: dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic_light",
    10: "fire_hydrant",
    11: "stop_sign",
    12: "parking_meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports_ball",
    33: "kite",
    34: "baseball_bat",
    35: "baseball_glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis_racket",
    39: "bottle",
    40: "wine_glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot_dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted_plant",
    59: "bed",
    60: "dining_table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell_phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy_bear",
    78: "hair_drier",
    79: "toothbrush",
}


# 80 traditional-Chinese class names. Picked colloquial Taiwanese phrasing
# (cell_phone → 手機 not 行動電話; cake → 蛋糕; donut → 甜甜圈). When YOLO26n
# emits a class outside this map, fall back to underscored English.
COCO_CLASSES_ZH: dict[int, str] = {
    0: "人", 1: "腳踏車", 2: "汽車", 3: "機車", 4: "飛機",
    5: "公車", 6: "火車", 7: "卡車", 8: "船", 9: "紅綠燈",
    10: "消防栓", 11: "停車牌", 12: "停車計費表", 13: "長椅", 14: "鳥",
    15: "貓咪", 16: "狗狗", 17: "馬", 18: "羊", 19: "牛",
    20: "大象", 21: "熊", 22: "斑馬", 23: "長頸鹿", 24: "背包",
    25: "雨傘", 26: "手提包", 27: "領帶", 28: "行李箱", 29: "飛盤",
    30: "雙板滑雪", 31: "單板滑雪", 32: "球", 33: "風箏", 34: "球棒",
    35: "棒球手套", 36: "滑板", 37: "衝浪板", 38: "網球拍", 39: "瓶子",
    40: "酒杯", 41: "杯子", 42: "叉子", 43: "刀子", 44: "湯匙",
    45: "碗", 46: "香蕉", 47: "蘋果", 48: "三明治", 49: "橘子",
    50: "花椰菜", 51: "胡蘿蔔", 52: "熱狗", 53: "披薩", 54: "甜甜圈",
    55: "蛋糕", 56: "椅子", 57: "沙發", 58: "盆栽", 59: "床",
    60: "餐桌", 61: "馬桶", 62: "電視", 63: "筆電", 64: "滑鼠",
    65: "遙控器", 66: "鍵盤", 67: "手機", 68: "微波爐", 69: "烤箱",
    70: "烤麵包機", 71: "水槽", 72: "冰箱", 73: "書", 74: "時鐘",
    75: "花瓶", 76: "剪刀", 77: "玩偶", 78: "吹風機", 79: "牙刷",
}

# Color label translations — used by debug overlay AND mirrored in:
#   - frontend object-config.ts
#   - interaction_executive brain_node.py
# 5/6 expanded 4 → 12 colours. Brown is a special case (warm hue + low V).
# black/white/gray are achromatic gates (S/V), not hue-based.
COLOR_ZH: dict[str, str] = {
    "red": "紅色",
    "orange": "橘色",
    "yellow": "黃色",
    "green": "綠色",
    "cyan": "青色",
    "blue": "藍色",
    "purple": "紫色",
    "pink": "粉紅色",
    "brown": "咖啡色",
    "black": "黑色",
    "white": "白色",
    "gray": "灰色",
}


def class_name_zh(class_id: int) -> str:
    """Return the zh-TW name for a COCO class id, or English fallback."""
    if class_id in COCO_CLASSES_ZH:
        return COCO_CLASSES_ZH[class_id]
    return COCO_CLASSES.get(class_id, "物件")


def class_color(class_id: int) -> tuple[int, int, int]:
    """Deterministic BGR color for a class_id using HSV hue spread.

    Uses a prime multiplier (37) on the hue channel to spread 80 classes
    across the 0-179 OpenCV hue range, producing visually distinct colors
    for classes that are likely to appear together.

    Returns:
        (B, G, R) tuple of ints in [0, 255]
    """
    h = (class_id * 37) % 180
    hsv = np.uint8([[[h, 200, 230]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))
