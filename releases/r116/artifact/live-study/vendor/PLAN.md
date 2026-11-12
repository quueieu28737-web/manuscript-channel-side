# 真实环境时序匹配实验（L 实验）方案

本方案要在本地重新采集一批执行数据，测量 S11 里只做了反事实模拟的东西：真实运行的时序匹配派发，以及 S11 结尾提出的"让规划器自己生成 cover"这一设计。它沿用 M3 的 fixture、工具、传输和规划器，只改 cover 的派发方式和计时层。

> 下文"M3"指 `review-r102/llm-extension` 的采集代码，`collect.py` 的行号以该版本为准。论文正文不使用这些内部代号。

---

## 0. 要回答的三个问题

| # | 问题 | 现有证据 | L 实验给出的答案 |
|---|---|---|---|
| Q1 | 在 TLS record 级时间戳下，未匹配 cover 还会被无标签规则剥离吗？ | 只有 client receipt（loopback，含 asyncio 调度） | 用 relay 记录的 record 时间戳和抓包复测 |
| Q2 | 真实运行的时序匹配派发，与反事实模拟结果一致吗？ | 只在 receipt 上做了平移模拟（S10/S11） | 真实 sleep 加服务端 hold，攻击者重新训练 |
| Q3 | 让规划器自己生成 cover（影子 episode），能否让诱饵不可区分？ | 未测（S11 的 Limits 段） | 等价检验：自适应最佳与仅看大小最佳的差在 ±12/120 以内 |

额外记录的代价有：延迟（真实任务的完成时间）、额外的模型 token 和调用次数、字节数。

---

## 1. 保持不变的部分

- **模型与选项**：Qwen3:8B、Llama3.1:8B，使用 `verification/weights-before.json` 中固定的权重；`temperature=0`，`num_ctx=4096`，`num_predict=96`，每个 fixture 一个 seed，`max_model_steps=10`。
- **Fixture 与划分**：沿用 `cohort-plan.json` 的 300 个 unit（120 训练 / 60 验证 / 120 测试），任务 ID、动作标签、检查项和订单都不变，测试集与 M3 是同一批 fixture。
- **传输**：七个 loopback MCP Streamable HTTP 服务，真实 TLS 1.3 / HTTP/2，请求按 4,096 字节、响应按 16,384 字节填充，共用 `/mcp` 路径，每个 episode 开始时初始化七个会话并在 episode 内复用。
- **cover 语义**：所有 cover 臂都用 **hidden isolated**，即在克隆状态上执行，响应不进入规划器。语义问题 M3 已经回答过，这里只研究时序，避免语义与时序混在一起。
- **unknown policy 与日志**：请求在派发前写入日志；没有终态的请求一律视为 unknown，不重放，并中止采集以便审计（与 M3 相同）。

## 2. 实验臂

每个模型 5 个臂，每臂 300 个 fixture，共 **3,000 个 episode**。其中影子臂的模型调用约为普通臂的两倍。

| 臂 ID | 名称 | 派发方式 | 规划器是否被阻塞 |
|---|---|---|---|
| `none` | 无 cover | — | — |
| `unmatched` | 未匹配 | 与 M3 isolated 臂相同：工具响应返回后立即派发 | 是（毫秒级） |
| `gdm_live` | 顺序时序匹配 | 先等待从历史池抽取的间隔，再调用；服务端把响应 hold 到抽取的时长 | 是（加上抽取的间隔和时长） |
| `concurrent` | 并发时序匹配 | 与规划器推理**并行**：触发后等待抽取的间隔再派发，服务端 hold 时长 | 否 |
| `shadow` | 影子 episode | 网关用同一模型在一张诱饵工单上并行运行一整个 episode，作为 cover | 否（但两路推理共享 GPU） |

### 2.1 历史池（gdm_live 与 concurrent 使用）

- **来源**：本实验 `none` 臂**训练集**中诚实调用的数据，不用 M3 的旧数据，以保证计时层一致。
  - 间隔池：非首个调用的 gap；
  - 时长池：按目的地分开的 duration；某个目的地样本数少于 20 时，回退到全体样本。
