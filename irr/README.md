# 独立二次编码（IRR）工具包

本目录支持整改方案中的实验 A：由一位未参与原始编码的研究者，独立重编 39 条记录的 351 个 R1–R9 单元格，以及 133 个相关记录对的可比性判断。

## 文件

| 文件 | 用途 |
|---|---|
| `coder2_sheet.csv` | 盲化编码表，共 351 行，已打乱顺序。表中只给出记录 ID、文献引用键、Table 13 的范围与定位符和条目编号，**不含**原始编码和理由。 |
| `../tools/irr_kit.py` | 生成编码表，并计算一致性：Cohen κ、Krippendorff α（名义尺度）、按记录聚类的 bootstrap 置信区间、逐条目 κ、混淆矩阵，以及第二编码者的编码对 Table 10 联合查询的影响。 |
| `../tools/audit_check.py` | 从 LaTeX 表格重算全部计数，并检查 Table 9（家族级）与记录级单元格是否一致。 |

## 规程

1. **编码手册冻结。** 只把正文 Table 8（R1–R9）、Table 4（比较契约）和 S34 的阅读规则（B/P/U/A/?/– 的判定口径）交给编码者 2，不提供 S33/S34 的逐格结论。
2. **培训集。** 用 3 条不在 39 条记录中的记录（例如从 32 个仅入图谱的家族中选取）做校准练习。练习结果不计入 IRR。
3. **独立编码。** 编码者 2 阅读原文的对应版本（版本号见 Table 13 和参考文献），填写 `code` 列，在 `note` 列写一句理由。编码完成前不得与编码者 1 交流。
4. **评分。**
   ```
   python3 tools/irr_kit.py score --coder2 irr/coder2_sheet.csv
   ```
   输出总体与逐条目一致性，以及 Table 10 的五个联合查询在编码者 2 的编码下是否改变。同时生成 `coder2_sheet_disagreements.csv`，用于裁决。
5. **裁决。** 两位编码者逐条讨论分歧，在 `resolution` 列写明原因：手册歧义、漏读或原文本身不清。裁决后的编码作为正式版本，用 `audit_check.py` 重算全部表格。
6. **记录对（133 对）。** 作者从已发布工件导出 `record_id,cohort` 成员文件，然后运行：
   ```
   python3 tools/irr_kit.py make-pair-sheet --membership cohorts.csv
   python3 tools/irr_kit.py score-pairs --archived archived_pairs.csv --coder2 irr/coder2_pairs.csv
   ```

## 报告口径

- 同时报告原始一致率、κ 和 α。R1 这类几乎全是 B 的条目会出现“一致率高、κ 低”的患病率悖论，应在脚注中说明，必要时补充 Gwet AC1。
- 门槛建议：α ≥ 0.80 视为可靠；0.667 ≤ α < 0.80 只能支持暂定结论，需逐条讨论低一致条目。
- 最关键的是“联合查询稳健性”：CachePrune 是否仍是唯一的推断–效用–成本三联包，2/17 的匹配自适应是否仍成立。论文的核心数字依赖这些结论，而不是单个单元格。
