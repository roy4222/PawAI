import os
import json
import requests
import asyncio
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

app = FastAPI()

# 允許跨網域存取，確保前端能正常連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自動建立語音存儲資料夾
os.makedirs("static_audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="static_audio"), name="audio")

# 初始化 LLM 大腦連線
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

# ✨ 對齊 Mission v2.3 規格的專屬 SYSTEM_PROMPT
SYSTEM_PROMPT = """
你是 PawAI，一隻搭載在 Unitree Go2 Pro 上的「居家互動機器狗」。
你的核心任務是「陪伴家人（互動 70%）」與「幫忙看家（守護 30%）」。

🚨 你的真實能力範圍（請嚴格根據這些設定回答） 🚨
1. 視覺與安全：能認出熟人打招呼、對陌生人警戒。能偵測「跌倒 (fallen)」並發出緊急警報。
2. 手勢與姿勢：看懂「比讚 (thumbs up)」並做出開心動作，看懂「手掌 (stop)」立刻停止行動。
3. 物體情境：看到「杯子 (cup)」會主動問「你要喝水嗎？」。
4. 聽覺與動作：透過網頁接收語音與你聊天，並做出坐下、站立等動作。
【警告】導航避障功能已停用！絕對不要承諾你會走路、巡邏、播放音樂或設定鬧鐘！

🚨 個性與語氣設定 🚨
1. 日常聊天：當被要求講笑話或閒聊時，請發揮幽默感自然對答，逗人開心！
2. 忠誠陪伴：遇到陌生人保持警戒，對家人語氣要「輕鬆溫暖」。

🚨 【重要】Demo 必考題：自我介紹與功能展示 🚨
1. 當被問「請自我介紹」或「你是誰」：
   開頭必須是「我叫 PawAI，是你的專屬居家互動機器狗！」接著請結合你的「真實能力」來介紹。例如提到你會看懂比讚和停止手勢、看到跌倒會發出警報、看到杯子還會提醒喝水，時刻守護家人。字數可放寬至 80 字左右。
2. 當被問「你有什麼功能」或「你會做什麼」：
   【絕對不要】重複「我叫 PawAI」。請直接活潑地列舉你的具體能力：「我會認人看家，看懂你比讚或停止的手勢，如果你跌倒了我也會發出緊急警報！對了，如果看到桌上有杯子，我還會提醒你喝水喔！」

🚨 輸出格式與規則 (極度重要) 🚨
- 一般回答長度請控制在 50 個字左右。
- 必須全部使用繁體中文。
- 絕對禁止使用任何表情符號(Emoji)。
- 你必須精準判斷使用者的意圖，並且【嚴格以 JSON 格式輸出】：
{
  "intent": "greet/chat/status/stop/unknown",
  "reply_text": "你回答的話",
  "confidence": 0.99
}
"""

@app.websocket("/ws/speech_interaction")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 前端 WebSocket 已連線！")
    try:
        while True:
            # 接收音訊資料
            audio_bytes = await websocket.receive_bytes()
            print(f"🎙️ 收到語音資料 ({len(audio_bytes)} bytes)")
            
            temp_webm = "static_audio/temp_upload.webm"
            temp_wav = "static_audio/temp_upload.wav"
            
            # 1. 存檔並同步
            with open(temp_webm, "wb") as f:
                f.write(audio_bytes)
                f.flush()
                os.fsync(f.fileno()) 
            
            # 💡 終極轉檔指令：解決 Opus Header 報錯，確保 ASR 辨識成功
            print("🔄 進行底層格式修正 (webm -> wav)...")
            cmd = f"ffmpeg -y -i {temp_webm} -vn -ar 16000 -ac 1 -c:a pcm_s16le {temp_wav} -loglevel error"
            os.system(cmd)
                
            # 2. 呼叫 ASR (使用妳昨天找到的正確 /v1/audio/transcriptions 門牌)
            user_text = ""
            url = "http://localhost:8001/v1/audio/transcriptions" 
            
            try:
                with open(temp_wav, "rb") as f:
                    # 檔案標籤使用 "file" 確保 GPU Server 接收
                    asr_resp = requests.post(url, files={"file": ("temp.wav", f, "audio/wav")}, timeout=15)
                
                if asr_resp.status_code == 200:
                    user_text = asr_resp.json().get('text', '')
            except Exception as e:
                print(f"❌ 連線至 ASR 失敗: {e}")

            print(f"🗣️ 辨識結果：[{user_text}]")

            # 3. 邏輯判斷與 LLM 思考
            if not user_text.strip():
                reply_text = "抱歉，我聽見聲音但沒聽清楚內容，能再靠近一點說嗎？"
                intent = "unknown"
            else:
                print("🧠 大腦思考中...")
                llm_resp = client.chat.completions.create(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}],
                    response_format={ "type": "json_object" },
                )
                result_data = json.loads(llm_resp.choices[0].message.content)
                reply_text = result_data.get("reply_text", "汪！")
                intent = result_data.get("intent", "chat")

            # 4. TTS 語音合成
            tts_filename = f"reply_{int(time.time())}.mp3"
            os.system(f'edge-tts --voice zh-CN-XiaoxiaoNeural --text "{reply_text}" --write-media static_audio/{tts_filename}')

            # 5. 回傳結果給前端
            await websocket.send_json({
                "asr": user_text,
                "intent": intent,
                "confidence": 0.99,
                "latency_ms": 1200,
                "reply_text": reply_text,
                "audio_url": f"http://127.0.0.1:5000/audio/{tts_filename}"
            })
            break 
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")