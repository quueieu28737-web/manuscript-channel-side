"""Render B1 tables from verified values; no fits or collection."""
from pathlib import Path
import csv,json,hashlib

H=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf8'))
assert load(H/'verification.json')['status']=='PASS'
assert load(H/'diagnostic/verification.json')['status']=='PASS'
recognition=load(H/'results/recognition.json');detectors=load(H/'results/cover-detection.json')
comparisons=load(H/'results/comparisons.json');diagnostic=load(H/'diagnostic/results.json')


def metric(model,arm,attack):
    return next(x for x in recognition if x['model']==model and x['arm']==arm and x['attack']==attack)


names={'none':'无 cover','transport_drop':'代理丢弃','read':'只读','isolated':'隔离隐藏','live_write':'真实状态写入','isolated_visible':'隔离可见'}
table=[];dtable=[];rows=[]
for model in ['qwen3:8b','llama3.1:8b']:
    for arm in names:
        old=metric(model,arm,'bytes/selected')['correct'];direct=metric(model,arm,'timing_size/selected')['correct']
        strip=metric(model,arm,'stripped/frozen_none')['correct'];priv=metric(model,arm,'privileged_cover_labels/frozen_none')['correct']
        detector=next(x for x in detectors if x['model']==model and x['arm']==arm)
        row={'model':model,'arm':arm,'n':120,'bytes_selected_correct':old,'timing_size_selected_correct':direct,
             'timing_informed_stripping_correct':strip,'privileged_reference_correct':priv,
             'cover_tp':detector['tp'],'honest_fp':detector['fp'],'cover_fn':detector['fn'],'honest_tn':detector['tn'],
             'cover_precision':detector['precision'],'cover_recall':detector['recall'],'cover_auc':detector['auc']}
        rows.append(row)
        if arm=='none':continue
        p=next(x['p_holm'] for x in comparisons['secondary_stripping_vs_bytes'] if x['model']==model and x['arm']==arm)
        table.append(f"| {model} | {names[arm]} | {old} | {direct} | {strip} | {priv} | {p:.3g} |")
        timed=next(x for x in diagnostic if x['model']==model and x['arm']==arm and x['view']=='timing_only')
        plain=next(x for x in diagnostic if x['model']==model and x['arm']==arm and x['view']=='no_clock_context')
        dtable.append(f"| {model} | {names[arm]} | {timed['task_correct']} | {plain['task_correct']} |")
