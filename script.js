// ============================================================
// GRIDTWIN FRONTEND - INTEGRATED WITH BACKEND
// HTML + CSS + JavaScript + Canvas + FastAPI
// ============================================================

// API Configuration
const API_BASE = window.location.origin;
let backendHealthy = false;
let lastSimulationResponse = null;

// Node position mappings (frontend coordinates preserved)
// Backend uses T8, but frontend displays at T5 position for backward compatibility
const nodePositions = {
    "S1": { x: 0.50, y: 0.12, label: "S1", type: "Substation" },
    "T7": { x: 0.35, y: 0.35, label: "T7", type: "Transformer" },
    "T8": { x: 0.65, y: 0.35, label: "T8", type: "Transformer" },  // Backend T8
    "T5": { x: 0.65, y: 0.35, label: "T5", type: "Transformer" },  // Frontend fallback
    "F3": { x: 0.35, y: 0.57, label: "F3", type: "Feeder" },
    "F5": { x: 0.65, y: 0.57, label: "F5", type: "Feeder" },
    "L1": { x: 0.22, y: 0.78, label: "L1", type: "Load" },
    "H1": { x: 0.48, y: 0.80, label: "H1", type: "Hospital" },
    "L2": { x: 0.75, y: 0.78, label: "L2", type: "Load" }
};

// Grid data from backend
let nodes = [];
let connections = [];
let backendGridData = null;

// Canvas state
const canvas = document.getElementById("gridCanvas");
const ctx = canvas.getContext("2d");

let selectedNode = null;
let simulationActive = false;

function setStatusIndicatorState(isHealthy) {
    const dots = document.querySelectorAll(".status-dot, .online-dot");
    dots.forEach(dot => {
        dot.classList.toggle("online", Boolean(isHealthy));
        dot.classList.toggle("offline", !isHealthy);
    });

    const systemStatus = document.querySelector(".system-status");
    if (systemStatus) {
        systemStatus.style.color = isHealthy ? "#2ddf8c" : "#ff5364";
        systemStatus.style.borderColor = isHealthy ? "#1d4434" : "#4a1d2a";
        systemStatus.style.background = isHealthy ? "#0b1914" : "#1c0f14";
        systemStatus.textContent = isHealthy ? "SYSTEM ONLINE" : "SYSTEM OFFLINE";
    }
}

// ============================================================================
// API HELPER FUNCTIONS
// ============================================================================

/**
 * Generic fetch helper with error handling
 */
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

        const data = await response.json();
        return data;
    } catch (error) {
        console.error(`API Call Failed: ${endpoint}`, error);
        return null;
    }
}

/**
 * Check backend health status
 */
async function checkBackendHealth() {
    const response = await apiCall("/health");

    if (response && response.status === "healthy") {
        backendHealthy = true;
        setStatusIndicatorState(true);
        console.log("Backend is HEALTHY ✓");
        return true;
    } else {
        backendHealthy = false;
        setStatusIndicatorState(false);
        console.error("Backend is OFFLINE");
        return false;
    }
}

/**
 * Load grid data from backend
 */
async function loadGridFromBackend() {
    const gridData = await apiCall("/api/grid");

    if (!gridData || !gridData.nodes) {
        console.error("Failed to load grid from backend");
        return false;
    }

    backendGridData = gridData;

    // Convert backend nodes to frontend format
    nodes = gridData.nodes.map(backendNode => {
        const pos = nodePositions[backendNode.id] || nodePositions["S1"];

        return {
            id: backendNode.id,
            name: backendNode.name,
            type: formatType(backendNode.type),
            x: pos.x,
            y: pos.y,
            status: backendNode.status,
            capacity_mw: backendNode.capacity_mw,
            load_mw: backendNode.load_mw,
            loading: calculateLoadingPercent(backendNode.load_mw, backendNode.capacity_mw),
            criticality: backendNode.criticality,
            critical: backendNode.is_critical_load,
            // Store backend-native fields
            _backendData: backendNode
        };
    });

    // Build connections from edges
    connections = [];
    const seenConnections = new Set();

    gridData.edges.forEach(edge => {
        const key = `${edge.source}|${edge.target}`;
        if (!seenConnections.has(key)) {
            connections.push([edge.source, edge.target]);
            seenConnections.add(key);
        }
    });

    console.log(`Grid loaded: ${nodes.length} nodes, ${connections.length} connections`);
    updateStatistics();
    drawGrid();

    return true;
}

