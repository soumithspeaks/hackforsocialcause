/**
 * AVRA Simulation - Three.js 3D Scene Manager
 * Creates navigable indoor/outdoor environments with obstacles.
 */
import * as THREE from 'three';

// ── Obstacle definitions ─────────────────────────────────────────
const OBSTACLE_DEFS = {
    pole: { color: 0x888888, width: 0.15, height: 2.5, depth: 0.15, label: 'pole', hazard: 'high' },
    chair: { color: 0x8B4513, width: 0.5, height: 0.9, depth: 0.5, label: 'chair', hazard: 'medium' },
    table: { color: 0x654321, width: 1.2, height: 0.75, depth: 0.7, label: 'table', hazard: 'medium' },
    person: { color: 0x2196F3, width: 0.5, height: 1.75, depth: 0.4, label: 'person', hazard: 'medium' },
    vehicle: { color: 0xD32F2F, width: 2.0, height: 1.5, depth: 4.5, label: 'vehicle', hazard: 'critical' },
    bench: { color: 0x795548, width: 1.5, height: 0.5, depth: 0.5, label: 'bench', hazard: 'low' },
    cone: { color: 0xFF6F00, width: 0.3, height: 0.7, depth: 0.3, label: 'cone', hazard: 'medium' },
    barrier: { color: 0xF44336, width: 1.5, height: 1.0, depth: 0.2, label: 'barrier', hazard: 'high' },
    trashcan: { color: 0x424242, width: 0.4, height: 1.0, depth: 0.4, label: 'trash_can', hazard: 'low' },
    stairs: { color: 0x9E9E9E, width: 2.5, height: 0.6, depth: 1.5, label: 'stairs', hazard: 'high' },
    real_car: { label: 'vehicle', hazard: 'critical' },
    real_person: { label: 'person', hazard: 'medium' },
    traffic_post: { label: 'pole', hazard: 'high' }
};

