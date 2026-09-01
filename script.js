// ============================================================
// GRIDTWIN FRONTEND
// HTML + CSS + JavaScript + Canvas
// ============================================================


// ================= GRID DATA =================

const nodes = [
    {
        id: "S1",
        type: "Substation",
        x: 0.50,
        y: 0.12,
        status: "normal",
        capacity: "500 MW",
        loading: "62%"
    },

    {
        id: "T7",
        type: "Transformer",
        x: 0.35,
        y: 0.35,
        status: "normal",
        capacity: "100 MW",
        loading: "72%"
    },

    {
        id: "T5",
        type: "Transformer",
        x: 0.65,
        y: 0.35,
        status: "normal",
        capacity: "120 MW",
        loading: "58%"
    },

    {
        id: "F3",
        type: "Feeder",
        x: 0.35,
        y: 0.57,
        status: "normal",
        capacity: "100 MW",
        loading: "68%"
    },

    {
        id: "F5",
        type: "Feeder",
        x: 0.65,
        y: 0.57,
        status: "normal",
        capacity: "100 MW",
        loading: "54%"
    },

    {
        id: "L1",
        type: "Load",
        x: 0.22,
        y: 0.78,
        status: "normal",
        capacity: "50 MW",
        loading: "60%"
    },

    {
        id: "H1",
        type: "Hospital",
        x: 0.48,
        y: 0.80,
        status: "normal",
        capacity: "30 MW",
        loading: "70%",
        critical: true
    },

    {
        id: "L2",
        type: "Industrial Load",
        x: 0.75,
        y: 0.78,
        status: "normal",
        capacity: "70 MW",
        loading: "65%"
    }
];


const connections = [
    ["S1", "T7"],
    ["S1", "T5"],
    ["T7", "F3"],
    ["T5", "F5"],
    ["F3", "L1"],
    ["F3", "H1"],
    ["F5", "H1"],
    ["F5", "L2"]
];


// ================= CANVAS =================

const canvas = document.getElementById("gridCanvas");
const ctx = canvas.getContext("2d");

let selectedNode = null;
let simulationActive = false;


// Resize canvas
function resizeCanvas() {

    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;

    ctx.scale(
        window.devicePixelRatio,
        window.devicePixelRatio
    );

    drawGrid();
}


// Get actual node position
function getPosition(node) {

    return {
        x: node.x * canvas.clientWidth,
        y: node.y * canvas.clientHeight
    };
}


// ================= DRAW GRID =================

function drawGrid() {

    ctx.clearRect(
        0,
        0,
        canvas.clientWidth,
        canvas.clientHeight
    );


    // Draw connections first
    connections.forEach(connection => {

        const nodeA = nodes.find(n => n.id === connection[0]);
        const nodeB = nodes.find(n => n.id === connection[1]);

        if (!nodeA || !nodeB) return;

        const a = getPosition(nodeA);
        const b = getPosition(nodeB);

        let lineColor = "#263548";

        if (
            simulationActive &&
            (
                connection.includes("T7") ||
                connection.includes("F3")
            )
        ) {
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

        if (node.status === "warning") {
            color = "#ffb547";
        }

        if (node.status === "failed") {
            color = "#ff5364";
        }

        if (node.critical) {
            color = "#a879ff";
        }

        drawNode(
            position.x,
            position.y,
            node,
            color
        );
    });
}


// ================= DRAW NODE =================

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
    if (node.type === "Industrial Load") icon = "L";
    if (node.type === "Hospital") icon = "H";

    if (node.status === "failed") {
        icon = "✕";
    }

    ctx.fillText(icon, x, y);


    // Label
    ctx.fillStyle = "#e8edf4";
    ctx.font = "bold 11px Arial";

    ctx.fillText(
        node.id,
        x,
        y + 35
    );


    // Status
    ctx.fillStyle = color;
    ctx.font = "9px Arial";

    let statusText = "NORMAL";

    if (node.status === "warning") {
        statusText = "WARNING";
    }

    if (node.status === "failed") {
        statusText = "FAILED";
    }

    ctx.fillText(
        statusText,
        x,
        y + 48
    );
}


// ================= CLICK HANDLING =================

