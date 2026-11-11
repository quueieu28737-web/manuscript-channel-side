# Independent second-coder packet (R110)

You are asked to code a small set of decisions that the SoK's headline claims
depend on. Work from the cited source documents only. Please do **not** read the
SoK manuscript, its supplement, `author-key.csv`, or any AI output before you
have finished all three sheets. AI tools may not be used for this task.

Expected effort: 33 required decisions (Sheets B and C) plus 88 recommended
decisions (Sheet A). Each row gives the source version, URL and the section or
table where the setting is described.

For every code, write the page, section or a short quote that supports it in
`evidence_quote_or_page`. If the source does not let you decide, use the
`unclear` code and explain why in `notes`. Do not guess.

---

## Sheet B — interventions (required, 9 settings × up to 3 fields)

Each row is a setting in which the source applies some intervention.

**B1_intervention_purpose** — what is the intervention trying to achieve?

| Code | Meaning |
|---|---|
| `query_workflow_privacy` | Hide a user's query, task or workflow from a communication observer. |
| `identity_obfuscation` | Hide or spoof *which* agent/model is running. |
| `adversarial_agent_blocking` | Detect, deceive or block an Agent that is itself the adversary. |
| `other` | None of the above (explain in notes). |
| `unclear` | The source does not let you decide. |

Code **B2** and **B3** only for rows that you coded `query_workflow_privacy`.
For other rows leave them empty.

**B2_protected_condition_adaptation** — does the source train or refit the
attacker on traffic produced *under the intervention*, or run an explicitly
adaptive attack against it?

| Code | Meaning |
|---|---|
| `located` | Yes, the inspected source text or code shows this for this setting. |
| `not_located` | The attack is not shown to be trained/refit on protected traffic. |
| `unclear` | Cannot decide from the source. |

**B3_original_task_utility_same_intervention** — does the source measure how
well the user's *original task* is still accomplished (answer quality, task
success, etc.) under *this same* intervention? Bytes, latency, or extra
queries alone do **not** count. A utility number from a *different* condition
of the same paper does **not** count.

| Code | Meaning |
|---|---|
| `located` | Yes, measured for this intervention. |
| `not_located` | Not measured for this intervention. |
| `unclear` | Cannot decide from the source. |

---

## Sheet C — transfer relations (required, 6 rows)

Each row states an established traffic-analysis evaluation condition (with its
classical anchors) and a proposed mapping to Agent execution. Choose one label:

| Code | Meaning |
|---|---|
| `retained` | The classical evaluation obligation still applies to Agents as stated. |
| `extended` | It applies, but Agents add an extra execution condition that must also be evaluated. |
| `untested_generalization` | The mapped Agent evidence does not test whether the classical *performance* result carries over. |
| `access_mismatch` | The classical result relies on observation rights that the proposed Agent observer does not have. |
| `unclear` | Cannot decide. |

Give a one-sentence reason.

---

## Sheet A — all 44 settings (recommended)

**A1_access_class** — what does the evaluated observer have access to?

| Code | Meaning |
|---|---|
| `transit` | Passive network metadata on a link (sizes, timing, destinations), no plaintext. |
| `recipient` | A contacted service reading requests addressed to it (headers, commands, arguments). |
| `active` | The observer chooses probes, challenges, planted content or offered actions. |
| `derived_preference` | An analysis of an inferred preference representation, not a new observation. |
| `unclear` | Cannot decide. |

**A2_has_protection_comparison** — does this setting compare a protected
condition against an unprotected one? `yes` / `no` / `unclear`.

---

## Returning the packet

Return the three CSV files. The author then runs `agreement.py`, which
reports raw agreement and Cohen's κ per field and lists every disagreement.
Disagreements are resolved by discussion against the cited source passage,
and the before/after values and reasons are recorded; neither coder's code
is overridden by vote.
