# PawAI Studio — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 不能做

- 不要改 Mock Server 的 event schema（其他模組依賴它做測試）
- 不要引入新的前端框架（已確定 Next.js）
- 不要建 WebSocket bridge（4/9 後團隊才做，Sprint 期間只交 interface draft）

## 改之前先看

- `pawai-studio/frontend/` — 前端程式碼
- `pawai-studio/backend/schemas.py` — 資料模型
- `docs/pawai-brain/studio/specs/event-schema.md` — 事件 schema 定義
- `docs/pawai-brain/studio/README.md`

## 驗證指令

```bash
cd pawai-studio && bash start.sh
# → http://localhost:3000/studio
# → http://localhost:8001/api/health
```
