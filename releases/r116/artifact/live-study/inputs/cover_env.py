"""Support-ticket fixture, services and cover arms for the executed-cover replay.

The six business actions and the one-to-three prerequisite checks follow the
paper's Section 7 workload. Each business action is served by a named service
(destination); prerequisite checks are served by crm/policy/orders. The
observer sees the destination of every TLS connection and the ciphertext
record lengths, never plaintext or state.
"""
import copy
import json
import random

ACTIONS = ["refund", "address_update", "escalation", "replacement", "cancellation", "receipt"]
ACTION_SERVICE = {
    "refund": "payments",
    "receipt": "billing",
    "address_update": "crm",
    "escalation": "helpdesk",
    "replacement": "shipping",
    "cancellation": "orders",
}
CHECKS = {"account": "crm", "policy": "policy", "approval": "policy", "status": "orders"}
# Read-only endpoint at each business service; used by the read-cover arm.
READ_ENDPOINT = {
    "payments": "payment_history",
    "billing": "invoice_lookup",
    "crm": "profile_lookup",
    "helpdesk": "ticket_history",
    "shipping": "shipment_tracking",
    "orders": "order_status",
}


def make_fixture(rng, task_id):
    orders = {}
    for k in range(3):
        oid = f"O{task_id}-{k}"
        orders[oid] = {
            "status": "delivered" if k < 2 else "pending",
            "amount": rng.randint(15, 400),
            "address": "home",
            "refunded": 0,
            "replacements": 0,
            "receipt_sent": False,
        }
    return {
        "customer": {"address": "home", "compensation_quota": 1, "escalated": False},
        "orders": orders,
        "ledger": [],
    }


def make_task(rng, task_id, action):
    fx = make_fixture(rng, task_id)
    pending = [o for o, v in fx["orders"].items() if v["status"] == "pending"]
    delivered = [o for o, v in fx["orders"].items() if v["status"] == "delivered"]
    target = pending[0] if action == "cancellation" else rng.choice(delivered)
    checks = rng.sample(sorted(CHECKS), rng.randint(1, 3))
    return {
        "task_id": task_id,
        "action": action,
        "target": target,
        "checks": checks,
        "fixture": fx,
        "ticket_len": rng.randint(300, 1400),
    }


def apply_action(state, action, order_id):
    """Apply a business action; return (ok, response_body)."""
    o = state["orders"].get(order_id)
    c = state["customer"]
    if action == "refund":
        if c["compensation_quota"] <= 0 or o is None or o["refunded"]:
            return False, {"error": "compensation_quota_exhausted"}
        c["compensation_quota"] -= 1
        o["refunded"] = o["amount"]
        state["ledger"].append(("refund", order_id, o["amount"]))
        return True, {"refund_id": f"R-{order_id}", "amount": o["amount"]}
    if action == "address_update":
        c["address"] = "new"
        for v in state["orders"].values():
            if v["status"] == "pending":
                v["address"] = "new"
        return True, {"address": "updated"}
    if action == "escalation":
        c["escalated"] = True
        return True, {"escalation_id": f"E-{order_id}"}
    if action == "replacement":
        if o is None or o["status"] != "delivered" or c["compensation_quota"] <= 0:
            return False, {"error": "not_eligible"}
        c["compensation_quota"] -= 1
        o["replacements"] += 1
        state["ledger"].append(("replacement", order_id, c["address"]))
        return True, {"shipment": f"S-{order_id}", "address": c["address"]}
    if action == "cancellation":
        if o is None or o["status"] != "pending":
            return False, {"error": "not_pending"}
        o["status"] = "cancelled"
        state["ledger"].append(("cancel", order_id, 0))
        return True, {"cancelled": order_id}
    if action == "receipt":
        if o is None:
            return False, {"error": "no_order"}
        o["receipt_sent"] = True
        return True, {"receipt": f"RC-{order_id}"}
    raise ValueError(action)


def reference_final_state(task):
    s = copy.deepcopy(task["fixture"])
    apply_action(s, task["action"], task["target"])
    return s


def pick_decoy(rng, task):
    """A plausible decoy: another action class on another object of the same customer."""
    action = rng.choice([a for a in ACTIONS if a != task["action"]])
    others = [o for o in task["fixture"]["orders"] if o != task["target"]]
    if action == "cancellation":
        cand = [o for o in task["fixture"]["orders"]
                if task["fixture"]["orders"][o]["status"] == "pending"]
        target = rng.choice(cand)
    else:
        target = rng.choice(others)
    return action, target


def body(obj, filler_len):
    """JSON body with randomized supplementary content, as in the paper's fixtures."""
    obj = dict(obj)
    obj["supplementary"] = "x" * filler_len
    return json.dumps(obj).encode()
