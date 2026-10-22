# Pilot Scientific Validation Report (Questions 1–5)

**Evaluation System**: DocumentRAG Tiered Verification Framework  
**Execution Mode**: Scientific Audit & Pilot Benchmark (Incremental Disk Flush)  
**Date**: July 22, 2026  

---

## Executive Overview
This document contains the step-by-step scientific audit and phase-by-phase validation of Questions 1 through 5. Every phase for every question is flushed directly to disk upon completion.

---

## Question Audit: Q1

### 1. Question Metadata
- **Question ID**: `Q1`
- **Target Paper**: `A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf`
- **Difficulty**: `Easy`
- **Evidence Type**: `TEXT`
- **Question Text**: "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
- **Expected Answer**: "The paper proposes a deep Q-learning approach for adaptive ramp metering that learns optimal signal timings to regulate vehicle flows from on-ramps to highways. The approach improves traffic flow efficiency and reduces congestion by dynamically adjusting metering rates based on traffic state."

*Phase 1 (Setup) completed and flushed to disk.*

### 2. Retrieval Quality Audit Table
| Chunk Index | Raw Vector Score | CrossEncoder Score | Sigmoid Normalized | Repository | Paper Title | Page | Section | Noise Filter | Relevance Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.4240 | -3.2466 | 0.0374 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 1 | Abstract | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 1 | 0.5301 | -1.4060 | 0.1969 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 2 | Introduction | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 2 | 0.5488 | 0.1907 | 0.5475 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 1 | method results in 1) lower travel times in the mainline, 2) shorter vehicle queues at the on- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 3 | 0.3937 | -5.9543 | 0.0026 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 6 | Training | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 4 | 0.5110 | -0.2560 | 0.4363 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 13 | Conclusion and Future Research | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 5 | 0.4562 | -3.1734 | 0.0402 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 2 | Related Works | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 6 | 0.4730 | -5.8962 | 0.0027 | `A Deep Reinforcement Learning Approach for Ramp Me` | `A Deep Reinforcement Learning Approach for Ramp Me` | 14 | analysis and simulation study. IEEE Transactions on Intelligent Transportation Systems, 2014. 15(5): p. | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |

- **Total Chunks Retrieved**: 7
- **Paper Matching Chunks**: 7
- **Query Relevant Non-Noise Chunks**: 7
- **Similarity Score Verification**: Verified independent computation. `Raw Vector Score` (MiniLM cosine sim) and `CrossEncoder Score` (reranker logits) differ appropriately.

*Phase 2 (Retrieval Provenance) completed and flushed to disk.*

### 3. Answer Generation & Claim Quality Audit
**Generated Answer**: "The main contributions of the deep reinforcement learning approach for ramp metering include:

1. The development and application of a Deep Q-learning algorithm specifically designed for ramp metering in traffic systems.
2. Use of an asynchronous method to speed up training, enhancing efficiency.
3. The model balances exploration (exploring different control actions) with exploitation (using the best known action), leading to better performance.
4. It utilizes raw data and its processed features as inputs for Q-networks, allowing the algorithm to make decisions based on actual traffic conditions.
5. The approach achieves stable training processes through stabilizing mechanisms like replay buffers and target networks.

These contributions aim to improve the efficiency and effectiveness of ramp meters in managing traffic flow more adaptively and dynamically."

| Claim # | Extracted Claim Text | Claim Quality Fidelity | Verification Tier | Status | Confidence | Escalated to Cross-Ev? | Escalation Reason / Provenance |
|---|---|---|---|---|---|---|---|
| 1 | The main contributions of the deep reinforcement learning approach for ramp metering include:

The development and application of a Deep Q-learning algorithm specifically designed for ramp metering in traffic systems. | **Direct Paper Claim** | `Single Chunk` | **SUPPORTED** | 100.0% | NO | Single top chunk provided direct high-confidence support |
| 2 | Use of an asynchronous method to speed up training, enhancing efficiency. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 3 | The model balances exploration (exploring different control actions) with exploitation (using the best known action), leading to better performance. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 50.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 4 | It utilizes raw data and its processed features as inputs for Q-networks, allowing the algorithm to make decisions based on actual traffic conditions. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 50.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 90.0%, Tier 2: NOT_FOUND at 95.0%). Multi-source joint entailment required. |
| 5 | The approach achieves stable training processes through stabilizing mechanisms like replay buffers and target networks. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 50.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 6 | These contributions aim to improve the efficiency and effectiveness of ramp meters in managing traffic flow more adaptively and dynamically. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 50.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |

- **Single Chunk Supported Claims (Tier 1)**: 1
- **Expanded Chunk Supported Claims (Tier 2)**: 0
- **Cross-Evidence Claims (Tier 3)**: 5
- **Tiered Policy Verification**: Confirmed early stopping at Tier 1 or Tier 2 when confidence threshold (>= 70%) is satisfied.

*Phases 3 & 4 (Answer & Claim Quality Audit) completed and flushed to disk.*

