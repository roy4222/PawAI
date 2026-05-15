"""Rule-based conversation mode classifier — OpenClaw-lite L8 hook lite.

Used by _build_user_message and graph.py to decide whether to inject
CAPABILITIES.md and capability_context JSON.

Order matters: safety > school_demo_request > self_intro_request > scene_query
             > identity > capability_question > action_request > chat (default).
5/15: school_demo_request broadened to bare "資管 / 資訊管理" keyword, then
given ASR-typo tolerance via homophone character classes — live ASR mis-hears
both the school name and the keyword itself (資管→直管, 資訊→資詢).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1C
N4 (2026-05-11): split `self_intro_request` from `identity` — the former
demands a full demo-host performance with scaffold; the latter is the casual
"你是誰" terse reply path. Pattern matched BEFORE identity so the more
specific intent wins.
N5 (2026-05-11): added `scene_query` — "看到什麼 / 我在幹嘛 / 你猜我"
must integrate face+pose+gesture+objects into scene description (not just
list objects). Placed before identity / capability_question.
"""
from __future__ import annotations
import re
from typing import Final

# Patterns ordered by priority (safety checked first)
# 5/9 review: regex broadened — "介紹一下" / "介紹一下你自己" / "自我介紹"
# / "介紹一下 PawAI" all previously missed and fell to chat mode (then got
# capability JSON injected → feature-list answer).
MODE_PATTERNS: Final[list[tuple[str, str]]] = [
    (
        "safety",
        r"停|停止|不要動|別動|先不要動|小心|警告|危險|stop",
    ),
    (
        "school_demo_request",
        # 學校招生 demo: 提到「資管 / 資訊管理」即觸發 facts 注入。
        # 5/15a 放寬：移除校名錨點（ASR 常把輔大→古大、輔仁→虎仁聽錯）。
        # 5/15b 加 ASR 錯字容錯：實機 ASR 把「資管」聽成「直管」、「資訊」
        # 聽成「資詢」太頻繁，純字面比對漏接。改用同音字族字元類：
        #   資 zī → 資直自諮姿滋紫字   訊 xùn → 訊詢訓迅尋
        #   管 guǎn → 管館官觀         理 lǐ → 理里裡
        # 第 3 段是收尾網：任何「X管系 / X管理系 / X館系」都接住（含校名被
        # ASR 砍爛的 case，如「古大司館系」），但用 (?!統) 排除「管理系統」
        # 這種 PawAI 自指、非學校語意的詞。
        # 放在 self_intro_request 之前，避免「請跟大家介紹資管系特色」被
        # self_intro 的「跟大家介紹」吃掉。
        r"[資直自諮姿滋紫字][管館官觀]"
        r"|[資直自諮姿滋紫字][訊詢訓迅尋][管館官觀][理里裡]"
        r"|[管館][理里]?系(?!統)",
    ),
    (
        "self_intro_request",
        # N4: explicit "please introduce yourself" for demo. Stricter than
        # `identity` — requires "自我介紹" / explicit 介紹+自己 / demo+介紹 /
        # 跟大家打個招呼 / 跟教授介紹 / 介紹一下你的功能.
        # Order matters: most specific first.
        r"自我介紹"
        r"|介紹.{0,3}(自己|你自己|妳自己|PawAI|paw\s*ai)"
        # N8 (2026-05-11): 「跟教授打招呼」應該走 chat → wave_hello path，
        # 不是 5 段完整自介。從此條 alternative 拿掉 "打.*招呼" / "問好"，只留 "介紹"。
        r"|跟\s*(教授|大家|觀眾|評審).{0,5}介紹"
        r"|(現在|目前|這邊).{0,8}demo.{0,8}(介紹|展示)"
        r"|(demo|展示).{0,8}你(自己|的)?"
        r"|介紹一下你的(功能|能力|專案)"
        r"|詳細(介紹|說明|講)一下(你|自己|你自己)"
        r"|你是誰.*詳細"
        r"|完整介紹"
        # "跟教授 demo，你自我介紹一下自己" (from demo objectives doc)
        r"|跟.{0,8}(教授|評審|觀眾).{0,8}demo",
    ),
    (
        "scene_query",
        # N5: 整合 face+pose+gesture+objects 做場景描述。
        # 注意：必須排在 capability_question 前，避免 "你會看到什麼" 撞線
        # （capability_question 要求 "你會" 前綴，不會 match bare "看到什麼"）。
        # N5.1 review: `你.{0,3}覺得我` 太寬會吃掉「你覺得我該展示哪個功能」
        # 等 capability/planning 問題 — 收緊到 scene-specific 動詞。
        r"看到(什麼|啥|哪些東西|哪些)"
        r"|我.{0,3}(看起來|現在)?在?(幹|做|忙)(什麼|啥|嘛|嗎)"
        r"|我.{0,3}看起來(是在|像|怎樣)"
        r"|你.{0,3}覺得我.{0,6}(在|看起來|像|站|坐|做什麼|幹什麼|幹嘛|忙什麼)"
        r"|你.{0,3}猜.{0,5}我.{0,5}(在|是|做|幹|站|坐|看起來)"
        r"|現場.{0,3}(有什麼|是什麼狀況)"
        r"|這裡.{0,3}有(什麼|啥)"
        r"|我.{0,3}(站|坐|在站|在坐).{0,5}(嗎|還是)"
        r"|我.{0,3}是.{0,3}(站|坐).{0,5}(著|還是)",
    ),
    (
        "identity",
        # Order: most specific first
        r"你是誰|你叫什麼|你叫啥|你誰啊|你是\s*AI"
        r"|介紹一下"  # bare "介紹一下" — chat continuation, still identity-flavoured
        r"|你會做(自我介紹|介紹)",
    ),
    (
        "capability_question",
        r"你會(什麼|啥|哪些|做什麼|做啥)"
        r"|(有|你有)(什麼|哪些)(功能|能力|技能)"
        r"|(能|可以)做(什麼|啥)"  # 5/12: "可以做什麼" was missing
        r"|功能有(哪些|什麼)"
        r"|(會|能|可以)什麼(動作|事|skill)"  # "會什麼動作", "可以什麼動作"
        r"|有什麼動作"
        r"|(具體|詳細)(可以|能|有)",  # "具體有哪些", "詳細可以做" — emphasis on detail
    ),
    (
        "action_request",
        r"扭|搖|伸|懶腰|揮|過來|坐下|跳舞|走|看[你我].*OK|比.*OK",
    ),
]


def classify_mode(user_text: str) -> str:
    """Return conversation mode: safety / identity / capability_question / action_request / chat.

    Default: "chat" when no pattern matches.
    """
    text = (user_text or "").strip()
    if not text:
        return "chat"
    for mode, pattern in MODE_PATTERNS:
        if re.search(pattern, text):
            return mode
    return "chat"
