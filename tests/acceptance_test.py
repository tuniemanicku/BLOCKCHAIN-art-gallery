"""Automated run of the official tests T1-T14 against a real 3-node cluster.

The test uses an isolated runtime directory and its own ports (9101-9103), so it
does not touch the demo environment.

    python tests/acceptance_test.py
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["SELLART_HOME"] = tempfile.mkdtemp(prefix="sellart-test-")

from sellart import operations as ops                          # noqa: E402
from sellart.client.node_client import NodeClient               # noqa: E402
from sellart.client.wallets import create_wallet, find_wallet   # noqa: E402
from sellart.config import ADMIN_WALLET_NAME, save_cluster_config  # noqa: E402
from sellart.launcher import reset_environment                  # noqa: E402

TEST_NODES = {"A": "http://127.0.0.1:9101", "B": "http://127.0.0.1:9102", "C": "http://127.0.0.1:9103"}
processes = {}
results = []


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def start_node(node_id):
    log_file = open(Path(os.environ["SELLART_HOME"]) / f"node-{node_id}.log", "a")
    processes[node_id] = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "manage.py"), "node", node_id],
        stdout=log_file, stderr=subprocess.STDOUT, env=os.environ.copy())


def wait_until(condition, timeout=15.0, step=0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def check(test_id, description, condition, detail=""):
    results.append((test_id, condition))
    print(f"  [{'PASS' if condition else 'FAIL'}] {test_id}: {description} {detail}")


def state(asset_id, node="Auto"):
    _, asset = client.asset(asset_id, node)
    return (asset["owner_name"], asset["status"]) if asset else None


def issue(owner, title):
    payload = ops.issue_payload(admin.public_key, owner.public_key, title, "Test Artist", "2026-11-22", 1000)
    result = client.submit(admin.sign(payload))
    assert result.ok, result.message
    return payload["asset_id"]


def transfer_op(owner, asset_id, recipient, node="Auto"):
    _, asset = client.asset(asset_id, node)
    return owner.sign(ops.transfer_payload(owner.public_key, asset_id, asset["version"], recipient.public_key))


def redeem_op(owner, asset_id):
    _, asset = client.asset(asset_id)
    return owner.sign(ops.redeem_payload(owner.public_key, asset_id, asset["version"]))


def all_nodes_agree(asset_id, expected):
    return all(state(asset_id, node) == expected for node in TEST_NODES)


def set_partition(groups):
    for group in groups:
        others = [n for n in TEST_NODES if n not in group]
        for node in group:
            client.set_partition(node, others)


# --------------------------------------------------------------------------
# Scenario
# --------------------------------------------------------------------------
def main():
    global client, admin
    reset_environment()
    admin = find_wallet(ADMIN_WALLET_NAME)
    config = save_cluster_config(admin.public_key, TEST_NODES)
    client = NodeClient(config)
    for node_id in TEST_NODES:
        start_node(node_id)
    assert wait_until(lambda: any((client.status(n) or {}).get("role") == "LEADER" for n in TEST_NODES)), \
        "no leader elected"
    print("cluster ready")

    users = {}
    for name in ("Alice", "Bob", "Charlie"):
        users[name] = create_wallet(name)
        result = client.submit(users[name].sign(ops.register_user_payload(users[name].public_key, name)))
        assert result.ok, result.message
    alice, bob, charlie = users["Alice"], users["Bob"], users["Charlie"]

    # T1 / T2
    a1 = issue(alice, "A1")
    check("T1", "A1 created for Alice, ACTIVE", state(a1) == ("Alice", "ACTIVE"))
    check("T2", "owner of A1 is Alice", client.asset(a1)[1]["owner_name"] == "Alice")

    # T3
    r = client.submit(transfer_op(alice, a1, bob))
    check("T3", "Alice -> Bob succeeds", r.ok and state(a1) == ("Bob", "ACTIVE"), r.message)

    # T4: Charlie signs a transfer of A1 to himself
    r = client.submit(transfer_op(charlie, a1, charlie))
    check("T4", "Charlie's transfer rejected", r.result == "REJECTED" and state(a1) == ("Bob", "ACTIVE"),
          r.message)

    # T5
    r = client.submit(redeem_op(bob, a1))
    check("T5", "Bob redeems A1", r.ok and state(a1) == ("Bob", "REDEEMED"), r.message)

    # T6
    _, asset = client.asset(a1)
    r1 = client.submit(bob.sign(ops.redeem_payload(bob.public_key, a1, asset["version"])))
    r2 = client.submit(bob.sign(ops.transfer_payload(bob.public_key, a1, asset["version"], charlie.public_key)))
    check("T6", "second redeem and transfer rejected",
          r1.result == r2.result == "REJECTED" and state(a1) == ("Bob", "REDEEMED"),
          f"{r1.message} | {r2.message}")

    # T7
    a2 = issue(alice, "A2")
    _, asset = client.asset(a2)
    payload = ops.transfer_payload(alice.public_key, a2, asset["version"], bob.public_key)
    r_unsigned = client.submit(ops.signed(payload, None))
    r_foreign = client.submit(ops.signed(payload, charlie.private_key))
    saved_operation = alice.sign(payload)
    r_ok = client.submit(saved_operation)
    check("T7", "unsigned + foreign signature rejected, Alice's signature accepted",
          r_unsigned.result == "REJECTED" and r_foreign.result == "REJECTED" and r_ok.ok
          and state(a2) == ("Bob", "ACTIVE"),
          f"{r_unsigned.message} | {r_foreign.message}")

    # T8
    r = client.submit(saved_operation)
    check("T8", "replayed operation rejected", r.result == "REJECTED" and state(a2) == ("Bob", "ACTIVE"),
          r.message)

    # T9
    a3 = issue(alice, "A3")
    client.submit(transfer_op(alice, a3, bob))
    client.submit(transfer_op(bob, a3, charlie))
    client.submit(redeem_op(charlie, a3))
    history = client.history(a3)
    types = [h["type"] for h in history]
    fields_ok = all(h["op_id"] and h["asset_id"] == a3 for h in history)
    check("T9", "history ISSUE, TRANSFER, TRANSFER, REDEEM",
          types == ["ISSUE", "TRANSFER", "TRANSFER", "REDEEM"] and fields_ok
          and state(a3) == ("Charlie", "REDEEMED"), str(types))

    # T10: independent verifier program
    verifier = subprocess.run([sys.executable, str(PROJECT_ROOT / "verifier" / "verify_chain.py"),
                               "--asset", a3], capture_output=True, text=True, env=os.environ.copy())
    check("T10", "independent verifier confirms Charlie / REDEEMED",
          verifier.returncode == 0 and "owner = Charlie  status = REDEEMED" in verifier.stdout
          and "SAME owner" in verifier.stdout)

    # T11: transfer via node A, read from B and C
    a4 = issue(alice, "A4")
    r = client.submit(transfer_op(alice, a4, bob), node="A")
    time.sleep(0.5)
    check("T11", "transfer via A visible on B and C",
          r.ok and state(a4, "B") == state(a4, "C") == ("Bob", "ACTIVE"), r.message)

    # T12: stop node A, transfer via B, confirm via C, restart A
    client.shutdown("A")
    processes["A"].wait(timeout=10)
    r = client.submit(transfer_op(bob, a4, charlie, node="B"), node="B")
    confirmed = wait_until(lambda: state(a4, "C") == ("Charlie", "ACTIVE"), timeout=5)
    start_node("A")
    synced = wait_until(lambda: state(a4, "A") == ("Charlie", "ACTIVE"), timeout=20)
    check("T12", "works with A down, A resynchronises after restart",
          r.ok and confirmed and synced, r.message)

    # T13: two conflicting, correctly signed operations sent concurrently via A and B
    a5 = issue(alice, "A5")
    wait_until(lambda: all_nodes_agree(a5, ("Alice", "ACTIVE")))
    op_to_bob = transfer_op(alice, a5, bob)
    op_to_charlie = transfer_op(alice, a5, charlie)
    outcome = {}
    threads = [threading.Thread(target=lambda: outcome.update(bob=client.submit(op_to_bob, "A"))),
               threading.Thread(target=lambda: outcome.update(charlie=client.submit(op_to_charlie, "B")))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    successes = [k for k, v in outcome.items() if v.ok]
    winner = successes[0].capitalize() if len(successes) == 1 else None
    agree = wait_until(lambda: all_nodes_agree(a5, (winner, "ACTIVE")), timeout=5) if winner else False
    check("T13", "exactly one conflicting transfer wins", len(successes) == 1 and agree,
          " | ".join(f"{k}: {v.result} {v.message}" for k, v in outcome.items()))

    # T14: partition A | B,C, conflicting transfers on both sides, then heal
    a6 = issue(alice, "A5' (T14)")
    wait_until(lambda: all_nodes_agree(a6, ("Alice", "ACTIVE")))
    op_to_bob = transfer_op(alice, a6, bob)
    op_to_charlie = transfer_op(alice, a6, charlie)
    set_partition([["A"], ["B", "C"]])
    time.sleep(3)
    r_a = client.submit(op_to_bob, "A")
    r_b = client.submit(op_to_charlie, "B")
    set_partition([["A", "B", "C"]])
    converged = wait_until(lambda: len({state(a6, n) for n in TEST_NODES}) == 1
                           and state(a6, "A")[1] == "ACTIVE", timeout=20)
    final_states = {n: state(a6, n) for n in TEST_NODES}
    check("T14", "single canonical owner after healing the partition", converged,
          f"A: {r_a.result} ({r_a.message}) | B: {r_b.result} | final {final_states}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        for process in processes.values():
            process.kill()
    sys.exit(exit_code)