/**
 * Get component details from backend
 */
async function getComponentDetails(componentId) {
    const response = await apiCall(`/api/components/${componentId}`);
    return response;
}

/**
 * Simulate failure via backend
 */
async function simulateFailureBackend(componentId) {
    const request = { component_id: componentId };

    const response = await apiCall("/api/simulate/failure", {
        method: "POST",
        body: JSON.stringify(request)
    });

    if (!response) {
        console.error("Simulation failed");
        return null;
    }

    lastSimulationResponse = response;
    return response;
}

/**
 * Reset simulation via backend
 */
async function resetSimulationBackend() {
    const response = await apiCall("/api/simulation/reset", {
        method: "POST",
        body: JSON.stringify({})
    });

    if (response && response.status === "success") {
        lastSimulationResponse = null;
        // Reload grid to get baseline state
        await loadGridFromBackend();
        return true;
    }

    return false;
}

// ============================================================================
// HELPER FUNCTIONS
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
    return `${capacityMw.toFixed(1)} MW`;
}

function getLoadingString(loadMw) {
    return `${loadMw.toFixed(1)} MW`;
}

// ============================================================================
// CANVAS FUNCTIONS
// ============================================================================

function resizeCanvas() {
    if (!canvas || !ctx) return;

    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(rect.width, 1);
    const height = Math.max(rect.height, 1);

    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(ratio, ratio);

    drawGrid();
}

function getPosition(node) {
    return {
        x: node.x * canvas.clientWidth,
        y: node.y * canvas.clientHeight
    };
}

function drawGrid() {
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);

    // Draw connections first
    connections.forEach(connection => {
        const nodeA = nodes.find(n => n.id === connection[0]);
        const nodeB = nodes.find(n => n.id === connection[1]);

        if (!nodeA || !nodeB) return;

        const a = getPosition(nodeA);
        const b = getPosition(nodeB);

        // Check if connection involves failed component
        let lineColor = "#263548";

        if (simulationActive &&
            (nodeA.status === "failed" || nodeB.status === "failed" ||
             nodeA.status === "warning" || nodeB.status === "warning")) {
            lineColor = "#ff5364";
        }

        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 3;
        ctx.stroke();
    });

    // Draw nodes
    nodes.forEach(node => {
        const position = getPosition(node);

        let color = "#2ddf8c";

        if (node.status === "warning" || node.status === "high_risk") {
            color = "#ffb547";
        } else if (node.status === "failed" || node.status === "critical") {
            color = "#ff5364";
        } else if (node.critical) {
            color = "#a879ff";
        }

        drawNode(position.x, position.y, node, color);
    });
}

function drawNode(x, y, node, color) {
    const radius = 20;

    // Glow
    ctx.beginPath();
    ctx.arc(x, y, radius + 7, 0, Math.PI * 2);
    ctx.fillStyle = color + "18";
    ctx.fill();

    // Node
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = "#0e1722";
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();

    // Icon
    ctx.fillStyle = color;
    ctx.font = "bold 13px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    let icon = "●";
    if (node.type === "Substation") icon = "S";
    if (node.type === "Transformer") icon = "T";
    if (node.type === "Feeder") icon = "F";
    if (node.type === "Load") icon = "L";
    if (node.type === "Hospital") icon = "H";
    if (node.type === "Emergency Service") icon = "E";

    if (node.status === "failed") {
        icon = "✕";
    }

    ctx.fillText(icon, x, y);

    // Label
    ctx.fillStyle = "#e8edf4";
    ctx.font = "bold 11px Arial";
    ctx.fillText(node.id, x, y + 35);

    // Status
    ctx.fillStyle = color;
    ctx.font = "9px Arial";

    let statusText = "NORMAL";
    if (node.status === "warning") statusText = "WARNING";
    if (node.status === "high_risk") statusText = "HIGH RISK";
    if (node.status === "critical") statusText = "CRITICAL";
    if (node.status === "failed") statusText = "FAILED";

    ctx.fillText(statusText, x, y + 48);
}

// ============================================================================
// CLICK HANDLING
// ============================================================================

canvas.addEventListener("click", async function(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    let clicked = null;

    nodes.forEach(node => {
        const position = getPosition(node);
        const distance = Math.sqrt(
            Math.pow(mouseX - position.x, 2) +
            Math.pow(mouseY - position.y, 2)
        );

        if (distance < 30) {
            clicked = node;
        }
    });

    if (clicked) {
        selectedNode = clicked;
        showComponentDetails(clicked);
    }
});

