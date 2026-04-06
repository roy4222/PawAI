# Demo 範圍與已知限制

**最後更新**：2026-04-06
**適用展示**：5/16 省夜 Demo、5/18 正式展示
**Demo 模式**：混合模式 — 視覺互動為主 + 網頁語音輔助

---

## Demo 模式說明

Go2 負責視覺感知（face/gesture/pose/object）+ Executive 決策 + TTS 播放。
語音入口由**瀏覽器收音**（Studio Gateway）提供，不依賴 Go2 機身麥克風。

使用者看到的仍然是機器狗在互動，只是收音點不在狗身上。
**Demo 話術**：「PawAI 以多模態互動為核心，語音入口可由 Studio 外部麥克風輔助。」

## Demo 啟用功能

| # | 功能 | 狀態 | Demo 角色 |
|:-:|------|:----:|-----------|
| 1 | 人臉辨識 | ✅ | 走近認出 → TTS 叫名字問候 |
| 2 | 語音互動（網頁） | ✅ | 瀏覽器 push-to-talk → Cloud ASR → LLM → TTS（繞過 Go2 風扇噪音） |
| 3 | 手勢辨識 | ✅ | stop（伸手掌）→ StopMove、thumbs_up → Content |
| 4 | 姿勢辨識 | ✅ | standing/sitting 辨識、fallen → EMERGENCY 警報 |
| 5 | AI 大腦（Executive） | ✅ | 事件聚合 + 優先序仲裁 + 狀態機 |
| 6 | 物體辨識 | ✅ | cup 觸發 TTS「你要喝水嗎？」（YOLO26n，大物件為主） |
| 7 | Studio Gateway | ✅ | FastAPI + rclpy on Jetson:8080，瀏覽器語音入口 |

## Demo 停用功能

| # | 功能 | 停用原因 | 替代方案 |
|:-:|------|----------|----------|
| — | Go2 機身語音 | Go2 風扇噪音 ASR ~25%，不可用 | Studio Gateway 網頁語音 |
| — | 導航避障 | D435 鏡頭角度限制，煞車距離不足 | 人工監控 + 手勢 stop |
| — | come_here 前進 | 依賴導航避障，停用後無安全保障 | Demo 不使用自主前進 |

## 已知限制

### 硬體
- **Go2 風扇噪音**：內建散熱風扇持續運轉，全向麥克風 SNR 不足。聊天可用但命令不可靠
- **Go2 禁連外網**：連外網會觸發自動韌體更新，Demo 當天必須 Ethernet 直連或離線
- **Jetson 供電（最大硬體風險）**：Go2 BAT → XL4015 降壓供電不穩，高負載時 Jetson 被強制關機（4/4 單日 3 次）。Demo 前必須解決（獨立電源或更好的降壓模組）
- **WebRTC 斷連**：Jetson 休眠後 DataChannel 靜默斷開，需重啟 Go2 driver

### 軟體
- **fallen 誤判**：正面站太近（<1m）+ 肩膀展開可能觸發 fallen（已加 vertical_ratio guard，大幅改善但非 100%）
- **greet cooldown**：同一人 30s 內不重複問候，離開再回來需等 30s
- **LLM 延遲**：Cloud Qwen2.5-7B P50 ~1.5s，加上 ASR + TTS 全鏈路 E2E 約 5-8s

## 安全措施

1. **手勢 stop 是主要停止手段**（Gate B 驗證 100%，< 1s 反應）
2. **人工監控**：Demo 期間操作員全程在場，隨時可手動遙控
3. **EMERGENCY 優先**：fallen 警報期間所有其他事件被忽略，30s timeout
4. **Executive 狀態機**：一次只處理一個事件，不會同時執行衝突動作

## Demo 操作注意事項

- 保持 **1-3m** 距離（手勢辨識最佳範圍）
- 避免正面站太近（<1m），減少 fallen 誤判風險
- 語音用**完整句子**（「請停下來」而非「停」），單字容易被 VAD 吞掉
- 偏向**聊天類對話**（「你好嗎」「今天天氣如何」），避免依賴精確命令
- Go2 開機後等 **WebRTC 連線穩定**（~10s）再開始互動
- 如果 TTS 突然無聲，可能是 WebRTC 斷連 → 重啟 go2 driver window