### 4. Step-by-Step Metric Verification
- **Grounding Score**: `100.00%` (Calculation: 6 supported / 6 total claims)
- **Semantic Similarity**: `84.25%` (Calculation: Cosine similarity between expected and generated embedding)
- **Completeness**: `79.13%` (Calculation: Sentence-level semantic recall of expected answer points)
- **Hallucination Score**: `0.00%` (Calculation: 0 ungrounded claims / 6 total claims)
- **Retrieved Evidence Coverage (Bounded <= 100%)**: `100.00%` (Calculation: min(100%, 7 relevant / 7 capacity))
- **Context Precision (Query Margin Filtered)**: `100.00%` (Calculation: 7 query-relevant / 7 total chunks)
- **Numerical Accuracy**: `100.00%` (Calculation: No numerical values in expected answer to compare)
- **Overall Quality Score**: `90.69%` (Calculation: Weighted sum minus hallucination penalty)


*Phase 5 (Metric Verification) completed and flushed to disk.*

## Question Audit: Q2

### 1. Question Metadata
- **Question ID**: `Q2`
- **Target Paper**: `Asynchronous Methods for Deep Reinforcement Learning.pdf`
- **Difficulty**: `Medium`
- **Evidence Type**: `TABLE`
- **Question Text**: "What asynchronous methods for deep reinforcement learning are introduced and how do they improve training stability?"
- **Expected Answer**: "The paper presents asynchronous variants of four standard RL algorithms (A3C, One-step Q-learning, N-step Q-learning, and Gorilla). Asynchronous execution decouples gradient updates across multiple parallel worker threads, stabilizing deep neural network training without relying on memory replay buffers."

*Phase 1 (Setup) completed and flushed to disk.*

### 2. Retrieval Quality Audit Table
| Chunk Index | Raw Vector Score | CrossEncoder Score | Sigmoid Normalized | Repository | Paper Title | Page | Section | Noise Filter | Relevance Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.8696 | 4.1630 | 0.9847 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 10 | Roboti Publishing, 2015. | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 1 | 0.7584 | 4.0666 | 0.9832 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | methods show significant speedups from using greater numbers of parallel actor-learners. Results for Sarsa are shown in Supplementary | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 2 | 0.6707 | 3.7826 | 0.9777 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | the asynchronous reinforcement learning framework could | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 3 | 0.6507 | 3.4774 | 0.9700 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 5 | car racing simulator (Wymann et al., 2013). We also use | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 4 | 0.7682 | 3.3369 | 0.9657 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 6 | received only a visual input in the form of an RGB image | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 5 | 0.6029 | 2.8314 | 0.9443 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 7 | against the total number of training frames for different | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 6 | 0.5073 | -1.0584 | 0.2576 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | Training epochs | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 7 | 0.4967 | -1.7811 | 0.1442 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 5 | Training time (hours) | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 8 | 0.5136 | -2.0146 | 0.1177 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 11 | maintains its own separate gradient and momentum vector. | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 9 | 0.4741 | -4.3895 | 0.0123 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 11 | 7. Optimization Details | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 10 | 0.4182 | -5.3483 | 0.0047 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 11 | throughput when using a large number of threads. | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 11 | 0.3850 | -6.0874 | 0.0023 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | Training time (hours) | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 12 | 0.4386 | -9.3043 | 0.0001 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 3 | state-action pairs potentially much more efficient. | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 13 | 0.0558 | -9.6587 | 0.0001 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | Training time (hours) | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 14 | 0.0134 | -9.7066 | 0.0001 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 8 | Training epochs | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 15 | 0.2961 | -9.7760 | 0.0001 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 6 | at https://youtu.be/0xo1Ldx3L5Q. | Clean Context | PAPER MATCH (Low query relevance margin) |
| 16 | -0.1114 | -10.0096 | 0.0000 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 5 | 4 days on CPU | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 17 | 0.0846 | -10.2744 | 0.0000 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 6 | Method | Clean Context | PAPER MATCH (Low query relevance margin) |
| 18 | 0.0541 | -10.2001 | 0.0000 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 5 | 4 days on CPU | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 19 | 0.2436 | -10.3417 | 0.0000 | `Asynchronous Methods for Deep Reinforcement Learning` | `Asynchronous Methods for Deep Reinforcement Learning` | 1 | countered by an online RL agent is non-stationary, and on- | Clean Context | PAPER MATCH (Low query relevance margin) |

- **Total Chunks Retrieved**: 20
- **Paper Matching Chunks**: 16
- **Query Relevant Non-Noise Chunks**: 13
- **Similarity Score Verification**: Verified independent computation. `Raw Vector Score` (MiniLM cosine sim) and `CrossEncoder Score` (reranker logits) differ appropriately.

*Phase 2 (Retrieval Provenance) completed and flushed to disk.*

### 3. Answer Generation & Claim Quality Audit
**Generated Answer**: "The paper introduces several asynchronous methods for deep reinforcement learning, including A3C (Asynchronous Advantage Actor-Critic), n-step Q-learning, and 1-step Q-learning with SARSA.

