"""V8 VMAG-10/UNIFY/07/ROOT — persisted multi-agent session-tree tests.

New test classes (plain assertions — no false-green markers):
  TestPersistOnSpawn               VMAG-10: spawn creates persisted node; terminal finalized
  TestUnifiedAllocator             VMAG-UNIFY: no M13Allocator; V4 manager governs spawns
  TestPersistedRecursion           VMAG-07: depth>1 persisted fan-out; invariant at each level
  TestViableFloorTermination       VMAG-07: viable-floor bounds recursion; no depth constant
  TestChatRootEnvelope             VMAG-ROOT: root node 60k + reserve; exhaustion denies
  TestConcurrentNoOversellChatRoot VMAG-ROOT: concurrent spawns cannot oversell

These drive the REAL planned V8-02 surface — `attach_multiagent_tools(node_manager=...)`
backed by a V4 `SessionTreeManager`, persisted child nodes, `ChildHandle.node`,
`release_child`. They are RED now (the surface does not exist: `attach_multiagent_tools`
still takes `allocator=`, spawns allocate via the in-memory `M13Allocator`, and no child
node is persisted) and GREEN after V8-02. No false-green masking (memory
`gsd-scaffold-fictional-api`); no depth constant (recursion is budget-structural).

The shared scripted provider comes from `tests/harness/conftest.py::scripted_multiagent_provider`.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


from voss.harness import multiagent
from voss.harness.session_tree import SessionTreeManager, SessionTreeNode


# --- disk helpers (verbatim from test_session_tree.py:59-73) ----------------
def _sessions_tree_dir(cwd: Path, root_id: str) -> Path:
    return cwd / ".voss" / "sessions" / root_id


def _node_path(cwd: Path, root_id: str, node_id: str) -> Path:
    return _sessions_tree_dir(cwd, root_id) / f"{node_id}.json"


def _load_nodes_from_disk(cwd: Path, root_id: str) -> dict[str, dict]:
    tree_dir = _sessions_tree_dir(cwd, root_id)
    nodes: dict[str, dict] = {}
    for path in tree_dir.glob("*.json"):
        data = json.loads(path.read_text())
        nodes[data["id"]] = data
    return nodes


# --- _NullRenderer (verbatim from test_multiagent_fanout.py:24-33) ----------
class _NullRenderer:
    """No-op renderer — swallows all Renderer-protocol calls. No
    show_subagent_* methods so PanelBridgeRenderer hasattr-guards exercise the
    no-base-method path."""

    def __getattr__(self, _attr):
        def _noop(*a, **k):
            return None

        return _noop


def _parse_budget(spawn_return: str) -> int:
    """Extract the integer from the `budget=<N>` token in a subagent_spawn
    success string (`spawned {agent} handle={h} budget={N} — ...`)."""
    return int(spawn_return.split("budget=")[1].split(" ")[0])


def _role_routing_provider(f):
    """A provider that routes each child run_turn's `stream()` to the scripted
    provider for the role whose name appears in the turn's messages. Lets per-
    role `scripts[...]` drive nested children (mirrors the `_RoleRoutingProvider`
    in test_multiagent_recursion.py:227)."""

    def _role_for(messages) -> str:
        # Route on the LAST user-message text (the spawned task), NOT the whole
        # transcript — the system prompt / prior assistant turns leak other role
        # names and would misroute (mirrors test_multiagent_recursion.py's
        # first-user-message routing).
        task_text = ""
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                task_text = json.dumps(m.get("content", ""), default=str)
        # Drop the "Working directory: <cwd>" suffix run_turn appends — the
        # pytest tmp_path embeds the test name (which can contain a role token
        # like "grandchild"), which would otherwise misroute.
        task_text = task_text.split("Working directory")[0]
        for role in sorted(f.scripts, key=len, reverse=True):
            if role in task_text:
                return role
        return next(iter(f.scripts), "root")

    class _RoleRoutingProvider:
        def stream(self, **kw):
            return f.provider(_role_for(kw.get("messages", []))).stream(**kw)

        async def complete(self, **kw):
            return await f.provider(next(iter(f.scripts), "root")).complete(**kw)

        def count_tokens(self, *, text, model):
            return max(len(text) // 4, 1)

    return _RoleRoutingProvider()


def _attach(tools, *, provider_factory, cwd, node_manager):
    """Canonical V8 invocation — note `node_manager=` (was `allocator=`)."""
    return multiagent.attach_multiagent_tools(
        tools,
        registry=multiagent.SubagentRegistry(),
        cwd=cwd,
        renderer=_NullRenderer(),
        provider=_role_routing_provider(provider_factory),
        model="stub",
        gate=None,
        cognition=None,
        node_manager=node_manager,
    )


class TestPersistOnSpawn:
    """VMAG-10: /agent spawn creates a persisted V4 node; terminal finalized."""

    async def test_spawn_creates_node_file(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        f.scripts["child-a"] = [f.done_plan("A-DONE", rationale="child a")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")

        nodes = _load_nodes_from_disk(tmp_path, root.id)
        child = next(
            (d for nid, d in nodes.items() if d.get("parent_run_id") == root.id),
            None,
        )
        assert child is not None, f"no persisted child under root: {list(nodes)}"
        assert child["parent_run_id"] == root.id
        assert child["envelope"]["limit"] > 0

    async def test_gather_finalizes_node(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        f.scripts["child-a"] = [f.done_plan("A-DONE", rationale="child a")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")
        await tools["subagent_gather"].invoke()

        nodes = _load_nodes_from_disk(tmp_path, root.id)
        child = next(d for nid, d in nodes.items() if d.get("parent_run_id") == root.id)
        assert child["terminal_state"] is not None
        assert child["terminal_state"]["exit_reason"] == "done"

    async def test_tree_reconstructs_from_disk(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        f.scripts["child-a"] = [f.done_plan("A-DONE", rationale="child a")]
        f.scripts["child-b"] = [f.done_plan("B-DONE", rationale="child b")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")
        await tools["subagent_spawn"].invoke(agent="child-b", task="child-b task")
        await tools["subagent_gather"].invoke()

        # Drop in-memory refs; the chain must reconstruct from disk alone.
        del tools, node_manager
        nodes = _load_nodes_from_disk(tmp_path, root.id)
        children = [d for nid, d in nodes.items() if nid != root.id]
        assert root.id in nodes
        assert len(children) == 2
        assert all(c["parent_run_id"] == root.id for c in children)


class TestUnifiedAllocator:
    """VMAG-UNIFY: the in-memory M13Allocator is gone; V4 manager governs spawns."""

    def test_no_m13allocator_attribute(self):
        assert not hasattr(multiagent, "M13Allocator")

    async def test_spawn_allocates_via_v4_manager(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        f.scripts["child-a"] = [f.done_plan("A-DONE", rationale="child a")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")

        # Allocation went through the V4 manager, not a separate in-memory system.
        assert len(node_manager._children) == 1


class TestChatRootEnvelope:
    """VMAG-ROOT: root node 60k envelope + carved reserve; exhaustion denies."""

    def test_root_node_created_with_envelope(self, tmp_path):
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        assert _node_path(tmp_path, root.id, root.id).is_file()
        assert root.envelope["limit"] == 60_000

    async def test_exhaustion_denies_spawn(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        for r in ("c0", "c1", "c2", "c3", "c4"):
            f.scripts[r] = [f.done_plan(f"{r}-DONE", rationale=r)]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=6_000)
        node_manager = SessionTreeManager(root, reserve=3_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        denied = None
        for r in ("c0", "c1", "c2", "c3", "c4"):
            ret = await tools["subagent_spawn"].invoke(agent=r, task=f"{r} task")
            if ret.startswith("<denied:"):
                denied = ret
                break
        assert denied is not None, "budget never exhausted — no denial returned"
        assert denied.startswith("<denied:")


class TestConcurrentNoOversellChatRoot:
    """VMAG-ROOT: concurrent spawns cannot oversell the chat root.

    Mirrors TestConcurrency in test_session_tree.py:167-176."""

    async def test_concurrent_no_oversell(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        for r in ("c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7"):
            f.scripts[r] = [f.done_plan(f"{r}-DONE", rationale=r)]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=30_000)
        node_manager = SessionTreeManager(root, reserve=10_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        spawn = tools["subagent_spawn"]
        await asyncio.gather(
            *[spawn.invoke(agent=r, task=f"{r} task") for r in
              ("c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7")],
            return_exceptions=True,
        )

        granted = sum(c.envelope["limit"] for c in node_manager._children)
        assert granted + node_manager._reserve <= root.envelope["limit"]


class TestPersistedRecursion:
    """VMAG-07: depth>1 persisted fan-out; invariant sum+reserve<=parent."""

    async def test_grandchild_node_persisted(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        # child-a fans out one grandchild then gathers; grandchild is terminal.
        f.scripts["child-a"] = [
            f.spawn_plan([("grandchild", "grandchild task")], rationale="fan out"),
            f.gather_plan([], final="child-a done"),
        ]
        f.scripts["grandchild"] = [f.done_plan("GC-DONE", rationale="grandchild")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")
        await tools["subagent_gather"].invoke()

        # Per-node SessionTreeManager → nested nodes persist under their parent
        # node's root_id dir, so glob across ALL session dirs and follow the
        # parent_run_id chain (NOT the chat-root id) per level.
        all_nodes: dict[str, dict] = {}
        for path in (tmp_path / ".voss" / "sessions").glob("*/*.json"):
            d = json.loads(path.read_text())
            all_nodes[d["id"]] = d

        child = next(d for d in all_nodes.values() if d.get("parent_run_id") == root.id)
        grandchild = next(
            (d for d in all_nodes.values() if d.get("parent_run_id") == child["id"]),
            None,
        )
        assert grandchild is not None, "grandchild node not persisted under the child"
        assert grandchild["parent_run_id"] == child["id"]
        assert grandchild["parent_run_id"] != root.id

    async def test_invariant_holds_at_each_level(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        f.scripts["child-a"] = [
            f.spawn_plan([("grandchild", "grandchild task")], rationale="fan out"),
            f.gather_plan([], final="child-a done"),
        ]
        f.scripts["grandchild"] = [f.done_plan("GC-DONE", rationale="grandchild")]
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=60_000)
        node_manager = SessionTreeManager(root, reserve=30_000, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        await tools["subagent_spawn"].invoke(agent="child-a", task="child-a task")
        await tools["subagent_gather"].invoke()

        all_nodes: dict[str, dict] = {}
        for path in (tmp_path / ".voss" / "sessions").glob("*/*.json"):
            d = json.loads(path.read_text())
            all_nodes[d["id"]] = d

        # For every parent, sum(child limits) + that level's reserve <= parent limit.
        floor = multiagent.VIABLE_FLOOR
        for parent in all_nodes.values():
            kids = [d for d in all_nodes.values() if d.get("parent_run_id") == parent["id"]]
            if not kids:
                continue
            kid_sum = sum(d["envelope"]["limit"] for d in kids)
            reserve = node_manager._reserve if parent["id"] == root.id else floor
            assert kid_sum + reserve <= parent["envelope"]["limit"]


class TestViableFloorTermination:
    """VMAG-07: viable-floor bounds recursion; no module-level depth constant."""

    async def test_viable_floor_denies_below_floor(self, tmp_path, scripted_multiagent_provider):
        f = scripted_multiagent_provider
        for r in ("c0", "c1", "c2"):
            f.scripts[r] = [f.done_plan(f"{r}-DONE", rationale=r)]
        # limit=5_000, reserve=0, viable floor 2_000 → a 3rd child's even slice
        # falls below the floor and is denied (budget-structural, not depth).
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=5_000)
        node_manager = SessionTreeManager(root, reserve=0, cwd=tmp_path)
        tools: dict = {}
        _attach(tools, provider_factory=f, cwd=tmp_path, node_manager=node_manager)

        rets = []
        for r in ("c0", "c1", "c2"):
            rets.append(await tools["subagent_spawn"].invoke(agent=r, task=f"{r} task"))
        assert any(ret.startswith("<denied:") for ret in rets), rets

    def test_no_module_level_depth_constant(self):
        import voss.harness.subagents as subagents

        for name in ("MAX_DEPTH", "DEPTH_LIMIT", "RECURSION_LIMIT"):
            assert not hasattr(multiagent, name), f"multiagent.{name} must not exist"
            assert not hasattr(subagents, name), f"subagents.{name} must not exist"