- **度量层**：使用 relay 的 **record 级时间戳**（见 §4），因为这是攻击者能看到的那一层。
- **冻结**：先采集 `none` 臂；用冻结的脚本提取历史池，计算哈希并提交到 git，**之后**才开始采集任何 cover 臂（见 §5 第 2–3 步）。

### 2.2 影子臂的诱饵工单

- **抽取方式**：对每个真实 fixture，从**全部 6 种动作中均匀抽取**诱饵动作，与真实标签独立，可以和真实动作相同。若排除真实动作，排除本身就会泄露信息。诱饵工单用该动作重新生成 fixture，生成器沿用 `inputs/workload.py`，seed 为 `seed+500000`。
- **起始顺序**：以 0.5 的概率让影子 episode 先开始。具体做法是网关把真实 `get_ticket` 的转发推迟 U(0.2, 1.5) 秒，在此期间先发出影子 `get_ticket`；否则影子 episode 在真实 `get_ticket` 返回后 U(0.2, 1.5) 秒开始。这样攻击者无法用"先出现的链就是真实任务"来判断。
- **结束方式**：影子 episode 一直运行到它自己的 `finish`、步数上限或无效输出为止。观察窗口是两条链的并集。真实任务的延迟只按真实链计算。
- **隔离**：影子 episode 的所有工具调用都在它自己的克隆状态上执行，消息不进入真实规划器。两条链复用同一组七个 MCP 会话，与真实网关共享连接的情形一致。

---

## 3. 代码改动（基于 M3 `collect.py`）

在新工作目录中复制 `experiment/`、`inputs/`、`requirements.txt` 和 `verification/weights-before.json` 后修改，`OUT` 目录指向新的 run 名。以下是关键改动的示意。

### 3.1 Record 级时间戳（`Wire.observe`，约第 57 行）

```python
def observe(self, side, b):
    t = time.perf_counter_ns()          # 单调时钟，用于时长
    self.counts[side] += len(b); self.chunks[side] += 1
    self.buffers[side].extend(b); buf = self.buffers[side]
    while len(buf) >= 5:
        n = int.from_bytes(buf[3:5], 'big')
        assert n <= 18432, 'unexpected TLS record length'
        if len(buf) < n + 5: break
        # 记录最后一个字节到达时的时间（record 完整时刻）
        self.records[side].append([buf[0], n + 5, t]); del buf[:n + 5]
```

在 `main()` 启动时保存一次 `{'perf_counter_ns': ..., 'time_ns': ...}` 锚点，供与抓包对齐。

### 3.2 每个调用的 record 区间（`tool_call`，约第 159 行）

`before` / `after` 快照里已经有 `records` 计数。在 `terminal` 中增加：

```python
'record_index': {'before': before['records'], 'after': after['records']}
```

分析时，用该区间内上行第一个 application-data record（类型 23）的时间作为调用开始，用下行最后一个的时间作为调用结束。这样攻击者的计时**只来自 relay 观测到的 record**，与 client receipt 无关。

### 3.3 服务端 hold（`server()` 的 `execute`，约第 111 行）

```python
async def execute(job_id, request_id, operation, order_id):
    t0 = time.perf_counter()
    ...  # 原有逻辑
    hold = REQUESTS[request_id].get('hold_s')
    if hold:                                   # 只有 gdm_live / concurrent 的 cover 设置
        await asyncio.sleep(max(hold - (time.perf_counter() - t0), 0))
    return obj
```

hold 放在服务端，使响应 record 的时间真正被推迟，而不是只在客户端等待。

### 3.4 `gdm_live`：顺序匹配（修改 `covers()`，约第 234 行）

```python
if arm == 'gdm_live':
    g = float(rng.choice(POOL['gap']))
    elapsed = time.perf_counter() - st['last_call_end']   # 在 tool_call 结束时更新
    await asyncio.sleep(max(g - elapsed, 0))
    hold = float(rng.choice(POOL['dur'].get(destination(op), POOL['dur']['__all__'])))
    response = await tool_call(..., kind='cover', hold_s=hold)
```