// ── Scene Presets ─────────────────────────────────────────────────
const SCENE_PRESETS = {
    indoor: {
        name: 'Indoor Corridor',
        floor: { width: 20, depth: 40, color: 0x2a2a3e },
        walls: true,
        wallColor: 0x1a1a2e,
        ceiling: true,
        ceilingHeight: 3.5,
        ambient: 0.4,
        fogColor: 0x0a0e17,
        fogNear: 15,
        fogFar: 40,
        skyColor: null,
        obstacles: [
            { type: 'chair', pos: [3, 0, -8] },
            { type: 'chair', pos: [-2, 0, -12] },
            { type: 'table', pos: [4, 0, -15] },
            { type: 'pole', pos: [0.5, 0, -6] },
            { type: 'person', pos: [-3, 0, -18] },
            { type: 'person', pos: [2, 0, -22] },
            { type: 'trashcan', pos: [-4, 0, -10] },
            { type: 'barrier', pos: [0, 0, -25] },
            { type: 'bench', pos: [5, 0, -30] },
            { type: 'cone', pos: [-1, 0, -16] },
            { type: 'stairs', pos: [0, 0, -35] },
        ],
    },
    outdoor: {
        name: 'Outdoor Sidewalk',
        floor: { width: 30, depth: 60, color: 0x3a3a3a },
        walls: false,
        ceiling: false,
        ambient: 0.6,
        fogColor: 0x1a2a3a,
        fogNear: 25,
        fogFar: 60,
        skyColor: 0x1a2a3a,
        obstacles: [
            { type: 'pole', pos: [3, 0, -5] },
            { type: 'pole', pos: [3, 0, -15] },
            { type: 'pole', pos: [3, 0, -25] },
            { type: 'vehicle', pos: [7, 0, -10] },
            { type: 'vehicle', pos: [-7, 0, -20] },
            { type: 'person', pos: [-1, 0, -8] },
            { type: 'person', pos: [1.5, 0, -14] },
            { type: 'person', pos: [-2, 0, -28] },
            { type: 'bench', pos: [-5, 0, -12] },
            { type: 'cone', pos: [0, 0, -18] },
            { type: 'cone', pos: [1, 0, -19] },
            { type: 'barrier', pos: [-1.5, 0, -30] },
            { type: 'trashcan', pos: [4, 0, -22] },
        ],
    },
    complex: {
        name: 'Complex Scene',
        floor: { width: 25, depth: 50, color: 0x2e2e40 },
        walls: true,
        wallColor: 0x1e1e30,
        ceiling: true,
        ceilingHeight: 4.0,
        ambient: 0.35,
        fogColor: 0x080c14,
        fogNear: 12,
        fogFar: 35,
        skyColor: null,
        obstacles: [
            { type: 'pole', pos: [2, 0, -4] },
            { type: 'pole', pos: [-2, 0, -4] },
            { type: 'chair', pos: [3, 0, -7] },
            { type: 'chair', pos: [4, 0, -7] },
            { type: 'chair', pos: [-3, 0, -9] },
            { type: 'table', pos: [3.5, 0, -8] },
            { type: 'table', pos: [-3, 0, -10] },
            { type: 'person', pos: [0, 0, -6] },
            { type: 'person', pos: [-1, 0, -12] },
            { type: 'person', pos: [2, 0, -16] },
            { type: 'person', pos: [-3, 0, -20] },
            { type: 'barrier', pos: [0, 0, -14] },
            { type: 'cone', pos: [1, 0, -13] },
            { type: 'cone', pos: [-1, 0, -13] },
            { type: 'stairs', pos: [0, 0, -24] },
            { type: 'trashcan', pos: [5, 0, -18] },
            { type: 'vehicle', pos: [-6, 0, -28] },
            { type: 'bench', pos: [6, 0, -22] },
        ],
    },
    realistic_outdoor: {
        name: 'Realistic City Street',
        floor: { width: 40, depth: 80, color: 0x1a1a1a }, // Dark asphalt
        walls: false,
        ceiling: false,
        ambient: 0.6,
        fogColor: 0x87CEEB, // Sky blue
        fogNear: 25,
        fogFar: 75,
        skyColor: 0x87CEEB,
        obstacles: [
            // Realistic vehicles
            { type: 'real_car', pos: [5, 0, -15], rot: 0 },
            { type: 'real_car', pos: [-4, 0, -35], rot: Math.PI },
            { type: 'real_car', pos: [4, 0, -50], rot: 0 },
            // Realistic people
            { type: 'real_person', pos: [-2, 0, -10] },
            { type: 'real_person', pos: [8, 0, -25] },
            { type: 'real_person', pos: [2, 0, -45] },
            // Traffic Posts
            { type: 'traffic_post', pos: [8, 0, -20] },
            { type: 'traffic_post', pos: [-8, 0, -40] },
            // Misc objects
            { type: 'bench', pos: [-9, 0, -18] },
            { type: 'trashcan', pos: [9, 0, -32] },
            { type: 'cone', pos: [0, 0, -28] },
            { type: 'cone', pos: [1.5, 0, -30] }
        ]
    },
    realistic_city: {
        name: 'Immersive City Block',
        floor: { width: 50, depth: 120, color: 0x222222 },
        walls: false,
        ceiling: false,
        ambient: 0.45,
        fogColor: 0x8ab4d0,
        fogNear: 30,
        fogFar: 100,
        skyColor: 0x8ab4d0,
        customBuilder: 'realistic_city',
        obstacles: [
            // Parked vehicles along road
            { type: 'real_car', pos: [5.5, 0, -8], rot: 0 },
            { type: 'real_car', pos: [5.5, 0, -24], rot: 0 },
            { type: 'real_car', pos: [-5.5, 0, -18], rot: Math.PI },
            { type: 'real_car', pos: [-5.5, 0, -40], rot: Math.PI },
            { type: 'real_car', pos: [5.5, 0, -55], rot: 0 },
            { type: 'real_car', pos: [-5.5, 0, -70], rot: Math.PI },
            // Pedestrians
            { type: 'real_person', pos: [-1.5, 0, -6] },
            { type: 'real_person', pos: [1, 0, -15] },
            { type: 'real_person', pos: [-2, 0, -32] },
            { type: 'real_person', pos: [2.5, 0, -50] },
            { type: 'real_person', pos: [0, 0, -65] },
            { type: 'real_person', pos: [-1, 0, -85] },
            // Traffic lights
            { type: 'traffic_post', pos: [4, 0, -28] },
            { type: 'traffic_post', pos: [-4, 0, -28] },
            { type: 'traffic_post', pos: [4, 0, -60] },
            // Street furniture
            { type: 'bench', pos: [-9, 0, -12] },
            { type: 'bench', pos: [9, 0, -35] },
            { type: 'bench', pos: [-9, 0, -58] },
            { type: 'trashcan', pos: [9, 0, -15] },
            { type: 'trashcan', pos: [-9, 0, -42] },
            { type: 'trashcan', pos: [9, 0, -72] },
            { type: 'cone', pos: [0.5, 0, -45] },
            { type: 'cone', pos: [1.5, 0, -46] },
            { type: 'cone', pos: [-0.5, 0, -47] },
            { type: 'barrier', pos: [0, 0, -90] },
            { type: 'pole', pos: [3, 0, -4] },
        ]
    }
};

