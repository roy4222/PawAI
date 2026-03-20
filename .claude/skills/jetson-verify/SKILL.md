---
name: jetson-verify
description: >
  Jetson 部署驗證工具。部署後跑 smoke test、整合前做 pre-flight check、
  Demo 前產出 go/no-go 報告。觸發詞："verify"、"驗證"、"健檢"、
  "smoke test"、"check jetson"、"jetson 狀態"、"/verify"。
  在 colcon build 成功後、WSL→Jetson sync 完成後、或使用者說
  「驗證」「smoke」「健檢」「ready」時應主動建議執行。
  不要在純聊天、文件摘要、或不需實際執行檢查時觸發。
---

# jetson-verify

## 用途

部署後一鍵驗證 Jetson 環境健康。自動偵測執行環境
（Jetson 本機 = local_jetson，WSL = remote_jetson），
跑完所有 checks 後輸出結構化 JSON + terminal 摘要。

## 使用方式

在 repo root 執行：

    python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke

## 參數

- `--profile`: smoke（v0）| integration（v1 預留）| demo（v2 預留）
- `--output-dir`: 預設 logs/jetson-verify/

## 輸出約定

- `stdout`: 完整 JSON（一次，machine-readable）
- `stderr`: 人類摘要（逐行 check + summary）
- `file`: 同一份 JSON 落盤到 output-dir，含 latest.json symlink

## 結果解讀

- overall=PASS, exit 0 → 可以繼續開發/測試
- overall=FAIL, exit 1 → 有 blocking check 失敗，修完再跑
- overall=ERROR, exit 2 → 驗證本身不可信（SSH、timeout、config 問題）
- SKIP → 模組沒啟動，不計分
- WARN → 非 blocking 未通過，留意但不阻擋

## 新增 check

編輯 profiles/<profile>.yaml，加一條 check entry。
每個 check 至少需要：id, command, expect, blocking, timeout_sec, message_template。
系統/ROS2 基礎 check 禁止加 precondition。
只有 module-level check 可以用 precondition 做 SKIP。

## Gotchas

見 references/gotchas.md（隨使用持續累積）。