// ============================================================================
// COMPONENT DETAILS
// ============================================================================

function showComponentDetails(node) {
    const details = document.getElementById("componentDetails");

    let statusClass = "status-normal";
    let statusText = "NORMAL";

    if (node.status === "failed") {
        statusClass = "status-failed";
        statusText = "FAILED";
    } else if (node.status === "warning" || node.status === "high_risk") {
        statusClass = "status-warning";
        statusText = node.status === "high_risk" ? "HIGH RISK" : "WARNING";
    }

    let html = `
        <div class="component-info">
            <div class="component-name">
                <div>
                    <h3>${node.id}</h3>
                    <div class="component-type">
                        ${node.name || node.type}
                    </div>
                </div>
                <span class="status-badge ${statusClass}">
                    ${statusText}
                </span>
            </div>

            <div class="info-row">
                <span>Type</span>
                <strong>${node.type}</strong>
            </div>

            <div class="info-row">
                <span>Capacity</span>
                <strong>${getCapacityString(node.capacity_mw)}</strong>
            </div>

            <div class="info-row">
                <span>Current Load</span>
                <strong>${getLoadingString(node.load_mw)}</strong>
            </div>

            <div class="info-row">
                <span>Loading</span>
                <strong>${node.loading}</strong>
            </div>

            <div class="info-row">
                <span>Critical Facility</span>
                <strong>
                    ${node.critical ? "YES" : "NO"}
                </strong>
            </div>
    `;

    // Only allow failure simulation for suitable components and not already failed
    if (
        (node.type === "Transformer" ||
         node.type === "Feeder" ||
         node.type === "Substation" ||
         node.type === "Load" ||
         node.type === "Hospital") &&
        node.status !== "failed"
    ) {
        html += `
            <button
                class="failure-btn"
                onclick="simulateFailureButtonClick('${node.id}')"
            >
                💥 SIMULATE FAILURE
            </button>
        `;
    } else if (node.status === "failed") {
        html += `
            <button
                class="failure-btn"
                onclick="resetSimulationButtonClick()"
            >
                ↻ RESET SIMULATION
            </button>
        `;
    }

    html += `</div>`;

    details.innerHTML = html;
    document.getElementById("componentHint").textContent =
        "Selected component: " + node.id;
}

// ============================================================================
// FAILURE SIMULATION
// ============================================================================

async function simulateFailureButtonClick(nodeId) {
    if (!backendHealthy) {
        alert("Backend is not available. Cannot simulate failure.");
        return;
    }

    // Show loading
    const failedNode = nodes.find(n => n.id === nodeId);
    if (!failedNode) return;

    // Call backend
    const simulationResult = await simulateFailureBackend(nodeId);

    if (!simulationResult) {
        alert("Simulation failed. Please try again.");
        return;
    }

    // Update node statuses based on backend response
    simulationActive = true;

    // Mark failed component
    failedNode.status = "failed";

    // Mark affected components
    if (simulationResult.affected_components) {
        simulationResult.affected_components.forEach(affectedNode => {
            const frontendNode = nodes.find(n => n.id === affectedNode.id);
            if (frontendNode) {
                frontendNode.status = "warning";
            }
        });
    }

    // Mark critical loads at risk
    if (simulationResult.critical_loads_at_risk) {
        simulationResult.critical_loads_at_risk.forEach(criticalNode => {
            const frontendNode = nodes.find(n => n.id === criticalNode.id);
            if (frontendNode) {
                frontendNode.status = "warning";
            }
        });
    }

    // Update statistics
    updateStatistics();

    // Show component
    showComponentDetails(failedNode);

    // Show simulation results
    showSimulationResults(simulationResult);

    // Update workflow
    updateWorkflow();

    drawGrid();
}

