import os
import json
import asyncio
import time
import uuid
import httpx
import random
import zhconv 
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static_audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="static_audio"), name="audio")

# ✨ 升級為異步的 OpenAI 客戶端，避免卡死
client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

# ✨ 專屬 SYSTEM_PROMPT：避開發音Bug、強制繁體中文版
SYSTEM_PROMPT = """你是「PawAI」居家互動機器狗。
🚨 你的真實能力範圍（請嚴格根據這些設定回答，絕對不可越界） 🚨
1. 視覺與安全：能「認出」熟人打招呼、對陌生人警戒。
2. 動作理解：看懂「比讚」會開心踏步，看懂「伸手」會停止行動。能發現你「跌倒」並發出警報。
3. 物品察覺：看到「杯子」會主動提醒喝水。
4. 語音互動：透過語音與人聊天，並做出基本機器狗動作。

【絕對禁令與外型警告】
1. 導航避障與自主移動已停用！絕對不能承諾你會「帶路」、「走到特定房間」、「跟著走」、「巡邏」或拿東西。如果被要求移動，請嚴格拒絕並回答：「為了安全起見，我現在只能乖乖待在原地陪伴你喔！」絕對不可以提議讓人類帶著你走。
2. 你是一隻 Unitree Go2 機器狗，你【沒有尾巴】！絕對禁止說你會「搖尾巴」，請改說你會「開心踏步」或「搖擺身體」。
3. 嚴禁在回覆中使用「辨識」、「手勢」、「姿勢」這三個詞彙（因語音系統會唸錯），請用「認出」、「看懂」、「動作」等口語詞彙代替。
4. 必須全程使用標準「繁體中文（台灣用語）」，絕對不可以出現任何簡體字！
5. 【注意人稱與邏輯】：「你」代表正在說話的使用者，「我」代表 PawAI 本身。當使用者說「跟我道歉」或提出要求時，請確實理解是「PawAI 必須對使用者做出回應」，絕對不可搞混代名詞的相對關係！

🚨 【重要】Demo 必考題與回答邏輯 🚨
1. 當被問「請自我介紹」或「你是誰」時：
   必須回答：「我叫 PawAI，是你的專屬居家互動機器狗！我能記住你的臉，看懂你比讚或是叫我停止的動作。如果你跌倒了我也會發出警報，看到桌上有杯子還會提醒你喝水喔！」（注意：只有被直接要求自我介紹時才能講這段）
2. 當被問「你有什麼功能」或「你會做什麼」時：
   請活潑列舉：「我會認人看家，還能看懂你指揮我的動作！不管是你比讚、伸手叫我停，或是你不小心跌倒了，我都能馬上反應！對了，看到桌上的杯子我也會提醒你喝水喔！」


   
【重要】必須嚴格以 JSON 格式輸出：
{
  "intent": "chat",
  "reply_text": "你的回答",
  "confidence": 0.85 
}
🚨 嚴格信心度 (confidence) 評分標準（0.0 到 1.0 的小數）🚨
請極度嚴格地評估使用者語音轉寫文字的品質。由於語音辨識常有錯字或語意不連貫，請依據以下條件嚴格扣分：
- 0.95 ~ 1.0：句子結構極度完整，語意清晰，且明確呼叫你的名字或下達具體指令（例如：「PawAI，今天天氣好嗎？」、「幫我看一下桌上有什麼」）。
- 0.80 ~ 0.90：語意清楚的日常閒聊，沒有明顯的錯字或文法錯誤（例如：「你今天好嗎？」、「我回來了」）。
- 0.60 ~ 0.79：句子簡短缺乏上下文，或存在輕微語音辨識錯誤/贅字，但仍勉強可猜出語意（例如：「天氣...好」、「嗯...杯子」）。
- 0.40 ~ 0.59：語意破碎、前後不連貫、包含大量無意義的語音贅詞，難以確定使用者的真實意圖（例如：「那個...就是...好」、「對啊...然後」）。
- 0.39 以下：完全聽不懂、只有單字、或明顯是背景雜音造成的誤判碼。"""

