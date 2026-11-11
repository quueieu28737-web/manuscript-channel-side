# 第二编码者手册（44 个设置 × 6 个字段）

**盲法要求：** 只能看 `coder2_template.csv` 里给出的信息（setting_id、来源、版本、URL、locator、接口、隐藏目标）和原论文本身。**不得**打开 `releases/r101/evidence` 下的其他 CSV，也不得阅读 SoK 正文的表 3、4、9 及补充材料 S4/S5。

| 字段 | 取值 | 判定规则 |
|---|---|---|
| access_class | transit / recipient / active / derived_preference | transit：只看加密流量的元数据；recipient：被 Agent 联系的服务，能看到发给它的请求；active：自己选择探针、挑战或陷阱的一方；derived_preference：分析下游数据集 |
| protection | Y / N | 该设置是否比较了某种防御或干预（包括身份混淆和拦截）与无防御的情形 |
| named_transfer | Y / N | 是否把某个部署因素（组合、拓扑、scaffold、模型等）整体留出作为测试集 |
| open_world | Y / N | 测试集中是否包含训练时未见过的类别，或需要拒识的未知样本 |
| failure_status | reported / partly_reported / not_located / not_applicable | **reported**：明确说明了失败、中断、拒绝或出错的执行在本设置总体中如何处理（排除、保留或重跑）。**partly_reported**：只说明了某一类失败，或只有采集层面的过滤规则。**not_located**：在 locator 指向的章节及方法部分都没有找到。**not_applicable**：本设置没有执行总体 |
| outcome_status | 同上 | **reported**：对本设置中的执行报告了与执行目标相应的结果（任务是否成功；对探针类设置，指探针或解析器本身的结果）。**partly_reported**：只有保留条件或终止条件，或只覆盖部分执行。not_located 和 not_applicable 的含义同上 |

**每格都要在 note 列写出依据**，包括节号和一句原文转述。

## 流程

1. 先用 10 个设置做试编码，与第一编码者讨论**定义**（不讨论具体答案）。如有需要，修改本手册。
2. 冻结手册后，独立完成全部 44 个设置。
3. 运行 `python irr_kappa.py coder2_human.csv`。
4. 报告每个字段的 κ（附 95% bootstrap 区间）。分歧通过讨论裁决，裁决后的值写入新的证据版本，原始的两份编码都要保留。
