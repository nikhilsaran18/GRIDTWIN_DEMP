/**
 * ============================================================================
 * GRIDTWIN - 3D DIGITAL TWIN & INTERACTIVE GRID VISUALIZER
 * Three.js WebGL Complete Interactive Digital Twin with Physical Infrastructure
 * ============================================================================
 */

(function(window) {
    'use strict';

    // Authoritative 3D Topology Coordinates for the 8-node GridTwin Network
    const GRID_3D_COORDS = {
        "S1": { x: 0,   y: 0, z: -24, label: "S1", name: "Main Substation S1", type: "substation" },
        "T7": { x: -20, y: 0, z: -8,  label: "T7", name: "Transformer T7",      type: "transformer" },
        "T8": { x: 20,  y: 0, z: -8,  label: "T8", name: "Transformer T8",      type: "transformer" },
        "F3": { x: -20, y: 0, z: 10,  label: "F3", name: "Distribution Feeder F3", type: "feeder" },
        "F5": { x: 20,  y: 0, z: 10,  label: "F5", name: "Distribution Feeder F5", type: "feeder" },
        "L1": { x: -30, y: 0, z: 26,  label: "L1", name: "Residential Load L1", type: "load" },
        "H1": { x: 0,   y: 0, z: 26,  label: "H1", name: "Hospital Critical Facility H1", type: "hospital", critical: true },
        "L2": { x: 30,  y: 0, z: 26,  label: "L2", name: "Commercial Load L2",  type: "load" }
    };

    class Grid3DVisualizer {
        constructor() {
            this.container = null;
            this.canvas = null;
            this.scene = null;
            this.camera = null;
            this.renderer = null;
            this.controls = null;
            this.isInitialized = false;
            this.active = false;

            // Scene Graph objects
            this.nodeMeshes = {};        // nodeId -> THREE.Group
            this.edgeLines = [];         // Array of edge records
            this.powerParticles = [];    // Animated flow packets
            this.particleSystems = [];   // Sparks, smoke, arcs
            this.activeLights = {};      // Status point lights
            this.selectionRings = {};    // Selection indicator per node

            // Camera default & preset viewpoints
            this.defaultCameraPos = new THREE.Vector3(0, 52, 68);
            this.defaultTarget = new THREE.Vector3(0, 0, 4);
            this.topCameraPos = new THREE.Vector3(0, 80, 2);
            this.topTarget = new THREE.Vector3(0, 0, 0);

            this.isCameraTransitioning = false;
            this.cameraShakeIntensity = 0;
            this.selectedNodeId = null;
            this.apiEdges = null;

            // Raycaster & Hover
            this.raycaster = new THREE.Raycaster();
            this.mouse = new THREE.Vector2();
            this.hoveredNodeId = null;
            this.tooltipEl = null;

            // Clock & Animation
            this.clock = new THREE.Clock();
            this.animating = false;
            this.isAutoRotating = false;

            // Bind event handlers
            this.onWindowResize = this.onWindowResize.bind(this);
            this.onMouseMove = this.onMouseMove.bind(this);
            this.onClick = this.onClick.bind(this);
            this.animate = this.animate.bind(this);
        }

        /**
         * Initialize the 3D scene inside container
         */
        init(containerId) {
            if (typeof THREE === 'undefined') {
                console.warn('[Grid3D] Three.js library not available.');
                return false;
            }

            this.container = document.getElementById(containerId);
            if (!this.container) {
                console.warn('[Grid3D] Container element not found:', containerId);
                return false;
            }

            this.canvas = document.getElementById('gridCanvas3D') || document.createElement('canvas');
            this.canvas.id = 'gridCanvas3D';
            if (!this.canvas.parentElement) {
                this.container.appendChild(this.canvas);
            }

            this.tooltipEl = document.getElementById('grid3dTooltip');

            const width = this.container.clientWidth || 800;
            const height = this.container.clientHeight || 380;

            // 1. Scene setup
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(0x0a1017);
            this.scene.fog = new THREE.FogExp2(0x0a1017, 0.007);

            // 2. Camera
            this.camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 1000);
            this.camera.position.copy(this.defaultCameraPos);

            // 3. WebGL Renderer
            this.renderer = new THREE.WebGLRenderer({
                canvas: this.canvas,
                antialias: true,
                powerPreference: 'high-performance'
            });
            this.renderer.setSize(width, height);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
            this.renderer.toneMappingExposure = 1.25;
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

            // 4. OrbitControls
            if (typeof THREE.OrbitControls !== 'undefined') {
                this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
                this.controls.enableDamping = true;
                this.controls.dampingFactor = 0.06;
                this.controls.maxPolarAngle = Math.PI / 2.05;
                this.controls.minDistance = 12;
                this.controls.maxDistance = 180;
                this.controls.target.copy(this.defaultTarget);
            }

            // 5. Lighting & Environment
            this.setupEnvironment();

            // 6. Build the physical 3D Grid Topology
            this.buildGridTopology();

            // 7. Event listeners
            window.addEventListener('resize', this.onWindowResize);
            this.canvas.addEventListener('mousemove', this.onMouseMove);
            this.canvas.addEventListener('click', this.onClick);
            this.canvas.addEventListener('mouseleave', () => this.hideTooltip());

            this.isInitialized = true;
            this.active = true;
            this.start();

            console.log('[Grid3D] 3D Digital Twin Visualizer initialized with authoritative topology layout.');
            return true;
        }

        /**
         * Setup Lighting, Metallic Base Ground, and Cyberpunk Grid Plane
         */
        setupEnvironment() {
            // Ambient Illumination
            const ambient = new THREE.AmbientLight(0x243b55, 1.4);
            this.scene.add(ambient);

            // Key Directional Sun
            const sunLight = new THREE.DirectionalLight(0xe0f2fe, 1.8);
            sunLight.position.set(40, 70, 45);
            sunLight.castShadow = true;
            sunLight.shadow.mapSize.width = 1024;
            sunLight.shadow.mapSize.height = 1024;
            sunLight.shadow.camera.near = 10;
            sunLight.shadow.camera.far = 160;
            sunLight.shadow.camera.left = -50;
            sunLight.shadow.camera.right = 50;
            sunLight.shadow.camera.top = 50;
            sunLight.shadow.camera.bottom = -50;
            this.scene.add(sunLight);

            // Cyan fill rim light
            const rimLight = new THREE.DirectionalLight(0x0284c7, 0.9);
            rimLight.position.set(-50, 30, -40);
            this.scene.add(rimLight);

            // Ground plane
            const groundGeo = new THREE.PlaneGeometry(240, 240);
            const groundMat = new THREE.MeshStandardMaterial({
                color: 0x070d14,
                roughness: 0.85,
                metalness: 0.2
            });
            const ground = new THREE.Mesh(groundGeo, groundMat);
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = -0.1;
            ground.receiveShadow = true;
            this.scene.add(ground);

            // Neon Dual-axis Grid Overlay
            const gridHelper = new THREE.GridHelper(200, 40, 0x1e3a5f, 0x0f2033);
            gridHelper.position.y = 0.0;
            this.scene.add(gridHelper);

            // Subtle perimeter border ring
            const ringGeo = new THREE.RingGeometry(85, 86, 64);
            const ringMat = new THREE.MeshBasicMaterial({
                color: 0x1e3a5f,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.35
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = -Math.PI / 2;
            ring.position.y = 0.05;
            this.scene.add(ring);
        }

        /**
         * Get 3D world space coordinate for a given node ID
         */
        getNodeWorldPos(nodeId) {
            const def = GRID_3D_COORDS[nodeId];
            if (def) {
                return { x: def.x, y: 0, z: def.z };
            }
            return { x: 0, y: 0, z: 0 };
        }

        /**
         * Build all physical 3D models and connect them with 3D catenary lines
         */
        buildGridTopology() {
            // Clean any existing models
            Object.values(this.nodeMeshes).forEach(group => this.scene.remove(group));
            this.nodeMeshes = {};
            this.edgeLines.forEach(edge => this.scene.remove(edge.mesh));
            this.edgeLines = [];
            this.powerParticles.forEach(p => this.scene.remove(p.mesh));
            this.powerParticles = [];

            // Node definitions
            const nodeIds = Object.keys(GRID_3D_COORDS);

            nodeIds.forEach(nodeId => {
                const info = GRID_3D_COORDS[nodeId];
                const pos = this.getNodeWorldPos(nodeId);
                let group;

                switch (info.type) {
                    case 'substation':
                        group = this.createSubstation3D(info);
                        break;
                    case 'transformer':
                        group = this.createTransformer3D(info);
                        break;
                    case 'feeder':
                        group = this.createFeeder3D(info);
                        break;
                    case 'hospital':
                        group = this.createHospital3D(info);
                        break;
                    default:
                        group = this.createLoadBuilding3D(info);
                        break;
                }

                group.position.set(pos.x, 0, pos.z);
                group.userData = {
                    nodeId: nodeId,
                    type: info.type,
                    status: 'normal'
                };

                // Selection Ring (invisible until selected)
                const selRingGeo = new THREE.RingGeometry(info.type === 'substation' ? 7 : 4.5, info.type === 'substation' ? 7.5 : 5.0, 32);
                const selRingMat = new THREE.MeshBasicMaterial({
                    color: 0x38bdf8,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: 0.0
                });
                const selRing = new THREE.Mesh(selRingGeo, selRingMat);
                selRing.rotation.x = -Math.PI / 2;
                selRing.position.y = 0.15;
                group.add(selRing);
                this.selectionRings[nodeId] = selRing;

                this.scene.add(group);
                this.nodeMeshes[nodeId] = group;
            });

            // 3D Power Lines matching authoritative grid.json
            const connections = this.apiEdges || [
                { source: "S1", target: "T7", active: true },
                { source: "S1", target: "T8", active: true },
                { source: "T7", target: "F3", active: true },
                { source: "T8", target: "F5", active: true },
                { source: "F3", target: "L1", active: true },
                { source: "F3", target: "H1", active: true },
                { source: "F5", target: "L2", active: true },
                { source: "F5", target: "H1", active: false } // Switchable tie line (open in baseline)
            ];

            connections.forEach(conn => {
                this.createPowerLine3D(conn.source, conn.target, conn.active);
            });
        }

        syncGridData(gridData) {
            if (!gridData) return;

            this.apiEdges = Array.isArray(gridData.edges)
                ? gridData.edges.map(edge => ({
                    source: edge.source,
                    target: edge.target,
                    active: edge.status !== 'failed'
                }))
                : null;

            if (Array.isArray(gridData.nodes)) {
                gridData.nodes.forEach(node => {
                    this.setNodeVisualState(node.id, node.status || 'normal');
                });
            }
        }

        /**
         * Physical 3D Substation Model (S1)
         */
        createSubstation3D(info) {
            const group = new THREE.Group();

            // Concrete Substation Switchyard Pad
            const padGeo = new THREE.BoxGeometry(12, 0.7, 12);
            const padMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9 });
            const pad = new THREE.Mesh(padGeo, padMat);
            pad.position.y = 0.35;
            pad.receiveShadow = true;
            group.add(pad);

            // Substation Security Perimeter Curb
            const curbGeo = new THREE.BoxGeometry(12.4, 0.2, 12.4);
            const curbMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.5 });
            const curb = new THREE.Mesh(curbGeo, curbMat);
            curb.position.y = 0.1;
            group.add(curb);

            // Steel Gantry Towers (2 Structural Towers)
            const trussMat = new THREE.MeshStandardMaterial({ color: 0x64748b, metalness: 0.8, roughness: 0.25 });
            [-4, 4].forEach(x => {
                const pylonGeo = new THREE.CylinderGeometry(0.25, 0.5, 8.5, 6);
                const pylon = new THREE.Mesh(pylonGeo, trussMat);
                pylon.position.set(x, 4.6, -3);
                pylon.castShadow = true;
                group.add(pylon);
            });

            // Gantry Overhead Crossbeam
            const beamGeo = new THREE.BoxGeometry(9.2, 0.35, 0.35);
            const beam = new THREE.Mesh(beamGeo, trussMat);
            beam.position.set(0, 8.8, -3);
            group.add(beam);

            // 3-Phase Ceramic Insulators with high voltage corona glow
            const insMat = new THREE.MeshStandardMaterial({ color: 0x93c5fd, roughness: 0.1, metalness: 0.1 });
            [-3, 0, 3].forEach(x => {
                const insGeo = new THREE.CylinderGeometry(0.2, 0.2, 1.4, 8);
                const ins = new THREE.Mesh(insGeo, insMat);
                ins.position.set(x, 7.8, -3);
                group.add(ins);
            });

            // Substation Main Step-Up Power Transformer Body
            const transGeo = new THREE.BoxGeometry(5.2, 3.4, 4.2);
            const transMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.6, roughness: 0.4 });
            const trans = new THREE.Mesh(transGeo, transMat);
            trans.position.set(0, 2.4, 2.0);
            trans.castShadow = true;
            trans.name = 'mainBody';
            group.add(trans);

            // Rotating Operational Beacon Light
            const beaconGeo = new THREE.SphereGeometry(0.45, 16, 16);
            const beaconMat = new THREE.MeshBasicMaterial({ color: 0x2ddf8c });
            const beacon = new THREE.Mesh(beaconGeo, beaconMat);
            beacon.position.set(0, 9.6, -3);
            beacon.name = 'statusBeacon';
            group.add(beacon);

            // Point Light Glow
            const light = new THREE.PointLight(0x2ddf8c, 1.6, 18);
            light.position.set(0, 9.6, -3);
            light.name = 'statusLight';
            group.add(light);
            this.activeLights[info.label] = light;

            // Overhead 3D Billboard Label
            group.add(this.createLabelSprite(info.label, "SUBSTATION 50MW", 0x2ddf8c, 11.2));

            return group;
        }

        /**
         * Physical 3D High-Voltage Transformer Model (T7, T8)
         */
        createTransformer3D(info) {
            const group = new THREE.Group();

            // Foundation Plinth
            const baseGeo = new THREE.BoxGeometry(7, 0.6, 7);
            const baseMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9 });
            const base = new THREE.Mesh(baseGeo, baseMat);
            base.position.y = 0.3;
            base.receiveShadow = true;
            group.add(base);

            // Main Transformer Steel Tank with corrugated stiffeners
            const tankGeo = new THREE.BoxGeometry(4.2, 3.6, 3.8);
            const tankMat = new THREE.MeshStandardMaterial({
                color: 0x2e3a4e,
                metalness: 0.75,
                roughness: 0.3
            });
            const tank = new THREE.Mesh(tankGeo, tankMat);
            tank.position.set(0, 2.4, 0);
            tank.castShadow = true;
            tank.name = 'mainTank';
            group.add(tank);

            // Flanking Radiator Cooling Fin Banks (Left & Right)
            const radMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.8, roughness: 0.4 });
            [-2.4, 2.4].forEach(x => {
                for (let i = -1.4; i <= 1.4; i += 0.55) {
                    const finGeo = new THREE.BoxGeometry(0.12, 2.8, 0.45);
                    const fin = new THREE.Mesh(finGeo, radMat);
                    fin.position.set(x, 2.4, i);
                    fin.castShadow = true;
                    group.add(fin);
                }
            });

            // Cylindrical Oil Conservator Drum mounted on top
            const drumGeo = new THREE.CylinderGeometry(0.55, 0.55, 3.2, 16);
            const drumMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.7, roughness: 0.3 });
            const drum = new THREE.Mesh(drumGeo, drumMat);
            drum.rotation.z = Math.PI / 2;
            drum.position.set(0, 4.8, -1.0);
            drum.castShadow = true;
            group.add(drum);

            // 3 Ceramic High-Voltage Bushings with Copper Terminal Spheres
            const bushingMat = new THREE.MeshStandardMaterial({ color: 0xbfdbfe, roughness: 0.15, metalness: 0.1 });
            [-1.2, 0, 1.2].forEach(x => {
                const bGeo = new THREE.CylinderGeometry(0.14, 0.22, 1.4, 8);
                const bushing = new THREE.Mesh(bGeo, bushingMat);
                bushing.position.set(x, 4.9, 0.7);
                bushing.castShadow = true;
                group.add(bushing);

                // Copper spherical terminal
                const capGeo = new THREE.SphereGeometry(0.2, 8, 8);
                const capMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.9, roughness: 0.1 });
                const cap = new THREE.Mesh(capGeo, capMat);
                cap.position.set(x, 5.7, 0.7);
                group.add(cap);
            });

            // Base Status Indicator Ring
            const ringGeo = new THREE.TorusGeometry(3.6, 0.12, 8, 32);
            const ringMat = new THREE.MeshBasicMaterial({ color: 0x2ddf8c });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 0.65;
            ring.name = 'statusRing';
            group.add(ring);

            // Status Point Light
            const light = new THREE.PointLight(0x2ddf8c, 1.5, 14);
            light.position.set(0, 6.2, 0);
            light.name = 'statusLight';
            group.add(light);
            this.activeLights[info.label] = light;

            // Overhead 3D Billboard Label
            group.add(this.createLabelSprite(info.label, "TRANSFORMER 10MW", 0x2ddf8c, 7.8));

            return group;
        }

        /**
         * Physical 3D Feeder / Distribution Pylon Model (F3, F5)
         */
        createFeeder3D(info) {
            const group = new THREE.Group();

            const pylonMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.6, roughness: 0.4 });
            const poleGeo = new THREE.CylinderGeometry(0.3, 0.45, 9.5, 8);
            const pole = new THREE.Mesh(poleGeo, pylonMat);
            pole.position.y = 4.75;
            pole.castShadow = true;
            group.add(pole);

            // Double Crossarms
            const armGeo = new THREE.BoxGeometry(5.2, 0.25, 0.35);
            const arm = new THREE.Mesh(armGeo, pylonMat);
            arm.position.y = 8.5;
            group.add(arm);

            // Suspension Bell Insulator cups
            const insMat = new THREE.MeshStandardMaterial({ color: 0x60a5fa, roughness: 0.2 });
            [-2.2, 0, 2.2].forEach(x => {
                const insGeo = new THREE.CylinderGeometry(0.14, 0.14, 0.8, 6);
                const ins = new THREE.Mesh(insGeo, insMat);
                ins.position.set(x, 8.0, 0);
                group.add(ins);
            });

            // SF6 Circuit Breaker Enclosure Box
            const boxGeo = new THREE.BoxGeometry(1.4, 2.0, 1.1);
            const boxMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.8, roughness: 0.2 });
            const box = new THREE.Mesh(boxGeo, boxMat);
            box.position.set(0, 3.2, 0.5);
            box.castShadow = true;
            box.name = 'mainBody';
            group.add(box);

            // Status Light
            const light = new THREE.PointLight(0x2ddf8c, 1.3, 12);
            light.position.set(0, 9.8, 0);
            light.name = 'statusLight';
            group.add(light);
            this.activeLights[info.label] = light;

            // Overhead 3D Billboard Label
            group.add(this.createLabelSprite(info.label, "FEEDER LINE", 0x2ddf8c, 10.8));

            return group;
        }

        /**
         * Physical 3D Hospital Critical Facility Model (H1)
         */
        createHospital3D(info) {
            const group = new THREE.Group();

            // Main Medical Center Complex Building
            const bldGeo = new THREE.BoxGeometry(8, 5.5, 6);
            const bldMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.45, metalness: 0.25 });
            const bld = new THREE.Mesh(bldGeo, bldMat);
            bld.position.y = 2.75;
            bld.castShadow = true;
            bld.name = 'hospitalBuilding';
            group.add(bld);

            // Elevated Emergency ICU Wing
            const towGeo = new THREE.BoxGeometry(4.8, 3.5, 4.8);
            const towMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.3, metalness: 0.4 });
            const tow = new THREE.Mesh(towGeo, towMat);
            tow.position.set(0, 7.25, 0);
            tow.castShadow = true;
            group.add(tow);

            // Rooftop Emergency Helipad Platform
            const padGeo = new THREE.CylinderGeometry(2.2, 2.2, 0.2, 32);
            const padMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.9 });
            const pad = new THREE.Mesh(padGeo, padMat);
            pad.position.set(0, 9.1, 0);
            group.add(pad);

            // Helipad 'H' Indicator
            const hBar1 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.05, 1.6), new THREE.MeshBasicMaterial({ color: 0xffffff }));
            const hBar2 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.05, 1.6), new THREE.MeshBasicMaterial({ color: 0xffffff }));
            const hBar3 = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.05, 0.3), new THREE.MeshBasicMaterial({ color: 0xffffff }));
            hBar1.position.set(-0.5, 9.22, 0);
            hBar2.position.set(0.5, 9.22, 0);
            hBar3.position.set(0, 9.22, 0);
            group.add(hBar1);
            group.add(hBar2);
            group.add(hBar3);

            // 3D Illuminated Red Medical Cross Insignia on Facade
            const crossH = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.5, 0.15), new THREE.MeshBasicMaterial({ color: 0xff2e50 }));
            const crossV = new THREE.Mesh(new THREE.BoxGeometry(0.5, 2.0, 0.15), new THREE.MeshBasicMaterial({ color: 0xff2e50 }));
            crossH.position.set(0, 7.25, 2.48);
            crossV.position.set(0, 7.25, 2.48);
            group.add(crossH);
            group.add(crossV);

            // Status Light
            const light = new THREE.PointLight(0xa879ff, 1.8, 16);
            light.position.set(0, 9.6, 0);
            light.name = 'statusLight';
            group.add(light);
            this.activeLights[info.label] = light;

            // Overhead 3D Billboard Label
            group.add(this.createLabelSprite(info.label, "HOSPITAL (CRITICAL)", 0xa879ff, 11.2));

            return group;
        }

        /**
         * Physical 3D Urban Load Building (L1 Residential / L2 Commercial)
         */
        createLoadBuilding3D(info) {
            const group = new THREE.Group();

            const isL1 = (info.label === 'L1');
            const height = isL1 ? 5.0 : 6.8;
            const bldGeo = new THREE.BoxGeometry(5.0, height, 5.0);
            const bldMat = new THREE.MeshStandardMaterial({
                color: isL1 ? 0x283548 : 0x1e3a5f,
                roughness: 0.4,
                metalness: 0.35
            });
            const bld = new THREE.Mesh(bldGeo, bldMat);
            bld.position.y = height / 2;
            bld.castShadow = true;
            bld.name = 'loadBuilding';
            group.add(bld);

            // Illuminated window matrices
            const winMat = new THREE.MeshBasicMaterial({ color: isL1 ? 0xfde047 : 0x38bdf8 });
            for (let y = 1.0; y < height - 0.6; y += 1.3) {
                [-1.4, 1.4].forEach(x => {
                    const winGeo = new THREE.BoxGeometry(0.9, 0.7, 0.08);
                    const win = new THREE.Mesh(winGeo, winMat);
                    win.position.set(x, y, 2.54);
                    group.add(win);
                });
            }

            // Status light
            const light = new THREE.PointLight(0x2ddf8c, 1.1, 12);
            light.position.set(0, height + 1.2, 0);
            light.name = 'statusLight';
            group.add(light);
            this.activeLights[info.label] = light;

            // Overhead 3D Billboard Label
            const subtitle = isL1 ? "RESIDENTIAL LOAD" : "COMMERCIAL LOAD";
            group.add(this.createLabelSprite(info.label, subtitle, 0x2ddf8c, height + 2.8));

            return group;
        }

        /**
         * High-visibility 3D Billboard Sprite Label
         */
        createLabelSprite(idText, subText, colorHex, yOffset) {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 100;
            const ctx = canvas.getContext('2d');

            // Background pill
            ctx.fillStyle = 'rgba(10, 16, 26, 0.88)';
            ctx.roundRect ? ctx.roundRect(8, 8, 240, 84, 14) : ctx.fillRect(8, 8, 240, 84);
            ctx.fill();
            ctx.lineWidth = 4;
            ctx.strokeStyle = '#38bdf8';
            ctx.stroke();

            // Main ID Title
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 36px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(idText, 128, 42);

            // Subtitle
            ctx.fillStyle = '#94a3b8';
            ctx.font = 'bold 16px Arial';
            ctx.fillText(subText, 128, 74);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({
                map: texture,
                depthTest: false,
                transparent: true
            });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(6.5, 2.5, 1);
            sprite.position.set(0, yOffset, 0);
            sprite.name = 'labelSprite';
            return sprite;
        }

        /**
         * 3D Catenary Power Transmission Line with Dynamic Flow Particle Packets
         */
        createPowerLine3D(sourceId, targetId, isActive) {
            const p1 = this.getNodeWorldPos(sourceId);
            const p2 = this.getNodeWorldPos(targetId);

            const v1 = new THREE.Vector3(p1.x, 3.8, p1.z);
            const v2 = new THREE.Vector3(p2.x, 3.8, p2.z);
            const mid = new THREE.Vector3(
                (v1.x + v2.x) / 2,
                Math.min(v1.y, v2.y) - 1.4, // Catenary sag
                (v1.z + v2.z) / 2
            );

            const curve = new THREE.QuadraticBezierCurve3(v1, mid, v2);
            const points = curve.getPoints(28);
            const lineGeo = new THREE.BufferGeometry().setFromPoints(points);

            const lineMat = new THREE.LineBasicMaterial({
                color: isActive ? 0x38bdf8 : 0x334155,
                linewidth: 2,
                transparent: true,
                opacity: isActive ? 0.9 : 0.2
            });

            const line = new THREE.Line(lineGeo, lineMat);
            this.scene.add(line);

            const edgeRecord = {
                source: sourceId,
                target: targetId,
                mesh: line,
                curve: curve,
                active: isActive,
                particles: []
            };

            // Energy flow packets
            if (isActive) {
                for (let i = 0; i < 3; i++) {
                    const pGeo = new THREE.SphereGeometry(0.24, 8, 8);
                    const pMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
                    const pMesh = new THREE.Mesh(pGeo, pMat);
                    this.scene.add(pMesh);

                    const particle = {
                        mesh: pMesh,
                        curve: curve,
                        progress: i / 3.0,
                        speed: 0.32,
                        active: true
                    };
                    this.powerParticles.push(particle);
                    edgeRecord.particles.push(particle);
                }
            }

            this.edgeLines.push(edgeRecord);
        }

        /**
         * DYNAMIC 3D FAILURE ANIMATION SEQUENCE
         */
        triggerFailureAnimation(nodeId, callback) {
            const meshGroup = this.nodeMeshes[nodeId];
            if (!meshGroup) {
                if (callback) callback();
                return;
            }

            console.log(`[Grid3D] Executing dynamic 3D failure animation for: ${nodeId}`);
            this.showCinematicBanner(nodeId);

            const pos = meshGroup.position;
            const targetCamPos = new THREE.Vector3(pos.x + 12, pos.y + 14, pos.z + 18);
            const targetLookAt = new THREE.Vector3(pos.x, pos.y + 3.0, pos.z);

            // Phase 1: Smooth Camera Zoom-In Focus (0.0s -> 0.8s)
            this.tweenCamera(targetCamPos, targetLookAt, 750, () => {
                // Phase 2: Warning Electrical Jitter & Strobe (0.8s -> 1.5s)
                this.createElectricalArcWarning(meshGroup, 650);

                setTimeout(() => {
                    // Phase 3: Major Arc Flash, Sparks & Smoke Discharge (1.5s -> 2.5s)
                    this.triggerArcFlashExplosion(meshGroup);
                    this.cameraShakeIntensity = 1.3;

                    // Apply visual damaged state to 3D model
                    this.setNodeVisualState(nodeId, 'failed');

                    // Phase 4: Smooth Pullback to Tactical Grid Overview (2.5s -> 3.5s)
                    setTimeout(() => {
                        this.hideCinematicBanner();
                        this.tweenCamera(this.defaultCameraPos, this.defaultTarget, 1100, () => {
                            if (callback) callback();
                        });
                    }, 1300);

                }, 650);
            });
        }

        /**
         * Pre-fault warning vibration and buzzing arcs
         */
        createElectricalArcWarning(meshGroup, durationMs) {
            const start = performance.now();
            const originalPos = meshGroup.position.clone();
            const light = meshGroup.getObjectByName('statusLight');

            const interval = setInterval(() => {
                const elapsed = performance.now() - start;
                if (elapsed > durationMs) {
                    clearInterval(interval);
                    meshGroup.position.copy(originalPos);
                    return;
                }

                // Jitter
                meshGroup.position.x = originalPos.x + (Math.random() - 0.5) * 0.35;
                meshGroup.position.z = originalPos.z + (Math.random() - 0.5) * 0.35;

                // Strobe
                if (light) {
                    light.color.setHex(Math.random() > 0.5 ? 0xffb547 : 0xff3b5c);
                    light.intensity = 2.2 + Math.random() * 3.0;
                }
            }, 45);
        }

        /**
         * High-energy Arc Flash, Spark Physics Particles and Volumetric Smoke
         */
        triggerArcFlashExplosion(meshGroup) {
            const origin = meshGroup.position.clone().add(new THREE.Vector3(0, 3.8, 0));

            // 1. Arc Flash Sphere
            const flashGeo = new THREE.SphereGeometry(3.0, 16, 16);
            const flashMat = new THREE.MeshBasicMaterial({
                color: 0xffffff,
                transparent: true,
                opacity: 1.0
            });
            const flashMesh = new THREE.Mesh(flashGeo, flashMat);
            flashMesh.position.copy(origin);
            this.scene.add(flashMesh);

            const flashAnim = {
                mesh: flashMesh,
                update: (dt) => {
                    flashMesh.scale.multiplyScalar(1.09);
                    flashMat.opacity -= dt * 3.2;
                    if (flashMat.opacity <= 0) {
                        this.scene.remove(flashMesh);
                        return false;
                    }
                    return true;
                }
            };
            this.particleSystems.push(flashAnim);

            // 2. Physics Sparks Particle Burst
            const sparkCount = 80;
            const sparkGeo = new THREE.BufferGeometry();
            const sparkPositions = new Float32Array(sparkCount * 3);
            const sparkVelocities = [];

            for (let i = 0; i < sparkCount; i++) {
                sparkPositions[i * 3] = origin.x;
                sparkPositions[i * 3 + 1] = origin.y;
                sparkPositions[i * 3 + 2] = origin.z;

                const theta = Math.random() * Math.PI * 2;
                const phi = Math.random() * Math.PI / 2;
                const speed = 9 + Math.random() * 14;

                sparkVelocities.push(new THREE.Vector3(
                    Math.cos(theta) * Math.sin(phi) * speed,
                    Math.cos(phi) * speed + 5,
                    Math.sin(theta) * Math.sin(phi) * speed
                ));
            }
            sparkGeo.setAttribute('position', new THREE.BufferAttribute(sparkPositions, 3));

            const sparkMat = new THREE.PointsMaterial({
                color: 0xffb547,
                size: 0.65,
                transparent: true,
                opacity: 1.0,
                blending: THREE.AdditiveBlending
            });
            const sparkPoints = new THREE.Points(sparkGeo, sparkMat);
            this.scene.add(sparkPoints);

            const sparkAnim = {
                age: 0,
                update: (dt) => {
                    sparkAnim.age += dt;
                    const posAttr = sparkGeo.attributes.position;
                    const arr = posAttr.array;

                    for (let i = 0; i < sparkCount; i++) {
                        const vel = sparkVelocities[i];
                        vel.y -= 19.0 * dt; // Gravity

                        arr[i * 3] += vel.x * dt;
                        arr[i * 3 + 1] += vel.y * dt;
                        arr[i * 3 + 2] += vel.z * dt;

                        // Floor bounce
                        if (arr[i * 3 + 1] < 0.2) {
                            arr[i * 3 + 1] = 0.2;
                            vel.y = -vel.y * 0.35;
                            vel.x *= 0.65;
                            vel.z *= 0.65;
                        }
                    }
                    posAttr.needsUpdate = true;
                    sparkMat.opacity = Math.max(0, 1.0 - (sparkAnim.age / 1.6));

                    if (sparkAnim.age > 1.7) {
                        this.scene.remove(sparkPoints);
                        return false;
                    }
                    return true;
                }
            };
            this.particleSystems.push(sparkAnim);

            // 3. Volumetric Dark Smoke Puff
            const smokeCount = 28;
            const smokeGroup = new THREE.Group();
            this.scene.add(smokeGroup);

            const smokeParticles = [];
            for (let i = 0; i < smokeCount; i++) {
                const sGeo = new THREE.DodecahedronGeometry(0.9 + Math.random() * 0.7, 1);
                const sMat = new THREE.MeshStandardMaterial({
                    color: 0x1e293b,
                    roughness: 0.95,
                    transparent: true,
                    opacity: 0.85
                });
                const sMesh = new THREE.Mesh(sGeo, sMat);
                sMesh.position.copy(origin).add(new THREE.Vector3(
                    (Math.random() - 0.5) * 1.6,
                    Math.random() * 0.6,
                    (Math.random() - 0.5) * 1.6
                ));
                smokeGroup.add(sMesh);

                smokeParticles.push({
                    mesh: sMesh,
                    vel: new THREE.Vector3(
                        (Math.random() - 0.5) * 2.2,
                        2.8 + Math.random() * 3.8,
                        (Math.random() - 0.5) * 2.2
                    ),
                    rotSpeed: (Math.random() - 0.5) * 2.2
                });
            }

            const smokeAnim = {
                age: 0,
                update: (dt) => {
                    smokeAnim.age += dt;
                    smokeParticles.forEach(sp => {
                        sp.mesh.position.addScaledVector(sp.vel, dt);
                        sp.mesh.scale.multiplyScalar(1.0 + dt * 0.45);
                        sp.mesh.rotation.x += sp.rotSpeed * dt;
                        sp.mesh.material.opacity = Math.max(0, 0.85 - (smokeAnim.age / 2.9));
                    });

                    if (smokeAnim.age > 3.0) {
                        this.scene.remove(smokeGroup);
                        return false;
                    }
                    return true;
                }
            };
            this.particleSystems.push(smokeAnim);
        }

        /**
         * Update visual status of a 3D node (normal, warning, failed)
         */
        setNodeVisualState(nodeId, status) {
            const group = this.nodeMeshes[nodeId];
            if (!group) return;

            group.userData.status = status;
            const light = group.getObjectByName('statusLight');
            const ring = group.getObjectByName('statusRing');
            const beacon = group.getObjectByName('statusBeacon');
            const mainTank = group.getObjectByName('mainTank');
            const mainBody = group.getObjectByName('mainBody');

            if (status === 'failed') {
                if (light) {
                    light.color.setHex(0xff5364);
                    light.intensity = 2.6;
                }
                if (ring) ring.material.color.setHex(0xff5364);
                if (beacon) beacon.material.color.setHex(0xff5364);
                if (mainTank) {
                    mainTank.material.color.setHex(0x181214);
                    mainTank.material.roughness = 0.95;
                }
                if (mainBody) {
                    mainBody.material.color.setHex(0x181214);
                }
            } else if (status === 'warning' || status === 'high_risk' || status === 'overloaded') {
                if (light) {
                    light.color.setHex(0xffb547);
                    light.intensity = 2.0;
                }
                if (ring) ring.material.color.setHex(0xffb547);
                if (beacon) beacon.material.color.setHex(0xffb547);
            } else {
                // Baseline Normal
                const defColor = (nodeId === 'H1') ? 0xa879ff : 0x2ddf8c;
                if (light) {
                    light.color.setHex(defColor);
                    light.intensity = 1.5;
                }
                if (ring) ring.material.color.setHex(defColor);
                if (beacon) beacon.material.color.setHex(defColor);
                if (mainTank) {
                    mainTank.material.color.setHex(0x2e3a4e);
                    mainTank.material.roughness = 0.3;
                }
                if (mainBody) {
                    mainBody.material.color.setHex(0x334155);
                }
            }
        }

        /**
         * Update power lines and affected nodes based on authoritative backend simulation response
         */
        updateCascade3D(simulationResult) {
            if (!simulationResult) return;

            const failedId = simulationResult.failed_component ? simulationResult.failed_component.id : null;
            if (failedId) {
                this.setNodeVisualState(failedId, 'failed');
            }

            // Sync all nodes from response.grid if present
            if (simulationResult.grid && simulationResult.grid.nodes) {
                simulationResult.grid.nodes.forEach(n => {
                    this.setNodeVisualState(n.id, n.status || 'normal');
                });
            } else {
                const affected = simulationResult.affected_components || [];
                affected.forEach(c => {
                    if (c.id !== failedId) {
                        const st = (c.status === 'failed' || c.status === 'overloaded' || c.status === 'critical_risk') ? 'failed' : 'warning';
                        this.setNodeVisualState(c.id, st);
                    }
                });
            }

            // Update 3D power lines based on authoritative edge statuses
            const affectedEdgeMap = {};
            (simulationResult.affected_edges || []).forEach(e => {
                affectedEdgeMap[e.id] = e.status || 'failed';
                affectedEdgeMap[`${e.source}|${e.target}`] = e.status || 'failed';
            });

            this.edgeLines.forEach(edge => {
                const edgeKey = `${edge.source}|${edge.target}`;
                const edgeStatus = affectedEdgeMap[edge.id] || affectedEdgeMap[edgeKey];
                const isSevered = (edge.source === failedId || edge.target === failedId) || edgeStatus === 'failed';

                if (isSevered) {
                    edge.mesh.material.color.setHex(0xff5364);
                    edge.mesh.material.opacity = 0.5;
                    edge.particles.forEach(p => { p.active = false; p.mesh.visible = false; });
                } else if (edgeStatus === 'warning') {
                    edge.mesh.material.color.setHex(0xffb547);
                    edge.mesh.material.opacity = 0.85;
                    edge.particles.forEach(p => { p.active = true; p.mesh.visible = true; });
                } else if (edgeStatus === 'rerouted') {
                    edge.mesh.material.color.setHex(0x38bdf8);
                    edge.mesh.material.opacity = 1.0;
                    edge.particles.forEach(p => { p.active = true; p.mesh.visible = true; });
                }
            });
        }

        /**
         * Select a 3D component and focus camera
         */
        selectComponent(nodeId) {
            this.selectedNodeId = nodeId;

            // Update selection indicator rings
            Object.keys(this.selectionRings).forEach(id => {
                const ring = this.selectionRings[id];
                if (ring) {
                    ring.material.opacity = (id === nodeId) ? 0.9 : 0.0;
                }
            });

            // Focus Camera smoothly on component
            const mesh = this.nodeMeshes[nodeId];
            if (mesh) {
                const pos = mesh.position;
                const camPos = new THREE.Vector3(pos.x + 12, pos.y + 14, pos.z + 18);
                const target = new THREE.Vector3(pos.x, pos.y + 3.0, pos.z);
                this.tweenCamera(camPos, target, 700);
            }
        }

        /**
         * Smooth camera transition helper
         */
        tweenCamera(targetPos, targetLookAt, durationMs, onComplete) {
            const startPos = this.camera.position.clone();
            const startLook = this.controls ? this.controls.target.clone() : this.defaultTarget.clone();
            const startTime = performance.now();

            this.isCameraTransitioning = true;

            const animateCam = () => {
                const elapsed = performance.now() - startTime;
                const progress = Math.min(1.0, elapsed / durationMs);

                // Smooth quadratic ease in-out
                const ease = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;

                this.camera.position.lerpVectors(startPos, targetPos, ease);
                if (this.controls) {
                    this.controls.target.lerpVectors(startLook, targetLookAt, ease);
                    this.controls.update();
                }

                if (progress < 1.0) {
                    requestAnimationFrame(animateCam);
                } else {
                    this.isCameraTransitioning = false;
                    if (onComplete) onComplete();
                }
            };

            animateCam();
        }

        /**
         * Camera View Presets
         */
        resetCamera() {
            this.selectedNodeId = null;
            Object.values(this.selectionRings).forEach(ring => ring.material.opacity = 0.0);
            this.tweenCamera(this.defaultCameraPos, this.defaultTarget, 850);
        }

        setTopView() {
            this.tweenCamera(this.topCameraPos, this.topTarget, 850);
        }

        fitGrid() {
            const fitPos = new THREE.Vector3(0, 60, 78);
            this.tweenCamera(fitPos, this.defaultTarget, 850);
        }

        toggleAutoRotate() {
            this.isAutoRotating = !this.isAutoRotating;
            if (this.controls) {
                this.controls.autoRotate = this.isAutoRotating;
                this.controls.autoRotateSpeed = 1.6;
            }
        }

        /**
         * Cinematic Overlay Banner
         */
        showCinematicBanner(nodeId) {
            const overlay = document.getElementById('cinematicOverlay');
            const title = document.getElementById('cinematicTitle');
            const subtitle = document.getElementById('cinematicSubtitle');

            if (overlay && title) {
                title.textContent = `CRITICAL OUTAGE: ${nodeId}`;
                if (subtitle) subtitle.textContent = `Executing physical arc fault simulation & digital twin isolation`;
                overlay.classList.remove('hidden');
            }
        }

        hideCinematicBanner() {
            const overlay = document.getElementById('cinematicOverlay');
            if (overlay) overlay.classList.add('hidden');
        }

        /**
         * Interactive Hover Tooltip
         */
        showTooltip(nodeId, mouseX, mouseY) {
            if (!this.tooltipEl) return;

            const info = GRID_3D_COORDS[nodeId] || {};
            const liveNodes = window.nodes || [];
            const liveNode = liveNodes.find(n => n.id === nodeId) || {};

            const ttId = document.getElementById('ttId');
            const ttType = document.getElementById('ttType');
            const ttStatus = document.getElementById('ttStatus');
            const ttLoad = document.getElementById('ttLoad');
            const ttCap = document.getElementById('ttCap');

            if (ttId) ttId.textContent = nodeId;
            if (ttType) ttType.textContent = info.name || info.type || 'Component';
            if (ttStatus) {
                const status = liveNode.status || 'healthy';
                ttStatus.textContent = status.toUpperCase();
                ttStatus.className = (status === 'failed') ? 'failed' : (status === 'warning' ? 'warning' : 'healthy');
            }
            if (ttLoad) ttLoad.textContent = liveNode.loading || 'Normal';
            if (ttCap) ttCap.textContent = liveNode.capacity || '10.0 MW';

            this.tooltipEl.style.left = `${mouseX + 16}px`;
            this.tooltipEl.style.top = `${mouseY + 16}px`;
            this.tooltipEl.classList.remove('hidden');
        }

        hideTooltip() {
            if (this.tooltipEl) {
                this.tooltipEl.classList.add('hidden');
            }
        }

        /**
         * CLEAN RESET
         */
        reset() {
            this.hideCinematicBanner();
            this.hideTooltip();
            this.cameraShakeIntensity = 0;
            this.selectedNodeId = null;

            // Remove temporary particle systems
            this.particleSystems.forEach(ps => {
                if (ps.mesh) this.scene.remove(ps.mesh);
            });
            this.particleSystems = [];

            // Restore all nodes to baseline normal state
            Object.keys(this.nodeMeshes).forEach(nodeId => {
                this.setNodeVisualState(nodeId, 'normal');
            });

            // Clear selection rings
            Object.values(this.selectionRings).forEach(ring => ring.material.opacity = 0.0);

            // Restore all power line meshes & particle flows
            this.edgeLines.forEach(edge => {
                edge.mesh.material.color.setHex(0x38bdf8);
                edge.mesh.material.opacity = 0.9;
                edge.particles.forEach(p => { p.active = true; p.mesh.visible = true; });
            });

            // Smoothly glide camera back to default overview
            this.resetCamera();
            console.log('[Grid3D] 3D Digital Twin returned to 100% normal baseline.');
        }

        /**
         * Window resize handler
         */
        onWindowResize() {
            if (!this.container || !this.renderer || !this.camera) return;
            const width = this.container.clientWidth;
            const height = this.container.clientHeight;
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(width, height);
        }

        /**
         * Mouse interaction & raycasting
         */
        onMouseMove(event) {
            const rect = this.canvas.getBoundingClientRect();
            this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            if (this.isCameraTransitioning) return;

            this.raycaster.setFromCamera(this.mouse, this.camera);
            const intersects = this.raycaster.intersectObjects(this.scene.children, true);

            let hitNodeId = null;
            for (let hit of intersects) {
                let current = hit.object;
                while (current && current !== this.scene) {
                    if (current.userData && current.userData.nodeId) {
                        hitNodeId = current.userData.nodeId;
                        break;
                    }
                    current = current.parent;
                }
                if (hitNodeId) break;
            }

            if (hitNodeId) {
                this.hoveredNodeId = hitNodeId;
                this.canvas.style.cursor = 'pointer';
                this.showTooltip(hitNodeId, event.clientX - rect.left, event.clientY - rect.top);
            } else {
                this.hoveredNodeId = null;
                this.canvas.style.cursor = 'default';
                this.hideTooltip();
            }
        }

        onClick(event) {
            if (this.isCameraTransitioning) return;
            this.raycaster.setFromCamera(this.mouse, this.camera);
            const intersects = this.raycaster.intersectObjects(this.scene.children, true);

            for (let hit of intersects) {
                let current = hit.object;
                while (current && current !== this.scene) {
                    if (current.userData && current.userData.nodeId) {
                        const nodeId = current.userData.nodeId;
                        console.log('[Grid3D] Clicked 3D node:', nodeId);
                        this.selectComponent(nodeId);

                        if (typeof window.selectNodeFrom3D === 'function') {
                            window.selectNodeFrom3D(nodeId);
                        }
                        return;
                    }
                    current = current.parent;
                }
            }
        }

        /**
         * Render & Animation Loop
         */
        start() {
            if (!this.animating) {
                this.animating = true;
                this.clock.start();
                this.animate();
            }
        }

        stop() {
            this.animating = false;
        }

        animate() {
            if (!this.animating) return;
            requestAnimationFrame(this.animate);

            const dt = this.clock.getDelta();

            // 1. OrbitControls update
            if (this.controls && !this.isCameraTransitioning) {
                this.controls.update();
            }

            // 2. Camera Shake decay
            if (this.cameraShakeIntensity > 0.01) {
                this.camera.position.x += (Math.random() - 0.5) * this.cameraShakeIntensity;
                this.camera.position.y += (Math.random() - 0.5) * this.cameraShakeIntensity;
                this.cameraShakeIntensity *= 0.90;
            }

            // 3. Update active power-flow particle packets
            this.powerParticles.forEach(p => {
                if (p.active) {
                    p.progress += dt * p.speed;
                    if (p.progress > 1.0) p.progress = 0.0;
                    const pos = p.curve.getPoint(p.progress);
                    p.mesh.position.copy(pos);
                }
            });

            // 4. Update dynamic particle systems (sparks, smoke, flash)
            for (let i = this.particleSystems.length - 1; i >= 0; i--) {
                const ps = this.particleSystems[i];
                const alive = ps.update(dt);
                if (!alive) {
                    this.particleSystems.splice(i, 1);
                }
            }

            this.renderer.render(this.scene, this.camera);
        }
    }

    // Expose Global Singleton
    window.Grid3D = Grid3DVisualizer;
    window.grid3D = new Grid3DVisualizer();

})(window);