export class SceneManager {
    constructor(canvas) {
        this.canvas = canvas;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.obstacles = [];
        this.clock = new THREE.Clock();

        // Player state
        this.moveSpeed = 4.0;
        this.lookSpeed = 0.002;
        this.velocity = new THREE.Vector3();
        this.direction = new THREE.Vector3();
        this.keys = { w: false, a: false, s: false, d: false, space: false };
        this.isPointerLocked = false;
        this.euler = new THREE.Euler(0, 0, 0, 'YXZ');
        this.playerHeight = 1.6;

        this._init();
    }

    _buildScene(presetDef) {
        if (presetDef.customBuilder === 'realistic_city') {
            this._buildRealisticCity(presetDef);
        } else {
            this._buildBasicShapes(presetDef);
        }
    }

    _buildBasicShapes(sceneObj) {
        // Fallback or debug shapes
    }

    _buildRealisticCity(sceneObj) {
        // Detailed immersive city scene generator
        const roadW = 16;
        const roadL = sceneObj.floor.depth || 120;

        // 1. Sidewalks (raised with curbs)
        const swMat = new THREE.MeshLambertMaterial({ color: 0x999999, roughness: 0.9 });
        const curbMat = new THREE.MeshLambertMaterial({ color: 0xcccccc });

        // Left sidewalk
        const lw = new THREE.Mesh(new THREE.BoxGeometry(10, 0.4, roadL), swMat);
        lw.position.set(-13, 0.2, -roadL / 2 + 10);
        this.scene.add(lw);
        const lCurb = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.5, roadL), curbMat);
        lCurb.position.set(-8, 0.25, -roadL / 2 + 10);
        this.scene.add(lCurb);

        // Right sidewalk
        const rw = new THREE.Mesh(new THREE.BoxGeometry(10, 0.4, roadL), swMat);
        rw.position.set(13, 0.2, -roadL / 2 + 10);
        this.scene.add(rw);
        const rCurb = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.5, roadL), curbMat);
        rCurb.position.set(8, 0.25, -roadL / 2 + 10);
        this.scene.add(rCurb);

        // 2. Road Markings
        const lineMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const yellowMat = new THREE.MeshBasicMaterial({ color: 0xffcc00 });

        // Dashed center line
        for (let z = 10; z > -roadL; z -= 6) {
            const dash = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 3), yellowMat);
            dash.rotation.x = -Math.PI / 2;
            dash.position.set(0, 0.05, z);
            this.scene.add(dash);
        }

        // Zebra Crosswalk at z = -20
        for (let x = -7; x <= 7; x += 1.5) {
            const stripe = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 6), lineMat);
            stripe.rotation.x = -Math.PI / 2;
            stripe.position.set(x, 0.05, -20);
            this.scene.add(stripe);
        }

        // 3. Detailed Buildings with Grid Windows
        const bldMats = [
            new THREE.MeshLambertMaterial({ color: 0x3d4045 }),
            new THREE.MeshLambertMaterial({ color: 0x5a4d41 }),
            new THREE.MeshLambertMaterial({ color: 0x2b3846 }),
            new THREE.MeshLambertMaterial({ color: 0x6e6259 })
        ];
        const winMat = new THREE.MeshStandardMaterial({
            color: 0xffffcc, emissive: 0x444422, roughness: 0.1, metalness: 0.8
        }); // Glowing windows at night

        const createBuilding = (x, z, width, depth, height, matIdx, hasShop = false) => {
            const group = new THREE.Group();

            // Main structure
            const bld = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), bldMats[matIdx % bldMats.length]);
            bld.position.set(0, height / 2, 0);
            group.add(bld);

            // Windows grid
            const cols = Math.floor(width / 3);
            const rows = Math.floor((height - (hasShop ? 6 : 2)) / 3);
            const startY = hasShop ? 6 : 3;

            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    // Randomly turn off some windows
                    if (Math.random() > 0.3) {
                        const win = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 1.8), winMat);
                        win.position.set(
                            -width / 2 + (width / (cols + 1)) * (c + 1),
                            startY + r * 3,
                            (x > 0 ? -depth / 2 - 0.01 : depth / 2 + 0.01) // Attach to front face
                        );
                        if (x > 0) win.rotation.y = Math.PI;
                        group.add(win);
                    }
                }
            }

            // Shop Awning
            if (hasShop) {
                const awning = new THREE.Mesh(
                    new THREE.BoxGeometry(width + 0.5, 0.5, 2.5),
                    new THREE.MeshLambertMaterial({ color: 0x992222 })
                );
                awning.position.set(0, 4, x > 0 ? -depth / 2 - 1.25 : depth / 2 + 1.25);
                awning.rotation.x = x > 0 ? Math.PI / 12 : -Math.PI / 12;
                group.add(awning);

                // Storefront glass
                const glass = new THREE.Mesh(
                    new THREE.PlaneGeometry(width - 2, 3.5),
                    new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.1, metalness: 0.9 })
                );
                glass.position.set(0, 2, x > 0 ? -depth / 2 - 0.02 : depth / 2 + 0.02);
                if (x > 0) glass.rotation.y = Math.PI;
                group.add(glass);
            }

            group.position.set(x, 0, z);
            this.scene.add(group);
        };

        // Left buildings
        createBuilding(-25, -10, 14, 14, 25, 0, true);
        createBuilding(-22, -30, 20, 16, 40, 1, false);
        createBuilding(-26, -55, 12, 12, 18, 2, true);
        createBuilding(-24, -80, 18, 20, 55, 3, false);

        // Right buildings
        createBuilding(25, -15, 18, 16, 35, 1, false);
        createBuilding(24, -40, 16, 12, 22, 2, true);
        createBuilding(26, -65, 14, 18, 45, 0, false);
        createBuilding(22, -90, 22, 14, 30, 3, true);

        // 4. Streetlamps (with actual spot lights)
        const createLamp = (x, z) => {
            const group = new THREE.Group();
            const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.15, 6), new THREE.MeshStandardMaterial({ color: 0x333333 }));
            pole.position.y = 3;
            group.add(pole);

            const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2), new THREE.MeshStandardMaterial({ color: 0x333333 }));
            arm.rotation.z = Math.PI / 2;
            arm.position.set(x > 0 ? -1 : 1, 5.8, 0);
            group.add(arm);

            const bulb = new THREE.Mesh(
                new THREE.SphereGeometry(0.2),
                new THREE.MeshBasicMaterial({ color: 0xffffe0 })
            );
            bulb.position.set(x > 0 ? -2 : 2, 5.7, 0);
            group.add(bulb);

            const light = new THREE.SpotLight(0xffffe0, 2.0); // intensity 2
            light.position.copy(bulb.position);
            light.target.position.set(x > 0 ? -2 : 2, 0, 0);
            light.angle = Math.PI / 4;
            light.penumbra = 0.5;
            light.distance = 25;
            light.castShadow = true;
            group.add(light);
            group.add(light.target);

            group.position.set(x, 0, z);
            this.scene.add(group);

            // Add as visual obstacle so VLM mentions it
            this.obstacles.push({
                mesh: group,
                label: 'streetlamp',
                hazard: 'low',
                position: { x: x, y: 0, z: z }
            });
        };

        for (let z = -10; z >= -100; z -= 30) {
            createLamp(-7.5, z);
            createLamp(7.5, z - 15);
        }

        // 5. Trees / Planters
        const createTree = (x, z) => {
            const group = new THREE.Group();
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.3, 3), new THREE.MeshLambertMaterial({ color: 0x5c4033 }));
            trunk.position.y = 1.5;
            group.add(trunk);

            const leavesMat = new THREE.MeshLambertMaterial({ color: 0x2d5a27 });
            const s1 = new THREE.Mesh(new THREE.DodecahedronGeometry(1.5), leavesMat);
            s1.position.y = 3.5;
            group.add(s1);
            const s2 = new THREE.Mesh(new THREE.DodecahedronGeometry(1.2), leavesMat);
            s2.position.set(0.5, 4.2, 0.5);
            group.add(s2);
            const s3 = new THREE.Mesh(new THREE.DodecahedronGeometry(1.0), leavesMat);
            s3.position.set(-0.6, 4.0, -0.4);
            group.add(s3);

            // Planter box
            const planter = new THREE.Mesh(new THREE.BoxGeometry(2, 0.5, 2), new THREE.MeshLambertMaterial({ color: 0x666666 }));
            planter.position.y = 0.25;
            group.add(planter);

            // Give random slight rotation for variety
            group.rotation.y = Math.random() * Math.PI;
            group.position.set(x, 0, z);
            this.scene.add(group);

            this.obstacles.push({
                mesh: group,
                label: 'tree',
                hazard: 'low',
                position: { x: x, y: 0, z: z }
            });
        };

        createTree(-7, -25);
        createTree(7, -45);
        createTree(-7, -65);
        createTree(7, -85);

        // 6. Fire Hydrant
        const createHydrant = (x, z) => {
            const h = new THREE.Mesh(
                new THREE.CylinderGeometry(0.2, 0.2, 0.8),
                new THREE.MeshLambertMaterial({ color: 0xcc0000 })
            );
            h.position.set(x, 0.4, z);
            this.scene.add(h);
            this.obstacles.push({
                mesh: h, label: 'fire hydrant', hazard: 'low', position: { x, y: 0, z }
            });
        };
        createHydrant(7.5, -12);
        createHydrant(-7.5, -55);
    }

    _init() {
        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true,
            alpha: false,
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;

        // Camera
        this.camera = new THREE.PerspectiveCamera(
            75, this.canvas.clientWidth / this.canvas.clientHeight, 0.1, 100
        );
        this.camera.position.set(0, this.playerHeight, 2);

        // Events
        window.addEventListener('resize', () => this._onResize());
        document.addEventListener('keydown', (e) => this._onKeyDown(e));
        document.addEventListener('keyup', (e) => this._onKeyUp(e));
        this.canvas.addEventListener('click', () => this._requestPointerLock());
        document.addEventListener('pointerlockchange', () => this._onPointerLockChange());
        document.addEventListener('mousemove', (e) => this._onMouseMove(e));
    }

    loadScene(preset = 'indoor') {
        const config = SCENE_PRESETS[preset] || SCENE_PRESETS.indoor;
        this.scene = new THREE.Scene();
        this.obstacles = [];

        // Fog
        this.scene.fog = new THREE.Fog(config.fogColor, config.fogNear, config.fogFar);
        this.scene.background = new THREE.Color(config.fogColor);

        // Lighting
        const ambient = new THREE.AmbientLight(0xffffff, config.ambient);
        this.scene.add(ambient);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(5, 10, 5);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.set(1024, 1024);
        this.scene.add(dirLight);

        // Accent lights for atmosphere
        const pointLight1 = new THREE.PointLight(0x3b82f6, 0.4, 15);
        pointLight1.position.set(-3, 2.5, -10);
        this.scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0xa855f7, 0.3, 15);
        pointLight2.position.set(3, 2.5, -20);
        this.scene.add(pointLight2);

        // Floor
        const floorGeo = new THREE.PlaneGeometry(config.floor.width, config.floor.depth);
        const floorMat = new THREE.MeshStandardMaterial({
            color: config.floor.color,
            roughness: 0.85,
            metalness: 0.1,
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.position.z = -config.floor.depth / 2 + 5;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Floor grid lines for depth perception
        const gridHelper = new THREE.GridHelper(
            Math.max(config.floor.width, config.floor.depth),
            Math.max(config.floor.width, config.floor.depth),
            0x333355, 0x222240
        );
        gridHelper.position.y = 0.01;
        gridHelper.position.z = -config.floor.depth / 2 + 5;
        this.scene.add(gridHelper);

        // Walls
        if (config.walls) {
            const wallMat = new THREE.MeshStandardMaterial({
                color: config.wallColor,
                roughness: 0.9,
                side: THREE.DoubleSide,
            });
            const hw = config.floor.width / 2;
            const hd = config.floor.depth;

            // Left wall
            const lw = new THREE.Mesh(new THREE.PlaneGeometry(hd, config.ceilingHeight || 3.5), wallMat);
            lw.position.set(-hw, (config.ceilingHeight || 3.5) / 2, -hd / 2 + 5);
            lw.rotation.y = Math.PI / 2;
            this.scene.add(lw);

            // Right wall
            const rw = new THREE.Mesh(new THREE.PlaneGeometry(hd, config.ceilingHeight || 3.5), wallMat);
            rw.position.set(hw, (config.ceilingHeight || 3.5) / 2, -hd / 2 + 5);
            rw.rotation.y = -Math.PI / 2;
            this.scene.add(rw);

            // Back wall
            const bw = new THREE.Mesh(new THREE.PlaneGeometry(config.floor.width, config.ceilingHeight || 3.5), wallMat);
            bw.position.set(0, (config.ceilingHeight || 3.5) / 2, -hd + 5);
            this.scene.add(bw);
        }

        // Ceiling
        if (config.ceiling) {
            const ceilMat = new THREE.MeshStandardMaterial({
                color: config.wallColor || 0x111122,
                roughness: 0.95,
            });
            const ceil = new THREE.Mesh(
                new THREE.PlaneGeometry(config.floor.width, config.floor.depth),
                ceilMat
            );
            ceil.rotation.x = Math.PI / 2;
            ceil.position.set(0, config.ceilingHeight || 3.5, -config.floor.depth / 2 + 5);
            this.scene.add(ceil);

            // Ceiling lights
            for (let z = -5; z > -config.floor.depth + 5; z -= 8) {
                const light = new THREE.PointLight(0xffffee, 0.6, 10);
                light.position.set(0, (config.ceilingHeight || 3.5) - 0.3, z);
                this.scene.add(light);

                // Light fixture
                const fixGeo = new THREE.CylinderGeometry(0.15, 0.25, 0.1, 8);
                const fixMat = new THREE.MeshStandardMaterial({ color: 0xcccccc, emissive: 0xffffee, emissiveIntensity: 0.4 });
                const fixture = new THREE.Mesh(fixGeo, fixMat);
                fixture.position.copy(light.position);
                this.scene.add(fixture);
            }
        }

        // Add Custom Builder Decorations
        if (config.customBuilder === 'realistic_city') {
            this._buildRealisticCity(config);
        } else if (preset === 'realistic_outdoor') {
            const roadWidth = 14;
            // Road markings
            for (let z = -2; z > -config.floor.depth; z -= 4) {
                const lineGeo = new THREE.PlaneGeometry(0.2, 2);
                const lineMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
                const line = new THREE.Mesh(lineGeo, lineMat);
                line.rotation.x = -Math.PI / 2;
                line.position.set(0, 0.02, z);
                this.scene.add(line);
            }
            // Sidewalks
            const sideWidth = 6;
            const sideGeo = new THREE.BoxGeometry(sideWidth, 0.15, config.floor.depth);
            const sideMat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.9 });
            const swLeft = new THREE.Mesh(sideGeo, sideMat);
            swLeft.position.set(-roadWidth / 2 - sideWidth / 2, 0.075, -config.floor.depth / 2 + 5);
            swLeft.receiveShadow = true;
            this.scene.add(swLeft);
            const swRight = new THREE.Mesh(sideGeo, sideMat);
            swRight.position.set(roadWidth / 2 + sideWidth / 2, 0.075, -config.floor.depth / 2 + 5);
            swRight.receiveShadow = true;
            this.scene.add(swRight);
            // Buildings
            const bldgMat = new THREE.MeshStandardMaterial({ color: 0x4a5a6a, roughness: 0.8 });
            const bldgMat2 = new THREE.MeshStandardMaterial({ color: 0x6a5a4a, roughness: 0.8 });
            for (let z = -10; z > -config.floor.depth; z -= 15) {
                const b1 = new THREE.Mesh(new THREE.BoxGeometry(8, 20, 10), bldgMat);
                b1.position.set(-15, 10, z);
                b1.castShadow = true;
                b1.receiveShadow = true;
                this.scene.add(b1);

                const b2 = new THREE.Mesh(new THREE.BoxGeometry(8, 25, 12), bldgMat2);
                b2.position.set(15, 12.5, z - 5);
                b2.castShadow = true;
                b2.receiveShadow = true;
                this.scene.add(b2);
            }
        }

        // Add obstacles
        config.obstacles.forEach((o) => {
            this._addObstacle(o.type, o.pos, o.rot);
        });

        // Reset camera
        this.camera.position.set(0, this.playerHeight, 2);
        this.euler.set(0, 0, 0);
        this.camera.quaternion.setFromEuler(this.euler);
    }

    _addObstacle(type, position, rotation = 0) {
        const def = OBSTACLE_DEFS[type];
        if (!def) return;

        let mesh;

        if (type === 'person' || type === 'real_person') {
            // Realistic person shape
            const group = new THREE.Group();

            // Legs
            const legGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.8, 8);
            const legMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.8 });
            const lLeg = new THREE.Mesh(legGeo, legMat);
            lLeg.position.set(-0.15, 0.4, 0);
            lLeg.castShadow = true;
            const rLeg = new THREE.Mesh(legGeo, legMat);
            rLeg.position.set(0.15, 0.4, 0);
            rLeg.castShadow = true;

            // Torso
            const torsoGeo = new THREE.BoxGeometry(0.45, 0.7, 0.25);
            const torsoMat = new THREE.MeshStandardMaterial({ color: 0x2196F3, roughness: 0.7 });
            const torso = new THREE.Mesh(torsoGeo, torsoMat);
            torso.position.y = 1.15;
            torso.castShadow = true;

            // Head
            const headGeo = new THREE.SphereGeometry(0.15, 16, 16);
            const headMat = new THREE.MeshStandardMaterial({ color: 0xffccaa, roughness: 0.6 });
            const head = new THREE.Mesh(headGeo, headMat);
            head.position.y = 1.6;
            head.castShadow = true;

            group.add(lLeg, rLeg, torso, head);
            group.position.set(...position);
            group.rotation.y = rotation;
            mesh = group;
        } else if (type === 'real_car') {
            // Realistic Car
            const group = new THREE.Group();
            const bodyGeo = new THREE.BoxGeometry(1.8, 0.6, 4.2);
            const bodyMat = new THREE.MeshStandardMaterial({ color: 0xAA2222, roughness: 0.3, metalness: 0.7 });
            const body = new THREE.Mesh(bodyGeo, bodyMat);
            body.position.y = 0.5;
            body.castShadow = true;

            const cabinGeo = new THREE.BoxGeometry(1.6, 0.5, 2.2);
            const cabinMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.1, metalness: 0.9 });
            const cabin = new THREE.Mesh(cabinGeo, cabinMat);
            cabin.position.set(0, 1.05, -0.2);
            cabin.castShadow = true;

            const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.2, 16);
            const wheelMat = new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.9 });
            const wheelLocs = [[-0.9, 0.3, 1.4], [0.9, 0.3, 1.4], [-0.9, 0.3, -1.4], [0.9, 0.3, -1.4]];
            wheelLocs.forEach(loc => {
                const wheel = new THREE.Mesh(wheelGeo, wheelMat);
                wheel.rotation.z = Math.PI / 2;
                wheel.position.set(...loc);
                group.add(wheel);
            });

            group.add(body, cabin);
            group.position.set(...position);
            group.rotation.y = rotation;
            mesh = group;
        } else if (type === 'traffic_post') {
            const group = new THREE.Group();
            const poleGeo = new THREE.CylinderGeometry(0.08, 0.08, 3.5, 8);
            const poleMat = new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.8 });
            const pole = new THREE.Mesh(poleGeo, poleMat);
            pole.position.y = 1.75;
            pole.castShadow = true;

            const lightGeo = new THREE.BoxGeometry(0.4, 1.0, 0.4);
            const lightMat = new THREE.MeshStandardMaterial({ color: 0x222222 });
            const box = new THREE.Mesh(lightGeo, lightMat);
            box.position.set(0, 3.2, 0);

            const lensGeo = new THREE.SphereGeometry(0.15, 8, 8);
            const redMat = new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xaa0000 });
            const lens = new THREE.Mesh(lensGeo, redMat);
            lens.position.set(0, 3.4, 0.2);

            group.add(pole, box, lens);
            group.position.set(...position);
            mesh = group;
        } else if (type === 'cone') {
            // Simple person shape (cylinder body + sphere head)
            const group = new THREE.Group();
            const bodyGeo = new THREE.CylinderGeometry(0.2, 0.25, 1.3, 8);
            const bodyMat = new THREE.MeshStandardMaterial({ color: def.color, roughness: 0.7 });
            const body = new THREE.Mesh(bodyGeo, bodyMat);
            body.position.y = 0.65;
            body.castShadow = true;
            group.add(body);

            const headGeo = new THREE.SphereGeometry(0.15, 8, 8);
            const headMat = new THREE.MeshStandardMaterial({ color: 0xffccaa, roughness: 0.6 });
            const head = new THREE.Mesh(headGeo, headMat);
            head.position.y = 1.45;
            head.castShadow = true;
            group.add(head);

            group.position.set(...position);
            mesh = group;
        } else if (type === 'cone') {
            const geo = new THREE.ConeGeometry(0.15, def.height, 8);
            const mat = new THREE.MeshStandardMaterial({ color: def.color, roughness: 0.6 });
            mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(position[0], def.height / 2, position[2]);
            mesh.castShadow = true;
        } else if (type === 'pole') {
            const geo = new THREE.CylinderGeometry(0.07, 0.07, def.height, 8);
            const mat = new THREE.MeshStandardMaterial({ color: def.color, metalness: 0.6, roughness: 0.3 });
            mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(position[0], def.height / 2, position[2]);
            mesh.castShadow = true;
        } else {
            const geo = new THREE.BoxGeometry(def.width, def.height, def.depth);
            const mat = new THREE.MeshStandardMaterial({ color: def.color, roughness: 0.7 });
            mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(position[0], def.height / 2 + (position[1] || 0), position[2]);
            mesh.castShadow = true;
        }

        this.scene.add(mesh);
        this.obstacles.push({
            mesh,
            type,
            label: def.label,
            hazard: def.hazard,
            position: new THREE.Vector3(...position),
        });
    }

    applyGVS(gvsData) {
        this.currentGVS = gvsData;
    }

    getCameraState() {
        return {
            position: {
                x: this.camera.position.x,
                y: this.camera.position.y,
                z: this.camera.position.z,
            },
            rotationY: this.euler.y,
        };
    }

    update() {
        if (!this.scene) return;
        // Cap delta at 0.05s (20 FPS) to prevent physics integration explosion on lag spikes
        const delta = Math.min(this.clock.getDelta(), 0.05);

        if (this.isPointerLocked) {
            // Movement
            this.velocity.x -= this.velocity.x * 8.0 * delta;
            this.velocity.z -= this.velocity.z * 8.0 * delta;

            this.direction.z = Number(this.keys.w) - Number(this.keys.s);
            this.direction.x = Number(this.keys.d) - Number(this.keys.a);
            this.direction.normalize();

            if (this.keys.w || this.keys.s) this.velocity.z -= this.direction.z * this.moveSpeed * delta;
            if (this.keys.a || this.keys.d) this.velocity.x += this.direction.x * this.moveSpeed * delta;

            // Galvanic Vestibular Stimulation Physics Pull (if active)
            if (this.currentGVS && this.currentGVS.active) {
                const strength = this.currentGVS.arrow_strength || 0;
                const angleRad = (this.currentGVS.arrow_angle || 0) * Math.PI / 180;

                // Target drift force — clamped to prevent physics explosion
                const rawDrift = Math.sin(angleRad) * strength * 0.6 * delta;
                const maxDrift = 0.015; // max lateral push per frame
                const targetDrift = Math.max(-maxDrift, Math.min(maxDrift, rawDrift));

                // Smooth via exponential lerp (prevents abrupt jumps)
                const lerpFactor = 1.0 - Math.exp(-6.0 * delta);
                const smoothDrift = (this._prevDrift || 0) + (targetDrift - (this._prevDrift || 0)) * lerpFactor;
                this._prevDrift = smoothDrift;

                this.velocity.x += smoothDrift;

                // Smooth involuntary heading (yaw) drift
                this.euler.setFromQuaternion(this.camera.quaternion);
                this.euler.y -= smoothDrift * 0.03; // gentler yaw twist
                this.camera.quaternion.setFromEuler(this.euler);
            } else {
                this._prevDrift = 0;
            }

            // Apply in camera's local space
            const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
            forward.y = 0;
            forward.normalize();
            const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
            right.y = 0;
            right.normalize();

            this.camera.position.addScaledVector(forward, -this.velocity.z);
            this.camera.position.addScaledVector(right, this.velocity.x);
            this.camera.position.y = this.playerHeight;
        }

        this.renderer.render(this.scene, this.camera);
    }

    captureFrame() {
        if (!this.renderer) return null;
        return this.canvas.toDataURL('image/jpeg', 0.35);
    }

    _onResize() {
        const parent = this.canvas.parentElement;
        if (!parent) return;
        const w = parent.clientWidth;
        const h = parent.clientHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    _onKeyDown(e) {
        const key = e.key.toLowerCase();
        if (key in this.keys) this.keys[key] = true;
        if (key === ' ') { this.keys.space = true; e.preventDefault(); }
    }

    _onKeyUp(e) {
        const key = e.key.toLowerCase();
        if (key in this.keys) this.keys[key] = false;
        if (key === ' ') this.keys.space = false;
    }

    _requestPointerLock() {
        this.canvas.requestPointerLock();
    }

    _onPointerLockChange() {
        this.isPointerLocked = document.pointerLockElement === this.canvas;
    }

    _onMouseMove(e) {
        if (!this.isPointerLocked) return;
        this.euler.setFromQuaternion(this.camera.quaternion);
        this.euler.y -= e.movementX * this.lookSpeed;
        this.euler.x -= e.movementY * this.lookSpeed;
        this.euler.x = Math.max(-Math.PI / 2.5, Math.min(Math.PI / 2.5, this.euler.x));
        this.camera.quaternion.setFromEuler(this.euler);
    }
}
