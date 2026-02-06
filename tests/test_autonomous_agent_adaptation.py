import asyncio
import subprocess

from core import autonomous_agent as aa


def _make_agent(monkeypatch):
    def _disable_evolution(self):
        self.soul_manager = None
        self.goal_generator = None
        self.knowledge_synthesizer = None
        self.integration_manager = None
        self.self_modifier = None
        self._evolution_enabled = False

    monkeypatch.setattr(aa.AutonomousAgent, "_init_evolution_components", _disable_evolution)
    return aa.AutonomousAgent()


def test_get_incomplete_features_ignores_modules_that_only_appear_in_collected_output(monkeypatch):
    agent = _make_agent(monkeypatch)

    output = """
tests/test_degradation_coordinator.py ................
tests/test_service_chain.py ................
tests/test_memory_distiller.py .............
=========================== 981 passed in 9.99s ===========================
"""

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(aa.subprocess, "run", fake_run)

    incomplete = asyncio.run(agent._get_incomplete_features())
    assert incomplete == ""


def test_get_incomplete_features_reports_only_failed_modules(monkeypatch):
    agent = _make_agent(monkeypatch)

    output = """
FAILED tests/test_service_chain.py::test_timeout - AssertionError
FAILED tests/test_task_audit.py::test_review - AssertionError
"""

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout=output, stderr="")

    monkeypatch.setattr(aa.subprocess, "run", fake_run)

    incomplete = asyncio.run(agent._get_incomplete_features())
    assert "Service Chain" in incomplete
    assert "Task Audit" in incomplete
    assert "Memory Distiller" not in incomplete


def test_build_cli_writes_module_without_generator_signature_error(monkeypatch, tmp_path):
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(aa, "BASE_DIR", tmp_path)

    result = asyncio.run(agent._build_cli("demo_tool", "Demo Tool", {"categories": []}))

    assert "Built CLI:" in result
    assert list(tmp_path.rglob("demo_tool.py")), "Expected generated module file"


def test_select_goal_driven_action_requires_mature_item_for_build(monkeypatch):
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(agent.curiosity, "get_mature", lambda: None)

    selected = agent._select_goal_driven_action({
        "BUILD": 6,
        "EXPLORE": 4,
        "VERIFY": 3,
        "CURATE": 2,
        "INTEGRATE": 1,
    })

    assert selected is None


def test_select_goal_driven_action_can_choose_build_with_item(monkeypatch):
    agent = _make_agent(monkeypatch)
    mature = {"topic": "Adaptive Memory", "categories": ["memory_systems"]}
    monkeypatch.setattr(agent.curiosity, "get_mature", lambda: mature)

    selected = agent._select_goal_driven_action({
        "BUILD": 7,
        "EXPLORE": 4,
        "VERIFY": 3,
        "CURATE": 2,
        "INTEGRATE": 1,
    })

    assert selected["type"] == "BUILD"
    assert selected["item"] == mature


def test_action_for_type_build_requires_mature_item(monkeypatch):
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(agent.curiosity, "get_mature", lambda: None)

    action = agent._action_for_type("BUILD")
    assert action is None


def test_action_for_type_build_returns_build_action(monkeypatch):
    agent = _make_agent(monkeypatch)
    mature = {"topic": "Adaptive Memory", "categories": ["memory_systems"]}
    monkeypatch.setattr(agent.curiosity, "get_mature", lambda: mature)

    action = agent._action_for_type("BUILD")
    assert action["type"] == "BUILD"
    assert action["item"] == mature
