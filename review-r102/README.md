# R102 审稿修订包：迁移矩阵 v2、M2 统计、M3 执行掩护测量

本目录针对 S&P 2027 修订稿审稿意见中的 M1–M5，给出可以直接放进论文的结果，以及配套的可复现代码。`releases/r101/` 下的任何文件都没有修改；`python releases/r101/evidence/verify_evidence.py` 仍能通过。

| 审稿问题 | 本包给出的内容 | 文件 |
|---|---|---|
| M1 迁移矩阵太单薄（6 行） | 扩充为 19 行，关系中新增 **Violated** 和 **New**，每行绑定 evidence-matrix 里的 setting ID | `transfer-matrix/transfer-matrix-v2.csv`、`latex/transfer-matrix-v2.tex` |
| M2 分母太小（4 个设置） | 对全部 44 个设置做确定性规则统计，规则见脚本 | `m2_statistics.py`、`m2-results/`、`latex/m2-availability.tex` |
| M3 缺少新测量 | 执行掩护回放实验：同一批运行上同时测隐私、任务结果和状态 | `m3-executed-cover/`、`latex/m3-*.tex` |
| M4 实验与部署图矛盾 | 写作修改，见下文第 4 节 | — |
| M5 独立编码 | 提供编码底稿；需要一位真人第二编码者，见第 5 节 | `m2-results/m2-setting-indicators.csv` |

复现命令（在仓库根目录执行，CPU 即可，约 15 分钟）：

```
pip install numpy scikit-learn
python review-r102/m2_statistics.py
cd review-r102/m3-executed-cover && python run_replay.py && python k_sweep.py
```

---

## 1. 迁移矩阵 v2（M1）

19 条关系的分布：Retained 9 条（其中 2 条程度被放大，1 条在 Agent 场景下尚未测试）、Extended 5 条、**Violated 3 条**、New 1 条、Untested 1 条。

| ID | 失效的经典假设 | 反例 |
|---|---|---|
| A1 | 只有一个在路径观察者，只看一条链路 | 任务信息分别在工具链路 T（WRA）、模型链路 M（CB、ANT）和接收方（PrivacyTrace）被恢复。**9 个防御设置中没有一个作用在模型链路 M 上** |
| E1 | 掩护流量在端点丢弃，不产生业务功能 | WRA 的诱饵确实执行了额外研究工作。本包回放中，在真实数据上执行写入的掩护，状态完整率只有 3.2–11.2%；而它的传输层隐私与"代理处丢弃"的掩护完全相同 |
| E2 | 掩护流量与真实流量不可区分 | 本包回放中，固定位置的单个诱饵：冻结攻击者降到 .37–.63，但位置规则或重训攻击者都能恢复到 BA 1.00 |

**正文建议的写法：** 两个核心发现改写为"经典假设在 Agent 中失效的位置"。A1 对应反馈路径，E1 和 E2 对应被执行的掩护。摘要中的 "These extend established evaluation principles" 删除。

## 2. M2 统计（44 个设置，全部来自作者已发布的 evidence 文件）

| 问题 | 结果 |
|---|---|
| 有任何防御比较 | 9/44 个设置（5/15 篇来源） |
| **防御作用在模型链路 M 上** | **0/5** |
| 防御作用在客户端链路 C 上 | 0/2 |
| 有命名的留出部署轴 | 4/44（3 篇来源） |
| 做了开放世界测试 | 2/44 |
| 给出部署场景下的基率 | 0/44 |
| 任务边界由评估者直接提供 | 43/44 |
| 完整报告执行结果 | 13/38 |
| 完整报告失败处理 | 19/42 |
| 9 个防御设置中：定位到自适应攻击 | 4/9 |
| 9 个防御设置中：匹配的原任务效用 | 1/9 |
| 9 个防御设置中：同一设置内的防御成本 | 2/9 |
| **9 个防御设置中：以上三项同时具备** | **0/9** |

每条指标都由 `m2_statistics.py` 中 `RULES` 定义的规则从发布的 CSV 机械地算出，没有重新阅读论文。

**建议加入正文的第三个发现：**
> "The literature is almost entirely attack-side (35/44 settings). No setting protects the model link where tool feedback lands, and no protection setting reports adaptation, original-task utility and cost together."

