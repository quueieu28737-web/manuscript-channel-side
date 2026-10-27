# A3: forward-citation context pilot

Search and inspection date: 2026-10-27. This is an exploratory, source-scoped pilot, not the proposed prevalence study. It has two seeds (Early Bird and KVGov), five purposefully selected citing papers, and six verified citation edges. Search-engine indexing and text availability determined selection; no sampling frame, random selection, or double coding was established. A zero count below cannot be read as a population rate. The Semantic Scholar citations API could not be accessed via the available web tool. OpenAlex returned a partial indexed list, as detailed below.

## Question and coding

Question: does a citing work carry Early Bird's approximately 6 ms / 4% semantic-cache anonymization overhead to a different prefix-cache defense, or KVGov's approximately 1.3 µs HMAC microbenchmark to a complete defended system? An affirmative judgment requires the citing work to attribute the numerical value to the seed and use it for a different configuration or cost object. A citation without that number is **not evaluated for this misuse**, not evidence that all of its other uses are sound. A separately observed possible source-version or metric mismatch is recorded as unresolved, rather than automatically classified as misuse.

Seed anchors:

- Early Bird, arXiv [2409.20002v1](https://arxiv.org/html/2409.20002v1), §5.1–5.2, Table 6: the K-prefix evaluation uses a simulated oracle; K=1 lists 100% recovery and 92.8% accuracy. Its 6 ms and approximately 4% concern semantic-cache de-identification. The later [v5](https://arxiv.org/html/2409.20002v5), §IV-B and §V-B, reports 89.0% average measured token recovery and semantic-cache anonymization overhead, respectively. These versions and outcomes cannot simply be interchanged.
- KVGov, arXiv [2608.09225v1](https://arxiv.org/html/2608.09225v1), §5.9, Table 9: +1.3 µs median is a Python HMAC key-derivation microbenchmark; §5.9 separately notes that lost cross-principal reuse is an efficiency cost left for workload-specific measurement.

## Inspected edges

| Citing paper and cited seed | Exact locator and observed context | Target-cost reuse judgment |
|---|---|---|
| [KVGov v1](https://arxiv.org/html/2608.09225v1) → Early Bird | §1 and §3.2 discuss 100% token reconstruction; §3.5 says attack goals and priors change comparability. The cited reference does not identify an Early Bird version or table. | No reuse of the 6 ms / 4% semantic-cache cost found in the inspected contexts. Its 100% statement could be read against v1's simulated K=1 recovery rather than v5's 89.0% measured recovery; the citation does not identify the supporting condition. Treat as **metric/source-version ambiguity**, not a demonstrated false citation or cost transfer. |
| [Time Will Tell v1](https://arxiv.org/html/2412.15431v1) → Early Bird | §IX-A.3 and reference [11] cite KV/semantic-cache attacks as related work and contrast their prefill signal with autoregressive decoding. | The cited passage does not borrow the semantic-cache cost. Not an assessable numeric-cost reuse. |
| [Characterizing Contention-Induced Reliability Collapse v1](https://arxiv.org/html/2609.06853v1) → Early Bird | §I, §II-B and reference [2] discuss cache-state inference and report the classifier TPR/FPR operating point, not the defense-cost figure. | No assessed reuse of the 6 ms / 4% cost. |
| Same paper → KVGov | §I, §II-C and reference [5] describe hardware cold/cached timing ratios and distinguish the simulated audit-scheduler analysis. | It does not use the 1.3 µs HMAC value as end-to-end defended cost in the inspected contexts. |
| [Foundation Models for Autonomous Driving Systems: An Initial Roadmap](https://orbilu.uni.lu/bitstream/10993/68181/1/3807455.pdf) → Early Bird | §4.2, p.16 and ref. [177] cite it, with another work, as an example of KV-cache optimization vulnerabilities. The search-indexed primary PDF context was available although a subsequent full PDF fetch timed out. | No numeric defense-cost transfer in the available passage; complete citation-context coverage remains unverified. |
| [PrefixWall v2](https://arxiv.org/html/2603.10726v2) → Early Bird | §1, §2.3 and §6 cite it for prefix-cache prompt recovery and the larger shared-prefix-granularity mitigation. | No transfer of the 6 ms/4% semantic-cache processing cost in the inspected citation contexts. This work is absent from the seven-entry OpenAlex seed list. |

These are citation edges, not six independent citing papers. Citation context and source version were checked in the linked primary HTML, except the Roadmap PDF passage as noted. The inspection does not assess all claims in these works.

## OpenAlex indexed-list retrieval

On 2026-10-27 UTC, the web tool could not access OpenAlex, Crossref or Semantic Scholar API URLs, and the sandboxed shell failed to connect through its proxy. A separately authorized, read-only external request succeeded via OpenAlex. `docs/r35_fetch_openalex.py` records the three DOI lookups, citing-work queries and exact UTC retrieval timestamp in `docs/R35-openalex-pilot.json` (public metadata only). The preprint and journal DOI both resolve to OpenAlex work `W4415284287`: the response says **7 indexed citing works** and returns all seven in one 200-item page. KVGov (`W7202173108`) has **0 indexed citing works** in that snapshot. These are counts in this index at retrieval, not estimates of all actual citing papers. Indeed, the verified 2609.06853v1 → KVGov edge above is absent from the reported zero, and KVGov v1 and Time Will Tell v1 cite Early Bird but do not appear in its seven-work list. The index therefore demonstrably misses relevant citation edges; deduplication across alternative versions and other indexes is required before any rate calculation.

| OpenAlex Early Bird citing work | Retrieval outcome |
|---|---|
| [Foundation Models for Autonomous Driving Systems: An Initial Roadmap](https://doi.org/10.1145/3807455) | Citation and local context verified in indexed source passage above; full source fetch timed out. |
| [SniffLlama educational-environment poster](https://doi.org/10.1145/3779208.3804883) | Publisher PDF not accessible through the web tool; a secondary index lists Early Bird among references, but citing passage remains **unknown**. |
| [Profit-aware deployment of inference chains](https://doi.org/10.1016/j.comnet.2026.112609) | Publisher search excerpt available; exact citing passage unavailable and remains **unknown**. |
| [InputSnatch, published chapter](https://doi.org/10.1007/978-981-92-4805-6_32) | Chapter full text unavailable. The accessible [2024 arXiv v2](https://arxiv.org/html/2411.18191v2) lacks the seed title/identifier, so its text cannot establish the published chapter's citation context; **unknown**. |
| [On-device agent personalization SoK](https://doi.org/10.1016/j.hcc.2026.100428) | Publisher returned HTTP 403; citing passage **unknown**. |
| [LLM latency equalization study](https://doi.org/10.5753/sbseg.2026.29354) | Primary PDF endpoint inaccessible via the web tool; citing passage **unknown**. |
| [Machine unlearning security survey](https://doi.org/10.1016/j.cosrev.2026.101080) | Citing passage not retrieved; **unknown**. |

The six unknowns are not negative judgments. This indexed list plus the independently located examples are insufficient to estimate prevalence and do not represent the requested twenty families.

## Decision for the manuscript

The source records establish that the illustrated cost and protection measurements refer to different mechanisms or cost objects. They do **not** by themselves establish that a later author or practitioner made the hypothesized attribution error. The pilot finds no qualifying 6 ms/4% or 1.3 µs transfer in the inspected passages. A 100–200 citation prevalence estimate cannot be computed from this convenience sample or from unsuccessful API access.

Recommended phrasing: “A deployment comparison must keep Early Bird's semantic-cache processing cost separate from its prefix-recovery mitigation, and KVGov's HMAC microcost separate from reuse losses. These source-bound distinctions identify measurements needed for a deployment decision; the present audit does not estimate downstream citation errors.” The ambiguity in the KVGov/Early Bird citation is suitable for a cautious provenance note only if both versions and outcome definitions are included; it is not evidence of cost misuse.

## Twenty-family indexed coverage

OpenAlex single-page retrieval completed at 2026-10-27T00:42:54.785542+00:00. All 20 frozen family identifiers resolved with matching titles; each citing query returned a count and all records in its first page. This is coverage of index lookups, not full citation coverage or full-text review. Zero means zero indexed by that endpoint, not no real citations. The same DOI and title across sources must be merged before analysis. The JSON retains exact seed identifiers, metadata, query URLs, counts and per-work links. Publisher and preprint variants are not guaranteed to be merged.

| Family key | OpenAlex seed | Indexed citing works | Context verification |
|---|---|---:|---|
| addagada2026kvgov | [W7202173108](https://openalex.org/W7202173108) | 0 | 0 indexed, but Abu Bakar paper independently cites it |
| carlini2024remote | [W4404261774](https://openalex.org/W4404261774) | 1 | PANShield chapter indexed; full citation context unavailable |
| chen2026sparleak | [W7215117480](https://openalex.org/W7215117480) | 0 | 0 indexed; unindexed edges remain possible |
| chu2025safekv | [W4416858267](https://openalex.org/W4416858267) | 0 | 0 indexed; unindexed edges remain possible |
| dangol2026workflow | [W7163886269](https://openalex.org/W7163886269) | 0 | 0 indexed; unindexed edges remain possible |
| earlybird2025 | [W4415284287](https://openalex.org/W4415284287) | 7 | Roadmap passage confirmed; six indexed candidates unknown; four other citing papers found outside index |
| gao2025iknow | [W4415110284](https://openalex.org/W4415110284) | 0 | 0 indexed; unindexed edges remain possible |
| hadad2026shape | [W7141170122](https://openalex.org/W7141170122) | 0 | 0 indexed; unindexed edges remain possible |
| hornetz2026tdxray | [W7166823931](https://openalex.org/W7166823931) | 0 | 0 indexed; unindexed edges remain possible |
| jeong2026wra | [W4416712246](https://openalex.org/W4416712246) | 0 | 0 indexed; unindexed edges remain possible |
| lee2026otro | [W7165053408](https://openalex.org/W7165053408) | 0 | 0 indexed; unindexed edges remain possible |
| netecho2025 | [W7102666194](https://openalex.org/W7102666194) | 0 | 0 indexed; unindexed edges remain possible |
| pouryousef2026traffic | [W7214803269](https://openalex.org/W7214803269) | 0 | 0 indexed; unindexed edges remain possible |
| spliceleak2026 | [W7165618382](https://openalex.org/W7165618382) | 0 | 0 indexed; unindexed edges remain possible |
| timewilltell2024 | [W4405714365](https://openalex.org/W4405714365) | 0 | 0 indexed; unindexed edges remain possible |
| uitraces2026 | [W7161240930](https://openalex.org/W7161240930) | 0 | 0 indexed; unindexed edges remain possible |
| wei2024speculation | [W4404355769](https://openalex.org/W4404355769) | 0 | 0 indexed; unindexed edges remain possible |
| whisperleak2025 | [W4416020692](https://openalex.org/W4416020692) | 0 | 0 indexed; unindexed edges remain possible |
| wu2026cacheprune | [W7162302835](https://openalex.org/W7162302835) | 0 | 0 indexed; unindexed edges remain possible |
| zhu2026turing | [W7154268333](https://openalex.org/W7154268333) | 0 | 0 indexed; unindexed edges remain possible |

The eight indexed citing-work records have distinct OpenAlex work IDs (seven Early Bird and one Carlini/Nasr). One indexed Early Bird work overlaps the independently found Roadmap. Together with four other independently verified citing papers, this gives 12 distinct candidates or citing papers, but 7 candidate records remain context-unknown. Only six seed-to-citing-paper edges, across five actual citing papers, have inspected primary-source passages. Numbers cannot be used to estimate citation misuse. PANShield’s DOI is https://doi.org/10.1007/978-3-032-25267-8_18; its citing paragraph could not be retrieved.
