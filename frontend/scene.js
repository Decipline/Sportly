import * as THREE from "https://unpkg.com/three@0.165.0/build/three.module.js";

const canvas = document.querySelector("#holoScene");
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
});

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
camera.position.set(0, 1.1, 8.5);

const group = new THREE.Group();
scene.add(group);

const coreGeometry = new THREE.IcosahedronGeometry(1.55, 4);
const coreMaterial = new THREE.MeshPhysicalMaterial({
  color: 0x8ff8ff,
  metalness: 0.28,
  roughness: 0.18,
  transmission: 0.35,
  thickness: 0.8,
  transparent: true,
  opacity: 0.78,
  emissive: 0x173f4b,
  emissiveIntensity: 0.38,
});
const core = new THREE.Mesh(coreGeometry, coreMaterial);
group.add(core);

const wire = new THREE.Mesh(
  new THREE.IcosahedronGeometry(1.75, 2),
  new THREE.MeshBasicMaterial({
    color: 0xffffff,
    wireframe: true,
    transparent: true,
    opacity: 0.16,
  }),
);
group.add(wire);

const ringMaterial = new THREE.MeshBasicMaterial({
  color: 0xffd166,
  transparent: true,
  opacity: 0.34,
  side: THREE.DoubleSide,
});

for (let index = 0; index < 3; index += 1) {
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.35 + index * 0.26, 0.012, 12, 160), ringMaterial);
  ring.rotation.x = Math.PI / 2 + index * 0.42;
  ring.rotation.y = index * 0.55;
  group.add(ring);
}

const nodeGeometry = new THREE.SphereGeometry(0.045, 14, 14);
const nodeMaterials = [0x7cf6c7, 0xff6fb1, 0xffd166, 0x8ff8ff].map(
  (color) =>
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.88,
    }),
);

const nodes = [];
for (let index = 0; index < 42; index += 1) {
  const angle = index * 0.73;
  const radius = 2.25 + Math.sin(index) * 0.7;
  const node = new THREE.Mesh(nodeGeometry, nodeMaterials[index % nodeMaterials.length]);
  node.position.set(Math.cos(angle) * radius, Math.sin(index * 1.7) * 1.25, Math.sin(angle) * radius);
  nodes.push(node);
  group.add(node);
}

const starGeometry = new THREE.BufferGeometry();
const starCount = 900;
const starPositions = new Float32Array(starCount * 3);
for (let index = 0; index < starCount; index += 1) {
  starPositions[index * 3] = (Math.random() - 0.5) * 22;
  starPositions[index * 3 + 1] = (Math.random() - 0.5) * 14;
  starPositions[index * 3 + 2] = (Math.random() - 0.5) * 18;
}
starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));

const stars = new THREE.Points(
  starGeometry,
  new THREE.PointsMaterial({
    color: 0xd8fbff,
    size: 0.018,
    transparent: true,
    opacity: 0.52,
  }),
);
scene.add(stars);

const keyLight = new THREE.PointLight(0x8ff8ff, 16, 10);
keyLight.position.set(-3, 2, 4);
scene.add(keyLight);

const accentLight = new THREE.PointLight(0xff6fb1, 9, 10);
accentLight.position.set(4, -2, 3);
scene.add(accentLight);

const warmLight = new THREE.PointLight(0xffd166, 7, 10);
warmLight.position.set(1, 3, -3);
scene.add(warmLight);

const pointer = new THREE.Vector2();
window.addEventListener("pointermove", (event) => {
  pointer.x = (event.clientX / window.innerWidth - 0.5) * 2;
  pointer.y = (event.clientY / window.innerHeight - 0.5) * 2;
});

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

window.addEventListener("resize", resize);
resize();

renderer.setAnimationLoop((timeMs) => {
  const time = timeMs * 0.001;

  group.rotation.y = time * 0.16 + pointer.x * 0.18;
  group.rotation.x = Math.sin(time * 0.4) * 0.12 + pointer.y * 0.08;
  core.rotation.y = time * 0.32;
  core.rotation.z = time * 0.18;
  wire.rotation.x = -time * 0.17;
  wire.rotation.y = time * 0.24;
  stars.rotation.y = time * 0.025;

  nodes.forEach((node, index) => {
    node.scale.setScalar(1 + Math.sin(time * 2.2 + index) * 0.28);
  });

  renderer.render(scene, camera);
});