`rng` 为 `np.random.default_rng([PLAN_L.seed, fixture_seed, decoy_index])`。用 `(fixture, decoy)` 作 seed，使同一 fixture 在不同模型间的抽样相同。

### 3.5 `concurrent`：并发派发（注意 AnyIO 作用域）

M3 的注释写明 MCP 会话不能在 LangGraph 节点的子任务里使用。因此在 `episode()` 的作用域内启动一个**常驻 dispatcher**，`covers()` 只负责把任务放进队列：

```python
queue = asyncio.Queue()
async def dispatcher():
    while (item := await queue.get()) is not None:
        decoy, t_trigger = item
        g = float(rng.choice(POOL['gap']))
        await asyncio.sleep(max(g - (time.perf_counter() - t_trigger), 0))
        hold = ...  # 同 3.4
        await tool_call(st, jid, tc, decoy['action'], decoy['order_id'], 'cover', out, hold_s=hold)
dispatch_task = asyncio.create_task(dispatcher())   # 在 ToolConnections 的 async with 内
...
# covers(): 不 await 调用，只入队
queue.put_nowait((decoy, time.perf_counter()))
...
# 规划器结束后：
await queue.put(None); await dispatch_task          # 所有 cover 完成后才关闭会话
```

并发调用共享 HTTP/2 连接。需要在 readiness 阶段确认 MCP SDK 1.21.1 支持同一会话上的并发 `call_tool`；若不支持，就为 cover 单独开一组会话，并在方案冻结前写明选择。

### 3.6 `shadow`：影子 episode

- 把 `episode()` 中的规划器部分（`planner` / `perform` / `StateGraph`）抽成 `run_chain(state, messages, kind)`。
- 真实链用 `kind='honest'`，影子链用 `kind='cover'` 和独立的 `st_shadow = make_state(decoy_unit, 'isolated')`。
- 两条链在同一个 `ToolConnections` 作用域里用 `asyncio.gather` 运行。影子链的工具调用 `kind='cover'`，写入 `st_shadow`，不改动真实状态。
- 按 §2.2 实现起始偏移：在 `tool_call` 增加 `delay_before_s` 参数，只用于真实 `get_ticket`。
- `result.json` 增加 `shadow_unit`、`shadow_model_usage`、`shadow_status`，并分别记录真实链的结束时间 `real_end` 和影子链的结束时间。

### 3.7 并发与 worker

- `workers = 1`：每次只运行一个 episode，避免两个 episode 争用 GPU 而污染时序（M3 用的是 2）。
- Ollama 保持 `OLLAMA_NUM_PARALLEL=2`，否则影子臂的两条链会被串行化。
- 臂的顺序按 fixture 轮转，与 M3 的 `arm_order` 相同。
- 记录 GPU 型号、驱动和 Ollama 版本，并在采集前后检查权重哈希。

---

## 4. 观测层

| 层 | 来源 | 用途 |
|---|---|---|
| L1 client receipt | `tool_call` 的 `start` / `end`（与 M3 相同） | 只用于和 M3 对照 |
| **L2 relay record** | §3.1 的 record 时间戳 | **主分析：攻击者的计时来源** |
| L3 抓包 | Windows：Npcap 并开启 loopback 适配器，用 `dumpcap -i \Device\NPF_Loopback -f "tcp portrange 40120-40126"`；Linux：`tcpdump -i lo` | 独立校验 L2，报告每个 record 的 \|L2−L3\| 的中位数和 99 分位 |

**攻击者的特权与 M3 / S11 相同**：看得到目的地、双向密文字节数和 L2 计时；episode 窗口和调用窗口由评测方提供；第一个 ticket 调用已知为诚实调用；训练集里的调用带 cover 标签。

**次要变体（探索性）**：不提供调用窗口，攻击者按 record 间隔自行切分调用，以检验结论是否依赖窗口特权。

