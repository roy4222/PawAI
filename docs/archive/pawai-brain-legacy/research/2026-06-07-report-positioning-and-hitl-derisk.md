# 2026-06-07 報告對外定位佐證 + HITL 技術 de-risk runbook（deep research 產出）

> **產出方式**：18-agent workflow（web fanout + 對抗式查證 + codebase de-risk）。18 agents。
> **性質**：階段一=報告對外定位（為何要機器狗 / Edge AI / LLM 不控制機器人=安全範式 / 可比較專案 / 誠實量化），全外部宣稱經查證、收斂到 confirmed 版本；階段二=今天 HITL 技術 de-risk runbook。
> **誠實鐵律**：守望/提醒/回報/非接觸；PawAI 自身數字標「自量基線」；對齊 `docs/mission/2026-06-18-demo-north-star.md`。
> **用途**：餵 PPT（`.tmp/open-slide/.../pawai-0618-presentation`）+ 報告 QA + 老師回饋（串故事/聚焦/Edge AI/為何要狗）。slide 金句與 QA 見附錄 A/B。

---

# Part 1 — 報告對外定位（含引用）

這份報告涉及大量已查證的引用與精細的誠實邊界,我先把 5 個維度的發現綜整成符合誠實鐵律的 markdown。不需要讀任何檔案——所有素材都在 JSON 裡,且要求只輸出 markdown 本文。

# PawAI 對外定位報告 — 從遙控狗到具身守望,以誠實量化為信任地基

> 給 Roy 拿去強化 PPT 與 QA。所有外部宣稱皆經查證,凡 corrected/收斂後的版本為準;PawAI 自身數字一律標「我方自量基線」。**用詞紀律**:守望/提醒/回報/非接觸;不碰守護/guardian/陌生人警報/照護/防跌。

---

## 1. 敘事主軸(串故事):Before → 工程改裝 → 量化驗證 → After

**一條線講完這個專案,讓教授看到「為何選 + 怎麼做 + 誠實到哪」。**

**Before(遙控狗)**:Unitree Go2 出廠是一台需要 App 拖放程式、靠原廠 GPT 黑盒回話的遙控四足。原廠規格頁宣稱有 GPT 語音、L2 LiDAR 自走、側隨 2.0,但第三方實測 GPT 語音「簡單指令約 80% 可用、複雜需改用 App」,且我們自己在 Go2 內建 LiDAR 實測過 ~2Hz/覆蓋 18% 不可用。它會動,但不是「會理解家裡、能被檢驗」的系統。

**工程改裝(為何要這個形態)**:我們選會移動的具身四足,是因為真實居家是多樓層、有門檻、有雜物的非結構空間——腿足在「形態潛力」上能爬樓梯、調身高鑽窄處、繞雜物(Frontiers 2023 review),且會移動的具身體理論上能補固定相機死角。但這是**形態潛力,不是 PawAI 已驗證的能力**(PawAI nav 零真實自走)。我們做的工程是:把 Go2 + D435 + RPLIDAR + Jetson,從硬體一路串到 PawAI Brain 三層決策(Safety → Policy → Expression),**不用原廠黑盒**,五路感知(人臉/語音/姿勢/物體)整合到單一 edge 裝置。

**量化驗證(誠實層 — 本報告的核心)**:我們沒有把一次成功的 demo 包裝成「全都會」。6/04 HITL baseline 用 preflight → observer → JSONL → scoreboard → readiness 的固定協議,量到:**3 項窄版 pass**(face 認註冊者 Roy / object.cup ~1m / voice.command 0.875)、**2 項 fail**(voice.stop 0.667 / gesture.wave recall=0.0)、**其餘 insufficient_data**,**readiness=not_ready**(fail-closed)。在「漂亮數字常是 shortcut」(arXiv 2606.04233)、「sim 95% 到真機常剩 30-60%」(arXiv 2510.20808)的領域裡,我們全部量在真機、敢標 not_ready。

**After(具身守望的雛形)**:目前是互動 70% / 守望 30% 的學生 POC。守望 30% 是「提醒/回報/非接觸」定位的雛形,**不是可靠的安全承諾**。安全用 deterministic rule-based 關鍵字短路繞過 LLM(危險動作如 backflip 為 demo-only 假動作,Go2 sport mode 本就無此能力),對齊業界「LLM 不直接控制機器人」範式。誠實的 After 不是「兌現了所有潛力」,而是「驗證了這個形態 + 整合 stack 值得投入,並用可重跑證據誠實標出走到哪」。

---

## 2. 為何要機器狗(embodied / 四足)

**核心論點:四足的價值只在「跨樓層 / 有地形 / 社會臨場感」場景才划算;單層平整空間輪式更合理。一律以「形態潛力」陳述,非 PawAI 已驗證能力。**

- **相對固定相機/音箱**:固定視角有死角、需要人持續盯螢幕(認知負荷有限),會移動的具身機器人理論上能「主動到現場看一眼」補盲區。⚠️ 來源為產業 vendor blog(Urban Robotics Foundation,非同行評審),且原頁未提「360 度視角」;只能當**通用安防原理**,PawAI nav 零真實自走,不可推論已具巡邏 [1]。
- **相對輪式**:腿足能爬樓梯、跨門檻、調身高繞障(Frontiers 2023 review);輪式在硬平面效率最佳但越障/上下樓梯受限。⚠️ 收斂措辭:樓梯對輪式是「major challenge」**而非 insurmountable**;輪式是「結構化平整地面效率最佳」而非「限制在平整地面」 [2]。
- **動物外形偏好(強證據)**:台灣調查(n=240,45-94 歲,71.7% 女性)顯示女性偏好動物外形 41.3% vs 男性 33.8%,P=.007 顯著 [3]。但「動物形態用姿態/頭部表達狀態引發寵物連結」屬研究**框架/動機**(arXiv 2512.17136,RL 技術論文、GO1 評估),**未對長者量到陪伴效果**。
- **具身物理在場 > 純螢幕**:LOVOT 研究(JMIR 2024,質性 n=5)受試者描述「有個活的東西陪著、我不孤單」 [4]。⚠️ 對象是寵型機器人非四足、極小樣本,**方向性支持,不可外推 PawAI/Go2 有同等效果**。
- **誠實反面**:現役商用四足在「可用性與信任」仍輸輪式——步態噪音降低引導有效性、仿生同理效果未充分發揮(arXiv 2210.08727,任務為導盲非守望) [5]。但這可工程化改善:安靜步態控制器降噪約 10 dB 到 ~50 dB、爬樓梯工作負荷接近導盲犬(arXiv 2505.11808,惟僅 n=4,**且 PawAI 未做此層優化**) [6]。
- **成本/成熟度**:Go2 Pro 約 US$2,800、2023 量產,對學生 POC 門檻最低 [7]。⚠️ 更新過時論點:「人形離量產數年」在 2026 已不準——1X NEO 已預購 US$20,000、主打 eldercare、2026 交付;Unitree G1 ~US$16K [8]。正確說法:**四足在價格與生態成熟度上對學生 POC 仍最務實,而非人形還沒到家用**。
- **具身代價(誠實列)**:腿足相對輪式平地較慢、功耗較高、高 DOF 線上規劃計算昂貴(跨來源共識) [9]。

---

## 3. Edge AI 論證

**核心取捨:把人臉/姿勢/物體視覺感知在 Jetson 端側處理完,讓敏感影像盡量不出戶——這是設計方向,PawAI 尚未全離線(語音主線仍走 Cloud)。**

- **邊緣 vs 雲端是被量過的工程取捨**(佐證來源:2025 Scientific Reports Jetson 病患監測實證,**非 PawAI 自測**):邊緣方案相較雲端基線約**降 83% 延遲、省 64% 能耗**,準確率 91.9%(雲端 LSTM 93.7%,差約 1.8pp) [10]。⚠️ **頭號數字陷阱**:28ms 屬論文另一個更輕的 dense 模型(92.4%),**不可與 91.9% 綁在一起**;雲端準確率 93.7%(93.6% 是其 F1,別寫 93.6%)。
- **即時反應與斷網韌性**:同篇明文「雲端中心架構不適合心臟事件這類低延遲關鍵任務」,雲端依賴帶來單點失效與攻擊面 [10]。
- **隱私/合規**:原始醫療影音「經不安全無線鏈路(over insecure wireless links)上傳」可能違反 HIPAA/GDPR [10]。⚠️ 保留此限定,**不可簡化成「上雲=違規」**。邊緣攝影機在裝置上分析、敏感資料 never leaves the device,較易符合 GDPR/CCPA(TechNexion,廠商觀點) [11]。
- **需求面證據(動機論證,非效果證明)**:質性研究顯示居家社交機器人使用者最大焦慮是「是不是一直在看/一直在聽」,並期待「可見的資料蒐集指示與隱私控制」(arXiv 2507.10786) [12];長者調查約 76% 正面、65% 願用,但隱私(收集無關資料、被駭)仍是阻力(FIU/Technology in Society 2024) [13]。⚠️ 兩者均為質性/接受度研究,**不證明 edge 一定提升接受度**;「本地處理是回應這需求的設計取向」是我方推論,非論文結論。
- **硬體可行**:NVIDIA Jetson Orin Nano **模組**(約信用卡大小)在 7–25W 內跑 67 INT8 TOPS、8GB LPDDR5,官方稱可跑 vision transformer/LLM/VLM [14]。⚠️ slide 講「模組級算力封套」較精確(devkit 含載板較大);官方能力宣稱 ≠ PawAI 已在端側跑 LLM。
- **趨勢(標註為分析機構預測,非硬事實)**:Gartner 預測 2025 約 75% 企業資料在雲/資料中心之外處理(2019<10%);BCC Research 估 Edge AI 市場 2025→2030 約 36.9% CAGR [15]。

---

## 4. LLM 不直接控制機器人 = 業界安全範式

**業界共識:LLM 當「高階提議者」而非「低階致動器」。PawAI 三層架構是這套範式的學生實作,非理論創新。**

- **SayCan**(Google 2022,arXiv 2204.01691):LLM 提議語意上有用的 skill(Say)、affordance value function 決定物理上做得到的(Can),兩者相乘選動作;論文明言 LLM「缺乏真實世界經驗,難以做具身決策」;真機 101 項廚房指令上 grounding 讓表現相對非 grounded baseline「接近翻倍」 [16]。
- **Code as Policies**(Google,ICRA 2023):LLM 不直接吐馬達指令,而是生成程式碼「參數化 control primitive API」、autonomously re-compose API calls——有界動作空間 [17]。⚠️ PawAI 的 skill allowlist 是更受限的選擇式做法,描述對應關係宜說「借用其有界 primitive 觀念」。
- **Inner Monologue**(Google 2022,arXiv 2207.05608):把 success detection / scene description / human feedback 三種 grounded feedback 注入 LLM planning prompt,在三 domain 顯著提升高階指令完成率 [18]。
- **RoboGuard**(arXiv 2503.07885):LLM 即使對齊過仍可被 jailbreak 做出「撞人、堵逃生門」;LTL + model checking 在 **non-adaptive RoboPAIR 攻擊**下把不安全計畫執行率從 **92.3% 壓到 2.3%**,安全計畫照常完成 [19]。⚠️ 這是 RoboGuard 結果**非 PawAI 實測**,且量自特定 jailbreak 情境。
- **Modular Safety Guardrails**(arXiv 2602.04056,2026-02 近期 position paper):model-internal safety 無法在部署時保證 action-level safety,致動器前要有一道 Action Gate「最後一道防線」、與上游 FM operationally independent、是 auditable/verifiable safety authority [20]。
- **RT-2**(Google DeepMind,光譜對照組):把動作當 token 由 VLA 直接輸出、端到端致動 [21]。PawAI 走相反的分層路線。⚠️「端到端難對單一動作做 deterministic 拒絕」是我方分析,非 RT-2 blog 原文宣稱。

**PawAI 設計對位(程式碼確認)**:
- **Safety 層**:`safety_gate.py` 用 deterministic 關鍵字(停/stop/暫停/煞車/緊急)bypass LLM 直送 stop_move;`safety_layer.py` 用 UNSAFE_KEYWORDS_REJECT(翻跟斗/倒立/backflip/handstand)回「這個動作不安全,我不能執行。」,**LLM whitelist 不含 backflip**——危險動作拒絕確為 rule-based 關鍵字比對、**非 LLM 判斷**。
- **Action grounding**:危險 api_id(1030/1031/1301)進 BANNED_API_IDS,`validate()` 對含 banned MOTION step 的 plan 原子拒絕。
- **fail-closed 世界狀態 gate**:`effective_status.py` 把 unknown/missing grade 當 insufficient_data,degraded/insufficient_data → motion/nav 類一律 blocked,所有動作經 interaction_executive 單一出口。
- ⚠️ PawAI 是「同一範式的精簡學生實作」,**非 RoboGuard 那種 LTL 形式化驗證等級**;安全層為 code + ~90+ pure-Python 單測層級,**brain.skill_gate/trace e2e 本輪 insufficient_data、未端到端實機驗證**。skill allowlist 精確數字會隨設定變動,**slide 勿寫死數字**(用「有界 skill allowlist」)。

---

## 5. 可比較專案光譜與 PawAI 誠實落點

**光譜兩端**:一端是成熟商用/臨床產品,另一端是概念驗證/研究原型。**PawAI 誠實落在後者(學生 POC),價值不在性能領先。**

