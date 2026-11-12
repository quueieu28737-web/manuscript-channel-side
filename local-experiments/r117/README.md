# R117 本机试验流程（P0 诊断 + 新采集方案）

这些试验回应 S&P 2027 模拟审稿意见中的 W2、W3、W4、W6。稿件本身已按"不做试验也成立"的口径改好（见 PR 说明）。下面的结果用于决定能否把这些限定改成正面结论。

- **P0-T / P0-A / P0-B / P0-C**：只读取本机已有的正式数据，**不调用模型、不重新采集**。脚本已在本目录实现，并用合成数据完整跑通过。
- **W6、P1**：需要新采集。第 6 节只给出流程，没有提供采集代码。

> 状态：DESIGN + CODE，NOT RUN ON REAL DATA。这些都是**结果已知后的探索性分析**，在稿件中只能写成 exploratory，不能写成确认性发现。

---

## 0. 前提

你本机需要有 R110 live-timing 的正式运行目录（下文记作 `$LIVE`）。它应包含：

```
$LIVE/experiment/analyze.py            # 冻结版分析脚本（P0-A 直接 import 它）
$LIVE/private-run/formal-none-v1/episodes/*/result.json
$LIVE/private-run/formal-none-v1/wire/*.json
$LIVE/private-run/formal-cover-v1/episodes/*/result.json   (+ connections/*.json)
$LIVE/private-run/formal-cover-v1/wire/*.json
$LIVE/analysis/predictions.csv         # analyze.py 的正式输出
$LIVE/analysis/results.json
$LIVE/analysis/validation-selection.json
```

Python 环境使用原 M3 运行时，至少需要 `numpy`、`scipy`、`scikit-learn==1.9.1`（版本见 `releases/r116/artifact/live-study/requirements.txt`）。sklearn 版本不同可能导致 RF 结果不能逐例复现，P0-A 会检查这一点。

## 1. 拉取代码

```bash
git fetch origin claude/r117-review-fixes
git checkout claude/r117-review-fixes
cd local-experiments/r117
export LIVE=/path/to/r110-live-timing      # 改成你的实际路径
export OUT=$HOME/r117-p0-out-v1            # 新建、仅本机的输出目录
```

## 2. 可选：合成数据冒烟测试

这一步只验证脚本在你的环境中能运行。数值没有科学意义。

```bash
python3 smoke/make_synthetic.py --out /tmp/smoke-live
( cd /tmp/smoke-live/experiment && python3 analyze.py )   # 用冻结 analyze.py 生成 analysis/
bash smoke/run_smoke.sh /tmp/smoke-live /tmp/smoke-out
```

`run_smoke.sh` 依次运行 freeze 和四个脚本，最后打印 `SMOKE OK`。

## 3. 冻结（必须在看任何新结果之前）

```bash
python3 freeze.py --live-dir "$LIVE" --out "$OUT"
git add freezes/ && git commit -m "R117: freeze P0 diagnostic code" && git push origin claude/r117-review-fixes
```

`freeze.py` 记录本目录脚本、`analyze.py` 和 record-only 模块的 SHA-256，以及库版本和时间。之后每个 `p0*.py` 都会核对自身哈希，不一致就拒绝运行。

如果需要改代码，请换一个新的 `$OUT`（例如 `-v2`）重新冻结，旧版本的结果保留。**不要根据测试结果回头改特征、阈值或选择规则。**

## 4. 运行四项诊断

按顺序运行。前两项很快，P0-A 和 P0-C 需要重新拟合，最耗时，建议后台运行：

```bash
python3 p0_terminal_coverage.py --live-dir "$LIVE" --out "$OUT" | tee "$OUT/p0t.log"
python3 p0b_shadow_roles.py     --live-dir "$LIVE" --out "$OUT" | tee "$OUT/p0b.log"
nohup python3 p0a_feature_ablation.py --live-dir "$LIVE" --out "$OUT" \
      --published ../../releases/r116/artifact/live-aggregates/attacks-and-tests.json > "$OUT/p0a.log" 2>&1 &
nohup python3 p0c_record_only_strong.py --live-dir "$LIVE" --out "$OUT" > "$OUT/p0c.log" 2>&1 &
```

