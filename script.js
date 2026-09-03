// ============================================================
// GRIDTWIN FRONTEND - PRODUCTION INTEGRATED CONTROLLER
// HTML5 + CSS3 + Canvas + Three.js WebGL + FastAPI
// ============================================================

// API Configuration
const API_BASE = window.location.port === "5500"
    ? "http://127.0.0.1:8001"
    : window.location.origin;

let backendHealthy = false;
let currentScenario = null;
let simulationActive = false;

// Authoritative 2D topology normalized coordinates
const nodePositions = {
    "S1": { x: 0.50, y: 0.12, label: "S1", type: "Substation" },
    "T7": { x: 0.35, y: 0.35, label: "T7", type: "Transformer" },
    "T8": { x: 0.65, y: 0.35, label: "T8", type: "Transformer" },
    "F3": { x: 0.35, y: 0.57, label: "F3", type: "Feeder" },
    "F5": { x: 0.65, y: 0.57, label: "F5", type: "Feeder" },
    "L1": { x: 0.22, y: 0.78, label: "L1", type: "Load" },
    "H1": { x: 0.48, y: 0.80, label: "H1", type: "Hospital" },
    "L2": { x: 0.75, y: 0.78, label: "L2", type: "Load" }
};

// Grid State
let nodes = [];
window.nodes = nodes;
let connections = [];
let edgeStates = {}; // edge_id or "src|tgt" -> status
let backendGridData = null;

// Canvas State
const canvas = document.getElementById("gridCanvas");
const ctx = canvas ? canvas.getContext("2d") : null;
let selectedNode = null;
let currentGridView = "2d";

// ============================================================================
// STATUS & HEALTH
// ============================================================================

function setStatusIndicatorState(isHealthy) {
    const dots = document.querySelectorAll(".status-dot, .online-dot");
    dots.forEach(dot => {
        dot.classList.toggle("online", Boolean(isHealthy));
        dot.classList.toggle("offline", !isHealthy);
    });

    const systemStatus = document.getElementById("systemStatusBadge");
    if (systemStatus) {
        systemStatus.style.color = isHealthy ? "#2ddf8c" : "#ff5364";
        systemStatus.style.borderColor = isHealthy ? "#1d4434" : "#4a1d2a";
        systemStatus.style.background = isHealthy ? "#0b1914" : "#1c0f14";
        systemStatus.innerHTML = `<span class="status-dot ${isHealthy ? 'online' : 'offline'}"></span> ${isHealthy ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}`;
    }

    const sidebarText = document.getElementById("sidebarStatusText");
    if (sidebarText) {
        sidebarText.textContent = isHealthy ? "Simulation Engine Online" : "Simulation Engine Offline";
    }
}

// ============================================================================
// API HELPERS
// ============================================================================

async function apiCall(endpoint, options = {}) {
    try {
        const url = `${API_BASE}${endpoint}`;
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            console.error(`API Error [${response.status}]: ${response.statusText}`);
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error(`API Call Failed: ${endpoint}`, error);
        return null;
    }
}

async function checkBackendHealth() {
    const response = await apiCall("/health");
    if (response && response.status === "healthy") {
        backendHealthy = true;
        setStatusIndicatorState(true);
        console.log("GridTwin Backend Online ✓");
        return true;
    } else {
        backendHealthy = false;
        setStatusIndicatorState(false);
        console.warn("GridTwin Backend Offline ⚠");
        return false;
    }
}

async function loadGridFromBackend() {
    const gridData = await apiCall("/api/grid");
    if (!gridData || !gridData.nodes) {
        console.error("Failed to load grid from backend");
        return false;
    }

    backendGridData = gridData;
    mapBackendGridToState(gridData);
    return true;
}

function mapBackendGridToState(gridData) {
    edgeStates = {};
    
    nodes = gridData.nodes.map(backendNode => {
        const pos = nodePositions[backendNode.id] || { x: 0.5, y: 0.5 };
        return {
            id: backendNode.id,
            name: backendNode.name,
            type: formatType(backendNode.type),
            rawType: backendNode.type,
            x: pos.x,
            y: pos.y,
            status: backendNode.status,
            capacity_mw: backendNode.capacity_mw,
            load_mw: backendNode.load_mw,
            loading: calculateLoadingPercent(backendNode.load_mw, backendNode.capacity_mw),
            criticality: backendNode.criticality,
            critical: backendNode.is_critical_load,
            _backendData: backendNode
        };
    });

    connections = [];
    const seenConnections = new Set();

    gridData.edges.forEach(edge => {
        const key = `${edge.source}|${edge.target}`;
        edgeStates[key] = edge.status || "normal";
        edgeStates[edge.id] = edge.status || "normal";
        if (!seenConnections.has(key)) {
            connections.push([edge.source, edge.target, edge.id, edge.status]);
            seenConnections.add(key);
        }
    });

    window.nodes = nodes;
    
    if (window.grid3D) {
        window.grid3D.syncGridData(gridData);
    }
    
    updateStatistics();
    drawGrid();
    renderRiskAnalysisBaseline();
    renderCriticalFacilitiesBaseline();
    renderRestorationBaseline();
}