| 專案 | 類型 | 載體/能力 | 成熟度 | 與 PawAI 關係 | 誠實對位 |
|------|------|----------|--------|--------------|---------|
| **PawAI** | 學生 POC | Go2+D435+RPLIDAR+Jetson,五感知+Brain 三層 | 互動 70%/守望 30%,readiness=**not_ready** | — | 3 項窄版 pass / 2 fail / 餘 insufficient,**零真實自走** |
| BD Spot+ChatGPT [22] | 概念驗證 | Spot+Whisper/GPT-4/BLIP-2/ElevenLabs | 官方自承 PoC(幻覺/6s 延遲/斷網掛) | **同格(LLM 接四足做互動 demo)** | 平台頂級、團隊世界級;但**未公開失敗邊界**,PawAI 有 |
| Glasgow RoboGuide [23] | 大學研究原型 | 四足+5G+LLM 口語導覽 | EPSRC 9 個月、2023/12 Hunterian 首測、未商用 | **最對等** | RoboGuide **已有真實室內避障導航 demo**,PawAI 零自走(該誠實承認落後) |
| CognitiveDog [24] | 研究原型(HRI 24) | Go1+自製夾爪+Mistral-7B+MiniGPT4-v2 | unseen env 64.79% | 研究定位相近(硬體不同) | 多了真實抓取+泛化數據;PawAI **公開完整 pass/fail 證據鏈** |
| Unitree Go2 原廠 [25] | 商用平台 | GPT 語音+L2 LiDAR 自走+側隨 2.0 | 第三方實測語音 ~80% 簡單指令 | PawAI 的載體本身 | PawAI **不用原廠黑盒**,自串可解釋可量測堆疊 |
| ANYbotics ANYmal [26] | 工業商用 | IP67+360°LiDAR+6 深度相機+氣體偵測 | ETH 源 2016 商品化、部署油氣廠 | **幾乎不重疊** | PawAI **絕不用巡檢/守護話術對齊** |
| ElliQ [27] | 出貨照護產品 | 桌上型、主動對話/健康提醒 | 2026/3 全美**首例**進 Medicaid(**僅華盛頓州**) | 陪伴光譜成熟端(靜態) | PawAI 為 POC,**禁照護語言**;差異是有實體四足互動 |
| PARO [28] | 醫療器材 | 海豹型生物回饋 | 2009 FDA Class II、30+ 國 | 陪伴光譜唯一法規認證端 | ⚠️ Class II ≠ 證實療效(多為小樣本);PawAI **不碰療效宣稱** |
| Hello Robot Stretch 3 [29] | 開源居家機械臂 | $24,950,NYU 合作開抽屜/撿物/**扶正掉落物品** | 出貨中 | manipulation 是 PawAI 完全沒有的 | PawAI 純感知+互動表達,**無物理操作** |
| SoftBank Pepper [30] | 失敗案例 | 社交人形 | 2020 停產 | 誠實警示 | 翻車主因=缺實體協助+期待落差;PawAI 收斂窄版+公開失敗是務實(⚠️ 別講 Pepper「普遍讓長者困惑」,研究結果混合) |

**PawAI 可誠實宣稱的三差異化(皆工程紀律,非性能領先)**:(1) **整合深度**——硬體到 Brain 三層全自串不用原廠黑盒;(2) **量化誠實層**——6/04 公開 3 pass/2 fail/餘 insufficient/readiness=not_ready 的 fail-closed 證據鏈;(3) **deterministic 安全 gate**——rule 短路繞過 LLM,且誠實揭露真機限制。

---

## 6. 誠實量化作為差異化

**機器人學習有公認的可重現性危機與 overclaiming 文獻;PawAI 的量化誠實層踩在領域共識方向上,可信度本身就是貢獻。**

- **可重現性危機**:Henderson 等(AAAI 2018)指深度 RL 結果「seldom straightforward」可重現、「non-reproducible and easily misinterpreted」,病因是 seed/環境隨機性變異未被量化 [31]。解法是報告所有 hyperparameter / 多次 trial / 信賴區間與顯著性檢定 [31]。⚠️ PawAI 是「固定協議 + 逐輪 JSONL」的**精神對齊**,**樣本小、未跑顯著性檢定、門檻自訂**,不可宣稱已達其統計嚴謹度。
- **過度宣稱批判**:benchmark 分數只在單一固定設定下成立卻被當通用能力(arXiv 2606.04233,2026 preprint) [32];LIBERO 上 0.09B 無語言編碼器探針即逼近 SOTA(Spatial 99.0%/Object 100.0%/Goal 98.8%,多數宣稱進步無統計顯著性),證明高分常是 shortcut/overfitting [32]。→ PawAI 嚴守窄版宣稱不外推。
- **把 fail 當特徵**:Trustworthy Evaluation(arXiv 2601.18723,2026 preprint)主張把 failure case 納入評測是「恢復信任」手段,binary 成功分數會掩蓋風險 [33]。→ voice.stop / gesture.wave 標 fail 連同 insufficient_data 一起呈現是可信度工程。
- **真機更難 + sim-to-real 落差**:真機可重現要選對指標並做正確統計(Lynnerup 等,PMLR v100) [34];sim 95% 到真機常剩 30-60%(arXiv 2510.20808,範圍性描述) [35]。→ PawAI 全部量在真機(Go2+Jetson),杜絕外推灌水。
- **頂會制度化報告紀律**:NeurIPS reproducibility checklist + code policy 要求交代執行次數/指標/超參數/限制;導入後**願意主動提交「程式碼」的作者比例由 <50% 升到約 75%**(Pineau 等,JMLR 2021) [36]。⚠️ **是 code submission 非「論文可重現素材」、是 nearly 75% 非「75%+」**;自報 code availability 38.76% 經 reviewer 查核降到 27.70%。
- **揭露限制提升信任**:model card(Mitchell 等,FAccT 2019)要求文件化用途/效能/限制 [37];補上詳細 model card 與下載量提升相關(+29.0%,95% CI 10.6–47.5%) [38]。⚠️ **29.0% 出自 Liang 等 2024 NMI,非 Mitchell;為相關非因果,兩來源勿合併引用**。
- **領域尚無統一評測標準**:Embodied Arena(arXiv 2509.15273)才剛整合 22 benchmark [39]。⚠️ 該論文**不含**「Task Success Rate/Realtime Responsiveness/Energy Efficiency」這三個指標(原稿捏造,已刪);實際為 Success Rate/SPL/matching accuracy 等。POC 自建誠實層「踩在領域方向上」作定位語可,**勿宣稱與 Embodied Arena 對標**。

---

## 7. 可直接放投影片的金句

> 每句標可放第幾段。所有「四足優勢」皆以形態潛力陳述。

- 「**我們不宣稱性能贏過任何人——價值不在性能,在整合深度 + 量化誠實層 + 安全 gate。**」(§1 / §5 總綱)
- 「真實居家是多樓層、有門檻、有雜物的非結構空間:腿足在形態上能爬樓梯、調身高、繞雜物——這是**四足形態潛力,PawAI 目前未驗證移動**。」(§2)
- 「中老年女性顯著偏好動物外形機器人(台灣 n=240,女 41.3% vs 男 33.8%,P=.007)。」(§2)
- 「敏感影像在 Jetson 端側處理完、盡量不出戶——這是**設計方向,我們尚未全離線**(語音主線仍走 Cloud)。」(§3)
- 「邊緣 vs 雲端是被量過的取捨:約**降 83% 延遲、省 64% 能耗**,準確率僅小讓步(91.9% vs 雲端 93.7%)——**這是論文數字,非 PawAI 自測**。」(§3)
- 「**連 Boston Dynamics 都把 Spot+ChatGPT 逐字叫 proof of concept**(幻覺、6 秒延遲、斷網就掛)。」(§4 / §5)
- 「業界共識:LLM 該當**高階提議者而非低階致動器**(SayCan / Code as Policies / RoboGuard)。」(§4)
- 「危險動作拒絕是 **deterministic 關鍵字比對、不是 LLM 判斷**;backflip 是 demo-only 假動作,Go2 sport mode 本就做不到。」(§4)
- 「**fail-closed:不確定時就不動**——能力健康度 fail/unknown/insufficient 時,motion/nav 一律 blocked。」(§4)
- 「我們 6/04 量到 **3 項窄版 pass、2 項 fail、其餘資料不足、readiness=not_ready**——敢標 not_ready 本身就是工程成熟度。」(§1 / §6)
- 「在『漂亮數字常是 shortcut』(LIBERO 0.09B 探針逼近 SOTA)、『sim 95% 到真機常剩 30-60%』的領域,**我們全部量在真機、公開失敗邊界**。」(§6)
- 「我們的 readiness 報告 = 一張**機器人版 model card / reproducibility checklist**。」(§6)
- 「對齊 Glasgow RoboGuide 時誠實說:**它已有真實室內避障導航 demo,我們導航還沒**。」(§5)

---

## 8. QA 彈藥庫

| 可能問題 | 誠實答法(壓在已驗證邊界內) |
|---------|--------------------------|
| 為什麼不用一台牆上相機+智慧音箱就好? | 固定相機有死角、需人盯螢幕(通用安防原理,vendor blog 非同行評審)。會移動的機器人理論上能補盲區,但誠實說 **PawAI nav 零真實自走、無巡邏**,「移動到多點」是形態潛力非現有能力。只看已驗證能力(認人/物體/語音),靜態裝置確實能做大部分。 |
| 為什麼不用輪式?更便宜更安靜更穩。 | 輪式在硬平面確實更快更省電更可靠(跨來源共識,我承認)。差別在地形:腿足能爬樓梯、跨門檻、繞障。但樓梯對輪式是「major challenge」**不是絕對無法跨越**。單層平整空間輪式其實合理,四足價值要在跨樓層/有地形才成立。 |
| 為什麼不用人形? | 主要是成本與生態:Go2 Pro 約 US$2,800,門檻最低。但更新一個資訊——「人形離量產數年」在 2026 已不準:1X NEO 預購 US$20K、主打 eldercare、2026 交付;Unitree G1 ~US$16K。誠實版:人形已進消費級早期,但居家照護安全門檻仍高,四足對學生 POC 仍最務實,**不是因為它最強**。 |
| 四足走路那麼吵又抖,長者不會被嚇到? | 真實缺點我不迴避:arXiv 2210.08727 顯示現役商用四足在可用性與信任輸輪式、步態噪音降低有效性。但可工程化改善:安靜步態控制器降噪約 10 dB 到 ~50 dB、爬樓梯工作負荷接近導盲犬(僅 n=4)。**PawAI 沒做這層優化,這是已知差距。** |
| 你說四足有陪伴優勢,有證據嗎? | 證據強度分清楚:陪伴最強實證來自寵型 LOVOT(JMIR 2024 質性 n=5),對象不是四足;四足專屬是台灣外形偏好調查(n=240,P=.007)。**我不宣稱 PawAI 已量到陪伴效果**——6/04 只量到能力層。 |
| 你們是不是已全離線了? | 還沒。語音主線(ASR/LLM/TTS)走 Cloud,斷網守望只是設計意圖、尚未驗證。視覺感知已在 Jetson 端側跑。我們宣稱的是「**朝資料不出戶的架構方向**」,不是「已全離線」。 |
| 你引的 28ms 是 PawAI 量的嗎? | 不是,是 2025 Jetson 病患監測同儕審查論文量的。而且 28ms 是論文裡一個較輕的 dense 模型;主打的 91.9% 模型自己延遲是 118ms。正確整組說法是「約降 83% 延遲、省 64% 能耗、準確率 91.9%」。PawAI 自己只有 6/04 那幾項窄版能力。 |
| 邊緣算力有限,精度會不會差很多反而不安全? | 差距比直覺小:邊緣 91.9% vs 雲端 93.7%,差約 1.8pp,但延遲/能耗有量級優勢。我們也不拿邊緣當迴避量測藉口——現況只有 3 pass、2 fail、餘資料不足,readiness=not_ready。 |
| 你 slide 上 GDPR 那句是不是太絕對? | 會收緊。論文原句前提是「**經不安全無線鏈路上傳原始醫療資料**」才可能違反,不是「上雲就違規」。正確講法:把原始影音留裝置端處理可降低合規風險與外傳暴露面。 |
| 你們這套是自己發明的嗎? | 不是,是「實作」業界已公認的範式(SayCan / Code as Policies / RoboGuard / arXiv 2602.04056)。我們的貢獻是整合與誠實量測,**不是理論創新**。 |
| 危險動作拒絕是 LLM 在判斷嗎? | 不是,刻意不讓 LLM 判斷安全。是 deterministic 關鍵字比對(safety_layer.py 寫死 backflip/倒立等),命中即拒;危險 api_id 放 BANNED_API_IDS,validate() 原子拒絕整個 plan。對應「安全與 planner 解耦」。 |
| backflip 你們到底會不會? | 誠實說:**demo-only 假動作,Go2 sport mode 本就沒這能力,我們也沒做**。它存在的唯一目的是當「被請求危險動作 → 系統主動拒絕」的反例 demo。 |
| 你說 RoboGuard 把危險率 92% 壓到 3%,PawAI 也有? | 沒有,那是 RoboGuard 在特定 jailbreak(non-adaptive RoboPAIR)下量的(精確 92.3%→2.3%),**佐證範式有效非 PawAI 實測**。PawAI 是輕量工程實作,不具 LTL 形式化驗證等級保證。 |
| 你們有真的自主導航、跟隨、避障、跌倒偵測嗎? | 誠實說:**沒有真實自走、沒有跟隨、沒有巡邏、沒有動態繞障,跌倒偵測也是關閉的(enable_fallen:=false)**。6/04 所有 nav 能力都是 insufficient_data;做過一次 supervised dry-run,Go2 在 AMCL gate 就被擋下、零 motion——只證明 action chain 接好且 fail-closed,不是導航能力。 |
| 你們很多項目標 fail/insufficient_data,不是代表做不好? | 在機器人學習領域,**掩蓋 fail 才是被批判的對象**(Henderson AAAI 2018 / Trustworthy Evaluation)。3 pass、2 fail、餘 insufficient、not_ready 是誠實能力快照,不是把一次成功包裝成「全都會」。 |
| 別的團隊 demo 什麼都會,你們為什麼只敢宣稱這麼窄? | 因為「單一設定成功被當通用能力」正是最新文獻點名的過度宣稱(arXiv 2606.04233)。窄而真比寬而虛更有可信度——這在學術上是加分。 |
| 你 slide 寫 NeurIPS 可重現素材 50%→75%+,準嗎? | 需修正:原文說的是「**主動提交程式碼的作者比例**」<50%→nearly 75%,是 code submission 非「論文可重現素材」、也非「75%+」;且自報 code availability 38.76% 經 reviewer 查核降到 27.70%。 |
| 你們跟 RT-2 那種真會動的機器人差在哪? | RT-2 是端到端 VLA(動作當 token 直接輸出),研究等級致動。PawAI 走相反的分層路線,LLM 不直接致動。差異不是「更會動」,是整合深度 + 量化誠實層 + 可稽核 deterministic gate。現況 readiness=not_ready。 |
| 你們的「守望」跟守護差在哪?是文字遊戲嗎? | 是嚴格範圍紀律。守護/照護/防跌/陌生人警報會暗示可靠安全承諾,但 voice.stop 量到 0.667 是 fail、跌倒偵測硬鎖沒開、nav 零自走。用守望/提醒/回報是把宣稱壓到實際能做到的窄版邊界,避免 over-claim 釀成安全誤信。 |
| 你引的論文編號看起來很新,是真的嗎? | 都可查證。SayCan(2204.01691)/Code as Policies(ICRA 2023)/Inner Monologue(2207.05608)/RoboGuard(2503.07885)已發表;最新兩篇 Modular Safety Guardrails(2602.04056,2026-02)、robot-manipulation benchmarking(2606.04233)、trustworthy eval(2601.18723)屬很新 preprint,簡報會標「2026 近期 preprint/position paper」並附存取日期。 |
| 你們三項 pass 聽起來很少,是不是沒做出什麼? | 3 窄版 pass(認 Roy n=9 registered_recall=1.0、~1m 杯子 conf 0.83-0.88、指令分類 0.875)+2 誠實標 fail+餘資料不足、not_ready。CognitiveDog 報 64.79%、很多 demo 只挑成功演,我們公開了完整證據鏈與失敗邊界。在「誠實度即可信度」標準下,**敢標 not_ready 本身就是工程成熟度**。 |
| 你們說安全層有 91 個測試,是哪 91 個?是不是湊數? | 誠實講,91 是「安全相關 pure-Python 單測」的量級(skill_policy_gate 28 + brain_rules 54 + test_safety_layer 23 等),不是某檔剛好 91。重點是這些是 code+單測層級證據,**不代表端到端實機驗證過**——brain.skill_gate/trace 這輪是 insufficient_data。 |

---

## 9. 參考來源清單

1. Urban Robotics Foundation, *Mobile Robots vs Fixed Security Cameras*(vendor blog,非同行評審). https://www.urbanroboticsfoundation.org/post/mobile-robots-vs-fixed-security-cameras
2. Frontiers in Mechanical Engineering 2023, legged locomotion review. https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2023.1142421/full
3. Taiwan robot appearance preference survey(n=240),PMC8386361. https://pmc.ncbi.nlm.nih.gov/articles/PMC8386361/
4. JMIR Human Factors 2024(LOVOT 質性研究,n=5),e56669. https://humanfactors.jmir.org/2024/1/e56669
5. arXiv 2210.08727(commercial quadruped vs wheeled,導盲任務 usability/trust). https://arxiv.org/abs/2210.08727
6. arXiv 2505.11808(安靜步態控制器,n=4 BLV). https://arxiv.org/html/2505.11808v1
7. NewAtlas / Unitree Go2 Pro 價格與量產(零售與評測). https://www.unitree.com/go2/
8. The Robot Report, *1X announces pre-order launch NEO humanoid*. https://www.therobotreport.com/1x-announces-pre-order-launch-neo-humanoid-robot/
9. Wikipedia, *Robot locomotion*(wheeled vs legged 能耗/速度/控制共識). https://en.wikipedia.org/wiki/Robot_locomotion
10. Scientific Reports / PMC12774896(2025 Jetson Nano 病患監測 edge vs cloud). https://pmc.ncbi.nlm.nih.gov/articles/PMC12774896/
11. TechNexion(edge AI 硬體廠商部落格). https://www.technexion.com/resources/privacy-challenges-of-smart-cameras-edge-ai-as-a-solution/
12. arXiv 2507.10786(居家社交機器人隱私焦慮,質性 19 訪談). https://arxiv.org/abs/2507.10786
13. FIU Business / Technology in Society 2024(長者陪伴機器人接受度,76%/65%). https://business.fiu.edu/news/2024/seniors-welcome-help-from-robot-companions-but-concerns-remain.html
14. NVIDIA Jetson Orin Nano Super Developer Kit(官方規格). https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/
15. BCC Research, *Edge AI Market to Grow at 36.9% CAGR*(市場機構估計;Gartner 75% 為二手轉述). https://www.bccresearch.com/pressroom/ift/edge-ai-market-to-grow-at-369-cagr
16. SayCan,arXiv 2204.01691(Google 2022). https://ar5iv.labs.arxiv.org/html/2204.01691
17. Code as Policies(Google,ICRA 2023). https://code-as-policies.github.io/
18. Inner Monologue,arXiv 2207.05608(Google 2022). https://arxiv.org/abs/2207.05608
19. RoboGuard,arXiv 2503.07885(IEEE RA-L,non-adaptive RoboPAIR 92.3%→2.3%). https://arxiv.org/html/2503.07885v2
20. *Modular Safety Guardrails Are Necessary for Foundation-Model-Enabled Robots*,arXiv 2602.04056(2026-02 position paper,preprint). https://arxiv.org/html/2602.04056v1
21. RT-2,Google DeepMind(端到端 VLA 對照組). https://deepmind.google/blog/rt-2-new-model-translates-vision-and-language-into-action/
22. Boston Dynamics, *Robots That Can Chat*(Spot+ChatGPT PoC). https://bostondynamics.com/blog/robots-that-can-chat/
23. University of Glasgow, *RoboGuide*(2024,EPSRC,Hunterian 2023/12 首測). https://www.gla.ac.uk/news/archiveofnews/2024/february/headline_1043333_en.html
24. CognitiveDog,arXiv 2401.09388(HRI 24 Companion,unseen env 64.79%). https://arxiv.org/html/2401.09388v1
25. Unitree Go2(原廠規格;第三方 review GPT 語音 ~80%). https://www.unitree.com/go2/
26. ANYbotics ANYmal(ETH 源 2016 商品化,IP67 工業巡檢). https://www.anybotics.com/robotics/anymal/
27. FierceHealthcare(ElliQ 2026/3 進華盛頓州 Medicaid,全美首例). https://www.fiercehealthcare.com/health-tech/intuition-robotics-secures-medicaid-coverage-social-ai-robot-elliq-washington-state
28. Wikipedia, *Paro (robot)*(2009 FDA Class II biofeedback). https://en.wikipedia.org/wiki/Paro_(robot)
29. Automated Warehouse, *Hello Robot Stretch 3*($24,950 開源,NYU GRAIL). https://www.automatedwarehouseonline.com/hello-robot-introduces-stretch-3-open-source-mobile-manipulator/
30. The Robot Report, *SoftBank stopped production of Pepper in 2020*. https://www.therobotreport.com/report-softbank-stopped-production-of-pepper-robot-in-2020/
31. Henderson et al., *Deep Reinforcement Learning that Matters*,AAAI 2018,arXiv 1709.06560. https://arxiv.org/abs/1709.06560
32. *What Are We Actually Benchmarking in Robot Manipulation?*,arXiv 2606.04233(2026 preprint). https://arxiv.org/abs/2606.04233
33. *Trustworthy Evaluation of Robotic Manipulation*,arXiv 2601.18723(2026 preprint). https://arxiv.org/html/2601.18723v1
34. Lynnerup et al., *A Survey on Reproducibility ... Real-World Robots*,PMLR v100(2020). https://proceedings.mlr.press/v100/lynnerup20a.html
35. *The Reality Gap in Robotics*,arXiv 2510.20808(Annual Review of Control 2026). https://arxiv.org/abs/2510.20808
36. Pineau et al., *Improving Reproducibility in ML Research (NeurIPS 2019 Program)*,JMLR 2021. https://www.jmlr.org/papers/v22/20-303.html
37. Mitchell et al., *Model Cards for Model Reporting*,FAccT 2019,arXiv 1810.03993. https://arxiv.org/abs/1810.03993
38. Liang et al., *Systematic analysis of 32,111 AI model cards*,Nature Machine Intelligence 2024(+29.0% 下載,相關非因果). https://www.nature.com/articles/s42256-024-00857-z
39. *Embodied Arena*,arXiv 2509.15273(整合 22 benchmark). https://arxiv.org/abs/2509.15273
40. PawAI 內部 capability baseline(2026-06-04 HITL,2026-06-18 capability-claim-matrix;我方自量、外部不可直接驗,對外以 Studio 即時 demo + git-tracked JSON 佐證). https://github.com/roy4222/PawAI

---

# Part 2 — 今天 HITL 技術 de-risk runbook

所有關鍵路徑都已確認(tmux session 名為 `demo` 而非分析中寫的 `pawai_demo`,我會在 runbook 標註)。文件已備齊,直接產出。

# PawAI Demo HITL De-Risk Runbook（2026-06-07）

> 一邊上機一邊對。每段 gate 過了再往下，不要信 CLI 的 `✓ Demo running`。
> Jetson repo 路徑 = `~/elder_and_dog`；tmux session 名 = `demo`（不是 `pawai_demo`，分析裡那個名字要替換）。
> 所有 check_command 可直接複製貼上。

---

## 上機前 30 秒防假成功

**最高優先的兩個靜默殺手**：(1) `.env` CRLF → 腳本靜默 abort 但 CLI 報成功；(2) `.env`/`.env.local` 檔名漂移 → 全程 RuleBrain（demo 看起來活著、其實沒 LLM）。兩者都讓 CLI 報成功、Studio 有畫面，最陰險。

```bash
# Step 0：清 CRLF + canonical 化 .env（兩個動作一起做）
ssh jetson-nano 'cd ~/elder_and_dog && sed -i "s/\r$//" .env .env.local 2>/dev/null; cp .env.local .env && sed -i "s/\r$//" .env'

# Step 1：確認 .env 真的有 OPENROUTER_KEY 且非 CRLF（否則全程 RuleBrain）
ssh jetson-nano 'file ~/elder_and_dog/.env; grep -c $'"'"'\r'"'"' ~/elder_and_dog/.env; grep -qE "^OPENROUTER(_API)?_KEY=" ~/elder_and_dog/.env && echo ENV_HAS_KEY || echo ENV_MISSING_KEY'
#   期望：file 不含 "CRLF"、grep -c 為 0、印 ENV_HAS_KEY

# Step 2：起 demo 後不信 CLI，親自數 node + tmux window（這是真 gate）
ssh jetson-nano 'zsh -lic "tmux ls; echo ---; ros2 node list 2>/dev/null | sort"'
```

**11-node GO 清單**（缺任一 = NO-GO，進對應 window 看 stderr）：

| 類別 | node |
|------|------|
| 決策/中控 | `brain_node`、`interaction_executive_node`、`conversation_graph_node`（langgraph 主線；legacy 才是 `llm_bridge_node`） |
| Studio/安全 | `studio_gateway_node`、`depth_safety_node` |
| 感知 | `face_identity_node`、`vision_perception_node`、`object_perception_node` |
| 語音/驅動 | `stt_intent_node`、`tts_node`、`go2_driver_node` |

> 不要信官方 `e2e_health_check.sh`：它只檢 4 個 legacy node、還包含 langgraph 模式不存在的 `llm_bridge_node`，會誤報。
> 改了 Python/yaml 卻沒生效？rsync 只搬源碼不 rebuild `install/`，必須 `colcon build --packages-select <pkg>` 再 source。

---

## P0 gate 順序

嚴格按序，前一段沒過不要做下一段。**起 brain 必走 `scripts/start_full_demo_tmux.sh`**（內建 camera+depth_safety+gesture override），不可用 `start_pawai_brain_tmux.sh` 或 `interaction_executive.launch.py`（都不起 depth_safety/camera → motion 全靜默被擋）。

```
[Gate 0] 上機前 30 秒（CRLF + .env + 數 11 node）
   ↓ 全綠
[Gate 1] depth_clear=true（motion 放行的總開關）
   ↓ data: true
[Gate 2] webrtc 鏈路活（/webrtc_req sub 含 go2_driver_node + ICE connected + 無多 instance）
   ↓ subscriber 唯一且 connected
[PRE-0] wave_hello 反證 driver 活著（echo /webrtc_req 出 api_id=1016 + Go2 真揮手）
   ↓ 1016 出現 + Go2 動
[S6] 翻跟斗 ×3（3/3 都要 blocked_by_safety + banned_api:1301 + 拒絕 TTS + /webrtc_req 無 1301）
```

**為何這個順序**：depth_clear 是所有 MOTION/NAV plan 的 fail-closed 總閘，false 時連 wave_hello 都被靜默擋 → 必須先過。webrtc 鏈路是末端，不通則任何 api_id 都發到虛空。PRE-0 用 wave_hello（1016，合法動作）反證 driver 真的會動，才能在 S6 把「Go2 不動」正確解讀為 safety 攔截而非 dry-run 假陽性。

---

### De-risk 面 1：depth_clear motion gate（#129/#130）

D435 depth → `/capability/depth_clear`（fail-closed Bool）→ SafetyLayer 原子拒絕含 MOTION/NAV step 的 plan。false 時 Go2 完全不動、終端無 error、極易誤判成「動作壞了」。SAFETY priority（stop_move/system_pause）與純語音 plan（chat_reply/say_canned/show_status）不受擋。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| Go2 對所有動作（揮手/坐下/自我介紹/wiggle/nav）無反應，語音正常，Studio 紅字 detail=`depth_not_clear_for_motion` | depth_safety_node 或 D435 沒起 / depth topic 沒發 → depth_clear 維持 fail-closed false → SafetyLayer 原子拒絕。最常見：用 `start_pawai_brain_tmux.sh` 或 IE launch（都不起 depth/camera） | `ssh jetson-nano 'zsh -lic "source ~/elder_and_dog/install/setup.zsh && timeout 3 ros2 topic echo /capability/depth_clear --once; echo ---; ros2 node list \| grep -E \"depth_safety\|camera\"; ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw --window 10"'` | echo `true`=過；`false` 但 node/hz 在=鏡頭前有近物移走或調 stop_distance；echo 不到/node 缺=改用 `start_full_demo_tmux.sh` 重起 | 起 demo 前先確認 `echo /capability/depth_clear --once` 回 `true`（這是 motion go gate） | `safety_layer.py:138-140`；`world_state.py:37,116-119`；`depth_safety_node.py:150-157` |
| depth_clear 抖動（一陣 true 一陣 false），動作偶被擋，終端 warn `depth frame stale: X.XXs > 1.00s` | depth frame 不穩（USB 頻寬/D435 掉幀/Jetson 負載高），frame_age 反覆超過 max_frame_age_s 1.0s | `ssh jetson-nano 'zsh -lic "source ~/elder_and_dog/install/setup.zsh && ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw --window 30"'` | hz 應接近 15Hz；遠低於 5 → 降 camera profile / 減並行負載 / 確認 USB3；短期 `-p max_frame_age_s:=2.0` 容忍掉幀 | Demo 前跑 30s hz 觀測確認穩 ≥10Hz 再上 | `depth_safety_node.py:159-169,83` |
| 鏡頭前沒障礙物動作卻被擋（或貼障礙卻放行） | D435 角度/高度問題：ROI 是影像中心 0.5×0.5，鏡頭朝下把地板掃進 ROI 當近物；朝上漏看正前方矮障礙。ROI 全無 valid pixel → 保守回 True | `ssh jetson-nano 'zsh -lic "source ~/elder_and_dog/install/setup.zsh && timeout 4 ros2 topic echo /capability/depth_clear"'`（同時手放鏡頭前 30cm 應翻 false） | 做手測：手放 30cm→false、移開→true、遮住→1s 內 false。不符就調 D435 物理角度對準行進路徑；參數 stop_distance_m(0.4)/roi_height_ratio(0.5) | 用手測當 1 分鐘 sanity check；調不好靠 LiDAR reactive_stop 兜底，motion 段拉到空曠處錄 | `depth_geometry.py:54-59,66-74`；`start_full_demo_tmux.sh:258`(camera_link TF) |

> 臨時繞過（**僅 isolated / 人盯場 / 前方淨空**）：`pkill depth_safety_node` 後 `ros2 topic pub --once /capability/depth_clear std_msgs/msg/Bool '{data: true}'`（latched，不 pkill 會被 5Hz tick 覆寫回去）。等於關前向防撞，最穩做法仍是修好 D435。

---

### De-risk 面 2：webrtc action 鏈路（wave_hello=1016 / sit_along=1005）

完整鏈：brain_node → `/brain/proposal` → interaction_executive_node → `/webrtc_req` → go2_driver_node → WebRTC DataChannel → Go2。**兩個獨立 dry-run 概念別混**：(A) IE 內部 dry-run（WebRtcReq import 失敗→回成功但沒發）；(B) 鏈路 dry-run（有發但 driver 沒訂閱）。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| wave/sit IE 回報 success，但 Go2 沒動、echo /webrtc_req 也沒東西 | IE 內部 dry-run：go2_interfaces 沒 import（WebRtcReq is None）→ MOTION step 短路回 `(True,'dry_run_webrtc_unavailable')`，一 byte 都沒發 | `ssh jetson-nano 'zsh -lic "tmux capture-pane -t demo -p 2>/dev/null \| grep -i \"dry-run motion\"; source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && python3 -c \"from go2_interfaces.msg import WebRtcReq; print(\\\"OK\\\")\""'` | import 失敗：`colcon build --packages-select go2_interfaces interaction_executive && source install/setup.zsh` 重啟 IE；確認不再有 `dry-run motion` | 直發 /webrtc_req 繞過 brain：照抄 `tools/pawai_cli/pawai_cli/main.py:1013-1043` inline publisher，api_id 換 1016/1005，等 `get_subscription_count()>0` 再 publish + spin 1.5s | `interaction_executive_node.py:208-210` |
| echo /webrtc_req 有 api_id=1016/1005，但 Go2 不動 | 鏈路 dry-run：go2_driver_node 不是 /webrtc_req subscriber（driver 沒起/crash/ROS_DOMAIN_ID 不一致）→ 發到虛空 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 topic info /webrtc_req -v 2>&1 \| grep -A3 Subscription"'` | Subscription 須 count≥1 且 Node=`go2_driver_node`。count=0 → `ros2 node list \| grep go2_driver_node`，沒有就重啟 robot.launch.py；driver 在跑但 count=0 → 比對 ROS_DOMAIN_ID | 直發也救不了（driver 是末端）；`ros2 launch go2_robot_sdk robot.launch.py enable_tts:=false nav2:=false slam:=false` | `go2_driver_node.py:309-314` |
| 重啟 launch 後 Go2 行為詭異、WebRTC buffer 爆、topic 搶來搶去 | 多 driver instance 殘留：`killall python3` 只殺 launch parent，C++ 子 process 殘留，下次 launch 再生一組搶同條 WebRTC | `ssh jetson-nano 'zsh -lic "ros2 node list \| grep -c go2_driver_node; ps aux \| grep -E \"go2_driver\|robot_state\|pointcloud\|joy_node\" \| grep -v grep \| wc -l"'` | 計數>1：`pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 joy_node; pkill -9 teleop; pkill -9 twist_mux`（或 `clean_full_demo.sh`），確認剩一個再重啟 | 清乾淨後重啟 driver，確認 /webrtc_req subscriber 唯一 | CLAUDE.md「多 driver instance 殘留」段 |
| Go2 剛重開機，driver 起來後 10s 內動作全無反應 | WebRTC ICE FROZEN→FAILED，通常第二個 candidate 才成功需等 10s+；此期間 DataChannel 非 open，send_command 直接 return 不發 | `ssh jetson-nano 'zsh -lic "tmux capture-pane -t demo -p 2>/dev/null \| grep -E \"Connection state:\|dc_state\" \| tail -20"'` | 等 log 出現 `Connection state: connected` 再發動作；卡 failed 用 Ethernet 直連 192.168.123.161 重啟 driver | 確認 log 出現 `connected` 再按 Studio button / 直發 webrtc | `webrtc_adapter.py:145-147`；`go2_connection.py:131-138` |
| Studio 按 wave/sit button 沒反應，但語音/手勢觸發正常 | Studio button 走 `/brain/skill_request`→brain_node→`/brain/proposal`→IE；brain_node 或 studio_gateway 沒起/斷線則 button 完全沒效 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 topic info /brain/skill_request -v 2>&1 \| grep -A3 Subscription; ros2 node list \| grep -E \"brain_node\|studio_gateway\""'` | /brain/skill_request subscriber 須含 brain_node 且 gateway 在跑；缺 brain_node 重啟 interaction_executive.launch.py | 繞過 button：直發 /webrtc_req 樣板，或用 wave 手勢觸發 | `studio_gateway.py:470-482`；`brain_node.py:227,1283` |

> **api_id 校正陷阱**：sit_along=`1005`=StandDown（趴下/降姿），**不是** Sit；真正的 Sit 是 1009。sit_along 刻意走 1005 當最接近 lay-flat 的姿勢。文件若把 sit_along 寫成 1009 會誤導。

---

### De-risk 面 3：S6 翻跟斗安全拒絕（#127）— 觸發層

**S6 不靠 intent label、也無任何同音容錯**。鏈路：ASR/文字 → `/event/speech_intent_recognized` 的 `text` 欄位 → `brain_node._on_speech_intent` 讀 `transcript = payload.get("transcript") or payload.get("text")` → `SafetyLayer.unsafe_request(text)` 純子字串比對 `keyword in text`。命中後 brain emit say_plan（拒絕句）+ motion_plan（backflip）→ IE 的 `validate()` 掃到 backflip=1301 ∈ BANNED_API_IDS → 即時發 `blocked_by_safety` / `banned_api:1301`，plan 永不入 queue。語音與 Studio 文字兩入口匯流到同一段邏輯，互為 fallback。

UNSAFE_KEYWORDS_REJECT = 翻跟斗/翻跟头/後空翻/后空翻/前空翻/倒立/backflip/front flip/frontflip/handstand（簡繁皆列，OpenCC 掛了也不影響）。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| 喊翻跟斗整鏈靜默：Go2 不動、無紅 badge、無拒絕 TTS、無 banned_api:1301 | ASR 聽錯成不含子字串的字（翻跟斗→翻根斗/反跟頭，~20% 風扇噪音誤判）→ unsafe_request 回 None → 落一般 chat 路徑。子字串比對無同音/拼音容錯，s2twp 只解簡繁救不了聽錯 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && timeout 20 ros2 topic echo /event/speech_intent_recognized --field text"'` | 看實際 text 不含關鍵字=聽錯。**改用 Studio 文字框打「PawAI 請翻跟斗」**（走 /api/text_input 繞過 ASR，100% 命中）；或字正腔圓單獨喊三字、靠近麥、降風扇噪音 | Studio chat 文字框輸入「PawAI 請翻跟斗」= 同條 brain→unsafe_request→BLOCKED 鏈，完全繞過 ASR | `safety_layer.py:23-26,68-85`；`stt_intent_node.py:983-985,1118` |
| Go2 不動、TTS 有拒絕句，但 Studio 紅 badge 一閃就被綠色 completed 蓋掉，抓不到證據 | composer-bar badge 只渲染 `brainResults[0]`（最新一筆）。一次翻跟斗產生兩筆 result：motion 的 blocked + say_canned 的 completed，到達順序受 TTS 播放耗時影響不保證 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && timeout 25 ros2 topic echo /brain/skill_result --field status"'` | **不要只看 composer badge**。直接看 `/brain/skill_result` echo：須出現 status=`blocked_by_safety` + detail=`banned_api:1301`（validate 即時發、永不被覆蓋的權威證據）。Studio 改看 skill-result bubble（逐筆渲染）或 Trace Drawer | 錄影抓 skill-result bubble（XCircle + blocked_by_safety + banned_api:1301）或直接展示 terminal echo 當 ground-truth | `chat-panel.tsx:83,529-553`；`bubble-skill-result.tsx:1-18`；`interaction_executive_node.py:85-92` |
| 懷疑 Go2 是真被擋還是只是沒連線（dry-run 假陽性） | 對 backflip 而言 100% 是 validate 攔的（擋在 dispatch 前）。但若把「普通動作也沒動」當 backflip 被擋會搞混：WebRtcReq import 失敗時正常 MOTION 走 dry-run 回 True 並 COMPLETED，Go2 同樣不動 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 topic info /webrtc_req -v \| grep -A3 Subscription && timeout 25 ros2 topic echo /webrtc_req"'` | 翻跟斗測試期間 /webrtc_req 須**完全沒有 api_id=1301**（被擋在 dispatch 前）。先發 wave_hello 確認 driver 活著（會有 1016）。backflip 不動 + skill_result 有 banned_api:1301 = 真攔截；所有動作都不動 = driver 沒接（另一問題） | Demo 不需 Go2「嘗試又被擋」。BLOCKED 發生在 validate（驅動無關），WSL 純跑 brain+IE 兩 node 即可離線重現整鏈當保底 | `interaction_executive_node.py:84-92,201-218`；`test_mini_e2e.py:226-249` |
| Go2 擋了、紅 badge 有，但拒絕 TTS「這個動作不安全，我不能執行。」沒播出來 | say_plan 與 motion_plan 故意拆兩個 plan（同 plan 會被原子拒絕，SAY 不會播）。say_plan 靠 tts_node 真播 /tts；tts_node 沒啟/mid-session 重啟致 Megaphone silent fail/喇叭 device index 跑掉就只擋不出聲 | `ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 node list \| grep tts && timeout 25 ros2 topic echo /tts --field data"'` | 確認 tts_node 在跑且 /tts 收到含「這個動作不安全」訊息。沒聲查喇叭 device（先 `source scripts/device_detect.sh` 取 `$DETECTED_SPK_DEVICE`）。避免 mid-session 重啟 tts_node（需連 driver 一起重啟） | 拒絕文字已在 /tts topic 與 Studio 訊息流可見；沒聲改用 Studio 拒絕文字氣泡 + blocked_by_safety bubble 當視覺證據，TTS 音訊非 go/no-go 必要條件 | `safety_layer.py:52-85`；`skill_contract.py:131-134`；`interaction_executive_node.py:177-199` |

> **S6 一鍵驗證**（開三個 echo 同框，再喊 3 次）：
> ```bash
> ssh jetson-nano 'zsh -lic "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && ros2 topic echo /brain/skill_result --field status & ros2 topic echo /brain/skill_result --field detail & ros2 topic echo /tts --field data & wait"'
> ```
> 判讀：每喊一次須各出現 1 筆 `blocked_by_safety` + 1 筆 `banned_api:1301` + 1 句拒絕 TTS；/webrtc_req 無 1301。離線保底：WSL 跑 brain_node+interaction_executive_node 兩 node 即可重現全鏈（BLOCKED 與驅動無關），`pytest -k 'unsafe or banned'` 36/36 綠當回歸守門。

---

### De-risk 面 4：S6 觸發路徑選擇（語音 no-VAD vs Studio 文字）

Demo 主線 = Studio push-to-talk → `/ws/speech` → SenseVoice Cloud(8001)，**不經 stt_intent_node、無前置 VAD**（按鈕界定起訖最穩）。no-VAD 旁線 = stt_intent_node energy_vad 自門檻。兩條都餵同一 `text` 欄位、都進同一 SafetyLayer。**「趴低」不是語音 keyword**（是 sit_along skill，只能 Studio button）。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| Studio 文字/PTT 喊翻跟斗有反應，純語音 no-VAD 完全沒觸發 | Demo 主線本就不靠 stt_intent_node。若以為在跑 stt_intent_node 但其實沒起/energy_vad 沒收到音/SenseVoice tunnel(8001) 斷，整條 no-VAD 不出 text 事件 | `ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source install/setup.zsh && ros2 node list \| grep -E \"stt_intent\|brain\|conversation_graph\" && curl -fsS -m3 http://127.0.0.1:8001/health \|\| echo SENSEVOICE_TUNNEL_DOWN"'` | Demo 主線一律 Studio PTT（不依賴 stt_intent_node/energy_vad）。要走 no-VAD 旁線：確認 ssh tunnel 8001 已開、`echo /state/interaction/speech` 看 warmup_done=true | 走 Studio PTT 或文字輸入（最短、最穩、不經 VAD） | `studio_gateway.py:765-809`；`stt_intent_node.py:807-866` |
| 用語音觸發核心指令（停/坐/站/過來/拍照）聽錯成 intent=unknown 或誤觸他類 | intent_classifier 也是純子字串比對無同音容錯，只硬編已知誤辨 alias；energy_vad 可能斷句過早。voice.stop=0.667（FN=2，不可當安全停車） | `ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && python3 -c \"import sys; sys.path.insert(0,\\\"speech_processor\\\"); from speech_processor.intent_classifier import IntentClassifier; c=IntentClassifier(); [print(t, c.classify(t).intent) for t in [\\\"坐下\\\",\\\"過來\\\",\\\"停\\\"]]\""'` | 核心動作 demo 全改 Studio button 觸發；語音僅留已驗證的 S6 安全拒絕 + wave_hello 兩條 | 全部核心動作走 Studio button/文字；語音只留對碼驗證的 S6 | `intent_classifier.py:36-200` |

> **拍板建議（已收斂方向）**：家裡錄製用語音版（無限重拍取 3/3 過的 take，鏡頭具身感最強）；學校 live 用 Studio 文字版求穩（100% 命中、零 ASR 風險）+ 家裡語音版預錄保底。兩條進同一 SafetyLayer、證據鏈（banned_api:1301）完全相同，文字版不損技術說服力——口白照講「100% rule-based 子字串比對、不經 LLM、雙層 fail-closed」。

---

### De-risk 面 5：S1 移動段（含真實移動的一鏡到底物理上不可能）

**五重結構限制**（全有 code 證據）：(1) IE 的 NAV executor 是 no-op #129，`interaction_executive_node.py:220-222` 直接回 `nav_unimplemented_phase_a`；(2) 8GB 統一記憶體 + brain stack 硬關 lidar/nav2/slam（`start_full_demo_tmux.sh:135-136`）；(3) demo lock 單一 owner + lane 互斥（brain ↔ nav_capability 不能並存）；(4) cmd_vel/webrtc 唯一 driver 消費者，一鏡內不可重啟；(5) F7 自走本身未通（`/cmd_vel_nav` 0 publisher + AMCL covariance plateau）。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| brain demo 一鏡內下「前進 N 公尺」→ Go2 不動，skill_result 含 `nav_unimplemented_phase_a` | IE NAV executor 是 no-op（Phase A 未接 Nav2），不發 cmd_vel/webrtc | `ssh jetson-nano 'zsh -lic "ros2 topic echo /brain/skill_result --once"'`（同時 echo /webrtc_req 應無新訊息） | S1 一律不走 brain NAV。移動退純顯示或最小 driver 直發 /cmd_vel 盲走。口白標 insufficient_data | S1 改 Foxglove 純感知顯示（另起 nav stack、另鏡）；講「守望互動小閉環」不講「走過去巡檢」 | `interaction_executive_node.py:220-222`；`skill_contract.py:451` |
| 選項A 純顯示想與 S2-S7 同鏡同跑 nav → OOM / lock 衝突 / 第二 stack 起不來 | 三重互斥：brain 硬關 nav stack + 8GB 不夠同跑 + lock lane 不能並存 + cmd_vel 唯一 driver | `ssh jetson-nano 'zsh -lic "ros2 node list \| grep -E \"nav2\|amcl\|cartographer\|brain_node\"; free -m \| head -2; cat /tmp/.pawai-demo-lock 2>/dev/null"'`（nav 與 brain node 不應同時出現；free 餘<800MB 危險） | 純顯示走完全獨立 session：`pawai demo stop` 清 brain → 另天/另鏡用 `start_nav2_amcl_demo_tmux.sh` → 只看 Foxglove **絕不發 goal**。剪輯拼兩鏡 | 純顯示只證感知到 scan/障礙/depth 三畫面，不宣稱自走 | `start_full_demo_tmux.sh:135-136`；`main.py:739-769`；`lock.py:54` |
| 選項B 盲走 `pub /cmd_vel x=0.3`→ Go2 不抬腳 | Go2 sport mode MIN_X=0.5 m/s 門檻，|x|<0.5 的 Move(1008) 被 silently 忽略 | `ssh jetson-nano 'zsh -lic "ros2 topic pub -1 /cmd_vel geometry_msgs/Twist \"{linear: {x: 0.5}}\"; sleep 0.6; ros2 topic pub -1 /cmd_vel geometry_msgs/Twist \"{linear: {x: 0.0}}\""'` | 盲走只起最小 driver（nav2:=false slam:=false，不互斥 brain），x 用 0.5、走 0.4-0.6s 立刻補 x=0（StopMove）。短促一步+馬上停站 2-3s 拍 | A2 家裡選配：抬腳走一小步+立即 StopMove | `robot_control_service.py:16-18,43-52` |
| 選項B 發 x=0 想停車→Go2 不停繼續走最多 2m（5/11 B4 撞牆） | sport mode 對 Move{x:0} silently 忽略，繼續執行最後有效 Move 到 timeout ~2-3s。driver 已修為 zero→StopMove(1003)，但繞過 driver 直發 sport API 會暴衝 | `ssh jetson-nano 'zsh -lic "ros2 topic pub -1 /cmd_vel geometry_msgs/Twist \"{linear: {x: 0.0}}\""'`（driver log 應印 `Sending StopMove (api_id=1003)`） | 盲走必經 /cmd_vel→driver（勿繞過直發 sport），確認跑修過的 handle_cmd_vel（11 unit test 綠）。停車一律靠 StopMove；拍攝人站前方 ≥1.5m 手按急停 | 學校現場明訂純顯示不碰 motion；盲走只在家裡可重拍時錄剪進去 | `robot_control_service.py:63-81` |

> **剪輯誠實性硬約束**：S1 任何片段字幕/口白須標「感知顯示」或「遙控短移」，**絕不可講「自主導航/自走巡檢/遇障繞行」**（audit §3 claim 表）。

---

### De-risk 面 6：Demo cold-start 靜默殺手

`pawai demo start` 只看 SSH rc，full mode 把 demo 腳本背景化 + 丟輸出 → rc 永遠 0、無事後驗證。以下都讓 CLI 報成功、demo 視覺上活著。

| 症狀 | 根因 | check_command | recovery | demo_fallback | code_ref |
|------|------|--------------|----------|--------------|----------|
| CLI 印 ✓ Demo running，但 tmux session 沒建/半數 window 空，Studio 連得到 gateway 但對話無反應 | `.env` 是 CRLF，`source .env` 在 `set -euo pipefail` 下撞 `$'\r'` 整腳本靜默 abort，但 SSH rc=0 照印成功。preflight 只檢 .env 存在不檢 CRLF | `ssh jetson-nano 'file ~/elder_and_dog/.env; grep -c $'"'"'\r'"'"' ~/elder_and_dog/.env'`（印 "with CRLF" 且計數>0 即中招） | `ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"` 重跑 demo；起完務必數 node 不信 ✓ | 展示在即無法排查：ssh 進 tmux 手動逐 window 啟動，每步看 stderr | `start_full_demo_tmux.sh:14,28`；`start.sh:155`；`main.py:899-919` |
| demo 起來、Studio 有畫面，但每輪都呆板罐頭回覆（RuleBrain），無 LLM 智能/persona | Jetson 只有 .env.local（真 keys）沒有 .env（檔名漂移），demo 腳本只 source .env → 缺 OPENROUTER_KEY → OpenRouterClient.is_available()=False → 每輪走 RuleBrain。最陰險 | `ssh jetson-nano 'ls -la ~/elder_and_dog/.env ~/elder_and_dog/.env.local 2>&1; grep -qE "^OPENROUTER(_API)?_KEY=" ~/elder_and_dog/.env && echo ENV_HAS_KEY \|\| echo ENV_MISSING_KEY'` | `ssh jetson-nano 'cp ~/elder_and_dog/.env.local ~/elder_and_dog/.env && sed -i "s/\r$//" ~/elder_and_dog/.env'` 後重啟。對話一輪確認 llm window engine=langgraph 非 wrapper_fallback | RuleBrain 仍能跑基本互動；要智能回覆須補 .env+重啟整個 session（不能只重啟 llm window，會 Megaphone/state 殘留） | `start_full_demo_tmux.sh:25-33`；`llm_client.py:27-45,84-91`；`conversation_graph_node.py:846,894` |
| 比讚/揮手/握拳 Go2 沒反應、Studio trace 無手勢事件 | config + launch default 把 gesture_backend 設成 rtmpose（不餵 WaveDetector→手勢永不觸發）。demo 主線唯一靠 `start_full_demo_tmux.sh:165` 的 `gesture_backend:=recognizer` override 救回，手動 ros2 launch 會中招 | `ssh jetson-nano 'zsh -lic "ros2 param get /vision_perception_node gesture_backend; ros2 param get /vision_perception_node pose_backend"'`（須各為 recognizer / mediapipe） | 務必用 `start_full_demo_tmux.sh` 啟動。已起錯：kill vision window，用 `ros2 launch vision_perception vision_perception.launch.py use_camera:=true pose_backend:=mediapipe gesture_backend:=recognizer max_hands:=2` 重啟 | 手勢臨場修不好，靠語音/物體/人臉三條撐場（5/27 demo 本就把手勢降為僅 Studio 視覺化） | `vision_perception.yaml:22-23`；`vision_perception.launch.py:21-22`；`start_full_demo_tmux.sh:159-166` |
| demo 全綠，但物體辨識（cup）數分鐘無 detection，object window 像卡住 | 首次啟動/trt_cache 被清時 TensorRT EP 冷建 engine 需 3-10 分鐘，但腳本啟動後只 `sleep 3` 就往下報完成，object node 還在背景 build engine | `ssh jetson-nano 'ls -la /home/jetson/trt_cache/ 2>&1 \| head; zsh -lic "timeout 8 ros2 topic hz /perception/object/debug_image"'`（cache 空+無 hz=還在冷建） | Demo 前提早 5-10 分鐘跑一次讓 TRT cache 落地（跨重啟保留），確認 hz ~6-8Hz 再展示。**切勿展示前清 trt_cache** | 首輪冷啟先用語音/手勢/人臉，等 object window 出現 `ONNX session ready` 再展示「看到杯子」 | `object_perception_node.py:238-266`；`start_full_demo_tmux.sh:274-279` |
| 無人跌倒 Go2 卻觸發 fallen_alert，明明傳了 `enable_fallen:=false` | **`enable_fallen:=false` 是死參數完全無效**：IE launch 沒宣告此 arg，brain_node._on_pose 的 fallen 路徑只受 fallen_accumulate_s(2s)+15s cooldown 控制，沒任何 enable_fallen 開關。fallen 偵測 demo 永遠開著 | `grep -n enable_fallen /home/roy422/newLife/elder_and_dog/interaction_executive/interaction_executive/brain_node.py /home/roy422/newLife/elder_and_dog/interaction_executive/launch/interaction_executive.launch.py`（兩者皆無輸出=參數無效已證實） | 真要關須改 code：brain_node fallen 路徑加 enable_fallen gate，或 launch override brain_node 把 fallen_accumulate_s 設超大。**別依賴 enable_fallen** | 展示避免讓人做躺/大幅彎腰姿勢觸發 pose=fallen；誤觸等 15s cooldown 過後繼續 | `brain_node.py:1073-1099`；`state_machine.py:76,146`；`interaction_executive_node.py:48-50` |
| 改了 Python/yaml/新參數，rsync 後重啟行為沒變 | rsync 只搬源碼不 rebuild install/，node 跑的是 install/ 下 colcon 安裝的版本 | `ssh jetson-nano 'zsh -lic "diff <(cat ~/elder_and_dog/vision_perception/config/vision_perception.yaml) <(cat ~/elder_and_dog/install/vision_perception/share/vision_perception/config/vision_perception.yaml) && echo IN_SYNC \|\| echo STALE_INSTALL"'` | `ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && colcon build --packages-select <pkg> && source install/setup.zsh"'` 再重啟。改 brain/yaml/新參數沒生效第一個查這 | 無 — 必須 colcon build，否則展示舊版行為 | `start_full_demo_tmux.sh:38`；CLAUDE.md「rsync 只搬源碼」段 |

---

## go/no-go 總表

每段 gate 逐項打勾，任一 NO-GO 即停、依對應 failure_mode recovery 修，修不了切 demo_fallback。

| 段 | gate 項目 | 一鍵驗證 | GO 判準 |
|----|----------|---------|---------|
| **Gate 0 防假成功** | .env 非 CRLF + 有 KEY + 11 node 齊 | `ssh jetson-nano 'file ~/elder_and_dog/.env; grep -qE "^OPENROUTER(_API)?_KEY=" ~/elder_and_dog/.env && echo HAS_KEY; tmux ls; ros2 node list 2>/dev/null \| sort'` | file 不含 CRLF + HAS_KEY + demo session 含 11 window + 11 node 全在 |
| **Gate 1 depth** | depth_clear=true + node 在 + hz≥10 | `ssh jetson-nano 'zsh -lic "source ~/elder_and_dog/install/setup.zsh && ros2 topic echo /capability/depth_clear --once; ros2 node list \| grep depth_safety; ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw --window 10"'` | echo `data: true` + depth_safety_node 在 + hz 穩定 ≥10 |
| **Gate 2 webrtc** | /webrtc_req sub 含 go2_driver_node + driver 唯一 + ICE connected | `ssh jetson-nano 'zsh -lic "source ~/elder_and_dog/install/setup.zsh && ros2 topic info /webrtc_req -v 2>&1 \| grep -A3 Subscription; ros2 node list \| grep -c go2_driver_node; tmux capture-pane -t demo -p \| grep \"Connection state:\" \| tail -1"'` | Subscription count≥1 含 go2_driver_node + driver 計數=1 + log `connected` |
| **PRE-0 wave** | wave_hello echo 出 1016 + Go2 真揮手 | 觸發 wave_hello（手勢/Studio button），`ros2 topic echo /webrtc_req` 看 api_id=1016 | echo 出 api_id=1016 + IE log 'ok'（非 dry_run）+ Go2 真揮手 |
| **S6 ×3** | 3/3 都 blocked + banned_api:1301 + 拒絕 TTS + /webrtc_req 無 1301 | S6 一鍵驗證指令（見面 3），喊/打 3 次 | 每次各 1 筆 `blocked_by_safety` + `banned_api:1301` + 1 句拒絕 TTS；/webrtc_req 無 1301 |
| **功能性確認** | gesture=recognizer + object hz + LLM 非 RuleBrain | `ssh jetson-nano 'zsh -lic "ros2 param get /vision_perception_node gesture_backend; ros2 topic hz /perception/object/debug_image"'` + 對話一輪 | gesture_backend=recognizer + object ~6-8Hz + llm window engine=langgraph 非 wrapper_fallback |
| **S1 移動（如演）** | 與互動鏈不同 lock/lane/鏡 + 不發 brain NAV/nav goal | `ssh jetson-nano 'zsh -lic "ros2 node list \| grep -E \"nav2\|amcl\|brain_node\""'` | nav 與 brain node 不同時出現；純顯示不發 goal；盲走 x=0.5 走 0.5s 立刻 StopMove |

---

## Roy 4 個待拍板的工程建議

**拍板 1 — S1 移動定位（核心問題）**：三選項評比 → 選項A 純顯示（可行性高、真自走 insufficient F7 未修、OOM/lock 風險中）；選項B 盲走遙控（driver cmd_vel 11 test 綠、不互斥 brain、但 MIN_X=0.5 踩 MAX 上限需人盯急停、暴衝史 B4）；選項C 完全不碰（100% 安全但缺「會動」畫面）。**推薦 A+B 混合分場拍**：學校現場用 A 純顯示 only（求穩、不可重拍），口白「守望互動小閉環/感知顯示」誠實標 insufficient_data；家裡備片用 B 盲走短移一步（無限重拍、可控急停）剪進影片當「移動」畫面；全程遵守 §gate（移動段永遠另鏡、不接 brain NAV、不發 nav goal）。與 production-plan / audit 已收斂方向一致，不踩三重互斥。

**拍板 2 — S6 觸發路徑（語音 vs Studio 文字）**：與 S1 無耦合，但同屬「戲劇性 vs 確定性」取捨。建議**家裡語音版預錄保底（具身感最強，無限重拍取 3/3 過的 take）+ 學校 live 用 Studio 文字版求穩（100% 命中、零 ASR 風險）**。兩條進同一 SafetyLayer、證據鏈 banned_api:1301 完全相同，文字版不損技術說服力。若 S1 選 B 盲走（已是戲劇性），S6 可選 Studio 文字平衡風險。

**拍板 3 — S2 認人對象（#128 enroll 新主角）**：與 S1/S6 無耦合，獨立決策。需確認新主角 enroll 進 face_db 且 face_identity_node 已 build/load。（本次 6 面分析未深掃 enroll 流程，建議上機前單獨 verify face_db 內容。）

**拍板 4 — 互動鏈節拍（≥8s 間隔 / 關 auto-fire）**：只約束 S2-S7 同 stack 段。S1 因「另 stack/另鏡」天然隔離，不受 perception auto-fire 互擾——這是「S1 拆出去」的額外好處。注意 **fallen auto-fire 無法靠 `enable_fallen:=false` 關**（死參數，見面 6），節拍控制須靠演出時避免觸發 pose=fallen 或改 code 加 gate。

---

## 附錄 A：可直接放投影片的金句（依維度）


### 為何要一隻「會移動的具身四足機器人」——相對於 靜態智慧音箱/牆上相機、輪式機器人、人形機器人，在居家/機構「到現場看一眼、認人、提醒、回報」這類非接觸守望+互動任務上的獨有價值
- 靜態相機/音箱看不到的地方就是看不到——固定視角有死角、要人盯螢幕（認知負荷有限）；會移動的具身機器人理論上能『主動到現場看一眼』補盲區（來源為通用安防原理，非 PawAI 已具備能力——PawAI nav 為零真實自走）。
- 真實居家是多樓層、有門檻、有雜物的非結構空間：Frontiers 2023 review 證實腿足能爬樓梯、調整身高鑽過窄處、繞雜物，輪式在硬平面效率最佳但越障/上下樓梯受限——這是四足『形態潛力』，PawAI 目前未驗證移動。
- 中老年女性偏好動物外形機器人有顯著統計證據（台灣調查 n=240，女 41.3% vs 男 33.8%，P=.007）；『動物形態用姿態/頭部表達狀態引發寵物連結』則屬研究框架而非對長者量到的陪伴效果。
- 具身物理在場 > 純螢幕的陪伴依附證據來自寵型機器人 LOVOT（JMIR 2024，質性 n=5：『有個活的東西陪著、我不孤單』），非四足——可作方向性支持，不可外推 PawAI/Go2 已有同等效果。
- 誠實反面：現役商用四足在『可用性與信任』仍輸輪式（arXiv 2210.08727：步態噪音降低有效性、仿生同理效果未充分發揮）；但這可工程化改善（arXiv 2505.11808 安靜步態控制器降噪約 10 dB 到 ~50 dB、爬樓梯工作負荷接近導盲犬，惟僅 n=4 小樣本，且 PawAI 未做此優化）。
- 成本/成熟度上四足對學生 POC 務實：Go2 Pro 約 US$2,800、2023 量產；惟『人形離量產數年』已過時——2026 已有 1X NEO（US$20K，主打 eldercare 預購/交付）、Unitree G1（~US$16K），居家照護安全門檻仍高，故四足仍是價格與生態最務實的選擇而非唯一選擇。
- 具身代價要誠實列：腿足相對輪式平地較慢、功耗較高、高 DOF 控制與線上規劃計算昂貴（跨來源共識）——四足的價值只在『跨樓層/有地形/社會臨場感』場景才划算，單層平整空間輪式更合理。
- PawAI 的誠實差異化不是『四足很酷/會 backflip』（backflip 為 demo-only 假動作），而是：感知-決策-表達整合深度 + 主動建立的量化誠實層（6/04 三項窄版 pass、兩項 fail、其餘資料不足、readiness=not_ready）+ rule-based 危險動作 gate。

### Edge AI 邊緣感知的論證（為何把人臉/語音/姿勢/物體感知放在 Jetson 這類裝置端、而非全雲端，對居家/機構照護場景特別重要）
- 照護現場最敏感的是『家中的影像與聲音』。Edge AI 的核心取捨是：把人臉/姿勢/物體等視覺感知在 Jetson 端側就處理完，讓敏感影像盡量不出戶（廠商與文獻語境的 never-leaves-the-device 設計方向），先天較易對齊 GDPR/CCPA 與資料主權——這是『設計方向』，PawAI 尚未全離線。
- 邊緣 vs 雲端是被量過的工程取捨（佐證來源：2025 Scientific Reports Jetson Nano 病患監測實證，非 PawAI 自測）：論文邊緣方案相較雲端基線約降 83% 延遲、省 64% 能耗，準確率 91.9%（雲端 LSTM 93.7%，差約 1.8pp）。延遲/能耗是量級優勢、精度只小讓步。注意 28ms 這個絕對數字屬論文另一個更輕的 dense 模型，不要和 91.9% 綁在一起講。
- 即時反應與斷網韌性：該論文明文『雲端中心架構不適合心臟事件這類低延遲關鍵任務』，且雲端依賴帶來單點失效與攻擊面。把感知放端側，才能在網路不穩/斷線時仍即時回應——這是 PawAI 守望路線圖想往的方向（目前語音主線仍走雲端、斷網守望未驗證）。
- 頻寬與成本：在地處理＋事件觸發式錄製避免把連續影音串上雲，省頻寬/儲存/雲費，去中心化也讓單一裝置被攻破不擴散到整網（TechNexion，廠商觀點，方向有學術交叉佐證）。
- 趨勢站在邊緣這側（標註為分析機構預測，非硬事實）：Gartner 預測 2025 約 75% 企業資料在雲/資料中心之外處理（2019<10%）；BCC Research 估 Edge AI 市場 2025→2030 約 36.9% CAGR。硬體面 NVIDIA Jetson Orin Nano 模組在 7–25W、模組約信用卡大小內跑 67 INT8 TOPS，官方稱可跑 vision transformer/LLM/VLM——讓端側多模態感知技術上可行。
- 需求面證據（動機論證，非效果證明）：質性研究顯示居家社交機器人使用者最大焦慮就是『是不是一直在看/一直在聽』，並期待『可見的資料蒐集指示與隱私控制』；長者調查約 76% 正面、65% 願用但隱私（收集無關資料、被駭）仍是阻力。Edge『資料在裝置內處理』回應了這個需求——是設計槓桿，不等於已通過長者實測。
- PawAI 誠實定位：我們把五路感知整合到單一 edge 裝置（學生 POC），是『朝向資料不出戶的設計方向』；目前語音主線（ASR/LLM/TTS）仍走 Cloud、斷網守望僅設計意圖未驗證；6/04 量到 3 項窄版 pass＋2 項 fail＋其餘資料不足、readiness=not_ready。Edge AI 是我們論證的價值與路線圖，不是已達成的全離線成果。

### 「LLM 不直接控制機器人」安全範式 — 學術/業界背書 + PawAI 定位
- 業界共識:LLM 該當『高階提議者』而非『低階致動器』——SayCan(Google 2022)以『Do As I Can, Not As I Say』定調:LLM 提議語意上有用的 skill(Say)、學到的 affordance value function 把關物理上做得到的(Can),在真機 101 項廚房指令上 grounding 讓表現相對非 grounded baseline『接近翻倍』。
- 為什麼非分層不可:RoboGuard(arXiv 2503.07885)證明 LLM 即使對齊過仍可被 jailbreak 做出『撞人、堵逃生門』;獨立外部 guardrail(LTL+model checking)在該 jailbreak 情境把不安全計畫執行率從 92%+ 壓到 3% 以下,安全計畫照常完成。(此為 RoboGuard 結果,佐證範式有效,非 PawAI 實測。)
- 安全必須『與模型解耦、不可繞過』:arXiv 2602.04056(2026 近期 position paper)指出安全只嵌在模型內結構上不足,致動器前要有一道 Action Gate『最後一道防線』,不論計畫怎麼產生都強制物理約束——這正是 action allowlist + fail-closed 的學理依據。
- PawAI Brain 三層(Safety→Policy→Expression)是這套範式的具體學生實作:危險動作(翻跟斗/倒立/backflip)由 rule-based 關鍵字 deterministic 拒絕(safety_layer.py,非 LLM 判斷),LLM 只能從有界 skill allowlist 選,危險 api_id(1030/1031/1301)進 BANNED_API_IDS 由 validate() 原子拒絕。
- 世界狀態 fail-closed:能力健康度為 fail / unknown / insufficient_data 時,motion 與 nav 類動作一律 blocked,所有動作經 interaction_executive 單一出口(effective_status.py 證據)——寧可不動,不冒險動。
- 誠實定位:PawAI 是把公認安全範式整合進居家互動四足的學生 POC,差異化在『整合深度 + 量化誠實層 + deterministic 安全 gate』,而非端到端致動能力(對照 RT-2 端到端)。現況 readiness=not_ready,僅 3 項窄版能力 pass(face 認註冊者 / object.cup ~1m / voice.command 0.875),nav 全 insufficient_data,跌倒偵測關閉。

### 可比較專案光譜中的誠實定位：PawAI 作為學生 POC，差異化在「整合深度 + 量化誠實層 + 安全 gate」而非性能領先
- 光譜兩端：一端是成熟商用/臨床產品——ANYmal(工業巡檢自走，IP67、360°LiDAR+6 深度相機+氣體偵測，ETH 2016 商品化)、PARO(2009 FDA Class II 生物回饋醫療器材、30+ 國)、ElliQ(2026/3 全美首例進 Medicaid 給付，惟僅華盛頓州)、Stretch 3(開源 $24,950 居家機械臂，NYU 合作)；另一端是概念驗證/研究原型——BD Spot+ChatGPT、Glasgow RoboGuide、CognitiveDog。PawAI 誠實落在後者，是學生 POC。
- 連最頂尖的 Boston Dynamics 都把 Spot+ChatGPT 逐字明說成 proof of concept(內部 hackathon、幻覺、6 秒延遲、斷網就掛)；Go2 原廠出廠就有 GPT 語音+L2 LiDAR 自走+側隨(但第三方實測語音僅 ~80% 簡單指令可用)。PawAI 不宣稱性能贏過他們——價值不在性能。
- PawAI 可誠實宣稱的三件工程紀律：整合深度(Go2+D435+RPLIDAR+Jetson 到 Brain 三層決策全自串、不用原廠 GPT 黑盒)、量化誠實層(6/04 公開 face/object.cup/voice.command 3 項窄版 pass + voice.stop/gesture.wave 2 fail + 其餘 insufficient_data + readiness=not_ready 的 fail-closed 證據鏈)、安全 gate(deterministic rule 短路繞過 LLM)。
- 安全用規則硬短路而非 LLM 自判——與前沿研究方向一致：arXiv 2410.13691(RoboPAIR, ICRA 2025) 對 GPT-3.5 整合的『同款 Unitree Go2』首次成功 jailbreak、常達 100%；多篇近期研究指向『單靠 LLM 判斷不足、需外部安全層』。誠實補充：PawAI 用輕量關鍵字短路是這精神的落地，非該論文背書關鍵字法本身；且 PawAI 安全層僅 code+單測層級(~91 pure-Python test)，本輪未做端到端實機 e2e。
- 誠實邊界：PawAI 互動 70%/守望 30%，零真實自走、無跟隨、無巡邏、無動態繞障、無跌倒偵測(demo 硬鎖 enable_fallen:=false)；3 項窄版 pass(認註冊者 Roy/~1m 杯子/指令分類 0.875)、2 項 fail、其餘資料不足。用守望/提醒/回報，不講守護/照護/防跌。對齊 RoboGuide 時要誠實說：它已有真實室內避障導航 demo，我們導航還沒。
- Pepper(2020 停產)的教訓：陪伴/人形機器人翻車主因是缺實體協助(取物/扶起做不到)+對話能力有限造成期待落差(研究：約 1/3 期望對話、僅約 1/5 實際體驗到)。PawAI 把範圍誠實收斂成窄版 POC、公開失敗項，是務實而非示弱——但別把 Pepper 講成『普遍讓長者困惑挫折』，研究結果其實是混合的。

### 誠實量化 / eval 文化作為可信度差異化：機器人學習可重現性危機與 overclaiming 文獻，論證 PawAI「preflight→observer→JSONL→scoreboard→readiness、會就說會、fail 標 fail、not_ready 照實呈現」量化誠實層為加分項，並把 voice.stop / gesture.wave 兩項真實 fail 框成可信度工程
- 可重現性危機是機器人學習的公認痛點：Henderson 等（AAAI 2018）指深度 RL 結果常『seldom straightforward』可重現、『non-reproducible and easily misinterpreted』——PawAI 用可重跑的固定協議＋逐輪 JSONL，把口頭宣稱換成可被檢驗的證據（精神對齊，非宣稱已達其統計嚴謹度）。
- 最新批判直指過度宣稱：benchmark 分數只在單一設定下成立卻被當通用能力（arXiv 2606.04233, 2026 preprint）——PawAI 嚴守窄版宣稱（face 認註冊者 Roy、cup ~1m、voice.command 0.875），不外推就是學術上的誠實。
- 把 fail 當特徵不是缺陷：Trustworthy Evaluation（arXiv 2601.18723, 2026 preprint）主張納入 failure case 才能『恢復信任』、binary 成功分數會掩蓋風險——voice.stop / gesture.wave 標 fail 連同 insufficient_data 一起呈現，是可信度工程的具體實踐。
- 高分≠可信：LIBERO 上 0.09B 無語言模型的探針即逼近 SOTA（Spatial 99.0%/Object 100.0%/Goal 98.8%，且多數宣稱的進步無統計顯著性）；sim 95% 到真機常剩 30-60%（範圍性描述，arXiv 2510.20808）——PawAI 全部量在真機（Go2+Jetson），杜絕外推灌水。
- 頂會把報告紀律制度化：NeurIPS reproducibility checklist + code policy 要求交代執行次數、指標、超參數、限制；導入後願意主動提交『程式碼』的作者比例由 <50% 升到約 75%（注意：是 code submission，非『論文可重現素材』；且自報 code availability 經 reviewer 查核會下修）——PawAI 的 readiness=not_ready 報告就是一張機器人版 model card / reproducibility checklist。
- 揭露限制提升而非削弱可信度：model card（Mitchell et al., FAccT 2019）要求文件化用途/效能/限制；另一研究（Liang et al. 2024, NMI）發現補上詳細 model card 與下載量提升相關（+29.0%，95% CI 10.6–47.5%，單一介入、相關非因果）——PawAI 列出 fail 與 insufficient_data 是同一誠實邏輯。
- 差異化定位：在具身 AI 尚無統一評測標準的當下（Embodied Arena 才剛整合 22 benchmark，arXiv 2509.15273），一個學生 POC 願意自建『會就說會、fail 標 fail、not_ready 照實呈現』的量化誠實層（preflight→observer→JSONL→scoreboard→readiness），可誠實宣稱的差異化＝整合深度＋量化誠實層＋安全 gate，可信度本身就是貢獻。


---

## 附錄 B：QA 彈藥庫（問題 → 誠實答法）


### 為何要一隻「會移動的具身四足機器人」——相對於 靜態智慧音箱/牆上相機、輪式機器人、人形機器人，在居家/機構「到現場看一眼、認人、提醒、回報」這類非接觸守望+互動任務上的獨有價值
- **Q：為什麼不直接用一台牆上相機 + 智慧音箱就好？那更便宜也更穩。**
  - A：固定相機有死角、視角固定，且需要人持續盯螢幕（認知負荷有限）——這是通用安防原理（Urban Robotics Foundation，屬 vendor blog 非同行評審）。會移動的具身機器人理論上能補盲區，但我要誠實說：PawAI 目前 nav 零真實自走、無巡邏，所以『移動到多點』是四足形態的潛在優勢，不是 PawAI 現在已驗證的能力。如果只看當前已驗證能力（認人/物體/語音指令），一台靜態裝置確實能做到大部分。
- **Q：那為什麼不用輪式機器人？輪式更便宜、更安靜、更穩。**
  - A：輪式在硬平面確實更快、更省電、控制更簡單可靠（這是跨來源共識，我承認）。差別在地形：真實居家有樓梯、門檻、雜物，腿足能爬樓梯、跨門檻、調身高繞障（Frontiers 2023 review）。但要修正一個常見過度說法——樓梯對輪式是『major challenge』而非『絕對無法跨越』。所以如果目標場域是單層平整空間，輪式其實是合理選擇；四足的價值要在跨樓層/有地形的場景才成立。
- **Q：為什麼不用人形機器人？人形更通用、能操作物品。**
  - A：主要是成本與生態成熟度：Go2 Pro 約 US$2,800，對學生 POC 門檻最低。但我得更新一個資訊——『人形離量產數年』在 2026 已不準確：1X NEO 已開放預購 US$20,000、主打 eldercare 且 2026 開始交付，Unitree G1 約 US$16K 在售。所以更誠實的說法是：人形已進入消費級早期，但居家照護的安全/可靠度門檻仍高，四足在價格與我們能取得的生態（Go2 ROS2 SDK）上仍是更務實的學生專案選擇，不是因為它最強。
- **Q：四足走路那麼吵又會抖，長者不會被嚇到或不信任嗎？**
  - A：這是真實缺點我不迴避：arXiv 2210.08727 顯示現役商用四足在可用性與信任明顯輸輪式，步態噪音會降低引導有效性、仿生同理效果未充分發揮。但這是可改善的工程問題——arXiv 2505.11808 的安靜步態控制器把噪音降約 10 dB 到 ~50 dB、爬樓梯工作負荷接近導盲犬（惟僅 4 名受試者，方向可信不宜當普適）。PawAI 目前沒做這層步態優化，這是已知差距。
- **Q：你說四足有『陪伴/社會臨場感』優勢，有證據嗎？還是你在替自己的選擇找理由？**
  - A：我把證據強度分清楚：陪伴/依附最強的實證來自寵型機器人 LOVOT（JMIR 2024，但只是 n=5 的質性研究），證明『會動的具身+物理在場』比螢幕更易引發依附——對象不是四足。四足專屬的是台灣調查（n=240，P=.007）顯示中老年女性顯著偏好動物外形，以及反應式機器狗手勢的研究（arXiv 2512.17136，但那是 RL 技術論文、在 GO1 上評估，沒有對長者量到陪伴效果）。所以我不會宣稱 PawAI 已量到陪伴效果——我們 6/04 只量到能力層（認人/物體/語音）。
- **Q：所以 PawAI 跟這些研究比，到底強在哪？是不是只是買了一台 Go2 跑 demo？**
  - A：誠實講，PawAI 不在任何單項能力上贏這些論文。差異化是整合深度（感知+決策+表達同一台跑）+ 量化誠實層（6/04 量到 face 認註冊者 Roy、object.cup~1m、voice.command 0.875 三項窄版 pass，voice.stop 和 gesture.wave fail，其餘 insufficient_data，readiness=not_ready）+ rule-based 危險動作 gate。我們刻意不吹牛：沒有自走、沒有跟隨、沒有巡邏、沒有跌倒偵測（enable_fallen:=false）、backflip 是 demo-only 假動作。
- **Q：既然這麼多能力都還沒做到，為什麼一開始就選會動的四足，而不是先做穩一個靜態互動裝置？**
  - A：合理質疑。誠實回答：選四足是為了驗證『具身形態 + 整合 stack』這個方向的可行性與摩擦點，不是因為現在就用得上移動能力。若只看已驗證能力（認人/物體/語音），確實靜態裝置就能做大部分。四足的價值是未來潛力（多點查看、跨地形、社會臨場感）。這份報告要呈現的是『為何這個形態值得投入』，不是『PawAI 已兌現這個形態的所有潛力』。
- **Q：你引的那些研究跟 PawAI 任務一樣嗎？導盲機器狗不就是在帶人走路？**
  - A：不一樣，我得講清楚邊界。導盲機器狗（arXiv 2210.08727 / 2505.11808）的任務是『主動牽引人移動』，PawAI 是『非接觸守望+互動』——我引它們只是用來做四足 vs 輪式的可用性/信任/噪音對比，不是宣稱 PawAI 會做導盲。同樣地『移動補盲區』的最強證據來自安防巡邏情境，不是居家照護，且 PawAI nav 為零真實自走，所以那是形態原理而非 PawAI 能力。

### Edge AI 邊緣感知的論證（為何把人臉/語音/姿勢/物體感知放在 Jetson 這類裝置端、而非全雲端，對居家/機構照護場景特別重要）
- **Q：你們現在是不是已經全部在裝置上跑、完全離線了？**
  - A：還沒有。語音主線（ASR/LLM/TTS）目前走 Cloud path，斷網時的守望也只是設計意圖、尚未驗證。人臉/姿勢/物體等視覺感知已在 Jetson 端側跑，語音是已知的下一步要往本地 fallback 收斂。所以我們宣稱的是『朝資料不出戶的架構方向』，不是『已全離線』。
- **Q：你引的那個 28ms 邊緣延遲，是 PawAI 量的嗎？**
  - A：不是。那是 2025 年一篇 Jetson Nano 病患監測的同儕審查論文（Scientific Reports）量的，用來支撐『邊緣 vs 雲端在延遲/能耗的通則取捨』，不是 PawAI 自己的數字。而且要誠實說：那 28ms 是論文裡一個較輕的 dense 模型；他們主打的 91.9% 準確率模型自己的延遲其實是 118ms。整組正確說法是『約降 83% 延遲、省 64% 能耗、準確率 91.9%』。PawAI 自己量到的只有 6/04 那幾項窄版能力。
- **Q：邊緣裝置算力有限，精度會不會比雲端差很多反而不安全？**
  - A：差距比直覺小。那篇 Jetson 論文裡邊緣方案 91.9%、雲端 LSTM 93.7%，差約 1.8 個百分點，但延遲/能耗有量級優勢。對居家即時互動這個取捨划算。我們也不拿邊緣當迴避量測的藉口——PawAI 現況只有 3 項窄版 pass、2 項 fail、其餘資料不足，readiness 仍是 not_ready。
- **Q：把鏡頭麥克風放家裡，長者本來就會怕，Edge AI 真的有幫助嗎？**
  - A：這正是需求面的證據。質性研究顯示使用者最大焦慮就是『是不是一直在看、一直在聽』，並期待看得到資料被蒐集的指示與隱私控制；長者調查也顯示多數人正面但隱私（收集無關資料、被駭）仍是阻力。Edge 讓我們能誠實說『原始影音在裝置內處理、不上傳』來回應這個焦慮——但這是設計槓桿，不是已通過長者實測的效果證明，那些研究本身也沒量化證明 edge 一定提升接受度。
- **Q：既然雲端模型更強，為什麼照護場景不直接全上雲？**
  - A：三個被同儕審查論文點名的硬理由：延遲——雲端 round-trip 不適合低延遲關鍵任務；隱私/合規——原始醫療影音經不安全無線鏈路上傳可能違反 HIPAA/GDPR；韌性——雲端依賴帶來單點失效與攻擊面，家裡斷網就停擺。守望要的是隨時在、就地反應、資料不外流，這是 Edge 的主場。
- **Q：Edge AI 只是行銷名詞嗎？有沒有真實產業/學界支撐？**
  - A：有。同儕審查面：2025 Scientific Reports 的 Jetson 病患監測實證量了邊緣 vs 雲端的延遲/能耗/精度取捨。趨勢面（要標是分析機構預測）：Gartner 估 2025 約 75% 企業資料在雲/資料中心外處理，BCC Research 估 Edge AI 市場約 36.9% CAGR。硬體面：NVIDIA Jetson Orin Nano 模組在 7–25W、約信用卡大小跑 67 TOPS。所以把多模態感知放端側是被驗證的工程方向，不是噱頭。
- **Q：那 PawAI 相對其他照護/居家機器人的誠實差異化在哪？**
  - A：三點且都可被檢驗：第一，整合深度——五路感知（人臉/語音/姿勢/物體）整合在單一 edge 裝置上的學生 POC；第二，量化誠實層——6/04 用 pass/degraded/fail gate 量了能力，敢公布 fail 與資料不足；第三，安全 gate——危險動作用 rule-based 關鍵字比對先擋（我們也誠實說那不是 LLM 判斷、backflip 是 Go2 sport mode 本就做不到的 demo-only 假動作）。我們不宣稱導航自走、跟隨、巡邏或跌倒偵測（enable_fallen=false）。
- **Q：你 slide 上 GDPR 那句是不是太絕對了？**
  - A：我會收緊。論文原句的前提是『經不安全無線鏈路（over insecure wireless links）傳輸原始醫療資料』才可能違反 HIPAA/GDPR，不是『只要上雲就違規』。所以正確講法是：把原始影音留在裝置端處理可降低這類合規風險與外傳暴露面，而不是斷言上雲一定違法。

### 「LLM 不直接控制機器人」安全範式 — 學術/業界背書 + PawAI 定位
- **Q：你們這套是自己發明的嗎?有什麼學術依據?**
  - A：不是我們發明的,我們是『實作』一個業界已公認的範式。SayCan(Google 2022)確立 LLM 當高階提議者、affordance value function 把關;Code as Policies 確立 LLM 只能組合預定義 API;RoboGuard 與 arXiv 2602.04056 確立安全要由獨立於 LLM 的外部 gate 強制執行。PawAI 三層架構是把這些原則落到一台居家四足 POC 上,我們的貢獻是整合與誠實量測,不是理論創新。
- **Q：危險動作拒絕是 LLM 在判斷安不安全嗎?萬一 LLM 判斷錯怎麼辦?**
  - A：不是,我們刻意不讓 LLM 判斷安全。是 deterministic 的 rule-based 關鍵字比對:safety_layer.py 裡寫死翻跟斗/backflip/倒立/handstand 等關鍵字,命中就直接回『這個動作不安全,我不能執行』。而且危險動作的 api_id 放在 BANNED_API_IDS(1030/1031/1301),就算被觸發,validate() 也會把整個 plan 原子拒絕。這對應學術上講的『安全與 planner 解耦』——不能把安全交給可能被 jailbreak 的模型。
- **Q：那 backflip 你們到底會不會做?是不是吹牛?**
  - A：誠實說:backflip 是 demo-only 的假動作,Go2 sport mode 本來就沒這能力,我們也沒做。它在系統裡存在的唯一目的,是當『被請求危險動作 → 系統主動拒絕』的反例 demo——讓觀眾看到安全 gate 真的會擋下來(BLOCKED_BY_SAFETY 視覺化),而不是真要表演翻跟斗。
- **Q：你們跟 RT-2 那種真正會動的機器人比,差在哪?**
  - A：差很多,方向也不同。RT-2 是端到端 VLA,把動作當 token 直接輸出,是研究等級致動系統。PawAI 走相反的分層路線——LLM 不直接致動,只從有界 skill 選。我們誠實的差異化不是『更會動』,而是整合深度(五感知+Brain+Studio 串成一條線)、量化誠實層(每項能力 pass/fail/insufficient_data 都量過)、把安全做成可稽核的 deterministic gate。現況 readiness=not_ready,只有 3 項窄版能力 pass。
- **Q：fail-closed 是什麼意思?對使用者有什麼好處?**
  - A：fail-closed 就是『不確定時就不動』。如果某能力的健康度是 fail、unknown 或資料不足(insufficient_data),系統會把所有 motion 與 nav 類動作 block 掉,預設往安全那邊倒。對照組是 fail-open(壞掉還照動)。我們程式碼 effective_status.py 明寫 unknown/missing grade 一律當 insufficient_data 處理並 block。學理上對應 arXiv 2602.04056 講的『致動器前最後一道防線』。
- **Q：你們有真的自主導航、跟隨、避障、跌倒偵測嗎?**
  - A：誠實說:沒有真實自走、沒有跟隨、沒有巡邏、沒有動態繞障,跌倒偵測也是關閉的(enable_fallen=false)。6/04 baseline 裡所有 nav 能力都是 insufficient_data;我們做過一次 supervised live dry-run,Go2 在 AMCL gate 就被擋下、零 motion——這只證明 action chain 有接好且 fail-closed,不是導航能力。守望那 30% 目前是『提醒/回報/非接觸』定位的雛形,所以整體 readiness 標記為 not_ready。
- **Q：你說 RoboGuard 把危險率從 92% 壓到 3%,那 PawAI 也有這個數字嗎?**
  - A：沒有,那是 RoboGuard 論文在特定 jailbreak 攻擊(non-adaptive RoboPAIR)下量的結果(精確是 92.3%→2.3%),我引用它只是佐證『獨立外部 gate』這個範式有效,不是 PawAI 的實測數字。PawAI 的安全 gate 是輕量工程實作(關鍵字 + banned api_id + fail-closed 能力 gate),不具備 RoboGuard 那種 LTL 形式化驗證等級的保證,定位上是『同一範式的精簡學生實作』。
- **Q：你引用的那幾篇論文是真的嗎?編號看起來很新。**
  - A：都是真的、可查證。SayCan(2204.01691, 2022)、Code as Policies(ICRA 2023)、Inner Monologue(2207.05608, 2022)、RoboGuard(2503.07885)都是已發表的。兩篇最新的:Trust in LLM-controlled Robotics survey(2601.02377)是 2025/12 投稿、Modular Safety Guardrails(2602.04056)是 2026/02 投稿,屬很新的預印本(非同儕審查),簡報時我會標『2026 近期 position paper/survey』並附存取日期。

### 可比較專案光譜中的誠實定位：PawAI 作為學生 POC，差異化在「整合深度 + 量化誠實層 + 安全 gate」而非性能領先
- **Q：你們跟 Boston Dynamics Spot + ChatGPT 比差在哪？是不是抄的？**
  - A：成熟度同格——Spot+ChatGPT 是 BD 官方逐字說的 proof of concept、出自內部 hackathon，有幻覺、6 秒延遲、斷網就掛。差別是他們底層 Spot 是頂級商用平台、團隊世界級。我們不是抄、也不宣稱性能贏：差異是把 Go2+感測器到 Brain 三層決策全自串、且公開了每項能力 6/04 的 pass/fail 量化證據，那篇 demo 沒公開失敗邊界。
- **Q：Unitree Go2 出廠就會聊天、會自走、會跟隨，那你們做了什麼？**
  - A：對，原廠 Go2 Pro 規格頁有 GPT 語音、L2 LiDAR 自走、側隨 2.0。但要誠實兩件事：一是第三方實測那 GPT 語音『簡單指令約 80% 可用、複雜要改用 App』、自走/跟隨多是規格頁宣稱；二是我們自己在 Go2 內建 LiDAR 實測過頻率太低(~2Hz)不可用。我們刻意不用那黑盒，自己串一套可解釋、可量測、有 deterministic 安全 gate 的互動堆疊。我們沒超越原廠性能，價值在整合深度與誠實量化。
- **Q：既然 ElliQ、PARO 都已是成熟產品甚至進 Medicaid / FDA，你們的意義在哪？**
  - A：它們證明陪伴在商業與法規上可行——但要精準：ElliQ 是 2026/3 才成全美首例進 Medicaid、而且只在華盛頓州，且是靜態桌面裝置；PARO 是 2009 FDA Class II 生物回饋裝置，臨床多是小樣本可行性研究、不等於證實療效。我們不跟它們比成熟度——我們是學生 POC，絕不宣稱照護/療效那種要臨床與法規背書的能力。我們的範圍誠實收斂在實體四足的互動表達。
- **Q：你們的安全機制是 rule-based 關鍵字比對，這不是很原始嗎？為什麼不用 LLM 判斷危險？**
  - A：這是刻意且符合研究方向的選擇。arXiv 2410.13691 對『跟我們同款的 Unitree Go2』首次成功 jailbreak、常達 100% 攻擊成功率；多篇近期研究指向單靠 LLM 判斷不足、需要 LLM 之外的安全層。我們用 deterministic 規則對停止/緊急硬短路繞過 LLM，就是這精神的輕量落地。我要誠實補兩句：那篇 RoboGuard 論文自己用的是更複雜的『受保護 LLM+時序邏輯』不是關鍵字法，所以我不會說『學術界證明關鍵字是對的』；而且我們的安全層目前是 code+約 91 個 pure-Python 單測層級，端到端實機 e2e 這一輪還沒量。
- **Q：Glasgow RoboGuide 也是大學的四足 + LLM，他們能避障導航帶盲人逛博物館，你們能嗎？**
  - A：不能，這是我們最該誠實的地方。RoboGuide 2023/12 在 Hunterian 博物館已有真實室內避障導航帶人逛展品的 demo，我們目前零真實自走、無動態繞障。我們跟它同屬大學研究原型級距，但他們的自走比我們前面。我們現階段強在量化誠實與安全 gate，不在導航。
- **Q：你們宣稱的『守望』跟守護差在哪？是不是在玩文字遊戲？**
  - A：是嚴格的範圍紀律不是文字遊戲。守護/照護/防跌/陌生人警報會暗示可靠的安全承諾，但我們 voice.stop 6/04 量到 0.667 是 fail、跌倒偵測 demo 根本硬鎖沒開(enable_fallen:=false)、nav 零自走。用守望/提醒/回報是把宣稱壓到實際能做到的窄版邊界內，避免 over-claim 釀成安全誤信——這正是 RoboPAIR 那類研究警示的風險。
- **Q：你們的 backflip 後空翻很厲害，是你們訓練的嗎？**
  - A：不是，那是 demo-only 的表演橋段。Go2 sport mode 本來就沒有後空翻能力，我們也沒做全身 RL 訓練。這不該被當成我們的技術成果。
- **Q：你們三項 pass 聽起來很少，這專案是不是沒做出什麼？**
  - A：3 項窄版 pass(認註冊者 Roy n=9 registered_recall=1.0、~1m 杯子 conf 0.83-0.88、指令分類 0.875)+2 項誠實標 fail+其餘資料不足、readiness=not_ready。數字看起來保守，但這正是重點：CognitiveDog 報 64.79%、市面很多 demo 只挑成功演，我們公開了完整 pass/fail/insufficient 證據鏈與失敗邊界。在『誠實度即可信度』標準下，敢標 not_ready 本身就是工程成熟度。
- **Q：你們說安全層有 91 個測試通過，那是哪 91 個？是不是湊數的？**
  - A：誠實講，91 是『安全相關 pure-Python 單測』的量級，不是某個檔案剛好 91 條。核心安全檔——pawai_brain 的 skill_policy_gate 有 28 條、interaction_executive 的 brain_rules 有 54 條、另有專門的 test_safety_layer 23 條，相關安全測試加起來就是這個量級。重點是這些是 code+單測層級的證據，不代表端到端實機驗證過——brain.skill_gate/trace 這輪是 insufficient_data，我們不會說它端到端 pass。

### 誠實量化 / eval 文化作為可信度差異化：機器人學習可重現性危機與 overclaiming 文獻，論證 PawAI「preflight→observer→JSONL→scoreboard→readiness、會就說會、fail 標 fail、not_ready 照實呈現」量化誠實層為加分項，並把 voice.stop / gesture.wave 兩項真實 fail 框成可信度工程
- **Q：你們很多項目標 fail 或 insufficient_data，這不是代表做得不好嗎？**
  - A：在機器人學習領域，掩蓋 fail 才是被批判的對象。Henderson（AAAI 2018）與 Trustworthy Evaluation（arXiv 2601.18723）都指出把 failure case 攤開、用固定協議量化是『恢復信任』的做法。我們 6/04 量到 3 項窄版 pass（face 認註冊者 Roy / object.cup ~1m / voice.command 0.875）、2 項 fail（voice.stop / gesture.wave）、其餘 insufficient_data，readiness=not_ready——這是一份誠實的能力快照，不是把 demo 一次成功包裝成『全都會』。對比『sim 95% 真機常剩 30-60%』的常見落差，我們寧可如實標真機結果。
- **Q：別的團隊 demo 看起來什麼都會，你們為什麼只敢宣稱這麼窄？**
  - A：因為『單一設定的成功被當成通用能力』正是最新文獻點名的過度宣稱（arXiv 2606.04233：benchmark score is a proxy, not an end）。我們的 face 只敢說『認得註冊者 Roy』、object 只敢說『cup 在約 1 公尺』、voice.command 只敢說『成功率 0.875』，因為那是我們真正量到的範圍。窄而真比寬而虛更有可信度——這在學術上是加分。
- **Q：這個量化誠實層（preflight→observer→JSONL→scoreboard→readiness）有什麼學術或工程價值？**
  - A：它是 robotics reproducibility checklist 與 model card 的精神對齊（不敢自稱已達其統計嚴謹度，我們樣本小、門檻自訂）。NeurIPS（Pineau 等）要求報告執行次數、指標、限制；model card（Mitchell 等, FAccT 2019）要求記載用途、效能與限制。我們的 pipeline 把每項能力的固定協議＋逐輪原始 JSONL ＋readiness 判定自動化，等於每次 demo 都產出一份可重跑、可被別人用同條件檢驗的能力報告，而不是靠記憶吹牛。
- **Q：voice.stop 和 gesture.wave fail，你們打算怎麼辦？這不影響安全嗎？**
  - A：我們明確標 fail 並寫進 readiness，正是為了不讓人誤以為這些能力可靠。要誠實澄清守望輔助的真實邊界：危險動作拒絕是 rule-based 關鍵字比對、不是 LLM 判斷；backflip 是 demo-only 假動作（Go2 sport mode 本就沒這能力）；nav 零真實自走、無跟隨、無巡邏、無動態繞障、無跌倒偵測（enable_fallen:=false）。把限制講清楚，比含糊宣稱『有機制』更負責任——這是可信度工程，不是免責。
- **Q：你們的 readiness 判定（pass/degraded/fail gate）會不會只是自己定的、沒有公信力？**
  - A：判定門檻確實是我們自訂的，這是這層的已知限制（就像 model card 的有效性依賴製作者誠信）。價值不在門檻權威，而在協議固定、可重跑、原始 JSONL 留證——任何人都能用同一條件重測、檢驗我們的數字。Lynnerup 等（PMLR v100）也強調真機評測重點是『選對指標＋正確統計做無偏報告』；我們做到的是『可被檢驗』，而非要求別人盲信分數。
- **Q：這個專案到底跟別人比強在哪？只是個學生 POC 吧？**
  - A：我們不宣稱模型最強，定位就是互動 70%/守望 30% 的學生 POC。誠實能講的差異化有三點：整合深度（多模態感知＋三層決策＋真機 Go2/Jetson 串起來能跑）、量化誠實層（自建 preflight→scoreboard→readiness，把能力攤成可重跑報告）、安全 gate（明確的規則化拒絕與真機限制揭露）。在具身 AI 連統一評測標準都還沒收斂的當下（arXiv 2509.15273 才剛整合 22 benchmark），一個 POC 願意做到『會就說會、fail 標 fail』，可信度本身就是貢獻。
- **Q：你投影片寫 NeurIPS 導入後可重現素材 50%→75%+，這數字準嗎？**
  - A：需要修正：原文（Pineau et al., JMLR 2021）說的是『主動提交程式碼的作者比例』從一年前 <50% 升到 nearly 75%，是 code submission，不是『論文可重現素材比例』，也不是『75%+』。而且自報的 code availability(38.76%) 經至少一位 reviewer 查核後降到 27.70%。所以正確講法是：NeurIPS 用 checklist + code policy 把報告紀律制度化，提交程式碼的作者比例由 <50% 升到約 75%。