These methods aim to improve training stability by allowing each actor-learner to make decisions independently. They do so using multiple threads or workers that can operate in parallel without directly communicating with each other. This is particularly useful for environments like Atari games which require a large number of computations per frame and where communication between learners could slow down the learning process.

The introduction states that asynchronous methods allow more data to be processed simultaneously, leading to higher "data efficiency". For example, in Figure 3 on page 8, it shows A3C showing increased data efficiency from using more parallel actor-learners. This means that by having more actors working together, the system can process and learn from more training examples within a given time frame.

Additionally, the paper mentions improvements for other methods like Sarsa in Supplementary Figure S9 on page 8-9, which further supports the notion of increased stability and efficiency when using asynchronous methods."

| Claim # | Extracted Claim Text | Claim Quality Fidelity | Verification Tier | Status | Confidence | Escalated to Cross-Ev? | Escalation Reason / Provenance |
|---|---|---|---|---|---|---|---|
| 1 | The paper introduces several asynchronous methods for deep reinforcement learning, including A3C (Asynchronous Advantage Actor-Critic), n-step Q-learning | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: PARTIALLY_SUPPORTED at 60.0%). Multi-source joint entailment required. |
| 2 | 1-step Q-learning with SARSA. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 75.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 0.0%, Tier 2: NOT_FOUND at 90.0%). Multi-source joint entailment required. |
| 3 | These methods aim to improve training stability by allowing each actor-learner to make decisions independently. | **Hallucinated Claim** | `None` | **NOT_FOUND** | 0.0% | NO | No candidate chunks or multi-source context supported the claim |
| 4 | They do so using multiple threads or workers that can operate in parallel without directly communicating with each other. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 5 | This is particularly useful for environments like Atari games which require a large number of computations per frame and where communication between learners could slow down the learning process. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 75.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 0.0%). Multi-source joint entailment required. |
| 6 | The introduction states that asynchronous methods allow more data to be processed simultaneously, leading to higher "data efficiency". | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 90.0%). Multi-source joint entailment required. |
| 7 | For example, in Figure 3 on page 8, it shows A3C showing increased data efficiency from using more parallel actor-learners. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 0.0%, Tier 2: NOT_FOUND at 0.0%). Multi-source joint entailment required. |
| 8 | This means that by having more actors working together, the system can process and learn from more training examples within a given time frame. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 0.0%). Multi-source joint entailment required. |
| 9 | Additionally, the paper mentions improvements for other methods like Sarsa in Supplementary Figure S9 on page 8-9, which further supports the notion of increased stability and efficiency when using asynchronous methods. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |

- **Single Chunk Supported Claims (Tier 1)**: 0
- **Expanded Chunk Supported Claims (Tier 2)**: 0
- **Cross-Evidence Claims (Tier 3)**: 9
- **Tiered Policy Verification**: Confirmed early stopping at Tier 1 or Tier 2 when confidence threshold (>= 70%) is satisfied.

*Phases 3 & 4 (Answer & Claim Quality Audit) completed and flushed to disk.*

### 4. Step-by-Step Metric Verification
- **Grounding Score**: `88.89%` (Calculation: 8 supported / 9 total claims)
- **Semantic Similarity**: `63.77%` (Calculation: Cosine similarity between expected and generated embedding)
- **Completeness**: `53.09%` (Calculation: Sentence-level semantic recall of expected answer points)
- **Hallucination Score**: `11.11%` (Calculation: 1 ungrounded claims / 9 total claims)
- **Retrieved Evidence Coverage (Bounded <= 100%)**: `100.00%` (Calculation: min(100%, 16 relevant / 10 capacity))
- **Context Precision (Query Margin Filtered)**: `65.00%` (Calculation: 13 query-relevant / 20 total chunks)
- **Numerical Accuracy**: `100.00%` (Calculation: No numerical values in expected answer to compare)
- **Overall Quality Score**: `77.50%` (Calculation: Weighted sum minus hallucination penalty)


*Phase 5 (Metric Verification) completed and flushed to disk.*

## Question Audit: Q3

### 1. Question Metadata
- **Question ID**: `Q3`
- **Target Paper**: `Attention Is All You Need.pdf`
- **Difficulty**: `Hard`
- **Evidence Type**: `FIGURE`
- **Question Text**: "What is the core architectural contribution of the Transformer model?"
- **Expected Answer**: "The Transformer architecture replaces recurrent and convolutional layers entirely with stacked self-attention and multi-head attention mechanisms, allowing significantly faster parallel training and superior sequence translation performance."

*Phase 1 (Setup) completed and flushed to disk.*

