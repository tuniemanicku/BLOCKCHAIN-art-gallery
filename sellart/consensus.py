"""Raft consensus over a hash-linked chain of blocks.

Why Raft?  It gives exactly the guarantees required by R11-R14:
  * every committed block is stored by a MAJORITY (2 of 3) of nodes      -> replication
  * any majority can keep working when one node fails                    -> fault tolerance
  * a single leader orders all operations, so of two conflicting
    operations the one ordered first wins and the other is rejected     -> deterministic conflicts
  * a minority partition can never commit; after the network heals the
    nodes adopt the majority's chain automatically                      -> no split-brain

Roles: FOLLOWER -> (election timeout) -> CANDIDATE -> (majority of votes) -> LEADER.

Write path: client -> any node -> (forwarded to) leader -> validate -> append block
-> replicate to followers -> majority acknowledged = COMMITTED -> SUCCESS.

All mutable state is protected by `self.lock`. Network calls are always made
WITHOUT holding the lock.
"""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from . import operations as ops
from .ledger import Ledger, OperationRejected
from .storage import NodeStorage

FOLLOWER, CANDIDATE, LEADER = "FOLLOWER", "CANDIDATE", "LEADER"

HEARTBEAT_INTERVAL = 0.15         # leader -> followers, seconds
ELECTION_TIMEOUT = (1.0, 2.0)     # follower waits this long without a leader before an election
RPC_TIMEOUT = 0.5                 # node -> node HTTP timeout
LEADER_LEASE = 0.9                # leader accepts writes only if a majority answered recently
COMMIT_WAIT = 4.0                 # how long a write waits for the majority
LEADER_WAIT = 4.0                 # how long a follower waits for a leader to appear
MAX_ENTRIES_PER_MESSAGE = 50
READ_SYNC_WAIT = 1.0              # how long a follower waits to catch up before answering a read

SUCCESS, REJECTED, FAILED = "SUCCESS", "REJECTED", "FAILED"


def log(node_id: str, message: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} [node {node_id}] {message}", flush=True)


