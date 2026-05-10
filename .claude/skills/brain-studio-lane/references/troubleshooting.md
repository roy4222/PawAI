# Troubleshooting — Brain × Studio Lane

按症狀查。每條：症狀 → 原因 → 修法。

## TTS 沒聲音

**症狀**：Studio chat 看到 reply 文字，但 Jetson 喇叭沒響。

**3 個可能原因**：

1. **tts_node 沒起**（`minimal` mode 是預期；`e2e/full` mode 不應該）
   ```bash
   ssh jetson-nano "ros2 node list | grep tts"
   # 沒看到 → mode 用對了嗎？minimal mode 故意不起 tts
   ```

2. **`/tts` topic 沒 publisher**（exec 沒發 SAY plan）
   ```bash
   ssh jetson-nano "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 topic info /tts -v"
   # Publisher count 應 ≥ 1（interaction_executive_node）
   # Subscription count 應 ≥ 1（tts_node + studio_gateway）
   ```
   只有 studio_gateway 在 sub → tts_node 沒跑。

3. **plughw card# 漂移** → tts_node 起來但 ALSA 開不到喇叭
   ```bash
   ssh jetson-nano "aplay -l | grep -i cd002"
   # 確認當前 card# 然後重啟 tts_node 用對的 plughw
   ```

## OpenRouter=off

**症狀**：conv_graph log 出現 `openrouter=off, using RuleBrain`，回答呆板像規則式。

**原因**：tmux pane 沒繼承 `OPENROUTER_API_KEY`。

**修法**（**5/11 已 patch `start_pawai_brain_tmux.sh`**，如果重現代表沒同步到 Jetson）：
```bash
# 確認 Jetson 上腳本有 .env source
ssh jetson-nano "grep '.env' ~/elder_and_dog/scripts/start_pawai_brain_tmux.sh | head -3"
# 應該看到：
# SOURCE_CMD="... && { [[ -f $WORKSPACE/.env ]] && set -a && source $WORKSPACE/.env && set +a; } || true"

# 沒有 → rsync 從 WSL 推：
rsync -a /home/roy422/newLife/elder_and_dog/scripts/start_pawai_brain_tmux.sh jetson-nano:~/elder_and_dog/scripts/

# 重啟 brain
ssh jetson-nano "tmux kill-session -t pawai_brain"
brain-studio-lane start <mode> [--studio]
```

## persona 6 檔載入失敗

**症狀**：conv_graph log 顯示 `persona=inline` 而不是 `persona=file`，或 `loaded directory ... 5 files`。

**原因**：
1. `install/pawai_brain/share/pawai_brain/personas/v1/` 沒有 6 檔（`colcon build` 沒 build 過 5/11 freeze 改動）
2. `WORKSPACE` 環境變數錯（Jetson 預設指 `~/newLife/elder_and_dog`，但 Jetson repo 在 `~/elder_and_dog`）

**修法**：
```bash
# 確認 install 6 檔
ssh jetson-nano "ls ~/elder_and_dog/install/pawai_brain/share/pawai_brain/personas/v1/"
# 應 6 檔：CAPABILITIES.md EXAMPLES.md IDENTITY.md MISSION.md OUTPUT.md STYLE.md

# 缺檔 → rebuild
ssh jetson-nano "cd ~/elder_and_dog && rm -rf build/pawai_brain install/pawai_brain && \
  source /opt/ros/humble/setup.zsh && colcon build --packages-select pawai_brain"

# 確認 WORKSPACE
# skill 的 start.sh 已自動帶 WORKSPACE=/home/jetson/elder_and_dog
```

## /brain/text_input 發了沒回應

**症狀**：`ros2 topic pub /brain/text_input ...` 後等很久沒看到 chat_candidate。

**檢查順序**：
```bash
# 1. conv_graph 在跑嗎
ssh jetson-nano "ros2 node list | grep conversation_graph_node"

# 2. log 有反應嗎
ssh jetson-nano "tmux capture-pane -t pawai_brain:conv_graph -p -S -50 | tail -20"

# 3. cloud LLM 通嗎
ssh jetson-nano "curl -s --max-time 3 http://localhost:8000/health"

# 4. 是否被 fallback 走 RuleBrain
ssh jetson-nano "tmux capture-pane -t pawai_brain:conv_graph -p -S -100 | grep -E 'openrouter|fallback|timeout'"
```

## Studio 連不到 Gateway

**症狀**：Frontend `/studio` 顯示連線錯誤、WebSocket disconnect。

**檢查**：
```bash
# Gateway 在嗎
ssh jetson-nano "curl -s http://localhost:8080/health"

# 從本機通嗎
curl -s http://100.83.109.89:8080/health

# Frontend env 對嗎
grep NEXT_PUBLIC_GATEWAY_URL /tmp/studio_frontend.log
# 應該看到 http://100.83.109.89:8080
```

## Frontend 卡在編譯 / 慢

**症狀**：`npm run dev` 啟動很慢、首次訪問 `/studio` 等很久。

**原因**：Next.js 16 + Turbopack 首次 compile 慢（特別在 WSL2 上）。

**修法**：等 30s（看 log `✓ Ready in XXXms` 才好）。如果一直卡 → 重新 `npm install`。

## tmux pane 殘留沒清

**症狀**：cleanup 後 `tmux ls` 還看到 session，或 `ros2 node list` 還有 conv_graph。

**修法**：
```bash
# 強清
ssh jetson-nano "tmux kill-server"  # ⚠️ 會殺所有 session 包括 nav
# 或單獨：
ssh jetson-nano "pkill -9 -f conversation_graph_node; pkill -9 -f tts_node; pkill -9 -f studio_gateway"
```

## ROS2 daemon 卡住

**症狀**：`ros2 topic info` hang、`ros2 node list` 慢。

**修法**：
```bash
ssh jetson-nano "ros2 daemon stop; sleep 1; ros2 daemon start"
```

## tts_node mid-session 重啟炸 Megaphone

**症狀**：用 `playback_method=datachannel`，重啟 tts_node 後 Go2 喇叭沒響（local plughw 不受影響）。

**原因**：舊 4001/4003 DataChannel 沒完全關閉，Go2 狀態機卡在中間。

**修法**：必須連 `go2_driver_node` 一起重啟（甚至 Go2 重開機）。**避免 mid-session 重啟 tts**。
（local playback 模式無此問題。）

## ASR 簡體輸出（不是繁中）

**症狀**：說中文，ASR 識別成簡體字（「这」「么」）。

**原因**：SenseVoice 模型本身輸出簡體。

**修法**：已加 OpenCC s2twp 自動轉繁。如果還是簡體 → 確認 `text_normalization.py` 有跑。
