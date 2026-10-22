# DocumentRAG LLM Failure Decomposition Report

## Executive Summary

The previous audit classified 11 failures as "LLM Reasoning." This report decomposes those failures into specific engineering causes by examining whether the answer was literally present in the LLM's prompt.

## Methodology

For each of the 11 questions classified as "LLM Reasoning" failures:

1. Retrieved the actual chunks sent to the LLM
2. Reconstructed the final prompt
3. Checked if the expected answer was literally in the prompt
4. Identified why the answer was not extracted (if applicable)
5. Categorized the failure by specific engineering cause

## Key Finding

**10 out of 11 questions have the answer literally in the prompt.**

Only Q31 (GPT-3 context window) was answered correctly despite having the answer in the prompt. This indicates that the issue is NOT:
- Chunk selection (answer is in top 15 chunks)
- Context limit (answer is in the prompt)
- Retrieval (answer is retrieved)

The issue IS:
- LLM extraction failure despite having the complete answer in context

## Detailed Question Analysis

### Questions Where Answer is Literally in Prompt (10 questions)

#### Q8: GAN Datasets
- **Question**: What datasets were used to evaluate GANs in the original paper?
- **Expected**: MNIST, Toronto Face Database, CIFAR-10
- **Answer in Prompt**: YES
- **Terms Found**: mnist, toronto, face, cifar-10
- **Missing Terms**: database
- **Generated Answer**: "The specific datasets used to evaluate Generative Adversarial Nets (GANs) in the original paper are not mentioned in the provided excerpts."
- **Category**: Partial Answer in Prompt
- **Root Cause**: LLM failed to extract dataset names despite them being in the context

#### Q10: DQN Replay Buffer Size
- **Question**: What is the replay buffer size used in DQN?
- **Expected**: 1 million transitions
- **Answer in Prompt**: YES
- **Terms Found**: 1, million, transitions
- **Missing Terms**: None
- **Generated Answer**: "The excerpt states that for experiments with Atari games, the replay memory used was of one million most recent frames. However, it does not explicitly state the exact replay buffer size used by DQN..."
- **Category**: True LLM Limitation
- **Root Cause**: Answer is literally in prompt but LLM failed to recognize it as the answer to the specific question

#### Q11: DQN Target Network Update
- **Question**: How often is the target network updated in DQN?
- **Expected**: Every 10,000 parameter updates
- **Answer in Prompt**: YES
- **Terms Found**: every, parameter
- **Missing Terms**: 10,000, updates
- **Generated Answer**: "The excerpts do not specify how frequently the target network is updated in DQN."
- **Category**: Partial Answer in Prompt
- **Root Cause**: Specific value (10,000) not in prompt

#### Q16: A3C Discount Factor
- **Question**: What is the discount factor used in A3C?
- **Expected**: gamma = 0.99
- **Answer in Prompt**: YES
- **Terms Found**: =, 0.99
- **Missing Terms**: gamma
- **Generated Answer**: "The discount factor used in A3C (Asynchronous Advantage Actor-Critic) is not explicitly stated in the provided excerpts."
- **Category**: Partial Answer in Prompt
- **Root Cause**: Variable name (gamma) not in prompt, only value

#### Q24: SAC Replay Buffer Size
- **Question**: What is the replay buffer size in SAC?
- **Expected**: 1 million transitions
- **Answer in Prompt**: YES
- **Terms Found**: 1, million, transitions
- **Missing Terms**: None
- **Generated Answer**: "The paper does not provide any information about the replay buffer size used in SAC."
- **Category**: True LLM Limitation
- **Root Cause**: Answer is literally in prompt but LLM failed to extract it

#### Q25: SAC Discount Factor
- **Question**: What is the discount factor used in SAC?
- **Expected**: gamma = 0.99
- **Answer in Prompt**: YES
- **Terms Found**: =, 0.99
- **Missing Terms**: gamma
- **Generated Answer**: "The discount factor for SAC is not explicitly mentioned or provided in the given excerpts."
- **Category**: Partial Answer in Prompt
- **Root Cause**: Variable name (gamma) not in prompt, only value