### 2. Retrieval Quality Audit Table
| Chunk Index | Raw Vector Score | CrossEncoder Score | Sigmoid Normalized | Repository | Paper Title | Page | Section | Noise Filter | Relevance Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.3793 | 0.0627 | 0.5157 | `Attention Is All You Need` | `Attention Is All You Need` | 1 | training for 3.5 days on eight GPUs, a small fraction of the training costs of the | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 1 | 0.2805 | -0.4329 | 0.3934 | `Attention Is All You Need` | `Attention Is All You Need` | 10 | Conclusion | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 2 | 0.2910 | -1.7905 | 0.1430 | `Attention Is All You Need` | `Attention Is All You Need` | 1 | arXiv:1706.03762v7  [cs.CL]  2 Aug 2023 | Clean Context | PAPER MATCH (Low query relevance margin) |
| 3 | 0.4327 | -4.7575 | 0.0085 | `Attention Is All You Need` | `Attention Is All You Need` | 8 | Results | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 4 | 0.2025 | -10.8452 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 2 | Model Architecture | Clean Context | PAPER MATCH (Low query relevance margin) |
| 5 | 0.1603 | -10.9525 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 2 | Background | Clean Context | PAPER MATCH (Low query relevance margin) |
| 6 | 0.1833 | -10.1308 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 2 | Introduction | Clean Context | PAPER MATCH (Low query relevance margin) |
| 7 | 0.2938 | -5.2247 | 0.0054 | `Attention Is All You Need` | `Attention Is All You Need` | 9 | results to the base model. | Clean Context | PAPER MATCH (Low query relevance margin) |
| 8 | 0.2696 | -9.9145 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 10 | Training | Clean Context | PAPER MATCH (Low query relevance margin) |
| 9 | 0.3924 | -6.6783 | 0.0013 | `Attention Is All You Need` | `Attention Is All You Need` | 8 | Training Cost (FLOPs) | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 10 | 0.1293 | -11.3663 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 5 | Model Architecture | Clean Context | PAPER MATCH (Low query relevance margin) |
| 11 | 0.1337 | -11.4103 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 7 | 2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece | Clean Context | PAPER MATCH (Low query relevance margin) |
| 12 | 0.1973 | -11.4276 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 6 | Why Self-Attention | Clean Context | PAPER MATCH (Low query relevance margin) |
| 13 | 0.1392 | -11.3559 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 4 | Model Architecture | Clean Context | PAPER MATCH (Low query relevance margin) |
| 14 | 0.2925 | -11.1795 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 7 | Training | Clean Context | PAPER MATCH (Low query relevance margin) |
| 15 | 0.0825 | -11.4143 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 9 | Results | Clean Context | PAPER MATCH (Low query relevance margin) |
| 16 | 0.1727 | -11.4474 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 13 | Input-Input Layer5 | Clean Context | PAPER MATCH (Low query relevance margin) |
| 17 | 0.0753 | -11.4023 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 7 | Training Data and Batching | Clean Context | PAPER MATCH (Low query relevance margin) |
| 18 | 0.0165 | -11.4053 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 15 | Input-Input Layer5 | Clean Context | PAPER MATCH (Low query relevance margin) |
| 19 | 0.1275 | -11.4205 | 0.0000 | `Attention Is All You Need` | `Attention Is All You Need` | 14 | Input-Input Layer5 | Clean Context | PAPER MATCH (Low query relevance margin) |

- **Total Chunks Retrieved**: 20
- **Paper Matching Chunks**: 20
- **Query Relevant Non-Noise Chunks**: 4
- **Similarity Score Verification**: Verified independent computation. `Raw Vector Score` (MiniLM cosine sim) and `CrossEncoder Score` (reranker logits) differ appropriately.

*Phase 2 (Retrieval Provenance) completed and flushed to disk.*

### 3. Answer Generation & Claim Quality Audit
**Generated Answer**: "The core architectural contributions of the Transformer model, as described in the papers excerpted, include:

1. **Self-Attention Mechanism**: The paper suggests that one key innovation is a self-attention mechanism applied to input sequences instead of traditional recurrent neural networks (RNNs). This allows the network to focus on different parts of the sequence based on their importance at any point in time.

2. **Dense Connections Without Recurrence**: Unlike RNNs, which require dense connections and recurrence through time, Transformers use a fully connected feed-forward structure for each position in the input sequences. This simplifies the architecture and makes it more efficient to train and apply.

3. **Multi-Head Attention**: The model introduces multi-head attention, where multiple independent attention mechanisms are applied simultaneously, allowing the model to capture complex relationships and dependencies within the data.

These architectural innovations contribute to the Transformer's effectiveness in tasks like machine translation, natural language understanding, and reasoning."

| Claim # | Extracted Claim Text | Claim Quality Fidelity | Verification Tier | Status | Confidence | Escalated to Cross-Ev? | Escalation Reason / Provenance |
|---|---|---|---|---|---|---|---|
| 1 | The core architectural contributions of the Transformer model, as described in the papers excerpted, include:

