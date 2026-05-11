
/**
 * ASL-3D Professional Three.js Viewer
 * Handles GLB loading, realistic lighting, and interactive controls.
 */

import * as THREE from 'https://cdn.skypack.dev/three@0.132.2';
import { OrbitControls } from 'https://cdn.skypack.dev/three@0.132.2/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'https://cdn.skypack.dev/three@0.132.2/examples/jsm/loaders/GLTFLoader.js';

class ASL3DViewer {
    constructor(containerId, modelUrl) {
        this.container = document.getElementById(containerId);
        this.modelUrl = modelUrl;
        
        if (!this.container) return;

        this.init();
        this.animate();
        this.loadModel();
        
        window.addEventListener('resize', () => this.onWindowResize(), false);
    }

    init() {
        // 1. Scene & Camera
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0d1117); // Dark background matching the theme

        this.camera = new THREE.PerspectiveCamera(45, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.camera.position.set(0, 2, 10);

        // 2. Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);

        // 3. Lights (Studio Setup)
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
        dirLight.position.set(5, 10, 7.5);
        dirLight.castShadow = true;
        dirLight.shadow.camera.top = 10;
        dirLight.shadow.camera.bottom = -10;
        dirLight.shadow.camera.left = -10;
        dirLight.shadow.camera.right = 10;
        dirLight.shadow.mapSize.width = 2048;
        dirLight.shadow.mapSize.height = 2048;
        this.scene.add(dirLight);

        const fillLight = new THREE.PointLight(0x6c63ff, 0.5); // Subtle purple accent
        fillLight.position.set(-5, 5, -5);
        this.scene.add(fillLight);

        // 4. Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.screenSpacePanning = false;
        this.controls.minDistance = 2;
        this.controls.maxDistance = 50;
        this.controls.maxPolarAngle = Math.PI;
    }

    loadModel() {
        const loader = new GLTFLoader();
        
        // Loading Indicator
        const loadingText = document.createElement('div');
        loadingText.style.position = 'absolute';
        loadingText.style.top = '50%';
        loadingText.style.left = '50%';
        loadingText.style.transform = 'translate(-50%, -50%)';
        loadingText.style.color = '#6c63ff';
        loadingText.style.fontFamily = 'sans-serif';
        loadingText.innerText = 'Chargement du modèle...';
        this.container.appendChild(loadingText);

        loader.load(this.modelUrl, (gltf) => {
            this.model = gltf.scene;
            
            // Auto-center and Scale
            const box = new THREE.Box3().setFromObject(this.model);
            const size = box.getSize(new THREE.Vector3()).length();
            const center = box.getCenter(new THREE.Vector3());

            this.model.position.x += (this.model.position.x - center.x);
            this.model.position.y += (this.model.position.y - center.y);
            this.model.position.z += (this.model.position.z - center.z);
            
            this.controls.maxDistance = size * 10;
            this.camera.near = size / 100;
            this.camera.far = size * 100;
            this.camera.updateProjectionMatrix();
            this.camera.position.copy(center);
            this.camera.position.x += size / 2.0;
            this.camera.position.y += size / 5.0;
            this.camera.position.z += size / 2.0;
            this.camera.lookAt(center);

            this.model.traverse((node) => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = true;
                    
                    // Improve Material Appearance
                    if (node.material) {
                        node.material.roughness = 0.7;
                        node.material.metalness = 0.2;
                    }
                }
            });

            this.scene.add(this.model);
            this.container.removeChild(loadingText);
            
        }, undefined, (error) => {
            console.error(error);
            loadingText.innerText = 'Erreur de chargement 3D';
        });
    }

    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.controls) this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}

// Export for global use
window.ASL3DViewer = ASL3DViewer;