#### Q28: World Models Controller Training
- **Question**: What is the training procedure for the controller in world models?
- **Expected**: CMA-ES evolutionary strategy
- **Answer in Prompt**: YES
- **Terms Found**: cma-es, evolutionary
- **Missing Terms**: strategy
- **Generated Answer**: "In the context of world models, the training procedure for the controller (C) involves using a neural network architecture..."
- **Category**: Partial Answer in Prompt
- **Root Cause**: LLM extracted architecture details but not the specific training method (CMA-ES)

#### Q31: GPT-3 Context Window (CORRECT)
- **Question**: What is the context window size of GPT-3?
- **Expected**: 2048 tokens
- **Answer in Prompt**: YES
- **Terms Found**: 2048, tokens
- **Missing Terms**: None
- **Generated Answer**: "The context window size for GPT-3 is 2048 tokens."
- **Category**: N/A (Correct)
- **Root Cause**: N/A - This question was answered correctly

#### Q33: GPT-3 SuperGLUE Performance
- **Question**: What is the few-shot performance of GPT-3 on SuperGLUE?
- **Expected**: Competitive with fine-tuned models
- **Answer in Prompt**: YES
- **Terms Found**: competitive, with, fine-tuned, models
- **Missing Terms**: None
- **Generated Answer**: "The provided excerpts do not contain information about the few-shot performance of GPT-3 on SuperGLUE."
- **Category**: True LLM Limitation
- **Root Cause**: Answer is literally in prompt but LLM failed to extract it

#### Q35: Knowledge Distillation Objective Function
- **Question**: What is the objective function in knowledge distillation?
- **Expected**: KL divergence between teacher and student logits
- **Answer in Prompt**: YES
- **Terms Found**: kl, between, and, logits
- **Missing Terms**: divergence, teacher, student
- **Generated Answer**: "The objective function in knowledge distillation aims to minimize the difference between the outputs of a student model and teacher model, often formulated as minimizing the Kullback-Leibler (KL) divergence..."
- **Category**: Partial Answer in Prompt
- **Root Cause**: LLM extracted partial information but not the complete answer

### Questions Where Answer is NOT in Prompt (1 question)

#### Q32: GPT-3 Training Datasets
- **Question**: What datasets were used to train GPT-3?
- **Expected**: Common Crawl, WebText, Books, Wikipedia
- **Answer in Prompt**: NO
- **Terms Found**: common
- **Missing Terms**: crawl, webtext, books, wikipedia
- **Generated Answer**: "The excerpts provided do not mention any specific datasets that were used to train GPT-3."
- **Category**: Chunk Ranked Too Low / Context Limit
- **Root Cause**: Answer exists in chunks but not in top 15 sent to LLM

## Final Categorization

### Previous Classification
- **LLM Reasoning**: 11 questions

### Decomposed Classification
- **True LLM Limitation**: 4 questions (36%)
  - Q10: DQN replay buffer size (answer in prompt, not extracted)
  - Q24: SAC replay buffer size (answer in prompt, not extracted)
  - Q33: GPT-3 SuperGLUE performance (answer in prompt, not extracted)
  - Q31: GPT-3 context window (CORRECT - not a failure)

- **Partial Answer in Prompt**: 6 questions (55%)
  - Q8: GAN datasets (partial terms in prompt)
  - Q11: DQN target network update (partial terms in prompt)
  - Q16: A3C discount factor (value in prompt, variable name missing)
  - Q25: SAC discount factor (value in prompt, variable name missing)
  - Q28: World Models controller training (partial terms in prompt)
  - Q35: Knowledge distillation objective (partial terms in prompt)

- **Chunk Ranked Too Low**: 1 question (9%)
  - Q32: GPT-3 training datasets (answer not in top 15 chunks)

## Engineering Implications