**Self-Attention Mechanism**: The paper suggests that one key innovation is a self-attention mechanism applied to input sequences instead of traditional recurrent neural networks (RNNs). | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 60.0%, Tier 2: PARTIALLY_SUPPORTED at 50.0%). Multi-source joint entailment required. |
| 2 | This allows the network to focus on different parts of the sequence based on their importance at any point in time. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 3 | **Dense Connections Without Recurrence**: Unlike RNNs, which require dense connections and recurrence through time, Transformers use a fully connected feed-forward structure for each position in the input sequences. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 4 | This simplifies the architecture and makes it more efficient to train and apply. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 95.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 0.0%, Tier 2: NOT_FOUND at 90.0%). Multi-source joint entailment required. |
| 5 | **Multi-Head Attention**: The model introduces multi-head attention, where multiple independent attention mechanisms are applied simultaneously, allowing the model to capture complex relationships and dependencies within the data. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: PARTIALLY_SUPPORTED at 60.0%). Multi-source joint entailment required. |
| 6 | These architectural innovations contribute to the Transformer's effectiveness in tasks like machine translation, natural language understanding, and reasoning. | **Hallucinated Claim** | `None` | **NOT_FOUND** | 0.0% | NO | No candidate chunks or multi-source context supported the claim |

- **Single Chunk Supported Claims (Tier 1)**: 0
- **Expanded Chunk Supported Claims (Tier 2)**: 0
- **Cross-Evidence Claims (Tier 3)**: 6
- **Tiered Policy Verification**: Confirmed early stopping at Tier 1 or Tier 2 when confidence threshold (>= 70%) is satisfied.

*Phases 3 & 4 (Answer & Claim Quality Audit) completed and flushed to disk.*

### 4. Step-by-Step Metric Verification
- **Grounding Score**: `83.33%` (Calculation: 5 supported / 6 total claims)
- **Semantic Similarity**: `80.31%` (Calculation: Cosine similarity between expected and generated embedding)
- **Completeness**: `57.30%` (Calculation: Sentence-level semantic recall of expected answer points)
- **Hallucination Score**: `16.67%` (Calculation: 1 ungrounded claims / 6 total claims)
- **Retrieved Evidence Coverage (Bounded <= 100%)**: `100.00%` (Calculation: min(100%, 20 relevant / 10 capacity))
- **Context Precision (Query Margin Filtered)**: `20.00%` (Calculation: 4 query-relevant / 20 total chunks)
- **Numerical Accuracy**: `100.00%` (Calculation: No numerical values in expected answer to compare)
- **Overall Quality Score**: `80.66%` (Calculation: Weighted sum minus hallucination penalty)


*Phase 5 (Metric Verification) completed and flushed to disk.*

## Question Audit: Q4

### 1. Question Metadata
- **Question ID**: `Q4`
- **Target Paper**: `Auto-Encoding Variational Bayes.pdf`
- **Difficulty**: `Easy`
- **Evidence Type**: `EQUATION`
- **Question Text**: "How does the Stochastic Gradient VB estimator enable efficient inference in Variational Autoencoders?"
- **Expected Answer**: "The paper introduces the reparameterization trick to rewrite the expectation of the latent variable variational lower bound into a differentiable form with respect to encoder parameters, enabling standard backpropagation training for continuous latent variable models."

*Phase 1 (Setup) completed and flushed to disk.*

### 2. Retrieval Quality Audit Table
| Chunk Index | Raw Vector Score | CrossEncoder Score | Sigmoid Normalized | Repository | Paper Title | Page | Section | Noise Filter | Relevance Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.7235 | 7.0011 | 0.9991 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 8 | Conclusion | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 1 | 0.5162 | 2.3225 | 0.9107 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 1 | Introduction | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 2 | 0.5157 | 3.3985 | 0.9677 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 1 | arXiv:1312.6114v11  [stat.ML]  10 Dec 2022 | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 3 | 0.6162 | 1.5704 | 0.8278 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 1 | Abstract | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 4 | 0.3193 | -10.7313 | 0.0000 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 6 | Related work | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 5 | 0.2839 | -7.2179 | 0.0007 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 7 | 1600 Frey Face, Nz =20 | Clean Context | PAPER MATCH (Low query relevance margin) |
| 6 | 0.4943 | -2.5455 | 0.0727 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 3 | 3. Efficient approximate marginal inference of the variable x. This allows us to perform all | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 7 | 0.4954 | -1.2329 | 0.2257 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 1 | Method | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 8 | 0.3660 | -8.4372 | 0.0002 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 4 | appendix B), such that only the expected reconstruction error Eqφ(z|x(i)) | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 9 | 0.5558 | -2.3419 | 0.0877 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 11 | MLP’s as probabilistic encoders and decoders | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 10 | 0.3476 | -11.1254 | 0.0000 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 13 | Full VB | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 11 | 0.4523 | -3.8212 | 0.0214 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 12 | Full VB | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 12 | 0.5023 | -3.8142 | 0.0216 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 8 | Future work | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 13 | 0.3710 | -6.9741 | 0.0009 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 2 | 3. Efficient approximate marginal inference of the variable x. This allows us to perform all | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 14 | 0.4615 | -6.6050 | 0.0014 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 6 | Experiments | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 15 | 0.3439 | -7.3337 | 0.0007 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 10 | Solution of −DKL(qφ(z)||pθ(z)), Gaussian case | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 16 | 0.3990 | -9.2889 | 0.0001 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 5 | Example: Variational Auto-Encoder | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 17 | 0.3722 | -8.4943 | 0.0002 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 12 | Monte Carlo EM | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 18 | 0.3645 | -8.6183 | 0.0002 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 2 | 1. Intractability: | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 19 | 0.2103 | -9.0100 | 0.0001 | `Auto Encoding Variational Bayes` | `Auto Encoding Variational Bayes` | 14 | Full VB | Clean Context | PAPER MATCH (Low query relevance margin) |

