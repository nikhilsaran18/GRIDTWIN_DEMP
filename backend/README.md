# GridTwin — Restoration & Optimization Engine (Member 2: Kishore G)

> **Track**: Critical Grid & Power Shield  
> **Module**: RESTORE (AI-Assisted Digital Twin for Cascading Grid Failure Simulation and Restoration Optimization)  
> **Simulation Disclaimer**: All results are generated within a `SIMULATED` decision-support prototype environment and do not represent certified utility-grade power-flow operations.

---

## 1. Overview & Architecture

The **Restoration Optimizer** is the **RESTORE** module in GridTwin's `SIMULATE → PREDICT → CONTAIN → RESTORE` workflow. When grid components fail (e.g., transformer failure leading to downstream feeder overloads), this engine calculates the optimal, capacity-safe switching and rerouting sequence to re-energize interrupted loads, giving absolute priority to critical infrastructure such as hospitals and emergency shelters.

```text
               Nikhil's Upstream Grid / Cascade Simulation
                                   │
                                   ▼
                ┌─────────────────────────────────────┐
                │ BaseGridAdapter / NikhilGridAdapter │
                └──────────────────┬──────────────────┘
                                   │ (Converts to Internal Pydantic Schema)
                                   ▼
                        Internal Grid Data Model
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
NetworkX Topology         Thermal Capacity           Google OR-Tools CP-SAT
 Path Generation             Validation               Integer Optimizer
(Alternate Routes)      (Feeder/Trans. Limits)    (Critical Prioritization)
      │                            │                            │
      └────────────────────────────┼────────────────────────────┘
                                   ▼
                       Multi-Strategy Ranker
                   (Pareto Evaluation & Scoring)
                                   │
                                   ▼
                        Before/After Impact &
                      Recovery Sequence Generator
                                   │
                                   ▼
               Structured Restoration Result (FastAPI Ready)
```

---

## 2. Mathematical Formulation (Google OR-Tools CP-SAT)

The optimizer solves a **pure integer linear programming (ILP)** problem using Google OR-Tools CP-SAT.

### A. Integer Scaling
To maintain high precision without floating-point approximations, all electrical quantities (MW) are scaled to integer kW with scaling factor $S = 1000$:
* $\hat{C}_e = \lfloor \text{capacity\_mw}_e \times 1000 \rfloor$ (Component capacity)
* $\hat{B}_e = \lfloor \text{base\_load\_mw}_e \times 1000 \rfloor$ (Active baseline uninterrupted power)
* $\hat{D}_l = \lfloor \text{demand\_mw}_l \times 1000 \rfloor$ (Load demand)
* $\hat{P}_l \in [1, 100]$ (Load priority integer)

### B. Decision Variables
* $x_{l, r} \in \{0, 1\}$: Binary variable indicating whether candidate alternate path $r \in \mathcal{R}_l$ is selected for affected load $l$.
* $y_{l} \in \{0, 1\}$: Binary variable indicating whether affected load $l \in \mathcal{L}_{\text{affected}}$ is restored.
* $\text{load}_e \in [0, \hat{C}_e]$: Integer variable representing post-restoration load on feeder/transformer $e \in \mathcal{E}$.
* $\text{margin}_e \in [0, \hat{C}_e]$: Integer variable representing reserve capacity margin on component $e$.

### C. Linear Constraints
1. **Restoration-Route Linkage**:
   $$\sum_{r \in \mathcal{R}_l} x_{l, r} = y_l \quad \forall l \in \mathcal{L}_{\text{affected}}$$
   *(Each affected load is energized by at most one alternate path; $y_l = 1 \iff$ exactly one route is active).*

2. **Feeder & Transformer Capacity Limits (Strictly Preventing Secondary Overloads)**:
   For every feeder and transformer $e \in \mathcal{E}$:
   $$\text{load}_e = \hat{B}_e + \sum_{l \in \mathcal{L}_{\text{affected}}} \sum_{r \in \mathcal{R}_l : e \in r} \hat{D}_l \cdot x_{l, r}$$
   $$\text{load}_e \le \hat{C}_e$$

3. **Linear Capacity Margin**:
   $$\text{margin}_e = \hat{C}_e - \text{load}_e \quad \forall e \in \mathcal{E}$$

4. **Failure Exclusion**:
   Paths traversing any failed equipment $c \in \mathcal{F}_{\text{failed}}$ are pre-pruned during graph search ($x_{l, r} = 0$).

### D. Multi-Objective Linear Function
$$\text{Maximize } \mathcal{Z} = \sum_{l \in \mathcal{L}_{\text{critical}}} W_{\text{crit}} \cdot \hat{P}_l \cdot \hat{D}_l \cdot y_l + \sum_{l \notin \mathcal{L}_{\text{critical}}} W_{\text{reg}} \cdot \hat{P}_l \cdot \hat{D}_l \cdot y_l + \sum_{e \in \mathcal{E}} W_{\text{margin}} \cdot \text{margin}_e - \sum_{l} \sum_{r \in \mathcal{R}_l} W_{\text{switch}} \cdot \text{hops}_r \cdot x_{l, r}$$

