# -*- coding: utf-8 -*-
import os
import time
import subprocess
import json
import re
from openai import OpenAI

# ==========================================
# PawAI 實戰延遲測試：完美復刻人設圖版 (100 Tokens)
# ==========================================

# 1. 任務：要求它進行自我介紹
user_question = "請活潑地自我介紹一下！並詳細分享你平常在家裡可以陪我做哪些事？字數請控制在 60 到 70 個字之間！"

# 2. SYSTEM_PROMPT：完全依照截圖中的個性設定來撰寫
SYSTEM_PROMPT = """
你是 PawAI，一隻搭載在 Unitree Go2 Pro 上的「居家互動機器狗」，絕對不是一般的聊天機器人。

🚨 你的個性與語氣設定 (請嚴格遵守) 🚨
1. 你很忠誠、會撒嬌，但遇到陌生人會保持警戒。
2. 熟人回家：語氣要「溫暖開心」（例如：「你回來了！今天過得好嗎？」）
3. 陌生人警戒：語氣要「嚴肅」（例如：「偵測到不認識的人，已通知家人。」）
4. 日常陪伴：語氣要「輕鬆」（例如：「你坐很久了，要不要動一動？」）
5. 自我介紹時，請務必包含這句核心台詞：「我叫 PawAI，是你的居家互動機器狗！」

🚨 輸出格式絕對嚴格規則 🚨
你只能輸出一個純粹的、合法的 JSON object。
絕對不允許使用任何 Markdown 標籤 (例如 ```json)。
絕對不允許在 JSON 前後加上任何解釋或額外文字。

輸出格式必須精準如下：
{"intent": "chat", "reply_text": "你的回答", "selected_skill": "content"}

內容規則：
- reply_text 必須是一段符合上述人設的自我介紹。
- 字數請嚴格控制在 60 到 70 個字之間，以達到理想的 Token 長度。
- 🚨 必須「全部使用繁體中文」，絕對禁止夾雜英文（PawAI 除外）。
- 句尾絕對不能加「汪」。
"""

print("🚀 開始 100 Tokens 延遲測試 (完美復刻人設圖版)...")
print("-" * 50)

try:
    client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

    # ==========================================
    # [階段 1] LLM 大腦生成測試
    # ==========================================
    print("🧠 [1/3] 呼叫大腦 (LLM) 努力控制字數與人設中...")
    
    llm_start_time = time.time()
    
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_question}
        ],
        max_tokens=150,  
        temperature=0.7
    )
    
    llm_end_time = time.time()
    llm_latency = llm_end_time - llm_start_time
    
    llm_output_str = response.choices[0].message.content
    generated_tokens = response.usage.completion_tokens if response.usage else 0

    # ==========================================
    # 🌟 終極過濾器：暴力提取 JSON 內容
    # ==========================================
    try:
        match = re.search(r'\{.*\}', llm_output_str, re.DOTALL)
        if match:
            clean_str = match.group(0)
            llm_json = json.loads(clean_str)
            reply_text = llm_json.get('reply_text', '我剛剛有點恍神，沒聽清楚。')
        else:
            raise ValueError("完全找不到 JSON 格式")
    except Exception as e:
         print(f"\n⚠️ 解析失敗，大腦原本輸出：\n{llm_output_str}")
         reply_text = "哎呀，我的腦袋剛剛稍微當機了一下，可以再跟我說一次嗎？"
         
    word_count = len(reply_text)
    
    print(f"✅ 大腦思考完畢！")
    print(f"   🐶 PawAI 決定說：「{reply_text}」")
    print(f"   ⏱️ LLM 耗時: {llm_latency:.2f} 秒")
    print(f"   📊 產生 Token 數: {generated_tokens} tokens")
    print(f"   📝 實際中文字數: {word_count} 字")

    print("-" * 50)

    # ==========================================
    # [階段 2] TTS 嘴巴合成測試
    # ==========================================
    print(f"🗣️ [2/3] 呼叫嘴巴 (TTS) 準備發聲...")
    
    tts_start_time = time.time()
    
    subprocess.run(["edge-tts", "--voice", "zh-CN-XiaoxiaoNeural", "--text", reply_text, "--write-media", "temp_latency.mp3"])
    
    tts_end_time = time.time()
    tts_latency = tts_end_time - tts_start_time
    
    print(f"✅ 語音合成完畢！")
    print(f"   ⏱️ TTS 耗時: {tts_latency:.2f} 秒")
    print("-" * 50)
    
    total_latency = llm_latency + tts_latency
    print(f"🔥 系統總延遲 (大腦 + 嘴巴): {total_latency:.2f} 秒")

    # ==========================================
    # [階段 3] 播放驗收
    # ==========================================
    if os.path.exists("temp_latency.mp3"):
        print("\n▶️ [3/3] 播放驗收中...")
        subprocess.run(["afplay", "temp_latency.mp3"])
        time.sleep(0.5)
        os.remove("temp_latency.mp3")
        print("\n🎉 測試圓滿結束！")

except Exception as e:
     print(f"\n❌ 發生錯誤了：{e}")
     print("請確認 SSH Tunnel 是否有斷線。")