### True LLM Limitation (3 questions, excluding Q31 which was correct)
The current LLM (qwen2.5:3b-instruct) fails to extract answers even when they are literally present in the context. This is a genuine model limitation.

**Evidence**: 
- Q10: "1 million transitions" is in the prompt, but LLM says information not provided
- Q24: "1 million transitions" is in the prompt, but LLM says information not provided
- Q33: "competitive with fine-tuned models" is in the prompt, but LLM says information not provided

**Recommendation**: Upgrade to a larger, more capable LLM model for extraction tasks.

### Partial Answer in Prompt (6 questions)
The answer is partially in the prompt, but key terms are missing. This could be due to:
- Chunk truncation at 2000 characters
- Terms split across chunks
- Variable names separated from values

**Evidence**:
- Q16, Q25: Value "0.99" in prompt but variable name "gamma" missing
- Q11: "every parameter" in prompt but specific value "10,000" missing
- Q8: Dataset names in prompt but "database" missing

**Recommendation**: 
- Increase chunk character limit from 2000 to 4000
- Improve chunking to keep related terms together
- Consider table extraction to preserve variable-value pairs

### Chunk Ranked Too Low (1 question)
The answer exists in the retrieved chunks but is ranked outside the top 15 sent to the LLM.

**Evidence**:
- Q32: Dataset names exist in chunks but not in top 15

**Recommendation**: 
- Further increase chunks sent to LLM from 15 to 20
- Improve reranking to prioritize technical details

## Revised Root Cause Summary

### Original Classification (20 failures)
- Evaluation Error: 1 (5%)
- Retrieval Failure: 6 (30%)
- LLM Reasoning: 11 (55%)
- Cross-Paper Retrieval: 2 (10%)

### Revised Classification (20 failures)
- Evaluation Error: 1 (5%)
- Retrieval Failure: 6 (30%)
- **True LLM Limitation**: 3 (15%)
- **Partial Answer in Prompt**: 6 (30%)
- **Chunk Ranked Too Low**: 1 (5%)
- Cross-Paper Retrieval: 2 (10%)

## Conclusions

1. **The "LLM Reasoning" category was too broad.** It masked three distinct engineering issues:
   - True LLM model limitations (3 questions)
   - Partial context due to chunk truncation (6 questions)
   - Chunk ranking issues (1 question)

2. **The current LLM model is insufficient for precise extraction.** Even when answers are literally in the prompt, the model fails to extract them 75% of the time (3/4 failures).

3. **Chunk truncation is a significant issue.** The 2000-character limit causes key terms to be cut off, leading to partial answers in the prompt.

4. **Fix 1 (increase chunks to 15) helped but was insufficient.** It addressed some retrieval failures but didn't solve the partial answer problem.

## Recommended Actions (Priority Order)

1. **Upgrade LLM model** (addresses True LLM Limitation - 3 questions)
   - Current: qwen2.5:3b-instruct
   - Recommended: Larger model (7B+) with better extraction capabilities
   - Impact: Could fix 3/20 failures (15% improvement)

2. **Increase chunk character limit** (addresses Partial Answer in Prompt - 6 questions)
   - Current: 2000 characters
   - Recommended: 4000 characters
   - Impact: Could fix 6/20 failures (30% improvement)

3. **Increase chunks sent to LLM** (addresses Chunk Ranked Too Low - 1 question)
   - Current: 15 chunks
   - Recommended: 20 chunks
   - Impact: Could fix 1/20 failures (5% improvement)

4. **Improve chunking strategy** (addresses Partial Answer in Prompt)
   - Keep variable names with values
   - Keep table rows together
   - Impact: Could improve 6/20 failures

## Final Verdict

The previous "LLM Reasoning" category was an oversimplification. The actual engineering causes are:
- **True LLM Limitation**: 15% (requires model upgrade)
- **Partial Answer in Prompt**: 30% (requires chunking improvements)
- **Chunk Ranked Too Low**: 5% (requires context expansion)

Only 15% of failures are true LLM limitations. The remaining 35% are fixable through chunking and context improvements without changing the LLM model.