class RaftNode:
    def __init__(self, node_id: str, cluster_config, storage: NodeStorage):
        self.id = node_id
        self.config = cluster_config
        self.peers = cluster_config.peers_of(node_id)        # peer id -> URL
        self.majority = len(cluster_config.nodes) // 2 + 1
        self.storage = storage
        self.lock = threading.RLock()
        self._thread_local = threading.local()  # one HTTP session per thread
        self.running = True

        # Persistent consensus state (survives restarts)
        self.current_term = storage.get_meta("current_term", 0)
        self.voted_for = storage.get_meta("voted_for")
        self.chain = storage.load_blocks()
        if not self.chain:
            genesis = ops.genesis_block(cluster_config)
            storage.append_blocks([genesis])
            self.chain = [genesis]
        self.commit_index = min(storage.get_meta("commit_index", 0), len(self.chain) - 1)

        # Volatile state
        self.role = FOLLOWER
        self.leader_id = None
        self.election_deadline = self._new_election_deadline()
        self.next_index = {}      # leader only: next block to send to each peer
        self.match_index = {}     # leader only: highest block known to be stored by each peer
        self.last_ack = {}        # leader only: time of the last successful answer of each peer
        self.wake_replicator = {peer: threading.Event() for peer in self.peers}
        self.commit_changed = threading.Condition(self.lock)
        self.blocked_peers = set()  # simulated network partition (see set_partition)

        # Two views of the state:
        #   committed_ledger - only committed blocks: this is what clients read
        #   tip_ledger       - all blocks incl. not yet committed: used by the leader to
        #                      validate new operations so two conflicting ones can't both enter
        self.committed_ledger = self._replay(self.commit_index)
        self.tip_ledger = self._replay(len(self.chain) - 1)
        self._save_snapshot()

    # ======================================================================
    # Lifecycle
    # ======================================================================
    def start(self) -> None:
        threading.Thread(target=self._election_timer_loop, daemon=True).start()
        for peer in self.peers:
            threading.Thread(target=self._replicator_loop, args=(peer,), daemon=True).start()
        log(self.id, f"started (term {self.current_term}, {len(self.chain)} blocks, "
                     f"committed up to #{self.commit_index})")

    def stop(self) -> None:
        self.running = False
        for event in self.wake_replicator.values():
            event.set()

    # ======================================================================
    # Client operations
    # ======================================================================
    def submit(self, operation: dict, forwarded: bool = False) -> dict:
        """Entry point for a signed operation sent by a client to this node."""
        with self.lock:
            is_leader = self.role == LEADER
        if is_leader:
            return self._submit_as_leader(operation)
        if forwarded:
            return self._result(FAILED, "this node is no longer the leader, please retry")
        return self._forward_to_leader(operation)

    def _submit_as_leader(self, operation: dict) -> dict:
        with self.lock:
            if not self._has_majority_lease():
                return self._result(
                    FAILED, "no majority of nodes reachable - this node is isolated, "
                            "the operation was not accepted")
            try:
                self.tip_ledger.validate(operation)
            except OperationRejected as error:
                return self._result(REJECTED, str(error))
            block = self._append_new_block(ops.OPERATION, operation=operation)
            term = self.current_term

            # Wait until a majority stores the block (or leadership is lost).
            deadline = time.time() + COMMIT_WAIT
            while self.commit_index < block["index"] and self.current_term == term and self.running:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self.commit_changed.wait(remaining)

            committed = (self.commit_index >= block["index"]
                         and block["index"] < len(self.chain)
                         and self.chain[block["index"]]["hash"] == block["hash"])
            if committed:
                return self._result(SUCCESS, f"committed in block #{block['index']} "
                                             f"(confirmed by a majority of nodes)",
                                    block_index=block["index"])
            return self._result(FAILED, "the operation was not confirmed by a majority in time; "
                                        "its final outcome will be decided by consensus")

    def _forward_to_leader(self, operation: dict) -> dict:
        """Followers pass writes to the leader; wait a moment if an election is running."""
        deadline = time.time() + LEADER_WAIT
        while time.time() < deadline and self.running:
            with self.lock:
                leader = self.leader_id if self.role != LEADER else self.id
            if leader == self.id:
                return self._submit_as_leader(operation)
            if leader and leader not in self.blocked_peers:
                try:
                    response = self._session().post(f"{self.peers[leader]}/operations",
                                                    json={"operation": operation, "forwarded": True,
                                                          "sender": self.id},
                                                    timeout=COMMIT_WAIT + 1)
                    result = response.json()
                    leader_changed_meanwhile = "no longer the leader" in result.get("message", "")
                    if not leader_changed_meanwhile:
                        result["handled_by"] = self.id
                        result["message"] += f" [forwarded to leader {leader}]"
                        return result
                except (requests.RequestException, ValueError):
                    with self.lock:
                        if self.leader_id == leader:
                            self.leader_id = None
            time.sleep(0.2)
        return self._result(FAILED, "no leader reachable from this node (it may be in a minority "
                                    "partition) - the operation was not accepted")

    def _result(self, result: str, message: str, **extra) -> dict:
        with self.lock:
            return {"result": result, "message": message, "handled_by": self.id,
                    "leader": self.leader_id, **extra}

    # ======================================================================
    # Read API (always the COMMITTED state of this node's own chain)
    # ======================================================================
    def status(self) -> dict:
        with self.lock:
            return {
                "node_id": self.id,
                "role": self.role,
                "term": self.current_term,
                "leader": self.leader_id,
                "chain_length": len(self.chain),
                "commit_index": self.commit_index,
                "last_committed_hash": self.chain[self.commit_index]["hash"],
                "blocked_peers": sorted(self.blocked_peers),
            }

    def catch_up_before_read(self) -> None:
        """Read-after-write consistency ("read index" in Raft terms).

        A follower may learn about a freshly committed block a few milliseconds after the
        client already got SUCCESS from the leader. Before answering a read, a follower asks
        the leader for its commit index and waits until it has applied that block itself.
        The answer still comes from this node's own copy of the chain. If the leader is not
        reachable (failure, partition) the node answers immediately with its local state.
        """
        with self.lock:
            if self.role == LEADER or not self.leader_id:
                return
            leader = self.leader_id
        answer = self._rpc(leader, "/raft/commit_index", {})
        if not answer:
            return
        deadline = time.time() + READ_SYNC_WAIT
        with self.lock:
            while self.commit_index < answer["commit_index"] and time.time() < deadline:
                self.commit_changed.wait(deadline - time.time())

    def handle_commit_index(self) -> dict:
        with self.lock:
            return {"term": self.current_term, "commit_index": self.commit_index,
                    "is_leader": self.role == LEADER}

    def committed_chain(self) -> list:
        with self.lock:
            return list(self.chain[: self.commit_index + 1])

    def operation_status(self, op_id: str) -> dict:
        with self.lock:
            for block in self.chain:
                operation = block.get("operation") or {}
                if operation.get("payload", {}).get("op_id") == op_id:
                    committed = block["index"] <= self.commit_index
                    return {"op_id": op_id, "block_index": block["index"],
                            "status": "COMMITTED" if committed else "PENDING"}
        return {"op_id": op_id, "status": "NOT_FOUND"}

    # ======================================================================
    # Simulated network partition (demo of T14)
    # ======================================================================
    def set_partition(self, blocked_peers) -> None:
        """Drop all node-to-node traffic with the given peers (both directions)."""
        with self.lock:
            self.blocked_peers = {p for p in blocked_peers if p in self.peers}
            log(self.id, f"network: blocked peers = {sorted(self.blocked_peers) or 'none'}")

    def is_blocked(self, peer_id: str) -> bool:
        with self.lock:
            return peer_id in self.blocked_peers

    # ======================================================================
    # Raft RPC handlers (called by other nodes)
    # ======================================================================
    def handle_request_vote(self, request: dict) -> dict:
        with self.lock:
            if request["term"] > self.current_term:
                self._become_follower(request["term"])
            last = self.chain[-1]
            candidate_is_up_to_date = (request["last_term"], request["last_index"]) >= (last["term"], last["index"])
            grant = (request["term"] == self.current_term
                     and self.voted_for in (None, request["candidate_id"])
                     and candidate_is_up_to_date)
            if grant:
                self.voted_for = request["candidate_id"]
                self.storage.set_meta(voted_for=self.voted_for)
                self.election_deadline = self._new_election_deadline()
            return {"term": self.current_term, "vote_granted": grant}

    def handle_append_entries(self, request: dict) -> dict:
        with self.lock:
            if request["term"] < self.current_term:
                return {"term": self.current_term, "success": False, "last_index": len(self.chain) - 1}
            if request["term"] > self.current_term or self.role != FOLLOWER:
                self._become_follower(request["term"])
            if self.leader_id != request["leader_id"]:
                self.leader_id = request["leader_id"]
                log(self.id, f"term {self.current_term}: following leader {self.leader_id}")
            self.election_deadline = self._new_election_deadline()

            # The previous block must match exactly (same hash => same history before it).
            prev_index = request["prev_index"]
            if prev_index >= len(self.chain) or self.chain[prev_index]["hash"] != request["prev_hash"]:
                return {"term": self.current_term, "success": False,
                        "last_index": min(prev_index - 1, len(self.chain) - 1)}

            self._store_entries_from_leader(request["entries"])

            last_new_index = prev_index + len(request["entries"])
            if request["leader_commit"] > self.commit_index:
                self._commit_up_to(min(request["leader_commit"], last_new_index))
            return {"term": self.current_term, "success": True, "match_index": last_new_index}

    def _store_entries_from_leader(self, entries: list) -> None:
        for position, block in enumerate(entries):
            index = block["index"]
            if index < len(self.chain) and self.chain[index]["hash"] == block["hash"]:
                continue  # already have it
            if block["hash"] != ops.block_hash(block) or block["prev_hash"] != self.chain[index - 1]["hash"]:
                log(self.id, f"refused corrupted block #{index} from leader")
                return
            if index <= self.commit_index:
                log(self.id, f"refused to overwrite committed block #{index}")
                return
            if index < len(self.chain):
                # Our uncommitted suffix conflicts with the leader's chain -> drop it.
                log(self.id, f"replacing uncommitted blocks from #{index} with the leader's chain")
                self.chain = self.chain[:index]
                self.storage.truncate_from(index)
                self.tip_ledger = self._replay(len(self.chain) - 1)
            new_blocks = []
            for candidate in entries[position:]:
                expected_prev = (new_blocks[-1] if new_blocks else self.chain[-1])["hash"]
                if candidate["hash"] != ops.block_hash(candidate) or candidate["prev_hash"] != expected_prev:
                    break
                new_blocks.append(candidate)
            self.storage.append_blocks(new_blocks)
            for new_block in new_blocks:
                self.chain.append(new_block)
                self._apply_quietly(self.tip_ledger, new_block)
            return

    # ======================================================================
    # Elections
    # ======================================================================
    def _election_timer_loop(self) -> None:
        while self.running:
            time.sleep(0.05)
            with self.lock:
                if self.role == LEADER:
                    self._step_down_if_isolated()
                    continue
                if time.time() < self.election_deadline:
                    continue
                self._become_candidate()
                request = {"term": self.current_term, "candidate_id": self.id,
                           "last_index": self.chain[-1]["index"], "last_term": self.chain[-1]["term"]}
                term = self.current_term
            self._run_election(request, term)

    def _become_candidate(self) -> None:
        self.role = CANDIDATE
        self.current_term += 1
        self.voted_for = self.id
        self.leader_id = None
        self.storage.set_meta(current_term=self.current_term, voted_for=self.id)
        self.election_deadline = self._new_election_deadline()

    def _run_election(self, request: dict, term: int) -> None:
        votes = 1  # our own vote
        with ThreadPoolExecutor(max_workers=len(self.peers)) as pool:
            answers = pool.map(lambda peer: self._rpc(peer, "/raft/vote", request), self.peers)
            for answer in answers:
                if not answer:
                    continue
                with self.lock:
                    if answer["term"] > self.current_term:
                        self._become_follower(answer["term"])
                        return
                if answer.get("vote_granted"):
                    votes += 1
        with self.lock:
            if self.role == CANDIDATE and self.current_term == term and votes >= self.majority:
                self._become_leader()

    def _become_leader(self) -> None:
        self.role = LEADER
        self.leader_id = self.id
        now = time.time()
        for peer in self.peers:
            self.next_index[peer] = len(self.chain)
            self.match_index[peer] = 0
            self.last_ack[peer] = now  # the votes we just received count as fresh answers
        log(self.id, f"term {self.current_term}: became LEADER")
        # A block of the new term lets the leader commit everything before it (Raft rule).
        self._append_new_block(ops.LEADER, info={"note": f"node {self.id} became leader"})

    def _become_follower(self, term: int) -> None:
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            self.storage.set_meta(current_term=term, voted_for=None)
        if self.role != FOLLOWER:
            log(self.id, f"term {self.current_term}: stepping down to FOLLOWER")
        self.role = FOLLOWER
        self.election_deadline = self._new_election_deadline()
        self.commit_changed.notify_all()

    def _step_down_if_isolated(self) -> None:
        """A leader that cannot reach a majority stops acting as leader."""
        if not self._has_majority_lease(window=ELECTION_TIMEOUT[1]):
            log(self.id, "lost contact with the majority")
            self.leader_id = None
            self._become_follower(self.current_term)

    def _has_majority_lease(self, window: float = LEADER_LEASE) -> bool:
        now = time.time()
        fresh = sum(1 for peer in self.peers if now - self.last_ack.get(peer, 0) <= window)
        return fresh + 1 >= self.majority

    @staticmethod
    def _new_election_deadline() -> float:
        return time.time() + random.uniform(*ELECTION_TIMEOUT)

    # ======================================================================
    # Replication (leader side)
    # ======================================================================
    def _replicator_loop(self, peer: str) -> None:
        while self.running:
            with self.lock:
                is_leader = self.role == LEADER
            if is_leader:
                self._send_append_entries(peer)
            self.wake_replicator[peer].wait(HEARTBEAT_INTERVAL)
            self.wake_replicator[peer].clear()

    def _send_append_entries(self, peer: str) -> None:
        with self.lock:
            if self.role != LEADER:
                return
            term = self.current_term
            next_index = max(1, min(self.next_index.get(peer, len(self.chain)), len(self.chain)))
            entries = self.chain[next_index: next_index + MAX_ENTRIES_PER_MESSAGE]
            request = {
                "term": term,
                "leader_id": self.id,
                "prev_index": next_index - 1,
                "prev_hash": self.chain[next_index - 1]["hash"],
                "entries": entries,
                "leader_commit": self.commit_index,
            }
        answer = self._rpc(peer, "/raft/append", request)
        if not answer:
            return
        with self.lock:
            if answer["term"] > self.current_term:
                self._become_follower(answer["term"])
                self.leader_id = None
                return
            if self.role != LEADER or self.current_term != term:
                return
            self.last_ack[peer] = time.time()
            if answer["success"]:
                self.match_index[peer] = answer["match_index"]
                self.next_index[peer] = answer["match_index"] + 1
                self._advance_commit_index()
                if self.next_index[peer] < len(self.chain):
                    self.wake_replicator[peer].set()  # more blocks to send
            else:
                # Follower is missing blocks or has a different history: go back and retry.
                self.next_index[peer] = max(1, min(next_index - 1, answer.get("last_index", 0) + 1))
                self.wake_replicator[peer].set()

    def _advance_commit_index(self) -> None:
        for index in range(len(self.chain) - 1, self.commit_index, -1):
            stored_by = 1 + sum(1 for peer in self.peers if self.match_index.get(peer, 0) >= index)
            # Raft safety rule: only blocks of the current term are committed by counting.
            if stored_by >= self.majority and self.chain[index]["term"] == self.current_term:
                self._commit_up_to(index)
                for event in self.wake_replicator.values():
                    event.set()  # tell followers about the new commit index immediately
                return

    def _append_new_block(self, kind: str, operation=None, info=None) -> dict:
        previous = self.chain[-1]
        block = ops.make_block(index=previous["index"] + 1, term=self.current_term,
                               prev_hash=previous["hash"], leader=self.id, kind=kind,
                               operation=operation, info=info)
        self.storage.append_blocks([block])
        self.chain.append(block)
        self._apply_quietly(self.tip_ledger, block)
        for event in self.wake_replicator.values():
            event.set()
        return block

    # ======================================================================
    # Committing
    # ======================================================================
    def _commit_up_to(self, index: int) -> None:
        for block in self.chain[self.commit_index + 1: index + 1]:
            self._apply_quietly(self.committed_ledger, block)
            if block["kind"] == ops.OPERATION:
                payload = block["operation"]["payload"]
                log(self.id, f"committed block #{block['index']}: {payload['type']} "
                             f"{(payload.get('asset_id') or '')[:8]}")
        self.commit_index = index
        self.storage.set_meta(commit_index=index)
        self._save_snapshot()
        self.commit_changed.notify_all()

    def _save_snapshot(self) -> None:
        ledger = self.committed_ledger
        self.storage.save_asset_snapshot([ledger.asset_view(a) for a in ledger.assets])

    def _replay(self, up_to_index: int) -> Ledger:
        ledger = Ledger(self.chain[0])
        for block in self.chain[1: up_to_index + 1]:
            self._apply_quietly(ledger, block)
        return ledger

    def _apply_quietly(self, ledger: Ledger, block: dict) -> None:
        """Apply a block; an invalid operation is skipped identically on every node."""
        try:
            ledger.apply_block(block)
        except OperationRejected as error:
            log(self.id, f"block #{block['index']} contains an invalid operation, skipped: {error}")

    # ======================================================================
    # Node-to-node HTTP
    # ======================================================================
    def _rpc(self, peer: str, path: str, body: dict):
        if self.is_blocked(peer) or not self.running:
            return None
        try:
            response = self._session().post(f"{self.peers[peer]}{path}",
                                            json={**body, "sender": self.id}, timeout=RPC_TIMEOUT)
            return response.json() if response.status_code == 200 else None
        except (requests.RequestException, ValueError):
            return None

    def _session(self) -> requests.Session:
        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = requests.Session()
        return self._thread_local.session