- **Total Chunks Retrieved**: 20
- **Paper Matching Chunks**: 20
- **Query Relevant Non-Noise Chunks**: 18
- **Similarity Score Verification**: Verified independent computation. `Raw Vector Score` (MiniLM cosine sim) and `CrossEncoder Score` (reranker logits) differ appropriately.

*Phase 2 (Retrieval Provenance) completed and flushed to disk.*

### 3. Answer Generation & Claim Quality Audit
**Generated Answer**: "The Stochastic Gradient Variance-Balanced (VB) estimator allows for more efficient and effective inference in Variational Autoencoders (VAEs). Specifically, it helps to reduce the variance of the gradient estimates during training, which can lead to faster convergence and better performance. This is important because VAEs often suffer from high variance when estimating gradients with respect to the model parameters, especially when using complex likelihood functions or large datasets.

In Variational Autoencoders, one defines an approximate posterior distribution over the latent variables that captures some properties of the true posterior but requires optimization to be tractable. The objective function involves a loss term derived from this approximate posterior and another term related to the likelihood of the observed data under the VAE model. To balance the trade-off between fitting the observed data and maintaining a flexible, stochastic representation of the latent variables, the Stochastic Gradient VB estimator is employed.

This approach ensures that even with stochastic gradient estimates, which are inherently noisy due to sampling randomness, the overall optimization process can converge towards better solutions faster and more reliably than traditional methods. The use of this estimator aids in balancing exploration (through flexible latent space) and exploitation (by fitting the observed data), crucial for effective learning and generation tasks.

In essence, by reducing variance, Stochastic Gradient VB enables more stable and efficient training of VAEs, allowing them to learn more accurate representations with fewer computational resources."

| Claim # | Extracted Claim Text | Claim Quality Fidelity | Verification Tier | Status | Confidence | Escalated to Cross-Ev? | Escalation Reason / Provenance |
|---|---|---|---|---|---|---|---|
| 1 | The Stochastic Gradient Variance-Balanced (VB) estimator allows for more efficient and effective inference in Variational Autoencoders (VAEs). | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 40.0%, Tier 2: PARTIALLY_SUPPORTED at 50.0%). Multi-source joint entailment required. |
| 2 | Specifically, it helps to reduce the variance of the gradient estimates during training, which can lead to faster convergence and better performance. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 80.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: PARTIALLY_SUPPORTED at 30.0%). Multi-source joint entailment required. |
| 3 | This is important because VAEs often suffer from high variance when estimating gradients with respect to the model parameters, especially when using complex likelihood functions or large datasets. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 60.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 4 | In Variational Autoencoders, one defines an approximate posterior distribution over the latent variables that captures some properties of the true posterior but requires optimization to be tractable. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 75.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 60.0%, Tier 2: PARTIALLY_SUPPORTED at 60.0%). Multi-source joint entailment required. |
| 5 | The objective function involves a loss term derived from this approximate posterior and another term related to the likelihood of the observed data under the VAE model. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 6 | To balance the trade-off between fitting the observed data and maintaining a flexible, stochastic representation of the latent variables, the Stochastic Gradient VB estimator is employed. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 50.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 50.0%, Tier 2: PARTIALLY_SUPPORTED at 50.0%). Multi-source joint entailment required. |
| 7 | This approach ensures that even with stochastic gradient estimates, which are inherently noisy due to sampling randomness, the overall optimization process can converge towards better solutions faster and more reliably than traditional methods. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 75.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 8 | The use of this estimator aids in balancing exploration (through flexible latent space) and exploitation (by fitting the observed data), crucial for effective learning and generation tasks. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 75.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 45.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 9 | In essence, by reducing variance, Stochastic Gradient VB enables more stable and efficient training of VAEs, allowing them to learn more accurate representations with fewer computational resources. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 60.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |

- **Single Chunk Supported Claims (Tier 1)**: 0
- **Expanded Chunk Supported Claims (Tier 2)**: 0
- **Cross-Evidence Claims (Tier 3)**: 9
- **Tiered Policy Verification**: Confirmed early stopping at Tier 1 or Tier 2 when confidence threshold (>= 70%) is satisfied.

*Phases 3 & 4 (Answer & Claim Quality Audit) completed and flushed to disk.*

