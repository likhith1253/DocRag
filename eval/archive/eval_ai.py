from agents.orchestrator import answer
from storage.registry import get_registry

repo_id = "5534d897-d89e-415b-8aad-172fcc3fa10f"

questions = [
    # Attention Is All You Need
    "What is the main architectural innovation introduced in the Attention Is All You Need paper?",
    "How many attention heads are used in the Transformer base model?",
    "What is the value of d_model in the Transformer base model?",
    
    # Generative Adversarial Nets
    "What is the main contribution of the Generative Adversarial Nets paper?",
    "What is the objective function for the generator in GANs?",
    
    # Playing Atari with Deep Reinforcement Learning
    "What is the main contribution of the Playing Atari with Deep Reinforcement Learning paper?",
    "What is the name of the algorithm introduced in this paper?",
    
    # Proximal Policy Optimization
    "What is the main contribution of the Proximal Policy Optimization Algorithms paper?",
    "What is the clipping parameter epsilon typically set to in PPO?",
    
    # World Models
    "What is the main contribution of the World Models paper?",
    "What is the name of the model architecture used for learning world dynamics?",
    
    # Soft Actor-Critic
    "What is the main contribution of the Soft Actor-Critic paper?",
    "What is the temperature parameter alpha used for in SAC?",
]

print("=== Evaluating AI Papers ===\n")

for i, q in enumerate(questions, 1):
    ans, bd = answer(q, repo_id=repo_id)
    status = "✅" if "cannot find" not in ans.lower() else "❌"
    print(f"Q{i} {status}")
    if status == "❌":
        print(f"  {ans[:100]}...")

print("\n=== Evaluation Complete ===")
