from aief.policy import resolve_policy

def test_most_restrictive_policy_wins():
    decision = resolve_policy("L4", [
        {"source":"factory", "risk":"medium", "maximumAutonomy":"L3", "allowedActions":["modify","push"]},
        {"source":"project", "risk":"high", "maximumAutonomy":"L2", "deniedActions":["push"], "requiredGates":["approve-plan"]},
    ])
    assert decision.effectiveRisk == "high"
    assert decision.authorizedAutonomy == "L2"
    assert decision.allowedActions == ["modify"]
    assert decision.deniedActions == ["push"]
    assert decision.requiredGates == ["approve-plan"]

def test_policy_is_order_independent():
    constraints = [{"risk":"low","maximumAutonomy":"L3"},{"risk":"critical","maximumAutonomy":"L1"}]
    assert resolve_policy("L4", constraints).authorizedAutonomy == resolve_policy("L4", list(reversed(constraints))).authorizedAutonomy
