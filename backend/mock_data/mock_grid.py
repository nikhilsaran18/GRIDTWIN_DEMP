"""
Rich synthetic mock grid dataset for GridTwin Restoration & Optimization testing.

Features:
- Dual supply substations (S1 North, S2 South)
- Three step-down transformers (T7, T8, T9)
- Three distribution feeders (F3, F5, F6)
- Multiple tie-switches for alternate rerouting paths
- Critical loads (Hospital H1, Emergency Shelter E1)
- Non-critical loads (Residential L2, L3, Commercial L4)
- Clear capacity limits enabling multi-strategy optimization
"""

from typing import Tuple, List, Dict
from restoration.models import (
    GridComponent,
    GridConnection,
    LoadDemand,
    ComponentType,
    ComponentStatus,
    SwitchState,
    LoadType,
)


def get_benchmark_grid() -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
    """
    Returns the benchmark GridTwin grid topology:
    - Primary supply via Substation S1 -> Transformer T7 -> Feeder F3 -> {H1, E1, L2, L3}
    - Alternate supply 1 via S1 -> Transformer T8 -> Feeder F5 (headroom: 0.95 MW)
    - Alternate supply 2 via S2 -> Transformer T9 -> Feeder F6 (headroom: 0.50 MW)
    """
    components = [
        # Substations (Generation/Bulk supply)
        GridComponent(
            id="S1",
            name="Substation North 110kV",
            type=ComponentType.SUBSTATION,
            capacity_mw=15.0,
            base_load_mw=3.5,
            status=ComponentStatus.OPERATIONAL,
            metadata={"voltage_kv": 110.0, "location": "North Sector"}
        ),
        GridComponent(
            id="S2",
            name="Substation South 110kV",
            type=ComponentType.SUBSTATION,
            capacity_mw=15.0,
            base_load_mw=3.0,
            status=ComponentStatus.OPERATIONAL,
            metadata={"voltage_kv": 110.0, "location": "South Sector"}
        ),

        # Transformers
        GridComponent(
            id="T7",
            name="Transformer T7 (110/11kV)",
            type=ComponentType.TRANSFORMER,
            capacity_mw=3.0,
            base_load_mw=0.0,  # Feeds F3 loads (interrupted upon failure)
            status=ComponentStatus.OPERATIONAL,
            metadata={"primary_feeder": "F3", "rating_mva": 3.5}
        ),
        GridComponent(
            id="T8",
            name="Transformer T8 (110/11kV)",
            type=ComponentType.TRANSFORMER,
            capacity_mw=2.5,
            base_load_mw=1.1,  # Serves baseline loads on F5
            status=ComponentStatus.OPERATIONAL,
            metadata={"primary_feeder": "F5", "rating_mva": 3.0}
        ),
        GridComponent(
            id="T9",
            name="Transformer T9 (110/11kV)",
            type=ComponentType.TRANSFORMER,
            capacity_mw=2.0,
            base_load_mw=1.0,  # Serves baseline loads on F6
            status=ComponentStatus.OPERATIONAL,
            metadata={"primary_feeder": "F6", "rating_mva": 2.5}
        ),

        # Feeders
        GridComponent(
            id="F3",
            name="Distribution Feeder F3 (11kV)",
            type=ComponentType.FEEDER,
            capacity_mw=2.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL,
            metadata={"source_transformer": "T7"}
        ),
        GridComponent(
            id="F5",
            name="Distribution Feeder F5 (11kV)",
            type=ComponentType.FEEDER,
            capacity_mw=1.5,
            base_load_mw=0.55,  # 0.55 MW base load -> 0.95 MW headroom
            status=ComponentStatus.OPERATIONAL,
            metadata={"source_transformer": "T8"}
        ),
        GridComponent(
            id="F6",
            name="Distribution Feeder F6 (11kV)",
            type=ComponentType.FEEDER,
            capacity_mw=1.2,
            base_load_mw=0.70,  # 0.70 MW base load -> 0.50 MW headroom
            status=ComponentStatus.OPERATIONAL,
            metadata={"source_transformer": "T9"}
        ),

        # Distribution Buses
        GridComponent(
            id="B_F3",
            name="Bus Feeder 3",
            type=ComponentType.BUS,
            capacity_mw=5.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_F5",
            name="Bus Feeder 5",
            type=ComponentType.BUS,
            capacity_mw=5.0,
            base_load_mw=0.55,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_F6",
            name="Bus Feeder 6",
            type=ComponentType.BUS,
            capacity_mw=5.0,
            base_load_mw=0.70,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_H1",
            name="Critical Bus Hospital H1",
            type=ComponentType.BUS,
            capacity_mw=2.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_E1",
            name="Critical Bus Emergency E1",
            type=ComponentType.BUS,
            capacity_mw=2.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_L2",
            name="Bus Residential L2",
            type=ComponentType.BUS,
            capacity_mw=2.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_L3",
            name="Bus Residential L3",
            type=ComponentType.BUS,
            capacity_mw=2.0,
            base_load_mw=0.0,
            status=ComponentStatus.OPERATIONAL
        ),
        GridComponent(
            id="B_L4",
            name="Bus Commercial L4",
            type=ComponentType.BUS,
            capacity_mw=2.0,
            base_load_mw=0.45,
            status=ComponentStatus.OPERATIONAL
        ),
    ]

    connections = [
        # S1 to Transformers T7 and T8
        GridConnection(id="C_S1_T7", source_id="S1", target_id="T7", capacity_mw=4.0, base_load_mw=0.0),
        GridConnection(id="C_S1_T8", source_id="S1", target_id="T8", capacity_mw=3.0, base_load_mw=1.1),

        # S2 to Transformer T9
        GridConnection(id="C_S2_T9", source_id="S2", target_id="T9", capacity_mw=3.0, base_load_mw=1.0),

        # Transformers to Feeders
        GridConnection(id="C_T7_F3", source_id="T7", target_id="F3", capacity_mw=2.5, base_load_mw=0.0),
        GridConnection(id="C_T8_F5", source_id="T8", target_id="F5", capacity_mw=2.0, base_load_mw=0.55),
        GridConnection(id="C_T9_F6", source_id="T9", target_id="F6", capacity_mw=1.8, base_load_mw=0.70),

        # Feeders to Main Distribution Buses
        GridConnection(id="C_F3_BF3", source_id="F3", target_id="B_F3", capacity_mw=2.0, base_load_mw=0.0),
        GridConnection(id="C_F5_BF5", source_id="F5", target_id="B_F5", capacity_mw=1.5, base_load_mw=0.55),
        GridConnection(id="C_F6_BF6", source_id="F6", target_id="B_F6", capacity_mw=1.2, base_load_mw=0.70),

        # Primary lines from F3 Bus to Loads
        GridConnection(id="C_BF3_H1", source_id="B_F3", target_id="B_H1", capacity_mw=1.5, base_load_mw=0.0),
        GridConnection(id="C_BF3_E1", source_id="B_F3", target_id="B_E1", capacity_mw=1.0, base_load_mw=0.0),
        GridConnection(id="C_BF3_L2", source_id="B_F3", target_id="B_L2", capacity_mw=1.0, base_load_mw=0.0),
        GridConnection(id="C_BF3_L3", source_id="B_F3", target_id="B_L3", capacity_mw=1.0, base_load_mw=0.0),

        # Existing line from F5 to Commercial L4
        GridConnection(id="C_BF5_L4", source_id="B_F5", target_id="B_L4", capacity_mw=1.0, base_load_mw=0.45),

        # Normally-Open Tie-Switches for Alternate Rerouting:
        # 1. Tie-Switch from F5 to Hospital H1
        GridConnection(
            id="SW_F5_H1",
            source_id="B_F5",
            target_id="B_H1",
            capacity_mw=1.5,
            base_load_mw=0.0,
            is_switchable=True,
            switch_state=SwitchState.OPEN,
            metadata={"switch_name": "Tie-Switch 5-H1"}
        ),
        # 2. Tie-Switch from F5 to Emergency Shelter E1
        GridConnection(
            id="SW_F5_E1",
            source_id="B_F5",
            target_id="B_E1",
            capacity_mw=1.0,
            base_load_mw=0.0,
            is_switchable=True,
            switch_state=SwitchState.OPEN,
            metadata={"switch_name": "Tie-Switch 5-E1"}
        ),
        # 3. Tie-Switch from F6 to Hospital H1
        GridConnection(
            id="SW_F6_H1",
            source_id="B_F6",
            target_id="B_H1",
            capacity_mw=1.2,
            base_load_mw=0.0,
            is_switchable=True,
            switch_state=SwitchState.OPEN,
            metadata={"switch_name": "Tie-Switch 6-H1"}
        ),
        # 4. Tie-Switch from F6 to Residential L2
        GridConnection(
            id="SW_F6_L2",
            source_id="B_F6",
            target_id="B_L2",
            capacity_mw=1.0,
            base_load_mw=0.0,
            is_switchable=True,
            switch_state=SwitchState.OPEN,
            metadata={"switch_name": "Tie-Switch 6-L2"}
        ),
    ]

    loads = [
        LoadDemand(
            id="H1",
            node_id="B_H1",
            name="Metro General Hospital",
            demand_mw=0.50,  # 500 kW
            load_type=LoadType.HOSPITAL,
            priority=100,
            is_critical=True,
            is_served=True,
            pre_fault_path=["S1", "T7", "F3", "B_F3", "B_H1"],
            metadata={"icu_beds": 45, "trauma_center": True}
        ),
        LoadDemand(
            id="E1",
            node_id="B_E1",
            name="Civic Emergency Center",
            demand_mw=0.25,  # 250 kW
            load_type=LoadType.EMERGENCY,
            priority=90,
            is_critical=True,
            is_served=True,
            pre_fault_path=["S1", "T7", "F3", "B_F3", "B_E1"],
            metadata={"first_responders": True}
        ),
        LoadDemand(
            id="L2",
            node_id="B_L2",
            name="North Residential Sector",
            demand_mw=0.35,  # 350 kW
            load_type=LoadType.RESIDENTIAL,
            priority=30,
            is_critical=False,
            is_served=True,
            pre_fault_path=["S1", "T7", "F3", "B_F3", "B_L2"],
            metadata={"households": 220}
        ),
        LoadDemand(
            id="L3",
            node_id="B_L3",
            name="South Residential Sector",
            demand_mw=0.40,  # 400 kW
            load_type=LoadType.RESIDENTIAL,
            priority=20,
            is_critical=False,
            is_served=True,
            pre_fault_path=["S1", "T7", "F3", "B_F3", "B_L3"],
            metadata={"households": 280}
        ),
        LoadDemand(
            id="L4",
            node_id="B_L4",
            name="East Commercial Plaza",
            demand_mw=0.45,  # 450 kW
            load_type=LoadType.COMMERCIAL,
            priority=40,
            is_critical=False,
            is_served=True,
            pre_fault_path=["S1", "T8", "F5", "B_F5", "B_L4"],
            metadata={"businesses": 35}
        ),
    ]

    return components, connections, loads


def get_bottleneck_grid() -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
    """
    Returns a grid where alternate paths exist but capacities are heavily loaded (insufficient capacity),
    forcing the optimizer to report that critical or all loads cannot be restored.
    """
    components, connections, loads = get_benchmark_grid()
    for c in components:
        if c.id == "F5":
            c.base_load_mw = 1.45  # Capacity is 1.50 MW -> only 0.05 MW headroom (cannot fit H1 0.50 MW)
        elif c.id == "F6":
            c.base_load_mw = 1.15  # Capacity is 1.20 MW -> only 0.05 MW headroom (cannot fit H1 0.50 MW)
        elif c.id == "T8":
            c.base_load_mw = 2.45
        elif c.id == "T9":
            c.base_load_mw = 1.95
    return components, connections, loads


def get_islanded_no_path_grid() -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
    """
    Returns a grid where all tie-switches are removed, so an outage on T7 completely islands the loads.
    """
    components, connections, loads = get_benchmark_grid()
    # Retain only primary connections, strip all tie switches
    primary_connections = [conn for conn in connections if not conn.id.startswith("SW_")]
    return components, primary_connections, loads