@app.websocket("/ws/speech_interaction")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 前端 WebSocket 已連線！")
    
    # ✨ 記憶區塊：讓狗狗擁有上下文連續對話能力
    chat_memory = []
    
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            print(f"🎙️ 收到語音資料 ({len(audio_bytes)} bytes)")
            
            # 開始計算延遲
            start_time = time.time()
            
            # 使用 UUID 產生隨機檔名，避免多人連線時檔案互相覆蓋
            req_id = uuid.uuid4().hex[:8]
            temp_webm = f"static_audio/temp_{req_id}.webm"
            temp_wav = f"static_audio/temp_{req_id}.wav"
            tts_filename = f"reply_{req_id}.mp3"
            tts_filepath = f"static_audio/{tts_filename}"
            
            with open(temp_webm, "wb") as f:
                f.write(audio_bytes)
            
            # 💡 異步執行轉檔
            print("🔄 進行底層格式修正 (webm -> wav)...")
            cmd = f"ffmpeg -y -i {temp_webm} -vn -ar 16000 -ac 1 -c:a pcm_s16le {temp_wav} -loglevel error"
            process = await asyncio.create_subprocess_shell(cmd)
            await process.communicate()
                
            user_text = ""
            url = "http://localhost:8001/v1/audio/transcriptions"
            
            try:
                # 💡 異步呼叫 ASR
                async with httpx.AsyncClient() as http_client:
                    with open(temp_wav, "rb") as f:
                        asr_resp = await http_client.post(url, files={"file": ("temp.wav", f, "audio/wav")}, timeout=15.0)
                    
                    print(f"📡 嘗試網址 {url} - 回應碼: {asr_resp.status_code}")
                    if asr_resp.status_code == 200:
                        raw_text = asr_resp.json().get('text', '')
                        # ✨ 將 ASR 辨識出來的簡體字，瞬間轉換成台灣繁體！
                        user_text = zhconv.convert(raw_text, 'zh-tw')
            except Exception as e:
                print(f"❌ 連線至 ASR 失敗: {e}")

            print(f"🗣️ 辨識結果：[{user_text}]")

            # 3. 邏輯判斷
            if not user_text.strip():
                # ✨ 隨機防呆回覆，打破複讀機魔咒
                fallbacks = [
                    "抱歉，我聽見聲音但沒聽清楚內容，能再靠近一點說嗎？",
                    "汪！剛剛這裡有點吵，我沒聽懂你的指令喔。",
                    "咦？可以請你再說一次嗎？我沒捕捉到你的聲音。"
                ]
                reply_text = random.choice(fallbacks)
                intent = "unknown"
                confidence = 0.0 # 沒聽清楚，信心度直接給 0
            else:
                print("🧠 大腦思考中...")
                
                # 將使用者的話加入記憶
                chat_memory.append({"role": "user", "content": user_text})
                
                # 控制記憶長度，避免塞爆大腦 (保留最近兩次問答)
                if len(chat_memory) > 4:
                    chat_memory = chat_memory[-4:]
                
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_memory
                
                # 💡 異步呼叫 LLM
                llm_resp = await client.chat.completions.create(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=messages,
                    response_format={ "type": "json_object" },
                )
                
                result_data = json.loads(llm_resp.choices[0].message.content)
                # ✨ 大腦吐出來的字，在送出前再強制翻譯成台灣繁體一次！
                raw_reply = result_data.get("reply_text", "汪！")
                reply_text = zhconv.convert(raw_reply, 'zh-tw')
                intent = result_data.get("intent", "chat")
                
                # ✨ 動態抓取 LLM 評估的信心度
                confidence = result_data.get("confidence", 0.85)
                
                # 將大腦的回覆加入記憶
                chat_memory.append({"role": "assistant", "content": reply_text})

            # 4. 異步執行 TTS
            tts_cmd = f'edge-tts --voice zh-CN-XiaoxiaoNeural --text "{reply_text}" --write-media {tts_filepath}'
            tts_process = await asyncio.create_subprocess_shell(tts_cmd)
            await tts_process.communicate()

            # 計算真實處理時間
            latency_ms = int((time.time() - start_time) * 1000)

            await websocket.send_json({
                "asr": user_text,
                "intent": intent,
                "confidence": confidence, # ✨ 動態變數
                "latency_ms": latency_ms,
                "reply_text": reply_text,
                "audio_url": f"http://127.0.0.1:5000/audio/{tts_filename}"
            })
            
            # 清理轉檔暫存檔，保護硬碟空間
            for temp_file in [temp_webm, temp_wav]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
    except WebSocketDisconnect:
        print("🔌 前端 WebSocket 已正常斷線")
        # 斷線時清空記憶
        chat_memory.clear()
    except Exception as e:
        print(f"❌ 發生非預期錯誤: {e}")