### P0-T 末端覆盖诊断（回应 W2/W3，不重新拟合）
对每个测试 fixture，按真实 wire trace 判断：真实业务动作之后有没有 cover（影子臂：有没有影子业务动作）、真实动作是否是最后一次调用。然后用已保存的预测，按这两个分层统计每个攻击的准确率。

- 输出：`p0t-summary.json`（每臂分层计数）、`p0t-attack-strata.csv`（每个攻击的分层准确率及描述性 Fisher p）。
- 计划层面的预期：按 `cohort-plan.json`，测试集约 79/120 个 fixture 没有 cover 排在参考动作之后。实际轨迹会因规划器偏离参考路径而不同。

### P0-B 影子角色与精确任务标签诊断（回应 W3，不重新拟合）
- **R1**：冻结的角色选择器（p≥.5 即判第一条链为真）与"只看启动顺序"基线（由 TRAIN 多数决定）比较角色准确率，exact McNemar，2 项 Holm。
- **R2**：按 real-first / shadow-first 分层的精确分链数和真实链识别数。
- **T1**：每个攻击在 21 个同标签、99 个异标签 fixture 上的**精确**准确率，替代正文中的 [49,70]/99 区间。
- **T2**：在异标签 fixture 上比较"预测=真实标签"与"预测=影子标签"的次数。对角色不敏感的攻击，这两个数的期望相等。做 sign test，只对验证选中的攻击做 Holm。

### P0-A 时间/位置消融（回应 W2、R115 意见 3.2）
直接 import 冻结的 `analyze.py`，在 Full、No-time、No-position 三种观察下，用同样的 seed 和选择规则重新拟合全部攻击。

- **必须先看** `p0a-reproduction.csv`：Full 变体应逐项复现已发布的计数。若不一致（多半是 sklearn 版本不同），后面的消融不可读，先停下排查环境。
- 家族 A（8 项 Holm）：Full 自适应 − No-time 自适应；No-time 自适应 − Full 选中 size-only。
- 家族 B（4 项 Holm）：Full 自适应 − No-position 自适应。
- 注意：No-time 保留了调用顺序，所以不能称为"没有上下文"。

### P0-C 无窗口强攻击（回应 W4）
在 S3 的 5 个 idle 网格和协议感知事件化上，加入 context removal 与 joint decoding（top-10 候选、最多去掉 2 个）。真实调用窗口只用于两处：给**训练**事件打 cover 标签，以及在测试预测完成后做事件级审计。

- 输出：`p0c-tests.csv`（8 个 cover 单元：选中强攻击 − 选中基线，Holm）、`p0c-attacks.csv`、`p0c-event-audit.csv`（检测器在测试上的 P/R/F1）。
- 脚本会在 `$OUT` 写入 `LOCAL-ONLY-p0c-inputs.jsonl`，内含逐例记录，**不得上传**。

## 5. 可以发回 / 不能上传的文件

| 可以发给我或放进仓库（聚合结果） | 只能留在本机（逐例数据） |
|---|---|
| `p0t-summary.json`、`p0t-attack-strata.csv` | `p0t-per-fixture.csv` |
| `p0a-summary.json`、`p0a-tests.csv`、`p0a-attacks.csv`、`p0a-reproduction.csv` | `LOCAL-ONLY-*` |
| `p0b-summary.json`、`p0b-role-tests.csv`、`p0b-start-order.csv`、`p0b-task-labels.csv` | 原始 `private-run/`、抓包、密钥 |
| `p0c-summary.json`、`p0c-tests.csv`、`p0c-attacks.csv`、`p0c-event-audit.csv` | |
| 各 `*.log`、`freeze.json` | |

把左列文件拷到 `local-experiments/r117/results-v1/` 后提交，或直接发给我。我会据此更新稿件。

