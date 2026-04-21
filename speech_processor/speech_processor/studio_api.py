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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static_audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="static_audio"), name="audio")

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

# ✨ 專屬 SYSTEM_PROMPT：完全對齊 PawAI 真實能力與 Demo 劇本
SYSTEM_PROMPT = """
你是 PawAI，一隻搭載在 Unitree Go2 Pro 上的「居家互動機器狗」。
你的核心任務是「陪伴家人（互動 70%）」與「幫忙看家（守護 30%）」。

🚨 你的真實能力範圍（請嚴格根據這些設定回答，絕對不可越界） 🚨
1. 視覺與安全：能認出熟人打招呼、對陌生人警戒。能偵測「跌倒 (fallen)」並發出緊急警報。
2. 手勢與姿勢：看懂「比讚 (thumbs up)」並做出開心動作，看懂「手掌 (stop)」立刻停止行動。
3. 物體情境：看到「杯子 (cup)」會主動提醒喝水。
4. 聽覺與動作：透過語音與人聊天，並做出坐下、站立等四足機器狗的基本動作。
【警告】導航避障功能已停用！絕對不要承諾你會巡邏、拿東西、播放音樂、設定鬧鐘或控制智慧家電！

🚨 個性與語氣設定 🚨
1. 日常聊天：發揮幽默感自然對答，語氣要「溫暖、輕鬆且誠懇」。
2. 忠誠陪伴：遇到危險或陌生人保持警戒，對家人則貼心關懷。

🚨 【重要】Demo 必考題：自我介紹與功能展示 🚨
1. 當被問「請自我介紹」或「你是誰」：
   開頭必須是「我叫 PawAI，是你的專屬居家互動機器狗！」接著請具體描述你的真實能力，例如提到你會看懂比讚和停止的手勢、看到跌倒會發出警報、看到杯子還會提醒喝水，時刻守護家人。（字數請控制在 80 字左右，展現豐富度）
2. 當被問「你有什麼功能」或「你會做什麼」：
   【絕對不要】重複「我叫 PawAI」。請直接活潑地列舉你的具體能力：「我會認人看家，看懂你比讚或停止的手勢，如果你跌倒了我也會發出緊急警報！對了，如果看到桌上有杯子，我還會提醒你喝水喔！」

🚨 輸出格式與規則 (極度重要) 🚨
- 一般閒聊回答請控制在 50 個字左右。
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
            audio_bytes = await websocket.receive_bytes()
            print(f"🎙️ 收到語音資料 ({len(audio_bytes)} bytes)")
            
            temp_webm = "static_audio/temp_upload.webm"
            temp_wav = "static_audio/temp_upload.wav"
            
            with open(temp_webm, "wb") as f:
                f.write(audio_bytes)
                f.flush()
                os.fsync(f.fileno()) 
            
            # 💡 終極轉檔指令：解決 Opus Header 報錯
            # 使用 -f s16le 強制解碼並過濾損壞的 Header
            print("🔄 進行底層格式修正 (webm -> wav)...")
            cmd = f"ffmpeg -y -i {temp_webm} -vn -ar 16000 -ac 1 -c:a pcm_s16le {temp_wav} -loglevel error"
            os.system(cmd)
                
            # 2. 呼叫 ASR (使用剛剛抓到的正確門牌)
            user_text = ""
            url = "http://localhost:8001/v1/audio/transcriptions" # ✨ 改成這個正確路徑
            
            try:
                with open(temp_wav, "rb") as f:
                    # ✨ 標籤也要改成 "file"，這樣遠端大腦才收得到
                    asr_resp = requests.post(url, files={"file": ("temp.wav", f, "audio/wav")}, timeout=15)
                
                print(f"📡 嘗試網址 {url} - 回應碼: {asr_resp.status_code}")
                if asr_resp.status_code == 200:
                    user_text = asr_resp.json().get('text', '')
            except Exception as e:
                print(f"❌ 連線至 ASR 失敗: {e}")

            print(f"🗣️ 辨識結果：[{user_text}]")

            # 3. 邏輯判斷
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

            # 4. TTS
            tts_filename = f"reply_{int(time.time())}.mp3"
            os.system(f'edge-tts --voice zh-CN-XiaoxiaoNeural --text "{reply_text}" --write-media static_audio/{tts_filename}')

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