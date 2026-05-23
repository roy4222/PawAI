# -*- coding: utf-8 -*-
import requests
import sounddevice as sd
import soundfile as sf
import time

# ==========================================
# PawAI 實戰測試：麥克風錄音轉文字 (ASR)
# ==========================================

duration = 3  # 設定錄音秒數
fs = 16000    # ASR 推薦的音訊取樣率

print("🎙️ 準備測試 ASR 耳朵功能...")
print("-" * 50)

try:
    # 1. 啟動麥克風錄音
    print(f"🔴 開始錄音！請對著麥克風說話... (錄製 {duration} 秒)")
    myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()  # 等待錄音結束
    
    # 將錄音檔暫存為 test.wav
    wav_filename = "test.wav"
    sf.write(wav_filename, myrecording, fs)
    print("✅ 錄音結束！")
    print("-" * 50)

    # 2. 將音檔送到 GPU 伺服器解析
    print("🚀 正在將聲音傳送給 GPU 伺服器 (Port 8001) 解析中...")
    start_time = time.time()
    
    with open(wav_filename, "rb") as f:
        # 發送 POST 請求給 ASR API
        resp = requests.post(
            "http://localhost:8001/v1/audio/transcriptions",
            files={"file": (wav_filename, f, "audio/wav")},
            timeout=10
        )
        
    end_time = time.time()
    
    # 3. 顯示結果
    if resp.status_code == 200:
        result = resp.json()
        recognized_text = result.get("text", "沒有辨識到文字")
        print("🎉 辨識成功！")
        print(f"   🐶 PawAI 聽到了：「{recognized_text}」")
        print(f"   ⏱️ 辨識耗時: {end_time - start_time:.2f} 秒")
    else:
        print(f"⚠️ 伺服器回傳錯誤代碼：{resp.status_code}")
        print(resp.text)

except Exception as e:
    print(f"\n❌ 發生錯誤了：{e}")
    print("請確認：\n1. 麥克風權限是否有開啟。\n2. SSH Tunnel 的 8001 port 是否有成功連線。")