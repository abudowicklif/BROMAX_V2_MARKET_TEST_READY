from bromax.agents import run_agents

def test_agent_vectors_sum_to_one_and_abstains():
    rows=[{"digit":i%10} for i in range(1200)]
    result=run_agents(rows,1000)
    assert abs(sum(result["ensemble"]["probabilities"])-1)<1e-8
    assert result["ensemble"]["status"]=="ABSTAIN"
