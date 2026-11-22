# Sellart – art gallery ownership tickets on a replicated blockchain

Sellart manages **ownership tickets for artworks** sold by an art gallery.
The gallery administrator issues a ticket after a purchase (`issue`), clients can
sell it to each other (`transfer`) and finally cash it out at the current price of
the artwork (`redeem`).

The project follows **path A** of the course requirements: a self-built distributed
system. Three independent nodes keep their own copy of a hash-linked blockchain
and agree on one state using the **Raft** consensus algorithm (implemented in this
repository). Every operation is signed with the user's **Ed25519** private key,
which never leaves the user's wallet.

> Documentation for users (Polish), in [results/](results/):
> * [instrukcja-obslugi.md](results/instrukcja-obslugi.md) – **user manual**: installation, every tab of
>   the application step by step, troubleshooting,
> * [weryfikacja-systemu.pdf](results/weryfikacja-systemu.pdf) – how each requirement is met and tested,
> * [slownik-pojec.md](results/slownik-pojec.md) – glossary of technical terms.

---

## 1. Quick start

Requirements: **Python 3.10+** (tested on 3.12, Windows 11).

```bash
pip install -r requirements.txt

python manage.py reset      # 1. clean state (deletes chains and wallets, new admin key)
python manage.py cluster    # 2. start nodes A, B, C (three separate processes / windows)
python manage.py app        # 3. open the desktop application
```

In the application open **Users & keys → "Create Alice, Bob and Charlie"**.
Everything is ready for the demonstration. How to use the application is described in the
user manual [results/instrukcja-obslugi.md](results/instrukcja-obslugi.md).

Other commands:

| Command | Purpose |
|---|---|
| `python manage.py node A` | run a single node in the current terminal |
| `python verifier/verify_chain.py` | independent verification of all nodes (no app needed) |
| `python verifier/verify_chain.py --asset <id>` | owner and status of one asset, checked on every node |
| `python tests/acceptance_test.py` | automated run of tests T1–T14 on an isolated cluster |

To return to a clean state: close the node windows (or *Network & nodes → Stop*),
then run `python manage.py reset` again.

---

## 2. Architecture

```
          Desktop app (PySide6)                 Independent verifier (CLI)
          + user wallets (private keys)         verifier/verify_chain.py
                    │  signed operations (HTTP/JSON)        │ reads /chain of each node
      ┌─────────────┼───────────────────────────────────────┼──────────┐
      ▼             ▼                                        ▼          ▼
  ┌────────┐    ┌────────┐    Raft: votes, block replication    ┌────────┐
  │ node A │◄──►│ node B │◄────────────────────────────────────►│ node C │
  │ :8001  │    │ :8002  │                                      │ :8003  │
  └───┬────┘    └───┬────┘                                      └───┬────┘
   node.db       node.db        each node: own SQLite file        node.db
 (own chain)   (own chain)      with its own copy of the chain   (own chain)
```

* **Node** (`sellart/node_server.py`, `sellart/consensus.py`) – an independent process
  with its own HTTP interface and its own SQLite database (`runtime/node-X/node.db`).
* **Blockchain** – every block holds one entry and the hash of the previous block.
  Block kinds: `GENESIS`, `OPERATION` (a signed user operation), `LEADER` (marks a
  new Raft leader).
* **Consensus (Raft)** – one leader orders all operations. A block is *committed*
  (and the client gets `SUCCESS`) only when a majority (2 of 3 nodes) stores it.
  If the leader fails, the remaining majority elects a new one. A restarted node
  receives the missing blocks automatically.
* **State machine** (`sellart/ledger.py`) – each node computes users, assets and
  their history by replaying its committed blocks. The rules are deterministic,
  so identical chains always give identical state.
* **Wallets** (`runtime/client/wallets/*.json`) – user-side key files. Nodes only
  ever see public keys.

### Operations

| Operation | Who signs | Effect |
|---|---|---|
| `REGISTER_USER` | the new user (own key) | publishes the user's name and public key |
| `ISSUE` | gallery admin | creates a ticket: uuid, owner, status `ACTIVE`, acceptance date, original author, price |
| `TRANSFER` | current owner | changes the owner |
| `REDEEM` | current owner | status → `REDEEMED`, records the payout = current price |
| `SET_PRICE` | gallery admin | revaluation – changes the current price |

Every signed operation contains `op_id` (unique, replay protection) and
`asset_version` (the asset state it was prepared for). An operation built on an
outdated version is rejected as a conflict.

### Results shown to the user

Every operation ends with one of:

* `SUCCESS` – committed in a block confirmed by a majority,
* `REJECTED` – breaks a rule (not the owner, invalid/missing signature, replay, REDEEMED, conflict…),
* `FAILED` – could not be processed (node isolated in a minority partition, no leader, node offline).

The result is shown in the *Operation results* panel at the bottom of the window.

### What is implemented by this project vs. infrastructure

Path A means all distributed-system mechanisms are implemented here: replication,
leader election, synchronisation after restart, conflict resolution and
convergence after a partition (`sellart/consensus.py`), signature verification
and replay protection (`sellart/ledger.py`). Only standard libraries are used for
HTTP, SQLite and Ed25519 primitives (`cryptography`).

---

## 3. Project layout

```
manage.py                 command line entry point
sellart/
  config.py               runtime paths, cluster configuration
  crypto.py               canonical JSON, SHA-256, Ed25519
  operations.py           operation and block format, operation builders
  ledger.py               deterministic rules: validation + applying blocks
  storage.py              per-node SQLite storage
  consensus.py            Raft over the blockchain (election, replication, commit)
  node_server.py          HTTP API of a node
  launcher.py             starting nodes, resetting the environment
  client/
    wallets.py            user-side key storage
    node_client.py        HTTP client with fail-over
    ui/                   desktop application (one file per tab)
verifier/verify_chain.py  independent verifier (does not import sellart)
tests/acceptance_test.py  automated T1–T14
results/                  user manual, verification document and glossary (Polish)
```

## 4. Node HTTP API

| Method | Path | Description |
|---|---|---|
| GET | `/status` | role, term, leader, committed height |
| GET | `/assets`, `/assets/<id>` | committed asset state |
| GET | `/assets/<id>/history` | ISSUE / TRANSFER / REDEEM history |
| GET | `/users` | registered users |
| GET | `/chain` | committed blocks (raw, signed) |
| GET | `/operations/<op_id>` | is the operation committed? |
| POST | `/operations` | submit a signed operation |
| POST | `/admin/network` | simulated partition `{"blocked": ["B","C"]}` |
| POST | `/admin/shutdown` | stop the node |

## 5. Data format (used by the independent verifier)

* `canonical_json(x)` = JSON with sorted keys, no whitespace, UTF-8.
* Operation signature = `Ed25519(private_key, canonical_json(payload))`, checked with `payload.signer`.
* Block hash = `SHA-256(canonical_json({index, term, prev_hash, timestamp, leader, kind, operation, info}))`.

## 6. Notes and limitations

* All nodes run on one computer (separate processes, ports 8001–8003), which the
  requirements explicitly allow.
* The network partition is simulated inside the nodes: a node drops every
  node-to-node message to/from the blocked peers (both directions). The desktop
  application can still reach all nodes, as required by test T14.
* Wallet files are stored unencrypted on the user side; in production they would
  be protected with a passphrase or a hardware key.