async function simulateFailureBackend(componentId) {
    const request = { component_id: componentId };
    return await apiCall("/api/simulate/failure", {
        method: "POST",
        body: JSON.stringify(request)
    });
}

async function resetSimulationBackend() {
    const response = await apiCall("/api/simulation/reset", {
        method: "POST",
        body: JSON.stringify({})
    });
    return response && response.status === "success";
}

// ============================================================================
// FORMATTING HELPERS
// ============================================================================

function formatType(backendType) {
    const typeMap = {
        "source": "Substation",
        "substation": "Substation",
        "transformer": "Transformer",
        "feeder": "Feeder",
        "load": "Load",
        "hospital": "Hospital",
        "emergency_service": "Emergency Service"
    };
    return typeMap[backendType] || backendType;
}

function calculateLoadingPercent(loadMw, capacityMw) {
    if (!capacityMw || capacityMw === 0) return "0%";
    const percent = Math.round((loadMw / capacityMw) * 100);
    return `${percent}%`;
}

function getCapacityString(capacityMw) {
    return typeof capacityMw === "number" ? `${capacityMw.toFixed(1)} MW` : "N/A";
}

function getLoadingString(loadMw) {
    return typeof loadMw === "number" ? `${loadMw.toFixed(1)} MW` : "N/A";
}

// ============================================================================
// 2D CANVAS RENDERING & LAYOUT ENGINE
// ============================================================================

function resizeAndRender2D() {
    const container = document.getElementById("canvasContainer");
    if (!container || !canvas || !ctx) return;

    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) return;

    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(ratio, ratio);

    drawGrid();
}

function getPosition(node) {
    const container = document.getElementById("canvasContainer");
    const width = container ? container.clientWidth : 800;
    const height = container ? container.clientHeight : 380;
    return {
        x: node.x * width,
        y: node.y * height
    };
}

function drawGrid() {
    if (!canvas || !ctx) return;
    const container = document.getElementById("canvasContainer");
    const width = container ? container.clientWidth : 800;
    const height = container ? container.clientHeight : 380;

    ctx.clearRect(0, 0, width, height);

    // 1. Draw connections
    connections.forEach(connection => {
        const srcId = connection[0];
        const tgtId = connection[1];
        const edgeId = connection[2];

        const nodeA = nodes.find(n => n.id === srcId);
        const nodeB = nodes.find(n => n.id === tgtId);

        if (!nodeA || !nodeB) return;

        const a = getPosition(nodeA);
        const b = getPosition(nodeB);

        const edgeStatus = edgeStates[`${srcId}|${tgtId}`] || edgeStates[edgeId] || "normal";

        let lineColor = "#263548";
        let lineWidth = 3;
        let isDashed = false;

        if (edgeStatus === "failed") {
            lineColor = "#ff5364";
            lineWidth = 3.5;
        } else if (edgeStatus === "warning") {
            lineColor = "#ffb547";
            lineWidth = 3.5;
        } else if (edgeStatus === "rerouted") {
            lineColor = "#38bdf8";
            lineWidth = 4;
        } else if (edgeStatus === "disconnected") {
            lineColor = "#3b2c40";
            lineWidth = 2;
            isDashed = true;
        } else if (simulationActive) {
            if (nodeA.status === "failed" || nodeB.status === "failed") {
                lineColor = "#ff5364";
            }
        }

        ctx.save();
        ctx.beginPath();
        if (isDashed) ctx.setLineDash([5, 5]);
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
        ctx.restore();
    });

    // 2. Draw nodes
    nodes.forEach(node => {
        const pos = getPosition(node);
        let color = "#2ddf8c"; // Normal Healthy

        if (node.status === "failed") {
            color = "#ff5364"; // Red
        } else if (node.status === "overloaded") {
            color = "#ff5364"; // Red
        } else if (node.status === "warning" || node.status === "high_risk" || node.status === "at_risk") {
            color = "#ffb547"; // Orange / Yellow
        } else if (node.status === "disconnected" || node.status === "critical_risk") {
            color = node.critical ? "#c084fc" : "#e879f9"; // Purple / Dim
        } else if (node.critical) {
            color = "#a879ff"; // Purple identity
        }

        drawNode(pos.x, pos.y, node, color);
    });
}

