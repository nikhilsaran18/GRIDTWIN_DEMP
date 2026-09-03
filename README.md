# GridTwin

### AI-Assisted Grid Restoration and Cascade Analysis Engine

> **Notice**: GridTwin is an interactive simulation and decision-support prototype platform designed to model cascade failures, dynamic risk propagation, and combinatorial restoration optimization.

---

## ⚡ Overview & Problem Statement

Modern electrical transmission and distribution networks are prone to cascading outages where a single component trip (such as an overloaded transformer or faulted feeder) can trigger sequential overload trips across neighboring lines, ultimately endangering critical public safety infrastructure like hospitals.

**GridTwin** solves this with an end-to-end digital twin and analytical decision engine:
1. **Physical & Topological Simulation**: Accurate representation of sub-station, transformer, feeder, and load topologies with thermal capacity constraints.
2. **Deterministic Cascade Analysis**: Real-time evaluation of power flow redistribution upon fault events.
3. **Multi-Factor Risk Assessment (Hema Risk Engine)**: Continuous scoring of loading stress, network dependency, critical facility exposure, and path redundancy.
4. **Optimal Combinatorial Restoration (OR-Tools)**: Fast, constraint-satisfying switching sequences prioritizing critical life-safety loads (Hospital H1).
5. **Dual 2D/3D Interactive Twin**: HTML5 Canvas topology combined with Three.js WebGL 3D infrastructure digital twin with arc-fault physics and power flow particles.

---

## 🔄 Core Workflow: SIMULATE → PREDICT → CONTAIN → RESTORE

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   01 SIMULATE   │  ──►  │   02 PREDICT    │  ──►  │   03 CONTAIN    │  ──►  │   04 RESTORE    │
│  Failure Ingest │       │  Cascade Impact │       │ Risk Intel & CF │       │ Optimal Sequence│
└─────────────────┘       └─────────────────┘       └─────────────────┘       └─────────────────┘
```

1. **01 SIMULATE**: Operator initiates an outage on any network component (e.g., Transformer `T7`, Feeder `F3`, Source `S1`).
2. **02 PREDICT**: The cascade engine calculates immediate and downstream connectivity loss, rerouting power flow and flagging thermal overload conditions (e.g. Feeder `F5` operating at 108% capacity).
3. **03 CONTAIN**: Risk engine identifies threatened critical facilities (`H1`), evaluates available backup path headroom, and generates risk level scores.
4. **04 RESTORE**: The restoration optimizer computes an ordered, constraint-checked switching schedule (e.g., isolating `T7`, closing `F5` tie-switch, restoring `H1`, managing load shed).

---

## 🏛 Authoritative Grid Architecture

```
                  ┌──────────────────────┐
                  │ Source Substation S1 │
                  │  (50.0 MW Capacity)  │
                  └──────────┬───────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌────────────────────┐        ┌────────────────────┐
   │   Transformer T7   │        │   Transformer T8   │
   │ (10.0 MW Capacity) │        │ (10.0 MW Capacity) │
   └──────────┬─────────┘        └──────────┬─────────┘
              │                             │
              ▼                             ▼
   ┌────────────────────┐        ┌────────────────────┐
   │     Feeder F3      │        │     Feeder F5      │
   │ (5.0 MW Capacity)  │        │ (6.0 MW Capacity)  │
   └───────┬────┬───────┘        └───────┬────┬───────┘
           │    │                        │    │
     ┌─────┘    └──────────┐      ┌──────┘    └─────┐
     ▼                     ▼      ▼                 ▼
┌──────────┐          ┌──────────────┐        ┌──────────┐
│ Load L1  │          │ Hospital H1  │        │ Load L2  │
│ (2.0 MW) │          │(Critical 2.5)│        │ (2.0 MW) │
└──────────┘          └──────────────┘        └──────────┘
```

---

## 🛠 Technology Stack

- **Backend**: Python 3.11+, FastAPI, NetworkX, Google OR-Tools CP-SAT, Uvicorn, Pydantic v2
- **Frontend**: Vanilla JavaScript (ES6+), HTML5 Canvas 2D Topology, Three.js (r128) WebGL 3D Digital Twin, Vanilla CSS Design System
- **Testing**: Pytest, FastAPI TestClient / HTTPX

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | System status & identifier |
| `GET` | `/health` | Live health probe for simulation, risk, and optimizer engines |
| `GET` | `/dashboard` | Serves the full GridTwin frontend dashboard |
| `GET` | `/api/grid` | Serialized 8-node topology, active capacities, and summary |
| `GET` | `/api/components/{id}` | Telemetry for specific component |
| `POST` | `/api/simulate/failure` | Primary simulation endpoint (`{"component_id": "T7"}`) |
| `POST` | `/api/simulation/reset` | Resets grid state to clean baseline |

---

## 🚀 Local Setup & Running

### 1. Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Git

### 2. Clone & Install
```bash
git clone https://github.com/nikhilsaran18/GRIDTWIN_DEMP.git
cd GRIDTWIN_DEMP
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
pytest
```

### 4. Start Local Development Server (From Repository Root)
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```
Open your browser to: **[http://127.0.0.1:8001/dashboard](http://127.0.0.1:8001/dashboard)**

---

## 🌐 Production Deployment

GridTwin is designed as a single deployable FastAPI service that delivers both backend APIs and frontend static assets from one origin.

### Startup Command:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Deploying to Render / Cloud Hosts:
1. Connect your GitHub repository.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Health Check Path: `/health`

---

## 📄 License & Attribution
Developed by the GridTwin Team (Nikhil Saran, Hema, Kishore, and collaborators).
