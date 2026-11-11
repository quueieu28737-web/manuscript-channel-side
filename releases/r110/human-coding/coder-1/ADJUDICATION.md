# Adjudication record: coder-1 vs. author (AU)

`agreement.py coder-1` (before discussion): 104/111 decisions agree.

| Field | Agreement | κ |
|---|---|---|
| Access class | 44/44 | 1 |
| Intervention purpose | 9/9 | 1 |
| Adaptation in the privacy settings | 4/4 | 1 |
| Utility in the privacy settings | 4/4 | 1 |
| Protection flag | 38/44 | .61 |
| Transfer relation | 5/6 | .77 |

The privacy denominator is identical (WRA-decoy, WRA-visibility, CG-transform, CG-live).

The **author decides** each item below against the cited passage. The "Recommendation" column is
an AI-drafted suggestion with its evidence; it is not a decision. Record the final code and reason
in `disagreements.csv`; no vote overrides the source.

| # | Item | AU | Coder | Evidence checked | Recommendation | Consequence if the coder's code is adopted |
|---|---|---|---|---|---|---|
| 1 | CG-composition, protection flag | no | yes | 2606.07150v3 §9.12: "the same metadata-protecting properties close it, only as a set … fresh identifiers alone barely move recovery … the two composed reach chance … capture ratio falls from κ=0.63 unprotected to ≈0" | The coder is right that §9.12 contains a with/without contrast. It is the §9.3 wire-property ladder re-measured on the wire-faithful corpus view, i.e. the same intervention as CG-transform. Either (a) code yes and record it under CG-transform (denominator stays 4), or (b) add it as a fifth privacy setting. | (b): the denominator becomes 5. Adaptation is not stated for the §9.12 ladder; utility is not located. **"Both" stays 0.** |
| 2 | CG-active, protection flag | no | yes | §9.4–9.5: front-running; "the metadata-minimization property collapses every one to the blind baseline" | The contrast exists, but its endpoint is integrity (front-running success), not inference of the workflow. Code yes, with purpose `workflow_integrity` (new) or `query_workflow_privacy`. | If `query_workflow_privacy`: the denominator grows by 1, and utility is not located. **"Both" stays 0.** |
| 3 | FAY-network, protection flag | no | yes | 2606.30119v1 §6.1–6.3: stealth/undetected configurations contrasted with standard ones | The stealth modes are agent-side evasion of site fingerprinting, i.e. identity obfuscation. Suggest yes / `identity_obfuscation`. | Identity-obfuscation settings +1; outside the privacy denominator. |
| 4 | FAY-combined, protection flag | no | yes | Same paper, §6–7 | As #3. | As #3. |
| 5 | ATR-main, protection flag | yes | no | 2610.32092v1 §4.1: every substitute model runs under the deceptive prompt; the comparisons are between methods, not between spoofed and unspoofed | The coder's reading matches the source: there is no unspoofed baseline in this setting. Suggest no. | Identity-obfuscation settings −1. |
| 6 | ATR-budget, protection flag | yes | no | §4.2, Table 3: a budget sweep under spoofing | As #5. Suggest no. | Identity-obfuscation settings −1. |
| 7 | T1, transfer relation | retained | extended | Table 2 row 1 already says that "tool bursts, model waits and task intervals are different units" | Under the codebook definition, an added Agent execution condition is `extended`. Suggest extended, or keep retained and state why the units are only a mapping detail. | Table 2 row 1 label changes. No headline claim depends on T1. |

If all seven of the coder's codes are adopted, these counts change:

- **Protection-flag counts.** Settings without a protection comparison go 35 → 33.
- **Identity-obfuscation settings.** 3 → 3 (ATR −2, FAY +2).
- **Privacy denominator.** 4 → 4–6 (items 1–2).
- **Finding 2.** "No setting reports both an adapted attacker and matched utility" holds under
  every combination.

After adjudication, update the counts in §2.2, §8.2, S5.1 and Table 2 (if T1 changes).
