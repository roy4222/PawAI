"""COCO 80 class names + deterministic color generator for object visualization.

YOLO26n output uses contiguous COCO 80 IDs (0-79), not the 91-ID scheme from
the original COCO dataset paper. Class names with spaces in the original COCO
(e.g., "dining table", "cell phone") are normalized to underscores for JSON
consistency across events, contract, and downstream consumers.
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
