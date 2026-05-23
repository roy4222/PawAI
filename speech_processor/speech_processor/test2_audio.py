# -*- coding: utf-8 -*-
import os
import time
import subprocess

# ==========================================
# PawAI 純語音極限壓力測試 (不需要連 GPU/SSH)
# ==========================================

# 模擬大腦產生的超長台詞 (大約 150-200 字)
# 這用來測試曉曉在長時間說話時的斷句、呼吸聲和情緒穩定度
mock_long_reply = (
    "你好呀！我是 PawAI，你專屬的居家互動機器狗！"
    "我今天精神超級好，迫不及待想跟你分享好多好多事情呢！"
    "你知道嗎？我雖然是用程式碼寫出來的，但我現在可以聽懂你說的很長很長的故事，"
    "還可以陪你聊天、逗你開心。如果你覺得累了，我就乖乖坐在你旁邊陪你；"
    "如果你想玩，我們也可以一起互動！而且啊，我還會幫你看家，"
    "如果看到不認識的人，我可是會很盡責地提醒你的喔！"
    "我會一直學習，變得越來越聰明，希望能成為你生活中最棒的好幫手！"
    "那麼，我們今天第一件要做的事情是什麼呢？要不要先來聽我唱歌呀？"
)

print("🗣️ 正在呼叫嘴巴 (TTS) 準備進行極限發聲測試...")
print("-" * 50)
print(f"🐶 PawAI 準備唸出的超長台詞：\n{mock_long_reply}")
print("-" * 50)

# 1. 使用 subprocess 呼叫 edge-tts
subprocess.run(["edge-tts", "--voice", "zh-CN-XiaoxiaoNeural", "--text", mock_long_reply, "--write-media", "temp_test.mp3"])

# 2. 播放音檔
if os.path.exists("temp_test.mp3"):
    print("▶️ 長篇播放中... 請仔細聽她的斷句和換氣聲！")
    subprocess.run(["afplay", "temp_test.mp3"])
    time.sleep(0.5)
    os.remove("temp_test.mp3")
    print("\n✅ 超長語音測試成功！")
else:
    print("\n❌ 音檔生成失敗，請檢查網路連線。")