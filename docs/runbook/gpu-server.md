# 學校 GPU 伺服器連線指南

**適用環境**：學校 GPU 伺服器 (RTX 8000 x5, 48GB VRAM)  
**最後更新**：2025/12/14

---

## 連線資訊

| 項目 | 數值 |
|------|------|
| **IP** | `140.136.155.5` |
| **Port** | `8022` |
| **帳號** | `roy422` |

> ⚠️ **此為敏感資訊，請勿外洩**

---

## 1. SSH 連線

### 基本連線

```bash
ssh roy422@140.136.155.5 -p 8022
```

第一次連線會問是否信任主機，輸入 `yes`，然後輸入密碼（密碼不會顯示）。

### SSH Tunnel（在家連線必用）

> 💡 用途：讓本機可以存取 GPU Server 上的 FastAPI 服務（Port 8050）

```bash
# Windows PowerShell / Mac Terminal
ssh -L 8050:localhost:8050 GPUServer
```

**說明：**
- `-L 8050:localhost:8050`：本機 8050 Port → GPU Server 8050 Port
- 保持此視窗開啟，Tunnel 才會持續運作
- 連線後可在另一個終端測試：`curl http://localhost:8050/health`

**SSH Config 設定（簡化指令）：**

在 `~/.ssh/config` 加入：

```
Host GPUServer
    HostName 140.136.155.5
    User roy422
    Port 8022
```

設定後只需輸入 `ssh GPUServer` 或 `ssh -L 8050:localhost:8050 GPUServer` 即可。

### 驗證 GPU 狀態

```bash
nvidia-smi
```

應看到 5 張 RTX 8000 (各 48GB VRAM)。

---

## 2. 環境建置

> ⚠️ **重要**：多人共用伺服器，**禁止直接修改系統 Python**！必須使用 Conda 虛擬環境。

### 安裝 Miniconda

```bash
# 下載安裝腳本
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 執行安裝（一路按 Enter 或 yes）
bash Miniconda3-latest-Linux-x86_64.sh

# 重新讀取設定
source ~/.bashrc
```

### 建立虛擬環境

```bash
# 建立 Python 3.10 環境
conda create -n torch_env python=3.10

# 啟動環境
conda activate torch_env
```

---

## 3. 安裝 PyTorch

> 💡 Driver 支援 CUDA 13.0，可安裝 CUDA 12.x 系列 PyTorch

```bash
# 確認已啟動環境 (torch_env)
conda activate torch_env

# 安裝 PyTorch (CUDA 12.1)
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 驗證安裝

```python
>>> import torch
>>> print(torch.cuda.is_available())
True   # ✅ 成功
>>> print(torch.cuda.device_count())
5      # ✅ 抓到 5 張卡
>>> print(torch.version.cuda)
12.1   # ✅ 版本正確
>>> exit()
```

---

## 4. 指定 GPU（共用禮儀）

> ⚠️ **除非必要，不要佔用所有卡！** 請挑選一張空閒的使用。

### 方法 A：程式碼中指定

```python
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # 只用第 0 號 GPU
import torch
```

### 方法 B：執行指令時指定（推薦）

```bash
# 用第 1 號卡
CUDA_VISIBLE_DEVICES=1 python train.py

# 用多張卡（如 2 和 3）
CUDA_VISIBLE_DEVICES=2,3 python train.py
```

---

## 5. VS Code Remote SSH（推薦）

### 安裝外掛

1. 安裝 **Remote - SSH** 外掛
2. 按 `F1` → 輸入 `ssh config` → 選 **Open SSH Configuration File**

### SSH Config 設定

在 `~/.ssh/config` 加入：

```
Host School_GPU
    HostName 140.136.155.5
    User roy422
    Port 8022
```

存檔後，在 VS Code 側邊欄的「遠端」圖示中選擇 `School_GPU` 連線。

---

## 6. Tmux（長時間訓練必用）

> 💡 避免網路斷線導致訓練中斷

### 基本指令

```bash
# 建立新 session
tmux new -s training

# 離開但不中斷（按 Ctrl+B 然後按 D）

# 重新連接
tmux attach -s training

# 列出所有 session
tmux ls
```

### 訓練範例

```bash
tmux new -s depth_test
conda activate depth-v2
CUDA_VISIBLE_DEVICES=0 python test_metric.py
# 按 Ctrl+B, D 離開
# 之後用 tmux attach -s depth_test 回來看結果
```

---

## 7. 專案專用環境

針對 Depth Anything V2 專案：

```bash
# 建立專用環境
conda create -n depth-v2 python=3.10
conda activate depth-v2

# 安裝 PyTorch (CUDA 12.4)
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 進入專案目錄
cd ~/Depth_Anything_V2/Depth-Anything-V2

# 安裝依賴
uv pip install -r requirements.txt
```

---

## 相關文件

- [Depth Anything V2 使用指南](./Depth%20Anything%20V2/depth-anything-v2-guide.md)
- [開發計畫](../00-overview/開發計畫.md)