function drawNode(x, y, node, color) {
    const radius = 20;

    // Outer Glow
    ctx.beginPath();
    ctx.arc(x, y, radius + 7, 0, Math.PI * 2);
    ctx.fillStyle = color + "20";
    ctx.fill();

    // Node Circle
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = "#0e1722";
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();

    // Node Type Glyph
    ctx.fillStyle = color;
    ctx.font = "bold 13px Inter, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    let icon = "●";
    if (node.type === "Substation") icon = "S";
    if (node.type === "Transformer") icon = "T";
    if (node.type === "Feeder") icon = "F";
    if (node.type === "Load") icon = "L";
    if (node.type === "Hospital") icon = "✚";

    if (node.status === "failed") icon = "✕";

    ctx.fillText(icon, x, y);

    // ID Label
    ctx.fillStyle = "#e8edf4";
    ctx.font = "bold 11px Inter, Arial, sans-serif";
    ctx.fillText(node.id, x, y + 34);

    // Status Label
    ctx.fillStyle = color;
    ctx.font = "9px Inter, Arial, sans-serif";
    let statusText = (node.status || "NORMAL").toUpperCase().replace("_", " ");
    ctx.fillText(statusText, x, y + 47);
}

// ============================================================================
// 2D CLICK & INTERACTION
// ============================================================================

if (canvas) {
    canvas.addEventListener("click", function(event) {
        const rect = canvas.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const mouseY = event.clientY - rect.top;

        let clicked = null;
        nodes.forEach(node => {
            const pos = getPosition(node);
            const dist = Math.hypot(mouseX - pos.x, mouseY - pos.y);
            if (dist < 28) clicked = node;
        });

        if (clicked) {
            selectedNode = clicked;
            showComponentDetails(clicked);
        }
    });
}

window.selectNodeFrom3D = function(nodeId) {
    const node = nodes.find(candidate => candidate.id === nodeId);
    if (!node) return;
    selectedNode = node;
    showComponentDetails(node);
    drawGrid();
};

// ============================================================================
// COMPONENT DETAILS PANEL
// ============================================================================

function showComponentDetails(node) {
    const details = document.getElementById("componentDetails");
    if (!details) return;

    let statusClass = "status-normal";
    let statusText = (node.status || "NORMAL").toUpperCase().replace("_", " ");

    if (node.status === "failed") {
        statusClass = "status-failed";
    } else if (node.status === "overloaded" || node.status === "critical_risk") {
        statusClass = "status-failed";
    } else if (node.status === "warning" || node.status === "at_risk" || node.status === "high_risk") {
        statusClass = "status-warning";
    }

    let html = `
        <div class="component-info">
            <div class="component-name">
                <div>
                    <h3>${node.id}</h3>
                    <div class="component-type">${node.name || node.type}</div>
                </div>
                <span class="status-badge ${statusClass}">${statusText}</span>
            </div>

            <div class="info-row">
                <span>Asset Class</span>
                <strong>${node.type}</strong>
            </div>

            <div class="info-row">
                <span>Rated Capacity</span>
                <strong>${getCapacityString(node.capacity_mw)}</strong>
            </div>

            <div class="info-row">
                <span>Simulated Load</span>
                <strong>${getLoadingString(node.load_mw)}</strong>
            </div>

            <div class="info-row">
                <span>Thermal Utilization</span>
                <strong>${calculateLoadingPercent(node.load_mw, node.capacity_mw)}</strong>
            </div>

            <div class="info-row">
                <span>Critical Priority</span>
                <strong>${node.critical ? "YES (Hospital Life-Safety)" : "Standard Demand"}</strong>
            </div>
    `;

    if (node.status === "failed") {
        html += `
            <button class="failure-btn" style="background:#112217;border-color:#1c513d;color:#2ddf8c;" onclick="resetSimulationButtonClick()">
                ↻ RESET SIMULATION
            </button>
        `;
    } else {
        html += `
            <button class="failure-btn" onclick="simulateFailureButtonClick('${node.id}')">
                💥 SIMULATE FAILURE
            </button>
        `;
    }

    html += `</div>`;
    details.innerHTML = html;

    const hint = document.getElementById("componentHint");
    if (hint) hint.textContent = `Selected: ${node.name || node.id}`;
}

