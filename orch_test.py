import json
from agents.orchestrator import Orchestrator
q='What are the experimental results for traffic flow in the ramp metering study?'
orch=Orchestrator()
res=orch.answer(q, repo_id=None, filters={'file':'A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf'})
print(json.dumps(res, indent=2, ensure_ascii=False))