with (H/'results-summary.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
positives=sum(r['cover_tp'] for r in rows);missed=sum(r['cover_fn'] for r in rows);false=sum(r['honest_fp'] for r in rows);honest=sum(r['honest_tn']+r['honest_fp'] for r in rows)
report=f'''# B1：控制器插入的诱饵可被回执计时识别并剥离

R107 已从 PR #5 的 `claude/sp27-r106-acceptance-revision` 拉取，固定提交为
`6c832f068a7fb2dfc38feb1bde37c38252250bd5`。原稿和方案位于 `upstream/releases/r107/`。
本轮没有新增 LLM 请求或采集回合。分析复用原 M3 的 3,600 个回合，保留
120/60/120 个 fixture 的训练、验证、测试划分；测试共 1,440 回合。

## 主要结果

**计时对攻击的作用在于分离真实调用和诱饵。** 把计时直接拼接到原 LR/RF 中，
十个预先固定的主比较都没有通过 Holm 校正，且点估计没有改善。预先列明的
检测—剥离次级攻击则在两个模型的全部五个 cover 条件下恢复了较高识别率：
Qwen 为 111–114/120（原尺寸攻击61–63），Llama 为107–115/120（原尺寸攻击72–82）。
全部十项次级比较通过各自的 Holm 家族校正；最大调整后 p 为
{max(r['p_holm'] for r in comparisons['secondary_stripping_vs_bytes']):.4g}。

| 模型 | 条件 | 原尺寸/目的地 | 直接加入计时 | 计时检测后剥离 | 给定 cover 真值后剥离 | 剥离−原尺寸 Holm p |
|---|---|---:|---:|---:|---:|---:|
'''+'\n'.join(table)+f'''

所有正确数的分母为120。主算法由 validation 选择；没有按这些测试数重新选择
分类器。cover 真值仅用于评分与特权参考，普通剥离攻击用的是预测的 cover 标签。
特权参考是一个特定分类器在更多信息下取得的分数，不是隐私上界。

无 cover 条件的原分类器分别为118/120和113/120。剥离后的部分结果仍低于
相应无 cover 点估计；本研究没有证明隐私收益严格为零或恢复完全等价。

## 诱饵检测

validation 在两个模型中都选出平衡 LR 检测器，阈值已在测试前确定。
测试中识别出 {positives}/{positives+missed} 个 cover（漏掉{missed}个），
{honest} 个 honest 调用中误删{false}个。各 cover 条件的检测精度均为1.000，
召回率为98.35%–100%，AUROC均为1.000。这是本次样本的表现，零误删不构成
对新数据的零错误保证。调用的相关性通过整 fixture 的条件 bootstrap 处理。

输入只有调用间隔、调用耗时、首调用标志和目的地；工具内容、动作、业务状态、
模型内容及模型 token/推理耗时没有进入普通检测器。初始取票已知由控制器执行，
该首调用先验被明确使用。观察者也获得了 episode 与调用窗口，以及带 cover
标签的训练/验证数据。

## 结果后输入消融（探索性，单独冻结和报告）

为检查恢复是否只是来自“换成两阶段算法”，在看到上述 B1 结果后另加了输入
消融。该部分没有改写 B1 主次检验：纯计时检测器只使用间隔、耗时、首调用标志；
无计时对照使用完整153维原观察、当前目的地、字节及位置上下文，共164维。
两者都按 train/validation 拟合选择，随后使用同一个冻结无 cover 分类器。

| 模型 | 条件 | 纯计时检测后剥离 | 强无计时上下文检测后剥离 |
|---|---|---:|---:|
'''+ '\n'.join(dtable)+'''

这项探索性消融与计时指纹解释一致，但不升级为新的确认性结果。全部算法和
误删率见 `diagnostic/`；独立数组复算见其 `verification.json`。

## 解释与下一步

源代码在诚实调用后直接执行 `covers()`，两次工具调用之间没有模型决策。
诚实路径通常先等待一次模型推理。validation 描述统计保存在
`validation/timing-description.json`，这一实现差异给了攻击者一个区分信号。
当前证据支持这条具体调度路径存在可利用的回执时间指纹。

时间戳来自客户端回执，含 Python/asyncio 调度与2ms计数等待，不能冒充中继
实际 TLS 记录或 WAN 包时戳。B1 是既有测试样本上的新观察者分析；原尺寸分数
和执行结果早已公开。新计时评分前已做本地代码/计划/输入冻结，主结果不显著
和有利次级结果同时保留。区间及检验条件于原合成总体、配对 fixture 和拟合的
攻击者，没有给真实生产流量或所有攻击者提供保护界。

A/B2 的修订计划在 `EXPERIMENT-PLANS.md`：先修复派发间隔，再做实际记录计时。
原八臂缺少预算匹配的2×2；保留全部用途时完整版本为十臂。±8pp只检验明确
攻击准确率的等价性，不是程序语义等价。TOST功效模拟也表明120/240对未必足够。
本轮没有启动 A 或 B2 的新采集，也没有把尚未测量的调度写成有效防御。

## 复算

使用原 Python3.12 环境（NumPy2.3.3、SciPy1.18.1、scikit-learn1.9.1）。
`b1.py` 的阶段为 freeze → prepare → evaluate；已存在的输出拒绝覆盖。
`verify_b1.py` 独立核对原基线、特征、LR/RF 数组推断、检测掩码和32项比较。
`verify_diagnostic.py` 核对单列探索性消融。重新运行须使用新输出副本，不能改写
本次冻结或结果文件。输入源为已发布的原 M3 synthetic export，哈希在freeze中。
'''
(H/'RESULTS.md').write_text(report,encoding='utf8')
summary={'status':'B1_COMPLETE_VERIFIED','upstream':'6c832f068a7fb2dfc38feb1bde37c38252250bd5',
         'freeze_utc':load(H/'freeze.json')['utc'],'new_collection':False,
         'primary_significant':sum(r['p_holm']<.05 for r in comparisons['primary_timing_size_vs_bytes']),
         'primary_tests':10,'secondary_stripping_significant':sum(r['p_holm']<.05 for r in comparisons['secondary_stripping_vs_bytes']),
         'secondary_stripping_tests':10,'test_cover_detected':positives,'test_cover_total':positives+missed,
         'honest_false_removals':false,'honest_test_calls':honest,
         'models':{m:{'original_cover_correct_range':[min(x['bytes_selected_correct'] for x in rows if x['model']==m and x['arm']!='none'),max(x['bytes_selected_correct'] for x in rows if x['model']==m and x['arm']!='none')],
                      'timing_stripped_correct_range':[min(x['timing_informed_stripping_correct'] for x in rows if x['model']==m and x['arm']!='none'),max(x['timing_informed_stripping_correct'] for x in rows if x['model']==m and x['arm']!='none')]} for m in ['qwen3:8b','llama3.1:8b']},
         'scope':'Retrospective endpoint-receipt timing and supplied-window attack; not measured packet timing or a new confirmation cohort.',
         'future_studies':'A and B2 revised designs only, no new collection started.'}
(H/'result-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
