import os
import time

# ==========================================
# PawAI 語音試鏡台本
# ==========================================

lines_to_test = [
    # --- 你的 6 句自我介紹 (Wow Moment) ---
    "你好！我是 PawAI，你專屬的居家互動機器狗！",
    "平常的時候，我會乖乖坐著陪在你身邊。",
    "只要你叫我，我就會馬上站起來！",
    "你可以用語音或手勢跟我互動，我會超級開心！",
    "我也會隨時注意周圍，幫你看家。",
    "讓我們一起創造充滿活力的每一天吧！",
    
    # --- 穩重對話版 Plan B 精選 ---
    "你回來啦！今天過得好不好呀？",
    "今天天氣感覺不錯呢！我們要不要一起做點什麼？",
    "我就靜靜地待在這裡陪你，有什麼心事都可以跟我說哦。",
    "你現在想聊聊天，還是想要安靜地休息一下呢？",
    "別擔心，我會一直待在這裡當你的好幫手的！",
    "偵測到不認識的人，我會持續提高警戒。",
    "你坐好久了哦，要不要起來伸個懶腰動一動呀？"
]

print("PawAI 語音試鏡開始！(使用語音: zh-CN-XiaoxiaoNeural)")
print("-" * 50)

for i, text in enumerate(lines_to_test):
    print(f"正在播放第 {i+1}/{len(lines_to_test)} 句: {text}")
    
    # 1. 呼叫 edge-tts 生成暫存音檔
    cmd_generate = f'edge-tts --voice zh-CN-XiaoxiaoNeural --text "{text}" --write-media temp_test.mp3'
    os.system(cmd_generate)
    
    # 2. 呼叫 Mac 內建的 afplay 播放音檔
    os.system('afplay temp_test.mp3')
    
    # 稍微停頓 0.8 秒，讓句子之間有呼吸空間
    time.sleep(0.8)

# 測完後把暫存檔案刪掉，保持資料夾乾淨
if os.path.exists("temp_test.mp3"):
    os.remove("temp_test.mp3")

print("-" * 50)
print("試鏡結束！")