canvas.addEventListener("click", function(event) {

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


// ================= COMPONENT DETAILS =================

function showComponentDetails(node) {

    const details =
        document.getElementById("componentDetails");

    let statusClass = "status-normal";
    let statusText = "NORMAL";

    if (node.status === "failed") {
        statusClass = "status-failed";
        statusText = "FAILED";
    }

    if (node.status === "warning") {
        statusClass = "status-warning";
        statusText = "WARNING";
    }


    let html = `

        <div class="component-info">

            <div class="component-name">

                <div>
                    <h3>${node.id}</h3>

                    <div class="component-type">
                        ${node.type}
                    </div>
                </div>

                <span class="status-badge ${statusClass}">
                    ${statusText}
                </span>

            </div>


            <div class="info-row">
                <span>Capacity</span>
                <strong>${node.capacity}</strong>
            </div>


            <div class="info-row">
                <span>Current Loading</span>
                <strong>${node.loading}</strong>
            </div>


            <div class="info-row">
                <span>Critical Facility</span>
                <strong>
                    ${node.critical ? "YES" : "NO"}
                </strong>
            </div>

    `;


    // Only allow failure simulation for suitable components
    if (
        node.type === "Transformer" ||
        node.type === "Feeder" ||
        node.type === "Substation"
    ) {

        if (node.status !== "failed") {

            html += `

                <button
                    class="failure-btn"
                    onclick="simulateFailure('${node.id}')"
                >
                    💥 SIMULATE FAILURE
                </button>

            `;

        } else {

            html += `

                <button
                    class="failure-btn"
                    onclick="resetSimulation()"
                >
                    ↻ RESET SIMULATION
                </button>

            `;

        }

    }


    html += `</div>`;

    details.innerHTML = html;

    document.getElementById("componentHint").textContent =
        "Selected component: " + node.id;
}


// ================= FAILURE SIMULATION =================

function simulateFailure(nodeId) {

    simulationActive = true;


    const failedNode =
        nodes.find(node => node.id === nodeId);

    if (!failedNode) return;


    // Mark failed component
    failedNode.status = "failed";


    // Simulated cascade
    const feeder =
        nodes.find(node => node.id === "F3");

    const hospital =
        nodes.find(node => node.id === "H1");


    if (feeder) {

        feeder.status = "warning";
        feeder.loading = "118%";

    }


    if (hospital) {

        hospital.status = "warning";

    }


    // Update statistics
    updateStatistics();


    // Show component
    showComponentDetails(failedNode);


    // Show cascade result
    document
        .getElementById("impactPanel")
        .classList.remove("hidden");


    document
        .getElementById("restorationPanel")
        .classList.remove("hidden");


    document
        .getElementById("failedName")
        .textContent = nodeId;


    // Update risk
    document
        .getElementById("riskScore")
        .textContent = "82%";


    document
        .getElementById("riskMeterFill")
        .style.width = "82%";


    document
        .getElementById("riskMeterFill")
        .style.background = "#ff5364";


    document
        .getElementById("riskValue")
        .textContent = "HIGH";


    document
        .getElementById("riskValue")
        .style.color = "#ff5364";


    // Change workflow
    updateWorkflow();


    drawGrid();

}


// ================= RESET =================

function resetSimulation() {

    simulationActive = false;

    nodes.forEach(node => {

        node.status = "normal";

    });


    const feeder =
        nodes.find(node => node.id === "F3");

    if (feeder) {
        feeder.loading = "68%";
    }


    const hospital =
        nodes.find(node => node.id === "H1");

    if (hospital) {
        hospital.status = "normal";
    }


    document
        .getElementById("impactPanel")
        .classList.add("hidden");


    document
        .getElementById("restorationPanel")
        .classList.add("hidden");


    document
        .getElementById("riskMeterFill")
        .style.width = "25%";


    document
        .getElementById("riskMeterFill")
        .style.background = "#2ddf8c";


    document
        .getElementById("riskValue")
        .textContent = "LOW";


    document
        .getElementById("riskValue")
        .style.color = "#2ddf8c";


    updateStatistics();

    drawGrid();


    document.getElementById("componentDetails").innerHTML = `

        <div class="empty-state">

            <div class="empty-icon">⌁</div>

            <h3>No Component Selected</h3>

            <p>
                Click a transformer, feeder, load or facility on the grid.
            </p>

        </div>

    `;

    document.getElementById("componentHint").textContent =
        "Select a component";


    updateWorkflow();

}


// ================= STATISTICS =================

function updateStatistics() {

    const total = nodes.length;

    const failed =
        nodes.filter(node => node.status === "failed").length;

    const warning =
        nodes.filter(node => node.status === "warning").length;

    const healthy =
        total - failed - warning;


    document.getElementById("totalComponents")
        .textContent = total;


    document.getElementById("healthyComponents")
        .textContent = healthy;


    document.getElementById("riskComponents")
        .textContent = warning;


    document.getElementById("failedComponents")
        .textContent = failed;
}


// ================= WORKFLOW =================

function updateWorkflow() {

    const steps =
        document.querySelectorAll(".workflow-step");


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


// ================= NAVIGATION =================

function showSection(sectionId) {

    document
        .querySelectorAll(".section")
        .forEach(section => {

            section.classList.remove("active-section");

        });


    const selectedSection =
        document.getElementById(sectionId);


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


    // Draw large map
    if (sectionId === "grid") {

        drawLargeGrid();

    }

}


// ================= RESTORATION =================

function showRestoration() {

    document.getElementById("restoreMessage").innerHTML = `

        ✓ Restoration plan generated successfully.

        <br><br>

        <strong>
            Recommended:
        </strong>

        Isolate failed component →
        Transfer feasible load →
        Prioritize critical facility →
        Restore remaining loads.

    `;

}


// ================= LARGE CANVAS =================

const largeCanvas =
    document.getElementById("gridCanvasLarge");

const largeCtx =
    largeCanvas.getContext("2d");


function drawLargeGrid() {

    const rect =
        largeCanvas.getBoundingClientRect();


    largeCanvas.width =
        rect.width * window.devicePixelRatio;

    largeCanvas.height =
        rect.height * window.devicePixelRatio;


    largeCtx.scale(
        window.devicePixelRatio,
        window.devicePixelRatio
    );


    const width = largeCanvas.clientWidth;
    const height = largeCanvas.clientHeight;


    largeCtx.clearRect(0, 0, width, height);


    // Background grid
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


    // Draw enlarged network
    const positions = {

        S1: [width * 0.5, height * 0.15],

        T7: [width * 0.32, height * 0.35],

        T5: [width * 0.68, height * 0.35],

        F3: [width * 0.32, height * 0.55],

        F5: [width * 0.68, height * 0.55],

        L1: [width * 0.20, height * 0.78],

        H1: [width * 0.50, height * 0.78],

        L2: [width * 0.80, height * 0.78]

    };


    // Connections
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


    // Nodes
    nodes.forEach(node => {

        const position = positions[node.id];

        if (!position) return;


        let color = "#2ddf8c";

        if (node.status === "warning") {
            color = "#ffb547";
        }

        if (node.status === "failed") {
            color = "#ff5364";
        }

        if (node.critical) {
            color = "#a879ff";
        }


        largeCtx.beginPath();

        largeCtx.arc(
            position[0],
            position[1],
            30,
            0,
            Math.PI * 2
        );

        largeCtx.fillStyle = "#0d1722";
        largeCtx.fill();

        largeCtx.strokeStyle = color;
        largeCtx.lineWidth = 4;

        largeCtx.stroke();


        largeCtx.fillStyle = color;
        largeCtx.font = "bold 15px Arial";
        largeCtx.textAlign = "center";
        largeCtx.textBaseline = "middle";

        largeCtx.fillText(
            node.id,
            position[0],
            position[1]
        );


        largeCtx.fillStyle = "#e7edf5";
        largeCtx.font = "bold 13px Arial";

        largeCtx.fillText(
            node.type,
            position[0],
            position[1] + 52
        );

    });

}


// ================= START =================

window.addEventListener(
    "resize",
    resizeCanvas
);


window.addEventListener(
    "load",
    () => {

        resizeCanvas();

        updateStatistics();

    }
);