// ============================================================================
// SIMULATION ORCHESTRATION (SIMULATE -> PREDICT -> CONTAIN -> RESTORE)
// ============================================================================

async function simulateFailureButtonClick(nodeId) {
    if (!backendHealthy) {
        alert("Backend service is offline. Cannot run simulation.");
        return;
    }

    const failedNode = nodes.find(n => n.id === nodeId);
    if (!failedNode) return;

    // Trigger 3D visual effects immediately
    if (window.grid3D?.isInitialized) {
        window.grid3D.triggerFailureAnimation(nodeId);
    }

    // Call authoritative backend endpoint
    const response = await simulateFailureBackend(nodeId);
    if (!response) {
        alert("Failure simulation failed on backend.");
        window.grid3D?.reset();
        return;
    }

    currentScenario = response;
    simulationActive = true;

    // Synchronize nodes & edges directly from authoritative backend response
    if (response.grid) {
        mapBackendGridToState(response.grid);
    } else {
        // Fallback update
        failedNode.status = "failed";
        if (response.affected_components) {
            response.affected_components.forEach(aff => {
                const fn = nodes.find(n => n.id === aff.id);
                if (fn) fn.status = aff.status || "warning";
            });
        }
    }

    // Update 3D Digital Twin
    if (window.grid3D?.isInitialized) {
        window.grid3D.updateCascade3D(response);
    }

    // Update all views
    updateStatistics();
    showComponentDetails(nodes.find(n => n.id === nodeId) || failedNode);
    renderFailureImpactAnalysis(response);
    renderRiskAnalysis(response.risk_summary, response.failed_component);
    renderCriticalFacilities(response);
    renderRestorationPlan(response.restoration);
    updateWorkflow();
    drawGrid();
}

// ============================================================================
// RESET ORCHESTRATION
// ============================================================================