**原始抓包不公开**。只公开从中导出、不含 payload 的逐 record 计时 CSV。

---

## 5. 采集流程

1. **Readiness**：用 `development_units`（6 个）跑遍所有臂，确认 §3.5 的并发调用可行、影子臂能正常结束，且 L2 与 L3 能对齐。readiness 结果不计入任何分母。
2. **冻结方案**：把 `analysis-plan-draft.json` 定稿为 `analysis-plan.json`，连同 `collect.py` 和分析脚本的哈希提交并**推送到 git**，然后才开始正式采集。
3. **阶段 A：采集 `none` 臂**（两个模型的全部划分）。用冻结的脚本 `extract_pools.py` 从 `none` 训练集提取间隔池和时长池（L2 层），写入 `pools.json`，提交并推送。
4. **阶段 B：采集四个 cover 臂**，按 fixture 轮转顺序。
5. **校验**：运行 `verify_collection.py`（需扩展到新增字段）、`verify_weights_after.py` 和 L2–L3 对齐检查。
6. **导出**：用与 `data/episodes.jsonl.gz` 相同的 schema 导出，增加 record 时间戳、`hold_s`、`shadow_*` 字段和 L3 导出的 CSV。

任何 unknown 请求都会中止采集。不要删除锁文件后重跑。

---

## 6. 攻击套件

所有攻击都在每个臂**各自**的训练集上重新拟合，在验证集上选择，与 S11 的规则相同。

| 类别 | 攻击 |
|---|---|
| 仅看大小 | byte LR、byte RF、frozen（no-cover 分类器）、last-destination、penultimate-destination |
| 时序 | timing+size LR/RF、gap detector 后剥离（S9）、无标签 GMM 后剥离（S10）、上下文检测器后剥离、联合解码（S11） |
| **影子臂专用** | **链分离攻击**：利用"每条链的调用之间隔着一次模型推理"这一结构，把调用分配到两条链（按与前一调用的重叠关系和间隔，做动态规划或二分图划分），分别对两条链分类，再用在训练集上学到的规则判断哪条是真实链。这是针对影子设计的自适应攻击，必须包含。 |

**最佳攻击的定义与 S11 相同**：

- `size_only_best`：在仅看大小的攻击中按验证集准确率选出；
- `adaptive_best`：在全部攻击中按验证集选出，平局时归于仅看大小。

---

## 7. 统计与判定（预注册）

- **单位**：每个模型 120 个配对测试 fixture。
- **检验**：精确 McNemar；区间用按动作分层的配对 bootstrap（10,000 次）。

| 家族 | 内容 | 检验 | 判定规则 |
|---|---|---|---|
| **P（主）** | `gdm_live`、`concurrent`、`shadow` × 2 个模型，共 6 个检验：adaptive_best − size_only_best | 精确 McNemar，Holm 校正 | 某臂若在任一模型上差值 ≥ 12/120 且 Holm p < .05，则判为 **"可区分"** |
| **E（主，等价）** | 同样 6 个对比 | 配对 TOST，界限 ±12/120（10 pp），每个 α = .05，Holm 校正 | 某臂在**两个模型上都通过** TOST，才可写"在 10 pp 界限内与仅看大小水平不可区分" |
| R（复现） | `unmatched` × 2：无标签 GMM 剥离 − size_only_best | 精确 McNemar，Holm 校正 | 两个模型都 ≥ 24/120 且显著，则复现成立 |
| C（cover 是否有效） | 4 个 cover 臂 × 2：size_only_best(臂) − size_only_best(`none`) | 精确 McNemar，Holm 校正 | 描述 cover 本身是否仍降低识别率；若影子臂在这里无效，Q3 的"不可区分"就没有意义 |
| 描述性 | 延迟（真实链 wall 时间相对 `none` 的增量）、token、模型调用次数、字节、L2–L3 误差、规划器决策一致性 | — | 只报告，不检验 |

