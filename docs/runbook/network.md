這是一份針對 **Unitree Go2 機器狗 / Kilo Code 開發環境** 的網路連線排查 SOP。這份文件是基於我們剛剛解決問題的過程總結而成的，未來遇到類似狀況可直接照表操課。

---

# 🛠️ 機器狗/開發板網路連線排查 SOP

**適用場景**：`git pull` 失敗、無法安裝套件、Ping 不通外網。
**核心邏輯**：先確認**物理連線**，再確認**路由方向**，最後確認**軟體設定**。

---

### 1️⃣ 第一步：快速診斷 (Status Check)

在終端機執行以下指令，判斷問題層級：

```bash
ping -c 4 8.8.8.8
```

*   **情況 A：Ping 成功 (0% packet loss)**
    *   代表網路是通的，問題出在 DNS 或 GitHub 阻擋。
    *   👉 跳至 **[4️⃣ GitHub 連線特化解法]**
*   **情況 B：Network is unreachable**
    *   代表電腦沒有「預設閘道 (Default Gateway)」，不知道怎麼出門。
    *   👉 跳至 **[2️⃣ 路由表修復]**
*   **情況 C：Destination Host Unreachable / 100% Packet Loss**
    *   代表有路走，但走錯路（走到死胡同）或是 IP 衝突。
    *   👉 跳至 **[2️⃣ 路由表修復]** 進行閘道測試。

---

### 2️⃣ 第二步：路由表與閘道修復 (關鍵步驟)

機器狗通常有多張網卡（例如 `enp0s1` 內網、`enp0s2` 外網），最常見的問題是**「預設閘道」設到了內網網卡**。

#### 1. 檢查目前路由
```bash
ip route
```
*   找第一行 `default via ... dev ...`
*   記下目前的 Gateway IP (例如 `192.168.12.1`)

#### 2. 尋找真正的出口
分別 Ping 看看各個網段的常見 Gateway（通常是 `.1`）：

```bash
# 測試網卡 1 (通常是 192.168.12.x 內網，往往不通外網)
ping -c 2 192.168.12.1

# 測試網卡 2 (通常是 192.168.1.x 外網/路由器)
ping -c 2 192.168.1.1
```

#### 3. 切換正確閘道
若發現 `192.168.1.1` 才是通的，但預設路由卻指到 `12.1`，請執行：

```bash
# 刪除錯誤的預設路由
sudo ip route del default

# 加入正確的路由 (將 enp0s2 替換為實際通的那張網卡代號)
sudo ip route add default via 192.168.1.1 dev enp0s2
```

---

### 3️⃣ 第三步：IP 衝突或設定髒掉 (Deep Clean)

如果路由看起來沒問題，但 `dhclient` 和 `ip route` 的資訊對不上（例如 Ping 報錯的 IP 跟查到的不一樣），代表網卡設定髒掉了。

```bash
# 1. 強制清洗網卡設定 (注意：如果是遠端連線可能會斷線)
sudo ip addr flush dev enp0s1  # 或 enp0s2，看哪張有問題

# 2. 重新向路由器要 IP
sudo dhclient -v enp0s1
```

---

### 4️⃣ 第四步：GitHub 連線特化解法

如果網路通了（Ping 8.8.8.8 成功），但 `git pull` 還是失敗：

#### 症狀 A：SSH Port 22 被擋 (Connection refused / timed out)
**解法**：走 HTTPS Port 443 通道。
編輯 `~/.ssh/config`：
```text
Host github.com
    Hostname ssh.github.com
    Port 443
    User git
```

#### 症狀 B：DNS 解析失敗 (Could not resolve host)
**解法**：手動指定 DNS。
編輯 `/etc/resolv.conf`，加入：
```text
nameserver 8.8.8.8
```

---

### 📝 常用指令速查表 (Cheat Sheet)

| 動作 | 指令 |
| :--- | :--- |
| **查路由** | `ip route` |
| **查 IP** | `ip addr show` |
| **測試外網** | `ping 8.8.8.8` |
| **測試 DNS** | `nslookup github.com` |
| **刪除預設閘道** | `sudo ip route del default` |
| **新增預設閘道** | `sudo ip route add default via <IP> dev <網卡>` |
| **重置 DHCP** | `sudo dhclient -v <網卡>` |