async function resetSimulationButtonClick() {
    if (!backendHealthy) {
        alert("Backend is offline. Cannot reset.");
        return;
    }

    const success = await resetSimulationBackend();
    if (!success) {
        alert("Reset request failed.");
        return;
    }

    currentScenario = null;
    simulationActive = false;

    // Reset 3D Visualizer
    window.grid3D?.reset();

    // Reload baseline grid
    await loadGridFromBackend();

    // Hide impact & restoration panels
    document.getElementById("impactPanel")?.classList.add("hidden");
    document.getElementById("restorationPanel")?.classList.add("hidden");

    // Reset Details
    const details = document.getElementById("componentDetails");
    if (details) {
        details.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⌁</div>
                <h3>No Component Selected</h3>
                <p>Click any substation, transformer, feeder, or load on the grid map to view live telemetry and simulate faults.</p>
            </div>
        `;
    }
    const hint = document.getElementById("componentHint");
    if (hint) hint.textContent = "Click any component to inspect";

    updateStatistics();
    updateWorkflow();
    drawGrid();
}

// ============================================================================
// DYNAMIC VIEW RENDERERS
// ============================================================================

function renderFailureImpactAnalysis(response) {
    const impactPanel = document.getElementById("impactPanel");
    const impactGrid = document.getElementById("impactGrid");
    const riskScoreEl = document.getElementById("riskScore");
    if (!impactPanel || !impactGrid) return;

    impactPanel.classList.remove("hidden");

    const overallRisk = Math.round(response.risk_summary?.overall_risk || 0);
    if (riskScoreEl) riskScoreEl.textContent = `${overallRisk}%`;

    const failed = response.failed_component || {};
    const failedTypeFormatted = formatType(failed.type || "Asset");

    let html = `
        <div class="impact-card failed-card">
            <span>FAILED COMPONENT</span>
            <strong>${failed.id || "N/A"}</strong>
            <small>${failed.name || failedTypeFormatted} (${failedTypeFormatted})</small>
        </div>
    `;

    // Overloaded / Warning Card
    const overloaded = response.overloaded_components || [];
    const warnings = response.warning_components || [];
    if (overloaded.length > 0) {
        const topOver = overloaded[0];
        const loadPct = calculateLoadingPercent(topOver.load_mw, topOver.capacity_mw);
        html += `
            <div class="impact-card warning-card">
                <span>OVERLOAD DETECTED</span>
                <strong>${topOver.id}</strong>
                <small>${topOver.name || formatType(topOver.type)}: ${loadPct} simulated loading</small>
            </div>
        `;
    } else if (warnings.length > 0) {
        const topWarn = warnings[0];
        const loadPct = calculateLoadingPercent(topWarn.load_mw, topWarn.capacity_mw);
        html += `
            <div class="impact-card warning-card">
                <span>HIGH LOADING WARNING</span>
                <strong>${topWarn.id}</strong>
                <small>${topWarn.name || formatType(topWarn.type)}: ${loadPct} simulated loading</small>
            </div>
        `;
    } else {
        html += `
            <div class="impact-card neutral-card">
                <span>NO OVERLOAD DETECTED</span>
                <strong>STABLE</strong>
                <small>Network capacity remains within simulated thermal limits</small>
            </div>
        `;
    }

    // Critical Facility Status Card
    const critRisk = response.critical_loads_at_risk || [];
    const h1Node = nodes.find(n => n.id === "H1");
    if (critRisk.length > 0 || (h1Node && h1Node.status !== "normal")) {
        const statusText = h1Node?.status === "critical_risk" ? "Emergency Supply Lost" : "Supply At Risk (Rerouting Required)";
        html += `
            <div class="impact-card critical-card">
                <span>CRITICAL FACILITY</span>
                <strong>H1 (Hospital)</strong>
                <small>${statusText}</small>
            </div>
        `;
    } else {
        html += `
            <div class="impact-card neutral-card">
                <span>CRITICAL SERVICES</span>
                <strong>SAFE</strong>
                <small>Hospital H1 fully supplied via operational feeder</small>
            </div>
        `;
    }

    impactGrid.innerHTML = html;
}

function renderRiskAnalysis(riskSummary, failedComp) {
    if (!riskSummary) return;

    const overallRisk = Math.round(riskSummary.overall_risk || 0);

    const fill = document.getElementById("riskMeterFill");
    if (fill) {
        fill.style.width = `${Math.max(8, overallRisk)}%`;
        if (overallRisk < 40) fill.style.background = "#2ddf8c";
        else if (overallRisk < 70) fill.style.background = "#ffb547";
        else fill.style.background = "#ff5364";
    }

    const riskVal = document.getElementById("riskValue");
    const riskSub = document.getElementById("riskSubtitle");
    if (riskVal) {
        let level = "LOW";
        let color = "#2ddf8c";
        let sub = "System operating under safe parameters";

        if (overallRisk >= 75) {
            level = "CRITICAL";
            color = "#ff5364";
            sub = "Critical contingency: active component loss & high stress";
        } else if (overallRisk >= 50) {
            level = "HIGH";
            color = "#ff5364";
            sub = "Elevated network risk with constrained backup capacity";
        } else if (overallRisk >= 30) {
            level = "MEDIUM";
            color = "#ffb547";
            sub = "Moderate vulnerability detected in current scenario";
        }

        riskVal.textContent = level;
        riskVal.style.color = color;
        if (riskSub) riskSub.textContent = sub;
    }

    const tag = document.getElementById("riskScenarioTag");
    if (tag) {
        tag.textContent = failedComp ? `Scenario: ${failedComp.id} (${failedComp.name || formatType(failedComp.type)}) Trip` : "Scenario: Baseline State";
    }

    const time = document.getElementById("riskTimestamp");
    if (time) time.textContent = `Evaluated: ${new Date().toLocaleTimeString()}`;

    // Risk Factor breakdown
    const factors = riskSummary.factors || {};
    const fLoad = document.getElementById("factorLoading");
    if (fLoad) fLoad.textContent = `${factors.component_loading ?? 18.5}%`;

    const fDep = document.getElementById("factorDependency");
    if (fDep) fDep.textContent = `${factors.network_dependency ?? 24.0}%`;

    const fCrit = document.getElementById("factorCriticalExposure");
    if (fCrit) fCrit.textContent = `${factors.critical_exposure ?? 15.0}%`;

    const fRed = document.getElementById("factorRedundancy");
    if (fRed) fRed.textContent = `${factors.redundancy ?? 88.0}%`;
}

function renderRiskAnalysisBaseline() {
    renderRiskAnalysis({
        overall_risk: 14.0,
        factors: {
            component_loading: 18.5,
            network_dependency: 24.0,
            critical_exposure: 15.0,
            redundancy: 88.0
        }
    }, null);
}

function renderCriticalFacilities(response) {
    const gridEl = document.getElementById("criticalFacilitiesGrid");
    if (!gridEl) return;

    const criticalNodes = nodes.filter(n => n.critical || n.id === "H1");
    if (criticalNodes.length === 0) {
        gridEl.innerHTML = `<div class="empty-state"><h3>No Critical Facilities Registered</h3></div>`;
        return;
    }

    let html = "";
    criticalNodes.forEach(fac => {
        let badgeClass = "safe";
        let statusText = "SAFE";
        let exposureText = "Normal Grid Supply";
        let actionText = "Continuous automated voltage & thermal monitoring active.";

        if (fac.status === "failed" || fac.status === "critical_risk") {
            badgeClass = "lost";
            statusText = "SUPPLY LOST";
            exposureText = "Unenergized - Source Outage";
            actionText = "Immediate deployment of emergency backup generation & blackstart tie-in required.";
        } else if (fac.status === "at_risk" || fac.status === "warning") {
            badgeClass = "at-risk";
            statusText = "AT RISK (REROUTED)";
            exposureText = `Primary feed interrupted via ${response?.failed_component?.id || "fault"}`;
            actionText = "Verify Feeder F5 thermal headroom & maintain tie-switch closure.";
        }

        const isAlternateAvailable = fac.status !== "critical_risk";

        html += `
            <div class="facility-card-advanced">
                <div class="facility-header">
                    <div class="facility-identity">
                        <div class="facility-icon-large">🏥</div>
                        <div>
                            <h3>${fac.name || "Hospital Critical Facility"} (${fac.id})</h3>
                            <p>Tier-1 Healthcare Life-Safety Infrastructure</p>
                        </div>
                    </div>
                    <span class="facility-badge ${badgeClass}">${statusText}</span>
                </div>

                <div class="facility-meta-grid">
                    <div class="facility-meta-item">
                        <span>Primary Feed Path</span>
                        <strong>Feeder F3 (via Transformer T7)</strong>
                    </div>
                    <div class="facility-meta-item">
                        <span>Alternate Feed Path</span>
                        <strong>Feeder F5 (via Transformer T8)</strong>
                    </div>
                    <div class="facility-meta-item">
                        <span>Supply Redundancy</span>
                        <strong style="color:${isAlternateAvailable ? 'var(--green)' : 'var(--red)'}">${isAlternateAvailable ? 'Active Dual-Feed Redundancy' : 'Unavailable'}</strong>
                    </div>
                    <div class="facility-meta-item">
                        <span>Demand / Capacity</span>
                        <strong>${getLoadingString(fac.load_mw)} / ${getCapacityString(fac.capacity_mw)}</strong>
                    </div>
                </div>

                <div class="facility-action-box">
                    <span>⚡</span>
                    <div><b>Recommended Operator Action:</b> ${actionText}</div>
                </div>
            </div>
        `;
    });

    gridEl.innerHTML = html;
}

function renderCriticalFacilitiesBaseline() {
    renderCriticalFacilities(null);
}

function renderRestorationPlan(restoration) {
    const restPanel = document.getElementById("restorationPanel");
    const restList = document.getElementById("restorationList");
    const scoreBadge = document.getElementById("restoreScoreBadge");
    const stratTitle = document.getElementById("restoreStrategyTitle");
    const centerDesc = document.getElementById("restoreCenterDescription");
    const centerActions = document.getElementById("restoreCenterActions");

    if (!restPanel || !restList) return;

    restPanel.classList.remove("hidden");

    const actions = restoration?.actions || [];
    const strat = restoration?.recommended_strategy;

    if (stratTitle && strat) {
        stratTitle.textContent = `${strat.strategy_id}: ${strat.description || "Optimized sequence"}`;
    }
    if (scoreBadge && strat) {
        scoreBadge.textContent = `SCORE: ${Math.round(strat.score)}/100`;
    }

    if (actions.length === 0) {
        restList.innerHTML = `<p style="color:var(--muted);padding:10px;">No restoration actions required for baseline state.</p>`;
        return;
    }

    const actionsHtml = actions.map(act => `
        <div class="restore-step">
            <span>${String(act.order).padStart(2, '0')}</span>
            <div>
                <strong>${act.action.toUpperCase()}: ${act.component || "Target Asset"}</strong>
                <p>${act.details || "Execute switching action according to standard protocol."}</p>
            </div>
            <b>✓</b>
        </div>
    `).join("");

    restList.innerHTML = actionsHtml;

    // Also populate Restoration Center page
    if (centerActions) {
        let centerHtml = `
            <div style="margin-top:20px;">
                <h3 style="margin-bottom:12px;font-size:15px;color:#38bdf8;">Recommended Sequence (${strat?.strategy_id || 'Active Plan'})</h3>
                <div class="restoration-list">${actionsHtml}</div>
            </div>
        `;

        if (restoration?.comparison) {
            const comp = restoration.comparison;
            centerHtml += `
                <table class="restore-metrics-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Pre-Restoration</th>
                            <th>Post-Restoration</th>
                            <th>Improvement</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Unserved Demand</td>
                            <td>${comp.before_optimization?.unserved_load_mw ?? 4.5} MW</td>
                            <td>${comp.after_optimization?.unserved_load_mw ?? 2.0} MW</td>
                            <td style="color:var(--green);font-weight:bold;">${comp.disruption_reduction_percent ?? 78.5}% Reduced</td>
                        </tr>
                        <tr>
                            <td>Critical Facilities Unserved</td>
                            <td>${comp.before_optimization?.critical_facilities_unserved ?? 1}</td>
                            <td>${comp.after_optimization?.critical_facilities_unserved ?? 0}</td>
                            <td style="color:var(--green);font-weight:bold;">100% Restored</td>
                        </tr>
                    </tbody>
                </table>
            `;
        }

        centerActions.innerHTML = centerHtml;
    }
}

function renderRestorationBaseline() {
    const centerActions = document.getElementById("restoreCenterActions");
    if (centerActions) {
        centerActions.innerHTML = `
            <div style="padding:18px;background:#090e15;border-radius:8px;border:1px solid var(--border);color:var(--muted);font-size:12px;">
                Grid is operating in steady baseline state. Select a component failure in the Overview or 3D Twin to synthesize an optimized combinatorial recovery plan.
            </div>
        `;
    }
}

// ============================================================================
// STATISTICS & WORKFLOW
// ============================================================================

function updateStatistics() {
    const total = nodes.length || 8;
    const failed = nodes.filter(n => n.status === "failed").length;
    const atRisk = nodes.filter(n => 
        n.status === "warning" || n.status === "high_risk" ||
        n.status === "at_risk" || n.status === "overloaded" ||
        n.status === "disconnected" || n.status === "critical_risk"
    ).length;
    const healthy = Math.max(0, total - failed - atRisk);

    const totalEl = document.getElementById("totalComponents");
    const healthyEl = document.getElementById("healthyComponents");
    const riskEl = document.getElementById("riskComponents");
    const failedEl = document.getElementById("failedComponents");

    if (totalEl) totalEl.textContent = total;
    if (healthyEl) healthyEl.textContent = healthy;
    if (riskEl) riskEl.textContent = atRisk;
    if (failedEl) failedEl.textContent = failed;
}

function updateWorkflow() {
    const steps = [
        document.getElementById("wfStep1"),
        document.getElementById("wfStep2"),
        document.getElementById("wfStep3"),
        document.getElementById("wfStep4")
    ];

    steps.forEach(s => s?.classList.remove("active-step"));

    if (!simulationActive) {
        steps[0]?.classList.add("active-step");
    } else {
        steps[0]?.classList.add("active-step");
        steps[1]?.classList.add("active-step");
        setTimeout(() => steps[2]?.classList.add("active-step"), 400);
        setTimeout(() => steps[3]?.classList.add("active-step"), 800);
    }
}

// ============================================================================
// NAVIGATION & 2D/3D TOGGLE
// ============================================================================

function showSection(sectionId) {
    document.querySelectorAll(".section").forEach(sec => sec.classList.remove("active-section"));
    const target = document.getElementById(sectionId);
    if (target) target.classList.add("active-section");

    document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));
    const clickedBtn = [...document.querySelectorAll(".nav-item")].find(btn => 
        btn.getAttribute("onclick")?.includes(sectionId)
    );
    if (clickedBtn) clickedBtn.classList.add("active");

    if (sectionId === "overview") {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => resizeAndRender2D());
        });
    } else if (sectionId === "grid") {
        requestAnimationFrame(() => {
            drawLargeGrid();
        });
    }
}

function switchGridView(mode) {
    currentGridView = mode;
    const canvas2D = document.getElementById("gridCanvas");
    const container3D = document.getElementById("grid3dContainer");
    const btn2D = document.getElementById("btnView2D");
    const btn3D = document.getElementById("btnView3D");

    btn2D?.classList.toggle("active", mode === "2d");
    btn3D?.classList.toggle("active", mode === "3d");

    if (mode === "3d") {
        if (canvas2D) canvas2D.style.display = "none";
        container3D?.classList.remove("hidden");
        if (window.grid3D) {
            if (!window.grid3D.isInitialized) {
                window.grid3D.init("grid3dContainer");
            }
            window.grid3D.onWindowResize();
        }
    } else {
        container3D?.classList.add("hidden");
        if (canvas2D) canvas2D.style.display = "block";
        requestAnimationFrame(() => {
            resizeAndRender2D();
        });
    }
}

function drawLargeGrid() {
    const largeCanvas = document.getElementById("gridCanvasLarge");
    if (!largeCanvas) return;

    const largeCtx = largeCanvas.getContext("2d");
    if (!largeCtx) return;

    const rect = largeCanvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(rect.width, 1);
    const height = Math.max(rect.height, 1);

    largeCanvas.width = Math.round(width * ratio);
    largeCanvas.height = Math.round(height * ratio);

    largeCtx.setTransform(1, 0, 0, 1, 0, 0);
    largeCtx.scale(ratio, ratio);
    largeCtx.clearRect(0, 0, width, height);

    // Draw Grid background lines
    largeCtx.strokeStyle = "#172230";
    largeCtx.lineWidth = 1;

    for (let x = 0; x < width; x += 40) {
        largeCtx.beginPath();
        largeCtx.moveTo(x, 0);
        largeCtx.lineTo(x, height);
        largeCtx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
        largeCtx.beginPath();
        largeCtx.moveTo(0, y);
        largeCtx.lineTo(width, y);
        largeCtx.stroke();
    }

    // Connections
    connections.forEach(conn => {
        const nodeA = nodes.find(n => n.id === conn[0]);
        const nodeB = nodes.find(n => n.id === conn[1]);
        if (!nodeA || !nodeB) return;

        largeCtx.beginPath();
        largeCtx.moveTo(nodeA.x * width, nodeA.y * height);
        largeCtx.lineTo(nodeB.x * width, nodeB.y * height);
        largeCtx.strokeStyle = (nodeA.status === "failed" || nodeB.status === "failed") ? "#ff5364" : "#30445a";
        largeCtx.lineWidth = 4;
        largeCtx.stroke();
    });

    // Nodes
    nodes.forEach(node => {
        const px = node.x * width;
        const py = node.y * height;
        let color = node.status === "failed" ? "#ff5364" : (node.critical ? "#a879ff" : "#2ddf8c");

        largeCtx.beginPath();
        largeCtx.arc(px, py, 26, 0, Math.PI * 2);
        largeCtx.fillStyle = "#0d1722";
        largeCtx.fill();
        largeCtx.strokeStyle = color;
        largeCtx.lineWidth = 4;
        largeCtx.stroke();

        largeCtx.fillStyle = color;
        largeCtx.font = "bold 14px Inter, Arial, sans-serif";
        largeCtx.textAlign = "center";
        largeCtx.textBaseline = "middle";
        largeCtx.fillText(node.id, px, py);

        largeCtx.fillStyle = "#e7edf5";
        largeCtx.font = "bold 12px Inter, Arial, sans-serif";
        largeCtx.fillText(node.type, px, py + 42);
    });
}

// ============================================================================
// INITIALIZATION
// ============================================================================

window.addEventListener("resize", () => {
    if (currentGridView === "2d") resizeAndRender2D();
});

window.addEventListener("DOMContentLoaded", async () => {
    console.log("GridTwin Frontend Initializing...");

    // Attach ResizeObserver to canvas container to ensure 2D graph is ALWAYS fitted
    const container = document.getElementById("canvasContainer");
    if (container && typeof ResizeObserver !== "undefined") {
        const observer = new ResizeObserver(() => {
            if (currentGridView === "2d") resizeAndRender2D();
        });
        observer.observe(container);
    }

    // Health Check
    await checkBackendHealth();

    // Load Authoritative Grid Data
    await loadGridFromBackend();

    // Wait for complete browser layout before rendering 2D canvas
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            resizeAndRender2D();
            console.log("GridTwin 2D Canvas Fitted ✓");
        });
    });

    updateStatistics();
    updateWorkflow();
});
