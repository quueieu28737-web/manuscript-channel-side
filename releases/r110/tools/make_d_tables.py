"""Generate Supplement S11 tables from releases/r110/d-ext results (no hand-copied numbers)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'releases/r110/d-ext'
cells = json.load(open(D / 'results/cells.json'))
prim = json.load(open(D / 'results/primary.json')); sec = json.load(open(D / 'results/secondary.json'))
fg = json.load(open(D / 'exploratory/feature-groups.json'))
M = {'qwen3:8b': 'Qwen3:8B', 'llama3.1:8b': 'Llama3.1:8B'}
P = {'transport_drop': 'Proxy discard', 'read': 'Read', 'isolated': 'Isolated, hidden', 'live_write': 'Live write', 'isolated_visible': 'Isolated, visible'}
V = {'C3a_gap': 'GM', 'C3b_gap_duration': 'GDM', 'C3c_position': 'PM'}
AB = {'byte_LR': 'LR', 'byte_RF': 'RF', 'frozen': 'Frz', 'position_last': 'Last', 'position_penultimate': 'Pen',
      'timing_size': 'T+S', 'b1_strip': 'Strip', 'ctx_strip': 'Ctx', 'joint': 'Joint'}
BS = '\\\\'


def cell(m, a, v):
    return next(x for x in cells if x['model'] == m and x['arm'] == a and x['variant'] == v)


rows = []
for v in V:
    for m in M:
        for a in P:
            c = cell(m, a, v); t = c['test_correct']; d = c['ctx_strip_detector']
            rows.append(' & '.join([M[m], P[a], V[v], str(t['byte_LR']), str(t['byte_RF']), str(t['position_last']),
                                    f"{c['size_only_best_correct']} ({AB[c['size_only_best']]})", str(t['timing_size']),
                                    str(t['b1_strip']), str(t['ctx_strip']), str(t['joint']),
                                    f"{c['adaptive_best_correct']} ({AB[c['adaptive_best']]})",
                                    f"{d['precision']:.2f}/{d['recall']:.2f}/{d['auc']:.2f}",
                                    f"{c['added_latency_pct_of_none_wall']:.1f}"]) + ' ' + BS)
    rows.append(r'\addlinespace[3pt]')
rows = rows[:-1]
(ROOT / 'tables/d-ext-cells.tex').write_text(r'''\begin{table*}[t]\centering\scriptsize
\caption{Adaptive attacks against timing-matched dispatch (correct/120 on the same test fixtures). GM: gap-matched; GDM: gap and duration matched (Section~\ref{supp:c-ext}); PM: gap drawn by call position, duration as GDM. LR/RF: byte learners; Last: last-destination rule; Best: validation-selected size-only attack among learners and position rules; T+S: refitted timing-plus-size learner; Strip: refitted gap detector, then removal; Ctx: context detector, then removal; Joint: joint decoding; Adapt.: validation-selected attack among all of them, ties to size-only. Ctx P/R/AUC: context detector on test calls. +Lat: added latency as a percentage of no-cover wall time. Every attacker is refitted on the transformed cohort.}\label{tab:d-cells}
\setlength{\tabcolsep}{2.6pt}
\begin{tabularx}{\textwidth}{@{}lYlrrrrrrrrrrr@{}}\toprule
Model & Policy & Var. & LR & RF & Last & Best & T+S & Strip & Ctx & Joint & Adapt. & Ctx P/R/AUC & +Lat\%\\\midrule
''' + '\n'.join(rows) + '''
\\bottomrule\\end{tabularx}
\\end{table*}
''')


def fp(p):
    return f'{p:.3g}' if p >= 1e-3 else f'{p:.1e}'


def tr(r, fam):
    c = cell(r['model'], r['arm'], r['variant'])
    con = f"Adapt.\\ ({AB[c['adaptive_best']]}) $-$ Best ({AB[c['size_only_best']]})"
    lo, hi = r['conditional_ci_pp']
    return ' & '.join([fam, M[r['model']], P[r['arm']], con, f"{r['difference_pp']:.1f}", f'[{lo:.1f}, {hi:.1f}]',
                       fp(r['p_raw']), fp(r['p_holm'])]) + ' ' + BS


rows = [tr(r, 'GDM') for r in prim] + [r'\addlinespace[3pt]'] + [tr(r, 'PM') for r in sec]
(ROOT / 'tables/d-ext-tests.tex').write_text(r'''\begin{table*}[t]\centering\scriptsize
\caption{Pre-registered families: validation-selected adaptive attack minus validation-selected size-only attack, exact paired McNemar tests. GDM is the primary family and PM the secondary family; each has ten tests and its own Holm correction. Differences and conditional intervals are percentage points. The rule for declaring the countermeasure defeated (at least 12/120 with Holm $p<.05$ in five or more cells) is met in two of ten cells in each family.}\label{tab:d-tests}
\setlength{\tabcolsep}{3pt}
\begin{tabularx}{\textwidth}{@{}lllYrrrr@{}}\toprule
Family & Model & Policy & Contrast (selected attacks) & $\Delta$ pp & 95\% cond.\ CI & Raw $p$ & Holm $p$\\\midrule
''' + '\n'.join(rows) + '''
\\bottomrule\\end{tabularx}
\\end{table*}
''')

G = ['all', 'no_timing', 'no_size', 'no_position_context', 'timing_only']
rows = []
for v in ['C3b_gap_duration', 'C3c_position']:
    for m in M:
        vals = {x['group']: x['test_auroc_non_first_calls'] for x in fg if x['model'] == m and x['variant'] == v}
        rows.append(' & '.join([M[m], V[v]] + [f'{vals[g]:.3f}' for g in G]) + ' ' + BS)
(ROOT / 'tables/d-ext-ablation.tex').write_text(r'''\begin{table}[t]\centering\footnotesize
\caption{Post-hoc exploratory ablation of the context detector: random forest refitted with input groups removed; test AUROC on non-first calls of all cover arms. It was run after the frozen results were saved and tests no claim.}\label{tab:d-ablation}
\setlength{\tabcolsep}{2.5pt}
\begin{tabularx}{\columnwidth}{@{}Ylrrrrr@{}}\toprule
Model & Var. & All & $-$Time & $-$Size & $-$Pos. & Time only\\\midrule
''' + '\n'.join(rows) + '''
\\bottomrule\\end{tabularx}
\\end{table}
''')
print('tables written')
