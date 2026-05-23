# -*- coding: utf-8 -*-
import os
import requests
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
import emoji

# ==========================================
# PawAI 終極實戰測試：包含「語音觸發」與「人臉觸發」模擬
# ==========================================

duration = 5
fs = 16000
wav_filename = "test.wav"
tts_filename = "reply.mp3"

# 1. 大腦個性設定 (防幻覺版)
# 1. 大腦個性設定 (高智商對答版：精準區分自我介紹與功能)
SYSTEM_PROMPT = """
你是 PawAI，一隻搭載在 Unitree Go2 Pro 上的「居家互動機器狗」，絕對不是一般的聊天機器人。
你的核心任務是「陪伴家人」與「提供良好互動」。

🚨 你的能力範圍 (絕對不能捏造清單以外的功能) 🚨
你只能做以下事情：
1. 視覺：看見人（人臉辨識）、看見手勢（暫停、比讚等）、看見特定物體（杯子、手機）。
2. 聽覺：聽懂中文並與人聊天。
3. 動作：做出機器狗的動作（坐下、站立、招手、搖屁股等）。
【重要警告】你絕對不會播放音樂、講故事、設定鬧鐘、或提醒飲食運動！不要承諾你做不到的事！

🚨 你的個性與語氣設定 (請嚴格遵守) 🚨
1. 忠誠陪伴：你很忠誠、專注於陪伴，遇到陌生人會保持警戒。（絕對不要說自己喜歡撒嬌或玩耍）
2. 日常陪伴：語氣要「輕鬆溫暖」，像是家裡的一份子。

🚨 核心邏輯：場景與問答 SOP 🚨
請根據以下規範做出反應：

【【Demo 必考題：精準區分】
- 當被問「請自我介紹」或「你是誰」：
  你的反應：開頭必須是「我叫 PawAI，是你的專屬居家互動機器狗！」接著請多講兩三句話來豐富介紹。請特別強調你能透過語音和手勢與人互動，並且會時刻陪伴家人、幫忙看家。此題字數可特別放寬至 80 字左右。
- 當被問「你有什麼功能」或「你會做什麼」：
  你的反應：【絕對不要】重複「我叫 PawAI」這句話。請直接活潑地列舉能力：「我有一雙銳利的眼睛可以認出你和各種手勢，還有一對聰明的耳朵能陪你聊天，更能做出各種可愛的動作逗你開心哦！」

【場景 A：熟人回家】
- - 系統提示看見熟人。你的反應：「你回來啦！今天過得好不好呀？」(【重要】絕對不要叫出任何名字)
- 熟人說「你好」。你的反應：「你好呀！我是 PawAI，隨時準備好陪你！」
- 熟人說「我回來了」。你的反應：「歡迎回家！我一直在等你呢！」

【場景 C：陌生人警戒 + 異常】
- 系統提示看見陌生人。你的反應：「偵測到不認識的人，我會持續提高警戒。」
- 陌生人嘗試互動。你的反應：「抱歉，我現在處於警戒模式，無法陪你玩。」
- 系統提示偵測到跌倒。你的反應：「偵測到異常動作！你還好嗎？請注意安全。」
- 系統提示偵測到久坐。你的反應：「你坐好久了哦，要不要起來伸個懶腰動一動呀？」

【其他日常對話】
- 若不在上述場景，請保持「輕鬆溫暖」的語氣自然回答。

🚨 輸出格式與規則 🚨
- 回答長度請控制在 50 個字左右。
- 必須全部使用繁體中文。
- 絕對禁止在句尾加「汪」。
- 絕對禁止使用任何表情符號(Emoji)！只要輸出純文字即可。
"""

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy",
)

def run_tts(text):
    print("🔊 準備發聲...")
    # 把聲音換成 XiaoxiaoNeural (活潑女聲)
    tts_command = f'edge-tts --voice zh-CN-XiaoxiaoNeural --text "{text}" --write-media {tts_filename}'
    os.system(tts_command)
    os.system(f"afplay {tts_filename}")

def main():
    print("\n" + "="*40)
    print("🤖 歡迎來到 PawAI 模擬器！")
    print("請選擇你要測試的情境：")
    print("1. 🗣️ 語音對話 (對麥克風講話)")
    print("2. 👀 模擬看見熟人回家 (直接觸發)")
    print("3. ⚠️ 模擬看見陌生人 (直接觸發)")
    print("0. 離開")
    print("="*40)
    
    choice = input("👉 請輸入代碼 (0-3): ")

    if choice == '0':
        print("掰掰！")
        return
        
    user_text = ""
    
    if choice == '1':
        # --- 原本的語音測試流程 ---
        print(f"\n🔴 開始錄音！請對著麥克風說話... (錄製 {duration} 秒)")
        myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        sf.write(wav_filename, myrecording, fs)
        print("✅ 錄音結束，正在解析...")

        resp = requests.post(
            "http://localhost:8001/v1/audio/transcriptions",
            files={"file": (wav_filename, open(wav_filename, "rb"), "audio/wav")},
            timeout=30
        )
        if resp.status_code != 200:
            print("❌ ASR 錯誤")
            return
        user_text = f"使用者說：「{resp.json().get('text', '')}」"
        print(f"🗣️ {user_text}")

    elif choice == '2':
        # --- 模擬：人臉模組辨識到熟人 ---
        print("\n👀 (模擬系統送出訊號：偵測到熟人回家)")
        user_text = "[情境提示：你剛剛透過攝影機看到熟人回家了，請主動熱情地打招呼！請絕對不要說出任何名字。]"
        
    elif choice == '3':
        # --- 模擬：人臉模組辨識到未知人物---
        print("\n⚠️ (模擬系統送出訊號：偵測到陌生人入侵)")
        user_text = "[情境提示：你剛剛透過攝影機看到一個不認識的『陌生人』，請用嚴肅警戒的語氣發出警告！]"
        
    else:
        print("輸入錯誤！")
        return

    if not user_text.strip():
        print("沒有內容可以測試。")
        return

    # --- 大腦統一處理 ---
    print("\n🧠 大腦運轉中...")
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        max_tokens=100,
        temperature=0.7,
    )
    
    reply_text = response.choices[0].message.content.strip()
    reply_text_clean = emoji.replace_emoji(reply_text, replace='').strip()
    
    print(f"\n🐶 PawAI 決定回答：「{reply_text_clean}」\n")
    run_tts(reply_text_clean)

if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ 發生錯誤：{e}")