## 6. 结果怎样改变稿件（事先写定）

| 诊断 | 结果 | 稿件处理 |
|---|---|---|
| P0-T | 选中自适应攻击在"末端未覆盖"层的准确率明显高于"已覆盖"层 | §7.1 写明历史臂残余识别主要来自末端动作暴露；§8 增加设计结论：cover 必须覆盖动作之后的位置 |
| P0-T | 两层差别很小 | 删除 §6/§7.1 中的替代解释句，W2 关闭 |
| P0-A | Full−No-time 大且 Holm 显著 | 历史臂泄漏包含时序成分，可以写"timing relations matter" |
| P0-A | Full−No-time 不显著，No-time − size 显著 | 改为"位置/目的地上下文"，删除时序归因 |
| P0-B | R1 选择器不优于启动顺序；T2 不显著 | 影子"未发现角色信号"可以写成描述性结果，但仍不能写成等价性 |
| P0-B | T2 显著偏向真实标签 | 报告角色泄漏，影子不能再说与理想参照"相容" |
| P0-C | 强攻击接近调用窗口下的自适应结果 | 撤回 §7.2 的边界作用，结论改为调用窗口不起保护作用 |
| P0-C | 强攻击仍明显低于调用窗口结果，且事件审计 F1 合理 | 可以写"在所测表示下，撤去窗口降低了攻击效果"，仍注明 episode 关联是给定的 |

所有新数字都在稿件中标为 exploratory，并引用 freeze 提交。

## 7. 需要新采集的两项（仅流程，未提供代码）

这两项会产生新的正式数据。请先完成第 4 节，再决定是否做。

### 7.1 W6：插入式无 cover 对照（量化采集阶段效应）
1. 在 `releases/r116/artifact/live-study/experiment/collect_cover_v3.py` 的 arm 轮换中加入 `none_interleaved` 臂，复用同一批 300 个 fixture，与四个 cover 臂一起轮换。无 cover 的逻辑沿用 `collect.py --phase none`。
2. 新建运行 ID（例如 `formal-interleaved-v1`）。沿用原有 gate：冻结 → push 并回读 → 采集 → `verify_collection_v2.py` → 权重核对。
3. 分析：用同一套 C 族攻击，比较 `none_interleaved` 与 `formal-none-v1` 的识别率、goal/state 和延迟（配对 McNemar 加配对差均值）。主要关注 Llama 延迟 0.88×/0.84× 的现象是否消失。
4. 稿件处理：差异小，删除 §8 的阶段混杂限定；差异大，改用插入式无 cover 作为基线重算表 9/12 的成本和 goal/state 列（识别率的 P/R 族不受影响）。

### 7.2 P1：同脚本控制器重放（区分"在线规划"与"多一个末端动作"）
按 `releases/r116/EXPERIMENT-PLANS.md` 的 P1 执行，并补上这次审稿新增的两点要求：
1. **新 fixture 与模板留出**：新实体、新措辞模板，训练/验证/测试按模板簇划分。
2. **cover 脚本**由冻结生成器产生，调用数和组成与影子相同，且**必须包含真实动作之后的槽位**（这是 W2 的关键）。
3. 臂：R0 无 cover；R1 即时；R2 训练条件间隔；R3 重放影子的相对等待；R4 每步在线计算但执行固定脚本；R5 自然影子（描述性参考）。
4. 样本量：先跑独立的训练/验证阶段估计 discordance，**在看测试集之前**固定样本量（EXPERIMENT-PLANS.md 中的 600 个测试 fixture 只是草案）。
5. 主要检验：R2−R3、R3−R4，每模型 2 项，共 4 项 Holm。等价性用 ±8pp TOST，两个模型都要通过。
6. 同批记录 goal、state、配额、调用数、tokens、字节和延迟。cover 脚本离线生成的成本也要计入。

完成后，§7.3 才能把影子的效果归因到"在线规划"或"末端覆盖"。