### 4. Step-by-Step Metric Verification
- **Grounding Score**: `100.00%` (Calculation: 9 supported / 9 total claims)
- **Semantic Similarity**: `63.03%` (Calculation: Cosine similarity between expected and generated embedding)
- **Completeness**: `68.09%` (Calculation: Sentence-level semantic recall of expected answer points)
- **Hallucination Score**: `0.00%` (Calculation: 0 ungrounded claims / 9 total claims)
- **Retrieved Evidence Coverage (Bounded <= 100%)**: `100.00%` (Calculation: min(100%, 20 relevant / 10 capacity))
- **Context Precision (Query Margin Filtered)**: `90.00%` (Calculation: 18 query-relevant / 20 total chunks)
- **Numerical Accuracy**: `100.00%` (Calculation: No numerical values in expected answer to compare)
- **Overall Quality Score**: `83.22%` (Calculation: Weighted sum minus hallucination penalty)


*Phase 5 (Metric Verification) completed and flushed to disk.*

## Question Audit: Q5

### 1. Question Metadata
- **Question ID**: `Q5`
- **Target Paper**: `Compliance_Generation_for_Privacy_Documents_under_.pdf`
- **Difficulty**: `Medium`
- **Evidence Type**: `MULTI_PAGE`
- **Question Text**: "What approach is used for automatic compliance checking in privacy policy documents under regulatory frameworks like GDPR?"
- **Expected Answer**: "The paper proposes an automated framework that checks privacy policy documents for compliance with regulations such as GDPR. It uses natural language processing to extract compliance clauses, detect missing disclosures, and flag problematic language that violates regulatory standards."

*Phase 1 (Setup) completed and flushed to disk.*

### 2. Retrieval Quality Audit Table
| Chunk Index | Raw Vector Score | CrossEncoder Score | Sigmoid Normalized | Repository | Paper Title | Page | Section | Noise Filter | Relevance Rationale |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.6547 | 1.4214 | 0.8056 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 8 | Privatech Project | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 1 | 0.4616 | -7.0392 | 0.0009 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 6 | dataset [7]. Bhatia and Breaux [6] also worked on the identification of incom- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 2 | 0.4998 | -2.7733 | 0.0588 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 1 | arXiv:2012.12718v1  [cs.AI]  23 Dec 2020 | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 3 | 0.6346 | -0.5330 | 0.3698 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 5 | Methods and Technologies | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 4 | 0.5025 | 1.7850 | 0.8563 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 7 | 2. The Naive Bayes classifier has been used by Zimmeck and Bellovin [25]) to | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 5 | 0.5239 | -0.1311 | 0.4673 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 12 | 9. Gopinath, A.A.M., Wilson, S., Sadeh, N.: Supervised and unsupervised methods for | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 6 | 0.5134 | -0.2162 | 0.4462 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 9 | 4. Assessment of the readability of privacy policies since the GDPR requires | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 7 | 0.3853 | -8.3696 | 0.0002 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 4 | Analysis of Lawyers Tasks for Legal Advice on GDPR Compliance The sec- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 8 | 0.5891 | -0.3120 | 0.4226 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 12 | 7. Contissa, G., Docter, K., Lagioia, F., Lippi, M., Micklitz, H.W., Pa�lka, P., Sar- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 9 | 0.4420 | -2.4236 | 0.0814 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 9 | 1. Detection of problematic clauses i.e. segments of text that could breach | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 10 | 0.3921 | -2.8903 | 0.0526 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 7 | 5. Decision tree and Random Forest have been used by Tesfay and al. [6], but | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 11 | 0.5599 | -3.1512 | 0.0410 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 4 | 5. Offline privacy policies: While a company may have a limited number of | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 12 | 0.4335 | -4.9902 | 0.0068 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 13 | 15. Palmirani, M., Martoni, M., Rossi, A., Bartolini, C., Robaldo, L.: Legal ontology | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 13 | 0.3325 | -5.0459 | 0.0064 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 4 | 4. Data supply chain: Data processing activities generally imply the partici- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 14 | 0.5318 | -5.5772 | 0.0038 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 13 | 19. Shvartzshnaider, Y., Apthorpe, N., Feamster, N., Nissenbaum, H.: Analyz- | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 15 | 0.4755 | -6.0967 | 0.0022 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 12 | 4. Anton, A.I., Earp, J.B., He, Q., Stufflebeam, W., Bolchini, D., Jensen, C.: Financial | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 16 | 0.4382 | -6.1823 | 0.0021 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 13 | 21. V. Stourm, D. Restrepo Amariles, S.N.: A framework for managers to evaluate and | Excluded: Short text snippet | IRRELEVANT / NOISE |
| 17 | 0.4712 | -6.7150 | 0.0012 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 14 | 26. Zimmeck, S., Story, P., Smullen, D., Ravichander, A., Wang, Z., Reidenberg, J., | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 18 | 0.4668 | -7.1172 | 0.0008 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 8 | 3. The PRIVACYQA is the latest shared corpus of the Usable privacy policy | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |
| 19 | 0.3513 | -7.1473 | 0.0008 | `Compliance Generation for Privacy Documents under ` | `Compliance Generation for Privacy Documents under ` | 7 | 3. Lebanoff and Liu [11] explored the auxiliary-classifier generative adversarial | Clean Context | **QUERY RELEVANT** (High similarity & paper match) |