function showSimulationResults(response) {
    // Show impact panel
    const impactPanel = document.getElementById("impactPanel");
    if (impactPanel) {
        impactPanel.classList.remove("hidden");
    }

    // Show restoration panel
    const restorationPanel = document.getElementById("restorationPanel");
    if (restorationPanel) {
        restorationPanel.classList.remove("hidden");
    }

    // Update failed component name
    const failedNameEl = document.getElementById("failedName");
    if (failedNameEl && response.failed_component) {
        failedNameEl.textContent = response.failed_component.id;
    }

    // Update risk score
    if (response.risk_summary) {
        const overallRisk = Math.round(response.risk_summary.overall_risk);

        const riskScoreEl = document.getElementById("riskScore");
        if (riskScoreEl) {
            riskScoreEl.textContent = overallRisk + "%";
        }

        const riskMeterFill = document.getElementById("riskMeterFill");
        if (riskMeterFill) {
            riskMeterFill.style.width = overallRisk + "%";
            if (overallRisk < 40) {
                riskMeterFill.style.background = "#2ddf8c";
            } else if (overallRisk < 70) {
                riskMeterFill.style.background = "#ffb547";
            } else {
                riskMeterFill.style.background = "#ff5364";
            }
        }

        const riskValueEl = document.getElementById("riskValue");
        if (riskValueEl) {
            let riskLevel = "LOW";
            let riskColor = "#2ddf8c";

            if (overallRisk >= 70) {
                riskLevel = "HIGH";
                riskColor = "#ff5364";
            } else if (overallRisk >= 40) {
                riskLevel = "MEDIUM";
                riskColor = "#ffb547";
            }

            riskValueEl.textContent = riskLevel;
            riskValueEl.style.color = riskColor;
        }
    }

    // Show cascade results if available
    if (response.cascade && response.cascade.length > 0) {
        const cascadeHtml = response.cascade
            .map(event => `<div>• ${event.component}: ${event.event}</div>`)
            .join("");

        const cascadeEl = document.getElementById("cascadeResults");
        if (cascadeEl) {
            cascadeEl.innerHTML = cascadeHtml || "No cascade events";
        }
    }

    // Show restoration info if available
    if (response.restoration) {
        let restoreMessage = "Analyzing restoration options...";

        if (response.restoration.recommended_strategy) {
            restoreMessage = `
                ✓ Restoration plan generated.
                <br><strong>Strategy:</strong> ${response.restoration.recommended_strategy.strategy_id}
                <br><strong>Score:</strong> ${response.restoration.recommended_strategy.score}/100
            `;
        } else if (response.restoration.available) {
            restoreMessage = "Optimizer available - analyzing best restoration path...";
        }

        const restoreMessageEl = document.getElementById("restoreMessage");
        if (restoreMessageEl) {
            restoreMessageEl.innerHTML = restoreMessage;
        }
    }

    // Show critical facilities at risk
    if (response.critical_loads_at_risk && response.critical_loads_at_risk.length > 0) {
        const facilitiesHtml = response.critical_loads_at_risk
            .map(facility => `<div>• ${facility.name || facility.id} (${facility.type})</div>`)
            .join("");

        const facilitiesEl = document.getElementById("criticalFacilitiesAtRisk");
        if (facilitiesEl) {
            facilitiesEl.innerHTML = facilitiesHtml || "No critical facilities at risk";
        }
    }
}

// ============================================================================
// RESET
// ============================================================================

async function resetSimulationButtonClick() {
    if (!backendHealthy) {
        alert("Backend is not available. Cannot reset simulation.");
        return;
    }

    const success = await resetSimulationBackend();

    if (!success) {
        alert("Reset failed. Please try again.");
        return;
    }

    resetSimulationUI();
}

