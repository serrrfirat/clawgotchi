from cognition.ikigai_engine import IkigaiEngine


def test_choose_action_penalizes_failing_actions(tmp_path):
    engine = IkigaiEngine(
        state_path=str(tmp_path / "ikigai_state.json"),
        gate_path=str(tmp_path / "policy_gate.json"),
        success_target=0.9,
    )

    for _ in range(12):
        engine.record_outcome("BUILD", success=False, result_text="build failed")
    for _ in range(6):
        engine.record_outcome("VERIFY", success=True, result_text="verified")

    choice = engine.choose_action(["BUILD", "VERIFY"], {"BUILD": 5, "VERIFY": 3})
    assert choice == "VERIFY"


def test_record_outcome_updates_ikigai_axes(tmp_path):
    engine = IkigaiEngine(
        state_path=str(tmp_path / "ikigai_state.json"),
        gate_path=str(tmp_path / "policy_gate.json"),
    )

    baseline = dict(engine.state["axes"])
    engine.record_outcome("EXPLORE", success=True, result_text="explored new topics")

    updated = engine.state["axes"]
    assert updated["novelty"] > baseline["novelty"]
    assert updated["energy"] > baseline["energy"]


def test_policy_promotion_requires_samples_and_lift(tmp_path):
    engine = IkigaiEngine(
        state_path=str(tmp_path / "ikigai_state.json"),
        gate_path=str(tmp_path / "policy_gate.json"),
    )

    for _ in range(19):
        engine.record_policy_outcome("ikigai", success=True)
        engine.record_policy_outcome("default", success=True)
    assert engine.should_promote_policy(min_samples=20, min_lift=0.03) is False

    engine.record_policy_outcome("ikigai", success=True)
    engine.record_policy_outcome("default", success=False)
    assert engine.should_promote_policy(min_samples=20, min_lift=0.03) is True


def test_policy_rollback_when_failure_budget_breaks(tmp_path):
    engine = IkigaiEngine(
        state_path=str(tmp_path / "ikigai_state.json"),
        gate_path=str(tmp_path / "policy_gate.json"),
        success_target=0.9,
    )

    engine.set_active_policy("ikigai")
    for _ in range(10):
        engine.record_policy_outcome("ikigai", success=False)

    assert engine.should_rollback_policy(window=10) is True