- **Total Chunks Retrieved**: 20
- **Paper Matching Chunks**: 18
- **Query Relevant Non-Noise Chunks**: 18
- **Similarity Score Verification**: Verified independent computation. `Raw Vector Score` (MiniLM cosine sim) and `CrossEncoder Score` (reranker logits) differ appropriately.

*Phase 2 (Retrieval Provenance) completed and flushed to disk.*

### 3. Answer Generation & Claim Quality Audit
**Generated Answer**: "Automatic compliance checking in privacy policy documents under regulatory frameworks like GDPR involves a combination of methods including:

1. **Machine Learning (ML) Classifiers**: Techniques such as Naive Bayes, Support Vector Machines (SVMs), Convolutional Neural Networks (CNNs), Logistic Regression (LR), and Random Forest are used to classify policy text into privacy practice categories.
2. **Annotation Methodologies**: Crowdsourcing is still used for annotation of legal documents due to the need for human judgment in ensuring accuracy, but researchers are developing methods to automate this process using machine learning algorithms.
3. **Legal Expert Rules**: Rule-based approaches continue to be employed as a part of knowledge engineering systems, though with limitations on precision and recall due to varying contextual meanings of keywords.

The focus is also on developing ML algorithms that can learn from privacy policies to recognize data practices and GDPR breaches. Additionally, the system designed aims to provide users with clear legal bases for automatic qualifications and visibility into missing information feedback."

| Claim # | Extracted Claim Text | Claim Quality Fidelity | Verification Tier | Status | Confidence | Escalated to Cross-Ev? | Escalation Reason / Provenance |
|---|---|---|---|---|---|---|---|
| 1 | Automatic compliance checking in privacy policy documents under regulatory frameworks like GDPR involves a combination of methods including:

**Machine Learning (ML) Classifiers**: Techniques such as Naive Bayes, Support Vector Machines (SVMs), Convolutional Neural Networks (CNNs), Logistic Regression (LR) | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 90.0%). Multi-source joint entailment required. |
| 2 | Random Forest are used to classify policy text into privacy practice categories. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 3 | **Annotation Methodologies**: Crowdsourcing is still used for annotation of legal documents due to the need for human judgment in ensuring accuracy, but researchers are developing methods to automate this process using machine learning algorithms. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 100.0%, Tier 2: NOT_FOUND at 100.0%). Multi-source joint entailment required. |
| 4 | **Legal Expert Rules**: Rule-based approaches continue to be employed as a part of knowledge engineering systems, though with limitations on precision and recall due to varying contextual meanings of keywords. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 85.0% | YES | Single chunks were insufficient (Tier 1: CONTRADICTED at 100.0%, Tier 2: PARTIALLY_SUPPORTED at 60.0%). Multi-source joint entailment required. |
| 5 | The focus is also on developing ML algorithms that can learn from privacy policies to recognize data practices and GDPR breaches. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 75.0% | YES | Single chunks were insufficient (Tier 1: NOT_FOUND at 0.0%, Tier 2: NOT_FOUND at 0.0%). Multi-source joint entailment required. |
| 6 | Additionally, the system designed aims to provide users with clear legal bases for automatic qualifications and visibility into missing information feedback. | **Direct Paper Claim** | `Cross-Evidence` | **SUPPORTED** | 90.0% | YES | Single chunks were insufficient (Tier 1: PARTIALLY_SUPPORTED at 60.0%, Tier 2: PARTIALLY_SUPPORTED at 60.0%). Multi-source joint entailment required. |

- **Single Chunk Supported Claims (Tier 1)**: 0
- **Expanded Chunk Supported Claims (Tier 2)**: 0
- **Cross-Evidence Claims (Tier 3)**: 6
- **Tiered Policy Verification**: Confirmed early stopping at Tier 1 or Tier 2 when confidence threshold (>= 70%) is satisfied.

*Phases 3 & 4 (Answer & Claim Quality Audit) completed and flushed to disk.*

### 4. Step-by-Step Metric Verification
- **Grounding Score**: `100.00%` (Calculation: 6 supported / 6 total claims)
- **Semantic Similarity**: `72.11%` (Calculation: Cosine similarity between expected and generated embedding)
- **Completeness**: `65.17%` (Calculation: Sentence-level semantic recall of expected answer points)
- **Hallucination Score**: `0.00%` (Calculation: 0 ungrounded claims / 6 total claims)
- **Retrieved Evidence Coverage (Bounded <= 100%)**: `100.00%` (Calculation: min(100%, 18 relevant / 10 capacity))
- **Context Precision (Query Margin Filtered)**: `90.00%` (Calculation: 18 query-relevant / 20 total chunks)
- **Numerical Accuracy**: `100.00%` (Calculation: No numerical values in expected answer to compare)
- **Overall Quality Score**: `85.65%` (Calculation: Weighted sum minus hallucination penalty)


*Phase 5 (Metric Verification) completed and flushed to disk.*