**功效说明**：M3 中 adaptive 与 size-only 的不一致对约占 15–25%。按 20% 计，配对差的标准误约为 0.041，TOST 的 90% 区间半宽约为 6.7 pp，小于 10 pp 的界限；因此如果真实差接近 0，每个模型 120 个 fixture 足以通过 TOST。此计算基于 M3 的估计，不构成对 L 实验的保证，正文需如实说明。

**有效性检查**（预先声明）：

- 在 hidden cover 臂中，规划器的诚实动作序列与 `none` 臂完全相同的 fixture 比例。由于 temperature=0，预期很高；M3 中 hidden 与 proxy 臂之间有 1（Qwen）和 15（Llama）个 fixture 的路径不同。
- 影子臂中两路并发推理会互相拖慢，所以要单独报告真实链的推理延迟分布与 `none` 臂的差异。

---

## 8. 可选：网络条件（次要，探索性）

在主实验之外，可以对测试集加一组受控网络延迟：

- Linux：`tc qdisc add dev lo root netem delay 20ms 5ms distribution normal`
- Windows：clumsy（lag 20 ms，抖动 5 ms）
- 或把七个工具服务放到另一台机器上

只对测试集采集，攻击者用主实验的训练集拟合，用来检验迁移。结果标注为探索性。

---

## 9. 需要回传的内容

1. `analysis-plan.json`、`pools.json` 和 `collect.py` 的冻结提交号（采集前已推送）。
2. `episodes.jsonl.gz`：与 M3 相同的 schema，加上新字段（不含 payload、凭据和模型权重）。
3. L3 导出的逐 record 计时 CSV，以及 L2–L3 对齐报告。
4. `verify_collection` 的输出、采集前后的权重哈希、硬件和软件版本。
5. 所有 unknown 和 readiness 记录（单独存放）。

收到之后，我会写 `l_ext.py`。它和 `d_ext.py` 结构相同：先冻结，再做复现检查（`none` 臂的 byte LR/RF 预测必须能由导出的特征重现），然后用 `verify_l.py` 做独立复核，最后把结果写入稿件。**分析代码也可以在你采集之前先写好并冻结**，这是更强的预注册方式，你确认后我就开始写。

## 10. 结果怎样写进稿件

计划新增补充材料 S12，并在 §7.1 Step 3 增加一段，必要时在 Table 7 增加一列 "Live"。正文仍须在 13 页内。各种结果对应的写法如下：

| 结果 | 正文表述 |
|---|---|
| 影子臂在 E 家族两个模型上都通过，且 C 家族显示 cover 有效 | Finding 3 改为正面结论：在实测界限内，由规划器自己生成的 cover 恢复了仅看大小的保护，代价是 X 倍 token 和 Y% 的延迟（或无额外延迟） |
| 影子臂在 P 家族被判为可区分（例如被链分离攻击识破） | "即使是规划器生成的 cover 也可被分离"，并说明分离依据是什么 |
| `gdm_live` 与 S11 的反事实结论一致 | S11 的结论升级为 live 证据，从局限中删除"仅为 receipt 级反事实" |
| `gdm_live` 与反事实不一致 | 如实报告，并给出原因分析（排队、服务端 hold 的实现方式等） |
| R 家族复现失败（record 层上剥离攻击失效） | Step 2 的结论要降级，并在摘要中修改 |

## 11. 伦理与资源

- **数据**：全部为合成数据，business action 只更新隔离的 fixture，抓包过滤只覆盖实验端口，不涉及人类参与者或任何外部服务。
- **资源**：本地 GPU 与 CPU。影子臂约需两倍模型调用。

## 12. 采集前检查清单

- [ ] readiness 通过（并发调用、影子结束、L2–L3 对齐）
- [ ] `analysis-plan.json` 与代码哈希已推送
- [ ] `none` 臂采集完成，`pools.json` 已推送
- [ ] 权重哈希与 `weights-before.json` 一致
- [ ] `workers = 1`，`OLLAMA_NUM_PARALLEL = 2`
- [ ] 抓包只过滤实验端口，并已在 readiness 中验证