## 3. M3：执行掩护回放（填补 E1、E2、E4 的空白）

### 设计

| 项 | 设定 |
|---|---|
| 工作负载 | 采用论文 §7 的 6 类工单动作，每个任务带 1–3 项前置检查。每类业务动作由一个独立服务承担：payments、billing、crm、helpdesk、shipping、orders |
| 规划器 | 参考程序（oracle），从而把掩护对状态和效用的影响与 LLM 的随机性分开 |
| 线上观测 | 每次调用都走一条真实的 TLS 1.3 连接（Python ssl + MemoryBIO）。观察者看到目标服务（SNI）和密文字节数，不观测时序 |
| 填充 | 论文的策略：请求体按 4,096 字节、响应体按 16,384 字节填充；另做一组不填充的敏感性分析 |
| 五个臂 | 无掩护；传输层终止（代理处丢弃）；只读掩护；隔离执行（在克隆状态上执行）；真实写入 |
| 掩护调度 | 固定在真实动作之后；固定在真实动作之前；随机 1–2 个；另做随机 k = 1–4 的扫描 |
| 攻击者 | D0（只用无掩护数据训练）；D2（在该臂受保护数据上重训的 LR 和 RF）；位置规则 |
| 规模 | 600 个任务（每类 100 个）× 2 个种子；按任务 50/50 划分；以任务为单位做 bootstrap |
| 同一批运行上的测量 | 平衡准确率 BA；目标是否达成；完整状态是否与参考一致；额外调用数；字节比 |

### 结果（论文填充策略；完整表见 `latex/m3-executed-cover.tex`、`latex/m3-cover-sweep.tex`）

| 臂 | 调度 | 冻结攻击者 BA | 最强攻击者 BA | 目标达成 | 状态完整 | 字节比 |
|---|---|---|---|---|---|---|
| 无掩护 | — | 1.00 | 1.00 | 100% | 100% | 1.00 |
| 传输层终止 | 固定在之后 / 之前 | .63 / .37 | **1.00 / 1.00** | 100% | 100% | 1.25 |
| 传输层终止 | 随机 1–2 个 | .38 | .68 | 100% | 100% | 1.37 |
| 只读掩护 | 随机 1–2 个 | .39 | **.79** | 100% | 100% | 1.37 |
| 隔离执行 | 随机 1–2 个 | .38 | .68 | 100% | 100% | 1.37 |
| 真实写入 | 固定在之前 | .37 | 1.00 | **87.2%** | **7.0%** | 1.25 |
| 真实写入 | 随机 1–2 个 | .38 | .68 | **87.8%** | **3.2%** | 1.37 |

随机 k 扫描（论文填充策略）：

| 诱饵数 k | 最强攻击者 BA | 字节比 | 真实写入：目标达成 / 状态完整 |
|---|---|---|---|
| 1 | .76 | 1.25 | 91.2% / 6.4% |
| 2 | .61 | 1.49 | 84.8% / 0.6% |
| 3 | .52 | 1.74 | 79.5% / 0.0% |
| 4 | .44 | 1.99 | 75.2% / 0.0% |

传输层终止的掩护在所有 k 下都保持 100% 的目标达成和状态完整，机会水平为 .167。

### 四条结论

1. **执行写入没有带来任何额外的传输层隐私**（E1、E4）。在每一种调度和 k 下，传输层终止、隔离执行和真实写入三个臂的攻击者 BA 完全相同，但只有真实写入破坏了状态。所以对传输观察者来说，执行掩护只有代价、没有收益。只有当观察者是工具接收方本身时，才有理由执行掩护，而这时就需要隔离。
2. **固定数量或固定位置的掩护可以被计数**（E2）。冻结攻击者看起来下降到 .37–.63，但重训攻击者或位置规则恢复到 1.00。这也是 D1（自适应攻击）的又一个实例。
3. **随机掩护有一条可量化的隐私-成本曲线。** k = 1 到 4 时，BA 从 .76 降到 .44，字节从 1.25 倍升到 1.99 倍。即使 k = 4，BA 也仍是机会水平 .167 的 2.6 倍。
4. **只填充消息体不够**（D3）。只读掩护的 HTTP 请求路径不在填充范围内，重训的 RF 由此把 BA 从 .68 提高到 .79。

