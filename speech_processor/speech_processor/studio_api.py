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

SYSTEM_PROMPT = """
你是 PawAI，一隻友善且忠誠的居家互動機器狗。
語氣要溫暖、輕鬆且誠懇。絕對禁止使用表情符號。
當對方問你是誰，請介紹：「我叫 PawAI，是你的居家互動機器狗！」
你必須以 JSON 格式輸出：{"intent": "...", "reply_text": "...", "confidence": 0.99}
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