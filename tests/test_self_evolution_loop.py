from cognition.self_evolution_loop import SelfEvolutionLoop


def test_record_cycle_persists_and_counts(tmp_path):
    loop = SelfEvolutionLoop(state_path=str(tmp_path / "self_evolution.json"))

    loop.record_cycle(action="BUILD", success=True, reward=0.9, policy="ikigai")
    loop.record_cycle(action="VERIFY", success=False, reward=0.2, policy="default")

    assert len(loop.state["cycles"]) == 2
    assert loop.state["cycles"][0]["action"] == "BUILD"


def test_success_rate_window(tmp_path):
    loop = SelfEvolutionLoop(state_path=str(tmp_path / "self_evolution.json"))

    for _ in range(8):
        loop.record_cycle(action="VERIFY", success=True, reward=1.0)
    for _ in range(2):
        loop.record_cycle(action="VERIFY", success=False, reward=0.0)

    assert loop.success_rate(window=10) == 0.8


def test_propose_hypothesis_targets_lowest_axis(tmp_path):
    loop = SelfEvolutionLoop(state_path=str(tmp_path / "self_evolution.json"))
    axes = {
        "energy": 0.7,
        "competence": 0.2,
        "impact": 0.9,
        "novelty": 0.6,
    }
    action_stats = {"VERIFY": {"attempts": 12, "successes": 6}}

    proposal = loop.propose_hypothesis(axes, action_stats)

    assert proposal is not None
    assert proposal["target_axis"] == "competence"
    assert proposal["suggested_action"] == "VERIFY"


def test_evaluate_hypothesis_detects_positive_lift(tmp_path):
    loop = SelfEvolutionLoop(state_path=str(tmp_path / "self_evolution.json"))
    hyp = loop.propose_hypothesis(
        {"energy": 0.4, "competence": 0.4, "impact": 0.4, "novelty": 0.4},
        {},
    )

    for _ in range(10):
        loop.record_cycle(action="VERIFY", success=False, reward=0.0)
    for _ in range(10):
        loop.record_cycle(action="VERIFY", success=True, reward=1.0)

    result = loop.evaluate_hypothesis(hyp["id"], baseline_rate=0.5, min_lift=0.1, window=10)

    assert result["promote"] is True
