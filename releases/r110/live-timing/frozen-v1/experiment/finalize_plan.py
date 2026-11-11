"""Resolve draft ambiguities before any formal outcomes exist."""
import json,sys
import numpy as np
from common import H,load,save,sha,now
from analyze import paired_tost

def main():
    from scipy.stats import multinomial
    n=120;q=.2;power05=power006=0.
    for plus in range(n+1):
        for minus in range(n-plus+1):
            prob=multinomial.pmf([plus,minus,n-plus-minus],n,[q/2,q/2,1-q])
            pv=paired_tost(plus,minus,n)
            if pv<.05:power05+=prob
            if pv<.05/6:power006+=prob
    power={'utc':now(),'n':n,'discordance_probability':q,'true_difference':0.,'margin':.1,
           'method':'Exact planning-probability sum under assumed multinomial; paired t-TOST rejection rule',
           'equivalence_power_alpha_05':power05,
           'equivalence_power_holm_first_alpha_05_over_6':power006,
           'note':'Planning distribution, not empirical power. Fixed 3000-episode budget retained; unresolved equivalence is an allowed outcome.'}
    save(H/'verification/design-power.json',power)
    p=load(H/'vendor/analysis-plan-draft.json');p['version']='L-live-timing-v1'
    p['status']='FINAL BEFORE FORMAL COLLECTION; freeze.json and remote readback are required'
    p['questions']['Q3']='Does planner-generated cover remove an accuracy advantage of this timing attack suite over validation-selected size-only attacks, within +/-10 points? Also report true/shadow role discrimination and chain candidate ambiguity.'
    p['collection']['same_connection_calls']='Serialized by service-specific locks. Seven MCP sessions are shared and reused; different destinations and planner inference remain concurrent. This restriction defines unambiguous TLS-record call windows and does not test unrestricted within-destination multiplexing.'
    p['collection']['arm_order']='All none episodes first. Then rotate unmatched,gdm_live,concurrent,shadow by the original unit list index; one model at a time, workers=1.'
    p['collection']['capture_gate']='All relay ingress TLS record types, lengths and counts must match independent Npcap TCP reassembly; report median/p99 timing error. Failed capture or unknown request stops collection, with no silent replacement.'
    p['collection']['phase_gates']='Push frozen plan/code before none; verify completed none and its capture; extract TRAIN-only pools with frozen script, hash and push/read back before cover.'
    p['timing_layers']['L2']='perf_counter_ns at relay completion of each encrypted TLS record (outer type 23). Connection initialization precedes call windows; outer type alone is not claimed to identify application plaintext. Each call window is nonoverlapping on its own connection; cross-connection overlap is allowed.'
    p['timing_layers']['L3']='Npcap captures both relay ingress legs. Independent TCP sequence reassembly reconstructs complete records, then matches types/lengths/counts and record-completion epoch times. Relay saves a simultaneous epoch/performance pair for each observed chunk.'
    p['observer']='Destination, bidirectional encrypted call bytes and relay-record completion timing; evaluator-supplied episode/call windows and labelled TRAIN calls. Same-connection windows serialized. First ticket known honest only in none/unmatched/gdm_live/concurrent; in shadow the first call role is UNKNOWN. No request identifiers, private role, operation, object, state, model link or token counts enter attack features.'
    p['shadow_controls']={'action_sampling':'All six classes, independently of the real class, including same-class tickets.',
                          'start':'Independent deterministic seed+500000; 50% shadow-first; later chain starts offset U(.2,1.5) after first chain ticket returns, matching the written draft control flow.',
                          'prior_baselines':{'six_class':1/6,'perfect_unordered_pair_of_independent_uniform_labels':7/12},
                          'interpretation':'Random order does not prove role indistinguishability. Recovering two candidate chains can still reveal task information.'}
    p['attacks']['size_only']=['byte_LR','byte_RF','frozen','position_last','position_penultimate']
    p['attacks']['timing']=['timing_size','gap_detector_strip','label_free_gmm_strip','context_strip','joint_decoding']
    p['attacks']['shadow_specific']='Beam-64 causal two-chain partition with no within-chain call overlap; transition log-gap model fitted on none TRAIN, no true role in inference. Clean-chain task classifier plus LR real-chain selector fitted on labelled shadow TRAIN. Chronological first chain is not assumed real; validation-selected as one candidate.'
    p['attacks']['configuration']='Original M3 byte153 and S11 timing49/context34 feature definitions; LR C=1/max_iter=3000/random102, RF300/n_jobs2/random102. Call detectors balanced classes, validation F1 then precision then LR then higher threshold; thresholds .05:.05:.95. GMM2 n_init5/log10 gaps, fit unlabelled condition TRAIN only. First event has no preceding gap and GMM leaves it unstripped as a heuristic, not a known honest role. Joint decoder evaluates all 0/1/2 removals with prior [.02,.49,.49], LR/RF context probabilities, lambda[0,.5,1,2,4] or marginal; selected on validation task accuracy. Original bounded-removal decoder is retained in shadow and complemented by chain separation.'
    p['attacks']['fitting']='Train per arm; validate for attack/threshold selection; ties to declared order with size first. No test-driven attack selection. Fitted conditional bootstrap intervals do not include model/refitting/selection uncertainty. Old M3/S11 fixture outcomes have already been seen; this is a new timing-layer collection on reused fixtures, not an untouched-workload confirmation.'
    p['tests']['E_primary_equivalence']='Same six contrasts. Paired t-TOST +/-0.1 on fixture-level {-1,0,1} accuracy differences; df=119, max of one-sided p values; Holm across six. Finite-sample approximation. At all ties use boundary no-discordance probability .9^120, not p=0. Both models must pass to report tested attack-suite accuracy increment within the margin; not universal cover or role indistinguishability. Report discordant counts and power limitations.'
    p['tests']['descriptive']='Real-chain latency, union observation duration, extra model calls/tokens, unique connection bytes, true/shadow role error, chain partition fidelity (evaluation labels only), same honest path as none, task/state success, timing comparison. Timing errors and roles are not added to a new uncorrected superiority family.'
    p['power_note']=power
    p['interpretation_rules']['shadow_pass']='If E passes in both models and C shows decreased size-only task accuracy: report equivalence of tested timing-suite increment within the margin and the remaining task recognition, role performance, and token/latency/byte cost. Do not call all cover indistinguishable.'
    p['implementation_adjustments']=['Service-specific locking prevents overlapping same-TLS-connection call windows while retaining inter-service and inference concurrency.',
        'The shadow-first control removes the known-honest first-call prior in that arm.',
        'Server hold starts when the request body is received; measured client/record duration includes transport and scheduling overhead, so target draws need not equal achieved durations.',
        'Parallel shadow GPU contention is part of this arm; two ordinary inference slots and no concurrent episodes. Model-dependent path changes are outcomes, not discarded samples.']
    p['publication']='Only reviewed synthetic, payload-free features/predictions, JSON pools, plans, code and hashes. Packet captures, raw transcripts, TLS keys and model weights stay private. New public results require current-byte scope review.'
    assert not (H/'experiment/analysis-plan.json').exists()
    save(H/'experiment/analysis-plan.json',p)
    print(json.dumps(power))

if __name__=='__main__':main()
