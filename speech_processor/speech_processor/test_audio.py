# -*- coding: utf-8 -*-
import subprocess
import time
import os
import requests
import json

# ==========================================
# PawAI 綜合測試：大腦 (LLM) + 嘴巴 (TTS)
# ==========================================

# 1. 你要問大腦的問題 (申論題，測試字數限制)
user_question = "請你詳細介紹一下你自己，能說多少就說多少！"

# 2. 你的 SYSTEM_PROMPT (記得換成你修改後、沒有「汪」的最終版本)
SYSTEM_PROMPT = """
你是 PawAI，一隻友善的機器狗助手，搭載在 Unitree Go2 Pro 上。
你能看見人（透過攝影機人臉辨識）、聽懂中文（透過語音辨識）、做出動作。

你只能輸出單一 JSON object：
{"intent": "", "reply_text": "", "selected_skill": "", "reasoning": "", "confidence": 0.0}

規則：
- reply_text 字數放寬至 50 字以內，語氣要活潑、會撒嬌。
- greet/chat/status 的 reply_text 必須非空
"""

print("🧠 正在呼叫 PawAI 的大腦思考中...")

try:
    # 呼叫本地 8000 port 的 vLLM 模型 (需要先建立 SSH tunnel)
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_question}
            ],
            "max_tokens": 150, # 測試放寬的 max_tokens
            "temperature": 0.6
        },
        timeout=10 # 設定 10 秒超時
    )
    
    # 解析 JSON 找到 reply_text
    response_data = response.json()
    llm_output_str = response_data['choices'][0]['message']['content']
    
    # 嘗試把字串解析成 JSON (因為 LLM 有時會亂加 Markdown 標籤)
    try:
        llm_json = json.loads(llm_output_str.strip('`').replace('json\n', ''))
        reply_text = llm_json.get('reply_text', '我不知道該說什麼。')
    except json.JSONDecodeError:
         print("❌ LLM 回傳的格式不是正確的 JSON。")
         reply_text = "我好像有點混亂，沒有正確回答。"
    
    print(f"\n🐶 PawAI 決定說：\n{reply_text}\n")
    
    print("🗣️ 正在呼叫嘴巴 (TTS) 唸出來...")
    # 使用 subprocess 呼叫 edge-tts
    subprocess.run(["edge-tts", "--voice", "zh-CN-XiaoxiaoNeural", "--text", reply_text, "--write-media", "temp_test.mp3"])
    
    if os.path.exists("temp_test.mp3"):
        subprocess.run(["afplay", "temp_test.mp3"])
        time.sleep(0.5)
        os.remove("temp_test.mp3")
        print("\n✅ 綜合測試成功！")
    else:
        print("\n❌ 音檔生成失敗。")

except requests.exceptions.ConnectionError:
     print("\n❌ 無法連上大腦！請確認是否已經執行 SSH Tunnel 指令：")
     print("ssh -f -N -L 8001:localhost:8001 -L 8000:localhost:8000 <帳號>@140.136.155.5")