* **Default Integer Weights & Objective Coefficients**:
  * $W_{\text{crit}} = 1000$ (Critical load weight factor)
  * $W_{\text{reg}} = 10$ (Regular load weight factor)
  * $W_{\text{margin}} = 5$ (Linear incentive to maximize unused capacity margin)
  * $W_{\text{switch}} = 50$ (Penalty per hop/switch operation to favor simpler, direct paths)
  * **Actual Objective Coefficients in Model**:
    * Hospital H1: $1000 \times 100 \times 500 = 50,000,000$
    * Emergency E1: $1000 \times 90 \times 250 = 22,500,000$
    * Residential L2: $10 \times 30 \times 350 = 105,000$
    * Residential L3: $10 \times 20 \times 400 = 80,000$

---

## 3. NetworkX Topology Graph Traversal

NetworkX is used to model electrical connectivity and find candidate alternate paths:
1. **Graph Construction**: Builds an undirected graph representing substations, transformers, feeders, buses, and switchable tie-lines.
2. **Failure Pruning**: Removes failed component nodes and severed connections from the graph.
3. **Outage Detection**: Identifies which loads lost connectivity to all operational substations in the post-fault baseline.
4. **Candidate Route Discovery**: Uses `nx.all_simple_paths` from operational substations to affected load nodes, recording intermediate feeders and transformers.

---

## 4. Multi-Strategy Generation & Ranking

Instead of hard-coded options, candidate strategies are generated through distinct optimization modes:
1. **Strategy 1 (Critical-First & Safe Margin)**: $W_{\text{crit}}=1000, W_{\text{margin}}=5$.
2. **Strategy 2 (Maximum Restored Demand)**: $W_{\text{reg}}=100, W_{\text{margin}}=0$.
3. **Strategy 3 (Minimal Switching)**: $W_{\text{switch}}=500$.
4. **Pareto Diversity Search**: Adds exclusion constraint $\sum_{r \in R^*} x_r \le |R^*| - 1$ to discover alternative feasible topologies.

### Ranking Criteria:
* **Criterion 1**: Feasibility (`True` > `False`).
* **Criterion 2**: Critical Load Restored % ($100\%$ required for top rank).
* **Criterion 3**: Disruption Reduction % (Higher restored MW).
* **Criterion 4**: Maximum Peak Utilization % (Lower peak loading is safer).
* **Criterion 5**: Switching Steps Count (Fewer actions preferred).

---

## 5. Dynamic Recovery Sequence Derivation

Generated directly from active decision variables:
1. **`ISOLATE`**: Marks faulted equipment as isolated in the simulated grid state ($c \in \mathcal{F}_{\text{failed}}$).
2. **`REROUTE`**: Closes switchable tie-lines for restored loads.
3. **`RESTORE`**: Energizes loads in strict priority order:
   $$\text{Order: } (-\text{is\_critical}, -\text{priority}, -\text{demand})$$
   * Step 5: `Hospital H1` (Priority 100, 0.50 MW)
   * Step 6: `Emergency Center E1` (Priority 90, 0.25 MW)
   * Step 7: `Residential L2` (Priority 30, 0.35 MW)

---

## 6. Adapter Integration for Member 1 (Nikhil)

The restoration engine is strictly decoupled from upstream grid schemas:

```python
# In backend/restoration/adapter.py:
class NikhilGridAdapter(BaseGridAdapter):
    def __init__(self, nikhil_payload: Dict[str, Any]):
        self.raw_data = nikhil_payload

    def load_grid_state(self):
        # Map Nikhil's raw JSON into GridComponent, GridConnection, LoadDemand
        components = [GridComponent(...) for item in self.raw_data["nodes"]]
        connections = [GridConnection(...) for item in self.raw_data["lines"]]
        loads = [LoadDemand(...) for item in self.raw_data["consumers"]]
        return components, connections, loads
```
**Zero changes are required in the optimizer when connecting Nikhil's schema.**

---

## 7. Judge Q&A & Explainability Reference

| Question for Judges | Mathematical & Algorithmic Answer |
| :--- | :--- |
| **What are the decision variables?** | Binary route selection $x_{l, r} \in \{0, 1\}$, binary load restoration $y_l \in \{0, 1\}$, and integer component flows $\text{load}_e \in [0, \hat{C}_e]$ and margins $\text{margin}_e$. |
| **What are the constraints?** | 1) Single-route restoration $\sum x_{l, r} = y_l$, 2) Hard component capacity limits $\text{load}_e \le \hat{C}_e$, 3) Failed component exclusion, 4) Dynamic capacity margin definitions. |
| **Why was Strategy 1 chosen over alternatives?** | It achieves 100% critical load restoration (Hospital H1 & Emergency E1) while maintaining safe reserve margins (Feeder F5 at 86.7% and F6 at 87.5% utilization), whereas alternatives either operate near 100% overload risk or require excessive switching. |
| **How was Hospital H1 prioritized?** | Critical loads receive a substantially higher weighted objective coefficient than regular loads through $W_{\text{crit}}$ and their priority values, ensuring critical infrastructure is strongly favored during optimization. |
| **How was capacity checked?** | By tracking $\text{base\_load}_e + \sum \text{restoration\_load} \le \text{capacity}_e$ across every individual feeder and transformer, computing utilization %, margin MW, and rejecting any overloaded route. |
| **How was before/after impact calculated?** | By comparing baseline interrupted demand (1.50 MW) against post-restoration served demand (1.10 MW), calculating disruption reduction: $\frac{1.50 - 0.40}{1.50} \times 100 = 73.3\%$. |

---

## 8. Running the Demo & Tests

### Run Visual CLI Demo:
```bash
python run_demo.py
```

### Run Pytest Test Suite:
```bash
python -m pytest tests/ -v
```