### 局限（必须写进正文）

- 规划器是参考程序，所以没有测量规划器看到诱饵响应后的行为变化。
- 业务动作与服务一一对应，这是一个设计假设；它对应的是 WRA 的"目的地关联"这类信道。
- 不观测时序。
- 工作负载是合成的。

能弥补这些局限的唯一后续实验，是在作者已有的 Qwen3:8B / Llama3.1:8B 和 LangGraph 基础设施上，用同样的五个臂跑真实 LLM 规划器（见第 5 节）。

### 可直接粘贴的 §5.3（英文）

> **Measuring the executed-cover boundary.** We replay the six support-ticket actions of Section 7 (600 tasks, two seeds) with one service per business action, real TLS 1.3 connections and the paper's body padding. The observer sees destinations and ciphertext bytes. Five arms share fixtures and decoy draws: no cover, cover terminated at an egress proxy, read-only cover, decoy execution on a cloned state and decoy execution on the live state. Privacy, task outcome and state are measured on the same runs (Table~\ref{tab:m3-cover}). A single decoy at a fixed position lowers a frozen attacker to .37–.63 balanced accuracy, but a refit attacker or a position rule recovers 1.00. Under random placement, the best attacker falls from .76 to .44 as the decoy count grows from one to four, at 1.25–1.99× bytes (Table~\ref{tab:m3-sweep}). Inference is identical for proxy-terminated, isolated and live-write cover, yet live writes preserve the reference state in only 0–11.2% of runs; goal success falls to 87.2% when the decoy precedes the real action and to 75.2–91.2% under random placement. Against a transit observer, executing cover therefore adds state risk without adding privacy. Unpadded request paths let a refit forest separate read-only cover (.79 versus .68). The planner is a reference program, so planner reaction to decoy feedback is outside this measurement.

## 4. 其余问题的修改方法

| 问题 | 能否改 | 做法 |
|---|---|---|
| M1 矩阵 | ✅ 已给出 | 用 `latex/transfer-matrix-v2.tex` 替换表 2；§4.1 的四类关系定义改为加入 Violated 和 New 后的版本 |
| M2 统计 | ✅ 已给出 | 用 `latex/m2-availability.tex` 替换表 9；§8 首段引用 "0/5 M-link" 和 "0/9 all three" |
| M3 测量 | ✅ 已给出回放结果；⚠️ LLM 规划器版本需要作者运行 | 新增 §5.3，加入两张表 |
| M4 本地模型与表 1 矛盾 | ✅ 纯写作修改 | §7.1 开头补一句："The local TLS gateway stands in for the *cloud model, remote tools* row of Table 1 with an egress vantage on M; it is not the *local model* row." 同时把 §7 压缩到约 1 页，结果表移到补充材料 |
| M5 独立编码 | ⚠️ 需要真人参与 | 请一位不参与写作的同行，只看 `evidence-matrix.csv` 中的 locator，独立填写 `m2-setting-indicators.csv` 里的 9 个指标列和 19 行矩阵的 relation 列，然后报告 Cohen's κ。AI 编码不能算作独立的人工编码 |
| 摘要和贡献 | ✅ | 写入三个数字：3 条 Violated；M 链路防御 0/5、三项齐全 0/9；回放中执行写入不增加隐私、状态完整 ≤ 11.2% |
| §2.3 相关综述 | ✅ | 把补充材料 S7 的综述对比表恢复为正文中三行的精简版 |
| 可读性 | ✅ | 每节开头加一个 Takeaway 框；删除 "Each check supports its matched premise" 一类的元叙述 |
| "Compilable LaTeX…" 句 | ✅ | 删除 |

## 5. 仍需作者完成的两件事

1. **LLM 规划器版本的 M3。** 用 §7 已有的 Qwen3:8B / Llama3.1:8B、LangGraph 和 MCP 环境，跑同样的五个臂，每臂 120 个测试任务。另加一个"诱饵响应对规划器可见"的臂，用来测规划器的反应。这台审稿机器没有 GPU，8B 模型在 CPU 上做不到这个规模，所以没有在这里运行。
2. **独立编码 κ**：见第 4 节。