function resetSimulationUI() {
    simulationActive = false;

    // Reset all node statuses
    nodes.forEach(node => {
        node.status = "normal";
    });

    // Hide panels
    const impactPanel = document.getElementById("impactPanel");
    if (impactPanel) {
        impactPanel.classList.add("hidden");
    }

    const restorationPanel = document.getElementById("restorationPanel");
    if (restorationPanel) {
        restorationPanel.classList.add("hidden");
    }

    // Reset risk meter
    const riskMeterFill = document.getElementById("riskMeterFill");
    if (riskMeterFill) {
        riskMeterFill.style.width = "0%";
        riskMeterFill.style.background = "#2ddf8c";
    }

    const riskValueEl = document.getElementById("riskValue");
    if (riskValueEl) {
        riskValueEl.textContent = "NORMAL";
        riskValueEl.style.color = "#2ddf8c";
    }

    updateStatistics();
    drawGrid();

    document.getElementById("componentDetails").innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">⌁</div>
            <h3>No Component Selected</h3>
            <p>
                Click a component on the grid to select it.
            </p>
        </div>
    `;

    document.getElementById("componentHint").textContent =
        "Select a component";

    updateWorkflow();
}

// ============================================================================
// STATISTICS
// ============================================================================

function updateStatistics() {
    const total = nodes.length;
    const failed = nodes.filter(node => node.status === "failed").length;
    const warning = nodes.filter(node =>
        node.status === "warning" || node.status === "high_risk"
    ).length;
    const healthy = total - failed - warning;

    document.getElementById("totalComponents").textContent = total;
    document.getElementById("healthyComponents").textContent = healthy;
    document.getElementById("riskComponents").textContent = warning;
    document.getElementById("failedComponents").textContent = failed;
}

// ============================================================================
// WORKFLOW
// ============================================================================

function updateWorkflow() {
    const steps = document.querySelectorAll(".workflow-step");

    steps.forEach(step => {
        step.classList.remove("active-step");
    });

    if (!simulationActive) {
        steps[0].classList.add("active-step");
    } else {
        steps[1].classList.add("active-step");

        setTimeout(() => {
            steps[2].classList.add("active-step");
        }, 600);

        setTimeout(() => {
            steps[3].classList.add("active-step");
        }, 1200);
    }
}

// ============================================================================
// NAVIGATION
// ============================================================================

function showSection(sectionId) {
    document
        .querySelectorAll(".section")
        .forEach(section => {
            section.classList.remove("active-section");
        });

    const selectedSection = document.getElementById(sectionId);

    if (selectedSection) {
        selectedSection.classList.add("active-section");
    }

    document
        .querySelectorAll(".nav-item")
        .forEach(button => {
            button.classList.remove("active");
        });

    const clickedButton =
        [...document.querySelectorAll(".nav-item")]
            .find(button =>
                button.getAttribute("onclick")
                    ?.includes(sectionId)
            );

    if (clickedButton) {
        clickedButton.classList.add("active");
    }

    if (sectionId === "grid") {
        requestAnimationFrame(() => {
            const gridSection = document.getElementById("grid");
            if (gridSection && gridSection.classList.contains("active-section")) {
                drawLargeGrid();
            }
        });
    }
}

// ============================================================================
// LARGE CANVAS
// ============================================================================

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

    const positions = {};
    nodes.forEach(node => {
        positions[node.id] = [
            node.x * width,
            node.y * height
        ];
    });

    connections.forEach(connection => {
        const a = positions[connection[0]];
        const b = positions[connection[1]];

        if (!a || !b) return;

        largeCtx.beginPath();
        largeCtx.moveTo(a[0], a[1]);
        largeCtx.lineTo(b[0], b[1]);
        largeCtx.strokeStyle = "#30445a";
        largeCtx.lineWidth = 5;
        largeCtx.stroke();
    });

    nodes.forEach(node => {
        const position = positions[node.id];

        if (!position) return;

        let color = "#2ddf8c";

        if (node.status === "warning" || node.status === "high_risk") {
            color = "#ffb547";
        } else if (node.status === "failed" || node.status === "critical") {
            color = "#ff5364";
        } else if (node.critical) {
            color = "#a879ff";
        }

        largeCtx.beginPath();
        largeCtx.arc(position[0], position[1], 30, 0, Math.PI * 2);
        largeCtx.fillStyle = "#0d1722";
        largeCtx.fill();
        largeCtx.strokeStyle = color;
        largeCtx.lineWidth = 4;
        largeCtx.stroke();

        largeCtx.fillStyle = color;
        largeCtx.font = "bold 15px Arial";
        largeCtx.textAlign = "center";
        largeCtx.textBaseline = "middle";
        largeCtx.fillText(node.id, position[0], position[1]);

        largeCtx.fillStyle = "#e7edf5";
        largeCtx.font = "bold 13px Arial";
        largeCtx.fillText(node.type, position[0], position[1] + 52);
    });
}

// ============================================================================
// INITIALIZATION
// ============================================================================

window.addEventListener("resize", resizeCanvas);

window.addEventListener("load", async () => {
    console.log("GridTwin Frontend initializing...");

    // Check backend health
    await checkBackendHealth();

    // Load grid from backend
    if (backendHealthy) {
        await loadGridFromBackend();
        console.log("✓ Frontend ready with backend data");
    } else {
        console.warn("⚠ Backend offline - frontend may not be fully functional");
        // Try to show something useful
        resizeCanvas();
    }

    updateStatistics();
    updateWorkflow();
});
