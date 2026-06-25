"""Generate a standalone advanced 3D asset visualizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
PLAN_PATH = Path(__file__).resolve().parent / "advanced_asset_plan.json"
SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index_with_overrides.json"
FALLBACK_SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index.json"
HTML_PATH = Path(__file__).resolve().parent / "advanced_asset_view.html"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_spatial() -> dict[str, Any]:
    return read_json(SPATIAL_PATH if SPATIAL_PATH.exists() else FALLBACK_SPATIAL_PATH)


def build_html(plan: dict[str, Any], spatial: dict[str, Any]) -> str:
    template = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>HVRA Advanced 3D Asset View</title>
<style>
:root { --paper:#f7f5ef; --panel:#fffdfa; --line:#d8d3c7; --ink:#181714; --muted:#777064; --accent:#2f8298; --allowed:#2f7d57; --conditional:#b27a1e; --blocked:#9d423f; }
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:var(--paper);color:var(--ink);font-family:Arial,sans-serif;}
#app{display:grid;grid-template-columns:280px 1fr 320px;height:100vh;}
.panel{background:rgba(255,255,252,.94);border-right:1px solid var(--line);padding:16px;overflow:auto;}
.right{border-left:1px solid var(--line);border-right:0;}
h1,h2{font-size:11px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 12px;}
p,li,button,.row{font-size:13px;line-height:1.45;}.hero{font-size:15px;margin-bottom:16px;}.small{font-size:11px;color:var(--muted);}
.tag{display:inline-block;padding:3px 7px;border:1px solid var(--line);border-radius:999px;margin:0 4px 6px 0;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
.asset{border-top:1px solid var(--line);padding:12px 0;}.asset strong{display:block;font-size:13px;margin-bottom:5px;}.allowed strong{color:var(--allowed);}.conditional strong{color:var(--conditional);}.blocked strong{color:var(--blocked);}
button{width:100%;text-align:left;border:1px solid var(--line);background:#fff;padding:9px 10px;margin:5px 0;cursor:pointer;}button.active{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent);}
#stage{position:relative;min-width:0;}#canvas{width:100%;height:100%;display:block;}.hud,.legend{position:absolute;background:rgba(255,255,252,.92);border:1px solid var(--line);padding:12px 14px;}.hud{left:18px;top:18px;width:250px;}.legend{right:18px;bottom:18px;width:260px;}.bar{height:8px;display:grid;grid-template-columns:1fr 1fr 1fr;margin:8px 0;}.bar span:nth-child(1){background:var(--allowed);}.bar span:nth-child(2){background:var(--conditional);}.bar span:nth-child(3){background:var(--blocked);}
#error{position:absolute;left:18px;bottom:18px;max-width:520px;background:#fff3f2;border:1px solid #c47670;color:#5b1f1c;padding:12px;display:none;white-space:pre-wrap;font-size:12px;}
</style>
<script type="importmap">{"imports":{"three":"../../interface/public/vendor/three/build/three.module.js"}}</script>
</head>
<body>
<div id="app">
<aside class="panel"><h1>Advanced Assets</h1><div class="hero">GLB-ready retrofit components with decision gates.</div><div id="summary"></div><h2 style="margin-top:18px">Visible Assets</h2><div id="assetButtons"></div></aside>
<main id="stage"><canvas id="canvas"></canvas><div class="hud"><h2>Room Preview</h2><div id="opening"></div><div class="small">Allowed/conditional assets use wall-hosted placeholders: rails, brackets, shelves, ladders, and trellis panels explain support logic before GLB assets are injected.</div></div><div class="legend"><h2>Suitability</h2><div class="bar"><span></span><span></span><span></span></div><div class="small">green allowed | amber conditional | red blocked</div></div><div id="error"></div></main>
<aside class="panel right"><h1>Decision Trace</h1><div id="trace"></div></aside>
</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from '../../interface/public/vendor/three/examples/jsm/controls/OrbitControls.js';

const PLAN = __PLAN__;
const SPATIAL = __SPATIAL__;
const canvas = document.getElementById('canvas');
const errorBox = document.getElementById('error');
function fail(err){ console.error(err); errorBox.style.display='block'; errorBox.textContent = String(err && err.stack ? err.stack : err); }

try {
const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf7f5ef);
const camera = new THREE.PerspectiveCamera(45, 1, .1, 100);
camera.position.set(6, 5.4, 8);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(.7, 1.4, .1); controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0xb8ad9b, 2.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.8); sun.position.set(5,8,4); scene.add(sun);

const room = SPATIAL.room || { height_m: 2.8, area_m2: 18.5 };
const height = Number(room.height_m || 2.8);
const points = (SPATIAL.layout_points || []).map(p => new THREE.Vector2(Number(p.xyz[0]), Number(p.xyz[2])));
const walls = SPATIAL.walls || [];
const wallById = Object.fromEntries(walls.map(w => [w.id, w]));
const assetObjects = new Map();

function mat(color, opacity=1, side=THREE.DoubleSide){ return new THREE.MeshStandardMaterial({ color, transparent:opacity<1, opacity, side, roughness:.75, metalness:.03 }); }
function box(group, size, pos, color, opacity=1){ const mesh = new THREE.Mesh(new THREE.BoxGeometry(size[0],size[1],size[2]), mat(color,opacity)); mesh.position.set(pos[0],pos[1],pos[2]); group.add(mesh); return mesh; }
function wallFrame(wallId){ const wall = wallById[wallId] || walls[walls.length-1]; const ids = wall && wall.source_points ? wall.source_points : [0,1]; const aRaw = SPATIAL.layout_points[ids[0]] || SPATIAL.layout_points[0]; const bRaw = SPATIAL.layout_points[ids[1]] || SPATIAL.layout_points[1]; const a = new THREE.Vector3(aRaw.xyz[0],0,aRaw.xyz[2]); const b = new THREE.Vector3(bRaw.xyz[0],0,bRaw.xyz[2]); const mid = a.clone().add(b).multiplyScalar(.5); const dir = b.clone().sub(a).normalize(); const normal = new THREE.Vector3(-dir.z,0,dir.x).normalize(); return {a,b,mid,dir,normal,length:a.distanceTo(b)}; }
function pointInPolygon(x,z){ let inside=false; for(let i=0,j=points.length-1;i<points.length;j=i++){ const xi=points[i].x, zi=points[i].y, xj=points[j].x, zj=points[j].y; const hit=((zi>z)!=(zj>z)) && (x < (xj-xi)*(z-zi)/(zj-zi+1e-9)+xi); if(hit) inside=!inside; } return inside; }
function interiorNormal(frame){ const plus=frame.mid.clone().add(frame.normal.clone().multiplyScalar(.18)); const minus=frame.mid.clone().add(frame.normal.clone().multiplyScalar(-.18)); if(pointInPolygon(plus.x, plus.z)) return frame.normal.clone(); if(pointInPolygon(minus.x, minus.z)) return frame.normal.clone().multiplyScalar(-1); return frame.normal.clone().multiplyScalar(-1); }
function openingFrame(){ const f=wallFrame(PLAN.opening_context.target_wall_id); const ratio=Number(PLAN.opening_context.wall_position_ratio ?? .5); const clamped=Math.min(Math.max(ratio,.08),.92); const center=f.mid.clone().add(f.dir.clone().multiplyScalar((clamped-.5)*f.length)); const inward=interiorNormal(f); return {...f, center, inward, ratio:clamped}; }
function openingVertical(){ const center=Number(PLAN.opening_context.vertical_position_ratio ?? .5); const bboxH=Number(PLAN.opening_context.bbox_height_ratio ?? .45); const topRatio=Math.max(0, center - bboxH/2); const bottomRatio=Math.min(1, center + bboxH/2); const headY=Math.min(height-.08, Math.max(.45, height*(1-topRatio))); const sillY=Math.max(0, Math.min(headY-.45, height*(1-bottomRatio))); const openingH=Math.max(.55, headY-sillY); const railY=Math.min(height-.05, headY+.08); const floorClearance=sillY < .2 ? .05 : .02; return {headY,sillY,openingH,railY,floorClearance,topRatio,bottomRatio}; }
function openingWidth(){ const f=openingFrame(); return Math.min(Number(PLAN.opening_context.width_m||1.6), Math.max(1.2,f.length*.72)); }
function sideHost(elementWidth=.65, margin=.18){
  const f=openingFrame(); const openW=openingWidth();
  const leftClear=Math.max(0, f.ratio*f.length-openW/2);
  const rightClear=Math.max(0, (1-f.ratio)*f.length-openW/2);
  let side = rightClear >= leftClear ? 1 : -1;
  const available = Math.max(leftClear, rightClear);
  let x = side*(openW/2 + margin + Math.min(elementWidth/2, Math.max(.10, available/2)));
  const maxX = Math.max(.2, f.length/2 - elementWidth/2 - .10);
  x = Math.max(-maxX, Math.min(maxX, x));
  return {side, x, available, openingWidth:openW};
}
function wallHostedAttach(group, offset=.035){ attach(group, offset); group.userData.host='interior wall surface'; return group; }
function wallSurfaceAttach(group){ attach(group, 0); group.userData.host='interior wall plane'; return group; }
function supportBracket(g,x,y,z=0,width=.22){ box(g,[width,.025,.055],[x,y,z+.055],0x7f7466,1); box(g,[.025,.16,.025],[x,y-.07,z+.012],0x7f7466,1); }
function roomSideMarker(g,labelX=0){ box(g,[.08,.08,.08],[labelX,.18,.22],0x2f8298,.75); }

function floorMesh(y, color, opacity){ if(points.length<3) return; const shape = new THREE.Shape(points); const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat(color,opacity)); mesh.rotation.x = -Math.PI/2; mesh.position.y = y; scene.add(mesh); }
function buildRoom(){ floorMesh(0,0xd9d2c1,.7); floorMesh(height,0xffffff,.16); walls.forEach(w=>{ const f=wallFrame(w.id); const geo=new THREE.BoxGeometry(f.length,height,.05); const mesh=new THREE.Mesh(geo, mat(w.id===PLAN.opening_context.target_wall_id?0xd8edf5:0xcfc7b6, w.id===PLAN.opening_context.target_wall_id ? .55 : .24)); mesh.position.copy(f.mid).add(new THREE.Vector3(0,height/2,0)); mesh.rotation.y = -Math.atan2(f.dir.z,f.dir.x); scene.add(mesh); }); }
function applyWallFrame(group, frame, origin, offset=0){
  const inward = frame.inward.clone().normalize();
  let xAxis = frame.dir.clone().normalize();
  const zAxis = inward;
  // Keep local X along the wall while local +Z always points into the room.
  if (new THREE.Vector3().crossVectors(xAxis, zAxis).y < 0) xAxis.multiplyScalar(-1);
  const yAxis = new THREE.Vector3(0,1,0);
  const basis = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
  group.setRotationFromMatrix(basis);
  group.position.copy(origin).add(inward.clone().multiplyScalar(offset));
  return group;
}
function attach(group, offset=.28){ const f=openingFrame(); applyWallFrame(group, f, f.center, offset); scene.add(group); }
function targetOpening(){ const f=openingFrame(); const v=openingVertical(); const width=openingWidth(); const h=v.openingH; const g=new THREE.Group(); applyWallFrame(g, f, f.center, .055); g.position.y=v.sillY+h/2; box(g,[width,h,.035],[0,0,0],0x9cc2d4,.42); box(g,[width+.12,.055,.08],[0,h/2,0],0x202426,1); box(g,[width+.12,.055,.08],[0,-h/2,0],0x202426,1); box(g,[.055,h,.08],[-width/2,0,0],0x202426,1); box(g,[.055,h,.08],[width/2,0,0],0x202426,1); box(g,[.035,h,.075],[0,0,0],0x202426,.8); scene.add(g); }
function drapes(asset){ const g=new THREE.Group(); const v=openingVertical(); const width=Math.max(1.35, Math.min(Number(PLAN.opening_context.width_m||1.6)+.55, 2.55)); const h=Math.max(.6, v.railY - v.sillY - v.floorClearance); box(g,[width+.32,.045,.08],[0,v.railY,0],0x7e5a4b,1); for(let i=0;i<14;i++){ const x=-width/2+i*(width/13); const m=new THREE.Mesh(new THREE.BoxGeometry(.115,h,.055),mat(i%2?0xd9b8a7:0xc99b86,.74)); m.position.set(x,v.sillY+v.floorClearance+h/2,.02+Math.sin(i)*.025); m.rotation.z=Math.sin(i*.7)*.028; g.add(m); } attach(g,.11); return g; }
function verticalBlind(asset){ const g=new THREE.Group(); const v=openingVertical(); const width=Math.max(1.25, Math.min(Number(PLAN.opening_context.width_m||1.6)+.45, 2.45)); const h=Math.max(.55, v.railY - v.sillY - v.floorClearance); box(g,[width+.2,.05,.08],[0,v.railY,0],0xf1efe5,1); for(let i=0;i<16;i++){ const x=-width/2+i*(width/15); const slat=new THREE.Mesh(new THREE.BoxGeometry(.052,h,.035),mat(0xf6f4ec,.86)); slat.position.set(x,v.sillY+v.floorClearance+h/2,.03); slat.rotation.y=.45; g.add(slat); } attach(g,.13); return g; }
function roller(asset){ const g=new THREE.Group(); const v=openingVertical(); const width=Math.max(1.25, Math.min(Number(PLAN.opening_context.width_m||1.6)+.35, 2.35)); const drop=Math.max(.55, Math.min(v.openingH*.65, 2.2)); box(g,[width+.18,.08,.09],[0,v.railY,0],0xe9e3d2,1); box(g,[width*.46,drop,.035],[-width*.25,v.railY-drop/2-.04,0],0xe1d7be,.58); box(g,[width*.46,drop,.035],[width*.25,v.railY-drop/2-.04,0],0xe1d7be,.58); attach(g,.13); return g; }
function plants(asset){
  const g=new THREE.Group();
  const host=sideHost(1.15,.24);
  const x=host.x;
  box(g,[1.55,.025,.62],[x,.012,.02],0xd8c7a8,.55);
  const species=[
    {x:-.42,z:.08,s:1.18,c:0x4f8b57,k:'tall_palm'},
    {x:.02,z:.20,s:.92,c:0x477d45,k:'broadleaf'},
    {x:.38,z:.02,s:.82,c:0x6ca56a,k:'fern'},
    {x:-.08,z:-.26,s:.84,c:0x3f7e4a,k:'small_tree'},
    {x:.56,z:-.18,s:.52,c:0x77a96a,k:'succulent'}
  ];
  species.forEach((p,i)=>plantModel(g,x+p.x,p.z,p.s,p.c,p.k,0,true));
  wallHostedAttach(g,.30); return g;
}
function insulationLayer(){ const f=openingFrame(); const g=new THREE.Group(); const layerH=Math.min(height*.94, height-.12); const layerW=f.length*.96; const mesh=new THREE.Mesh(new THREE.BoxGeometry(layerW, layerH, .075), mat(0xf3ead7,.72)); mesh.position.set(0, layerH/2, 0); g.add(mesh); const label=new THREE.Mesh(new THREE.BoxGeometry(layerW,.045,.09), mat(0xcab78f,.9)); label.position.set(0,layerH-.08,.04); g.add(label); applyWallFrame(g, f, f.mid, .07); scene.add(g); g.visible=false; assetObjects.set('wall_insulation_reinforcement_layer', g); return g; }

function plantModel(g,x,z,scale,color=0x4f8b57,kind='leafy',baseY=0,faceOut=true){
  scale *= (height > 3.4 ? 1.48 : 1.22);
  const potColor = kind==='succulent' ? 0x9b6b4f : kind==='tall_palm' ? 0x6e5843 : 0x7b5842;
  const potTop = .105*scale, potBottom = .072*scale, potH = .16*scale;
  const pot=new THREE.Mesh(new THREE.CylinderGeometry(potTop,potBottom,potH,18),mat(potColor,1)); pot.position.set(x,baseY+potH/2,z); g.add(pot);
  const zBias=faceOut ? .05*scale : -.05*scale;
  function leaf(px,py,pz,sx,sy,sz,c=color,rx=0,ry=0,rz=0){ const m=new THREE.Mesh(new THREE.SphereGeometry(.055*scale,12,8),mat(c,.96)); m.scale.set(sx,sy,sz); m.position.set(px,py,pz); m.rotation.set(rx,ry,rz); g.add(m); return m; }
  function stem(px,py,pz,h,r=.014){ const m=new THREE.Mesh(new THREE.CylinderGeometry(r*scale,r*1.35*scale,h,8),mat(0x355e3f,1)); m.position.set(px,py+h/2,pz); g.add(m); return m; }

  if(kind==='succulent'){
    for(let i=0;i<12;i++){ const a=i*6.28/12; leaf(x+Math.cos(a)*.045*scale,baseY+potH+.045*scale,z+zBias+Math.sin(a)*.025*scale,1.25,.28,.55, i%2?0x78a96b:0x5f925c,0,.3,a); }
    for(let i=0;i<7;i++){ const a=i*6.28/7; leaf(x+Math.cos(a)*.022*scale,baseY+potH+.09*scale,z+zBias+Math.sin(a)*.012*scale,.95,.24,.45,0x8fbc77,0,.35,a); }
    return;
  }

  if(kind==='tall_palm'){
    const h=.95*scale; stem(x,baseY+potH,z+zBias*.3,h,.012);
    for(let i=0;i<12;i++){ const a=i*6.28/12; leaf(x+Math.cos(a)*.12*scale,baseY+potH+h+.03*scale,z+zBias+Math.sin(a)*.09*scale,2.7,.28,.65,i%2?color:0x2f7441,.2,.35,a); }
    return;
  }

  if(kind==='small_tree'){
    const h=.58*scale; stem(x,baseY+potH,z+zBias*.2,h,.018);
    for(let i=0;i<10;i++){ const a=i*6.28/10; leaf(x+Math.cos(a)*.12*scale,baseY+potH+h+.02*scale+Math.sin(i)*.025*scale,z+zBias+Math.sin(a)*.09*scale,1.45,.48,.8,i%2?0x477d45:0x356f3d,0,.2,a); }
    return;
  }

  if(kind==='fern'){
    for(let i=0;i<16;i++){ const a=i*6.28/16; stem(x,baseY+potH,z,.30*scale,.006); leaf(x+Math.cos(a)*.12*scale,baseY+potH+.22*scale+Math.sin(i)*.015*scale,z+zBias+Math.sin(a)*.08*scale,1.8,.23,.48,i%2?color:0x4d8c4f,.25,.35,a); }
    return;
  }

  if(kind==='spider' || kind==='grass'){
    for(let i=0;i<18;i++){ const a=i*6.28/18; leaf(x+Math.cos(a)*.08*scale,baseY+potH+.20*scale+Math.sin(i)*.025*scale,z+zBias+Math.sin(a)*.055*scale,2.25,.18,.36,i%2?0x72a76c:0x4f8b57,.35,.25,a); }
    return;
  }

  if(kind==='trailing'){
    for(let i=0;i<5;i++){ const dx=(-.16+i*.08)*scale; stem(x+dx,baseY+potH-.34*scale,z+zBias,.34*scale,.004); for(let j=0;j<4;j++){ leaf(x+dx+(j%2? .025:-.025)*scale,baseY+potH-.08*scale-j*.075*scale,z+zBias+.02*scale, .75,.22,.38, j%2?0x4f8b57:0x2f7441,0,.15,j); } }
    return;
  }

  // broadleaf / upright default
  const count=kind==='broadleaf'?11:9;
  for(let i=0;i<count;i++){ const a=i*6.28/count; stem(x+Math.cos(a)*.035*scale,baseY+potH,z+Math.sin(a)*.025*scale,.34*scale,.007); leaf(x+Math.cos(a)*.10*scale,baseY+potH+.32*scale+Math.sin(i)*.018*scale,z+zBias+Math.sin(a)*.06*scale,1.45,.42,.75,i%2?color:0x2f7441,.15,.3,a); }
}
function daylightPlanterShelf(asset){
  const g=new THREE.Group(); const v=openingVertical();
  const width=Math.max(.95, Math.min(Number(PLAN.opening_context.width_m||1.6)*.55, 1.35));
  const host=sideHost(width,.20); const x=host.x; const y=Math.max(.82, Math.min(1.12, v.sillY+.78));
  // Wall-hosted console shelf: back plate and brackets explain the support system.
  box(g,[width,.08,.22],[x,y,.11],0xb79266,1);
  box(g,[width+.08,.20,.035],[x,y-.08,.018],0xf0e7d6,.92);
  supportBracket(g,x-width*.32,y-.07,0,.16); supportBracket(g,x+width*.32,y-.07,0,.16);
  [{dx:-.30,s:.48,k:'succulent',c:0x7aa86b},{dx:-.08,s:.58,k:'spider',c:0x72a76c},{dx:.15,s:.56,k:'trailing',c:0x4f8b57},{dx:.34,s:.60,k:'broadleaf',c:0x5f925c}].forEach(p=>plantModel(g,x+p.dx,.30,p.s,p.c,p.k,y+.045,true));
  wallSurfaceAttach(g); return g;
}
function hangingPlanterRail(asset){
  const g=new THREE.Group(); const v=openingVertical();
  const width=Math.max(1.05, Math.min(Number(PLAN.opening_context.width_m||1.6)*.62, 1.45));
  const host=sideHost(width,.18); const x=host.x; const railY=Math.max(v.railY-.12, height*.62);
  // Renter-friendly wall/track rail placeholder with small standoff brackets.
  box(g,[width,.045,.07],[x,railY,.035],0x5f4a35,1);
  supportBracket(g,x-width*.38,railY-.02,0,.14); supportBracket(g,x+width*.38,railY-.02,0,.14);
  [{dx:-.30,s:.72,k:'trailing',c:0x3f7e4a},{dx:-.08,s:.68,k:'spider',c:0x72a76c},{dx:.14,s:.66,k:'fern',c:0x6ca56a},{dx:.34,s:.72,k:'trailing',c:0x4f8b57}].forEach(p=>{ const px=x+p.dx; box(g,[.012,.42,.012],[px,railY-.20,.09],0x6f6a5f,1); plantModel(g,px,.28,p.s,p.c,p.k,railY-.78,true); });
  wallSurfaceAttach(g); return g;
}
function verticalPlantLadder(asset){
  const g=new THREE.Group(); const width=.78; const host=sideHost(width,.28); const x=host.x; const h=Math.min(2.35,height-.32);
  // Leaning ladder shelf: wall-adjacent, not centered over glazing.
  box(g,[.06,h,.055],[x-width*.34,.24+h/2,.028],0x8b6b48,1); box(g,[.06,h,.055],[x+width*.34,.24+h/2,.028],0x8b6b48,1);
  [{y:.52,dx:-.20,s:.74,k:'fern',c:0x6ca56a},{y:.98,dx:.18,s:.82,k:'broadleaf',c:0x4f8b57},{y:1.44,dx:-.14,s:.68,k:'spider',c:0x72a76c},{y:1.90,dx:.18,s:.70,k:'trailing',c:0x3f7e4a}].forEach(p=>{ box(g,[width,.055,.30],[x,p.y,.16],0xc7aa82,1); plantModel(g,x+p.dx,.30,p.s,p.c,p.k,p.y+.045,true); });
  wallSurfaceAttach(g); return g;
}
function trellisClimber(asset){
  const g=new THREE.Group(); const width=.72; const host=sideHost(width,.28); const x=host.x; const h=Math.min(2.35,height-.32);
  // Trellis is a wall-mounted panel beside the opening, with leaves biased into the room.
  for(let i=0;i<5;i++) box(g,[.026,h,.03],[x-width*.38+i*(width*.19),.32+h/2,.015],0xb79569,1);
  for(let j=0;j<6;j++) box(g,[width,.024,.03],[x,.56+j*.30,.015],0xb79569,1);
  for(let v=0;v<4;v++){ box(g,[.018,1.55,.018],[x-width*.30+v*width*.20,1.25,.035],0x355e3f,.9); } for(let i=0;i<38;i++){ const leaf=new THREE.Mesh(new THREE.SphereGeometry(.052+(i%3)*.006,10,8),mat(i%2?0x4f8b57:0x2f7441,.95)); leaf.scale.set(i%3===0?1.9:1.35,.45,.58); leaf.position.set(x-width*.34+Math.random()*width,.52+Math.random()*1.78,.30); leaf.rotation.y=.35; g.add(leaf); }
  wallSurfaceAttach(g); return g;
}
function addAsset(asset){ let obj=null; if(asset.procedural_fallback==='curtain_drapes') obj=drapes(asset); else if(asset.procedural_fallback==='vertical_blind') obj=verticalBlind(asset); else if(asset.procedural_fallback==='roller_shade') obj=roller(asset); else if(asset.procedural_fallback==='plant_corner_dense') obj=plants(asset); else if(asset.procedural_fallback==='daylight_planter_shelf') obj=daylightPlanterShelf(asset); else if(asset.procedural_fallback==='hanging_planter_rail') obj=hangingPlanterRail(asset); else if(asset.procedural_fallback==='vertical_plant_ladder') obj=verticalPlantLadder(asset); else if(asset.procedural_fallback==='trellis_climber_screen') obj=trellisClimber(asset); if(obj) assetObjects.set(asset.asset_id,obj); }
function text(){ document.getElementById('summary').innerHTML=`<span class="tag">${PLAN.summary.allowed} allowed</span><span class="tag">${PLAN.summary.conditional} conditional</span><span class="tag">${PLAN.summary.blocked} blocked</span><p>${PLAN.summary.preferred_next_step}</p>`; document.getElementById('opening').innerHTML=`<div class="tag">${PLAN.opening_context.opening_type}</div><div class="small">target wall: ${PLAN.opening_context.target_wall_id||'unknown'}</div>`; const all=[...PLAN.allowed_assets,...PLAN.conditional_assets,...PLAN.blocked_assets]; document.getElementById('trace').innerHTML=all.map(a=>`<div class="asset ${a.status}"><strong>${a.label} · ${a.status}</strong><div class="small">${a.family}<br>${a.future_glb_slot||''}</div><p>${(a.reasons||[]).join(' ')}</p>${a.plant_palette&&a.plant_palette.length?`<div class="small">palette: ${a.plant_palette.join(', ')}</div>`:''}</div>`).join(''); }
function buttons(){ const list=[...PLAN.allowed_assets,...PLAN.conditional_assets]; const c=document.getElementById('assetButtons'); c.innerHTML=''; const all=document.createElement('button'); all.textContent='show all allowed + conditional'; all.onclick=()=>assetObjects.forEach((o,id)=>o.visible=id!=='wall_insulation_reinforcement_layer'); c.appendChild(all); const ins=document.createElement('button'); ins.textContent='show insulation reinforcement layer'; ins.onclick=()=>{ assetObjects.forEach((o,id)=>o.visible=id==='wall_insulation_reinforcement_layer'); document.querySelectorAll('button').forEach(x=>x.classList.remove('active')); ins.classList.add('active'); }; c.appendChild(ins); list.forEach(a=>{ const b=document.createElement('button'); b.textContent=`${a.label} - ${a.status}`; b.onclick=()=>{ assetObjects.forEach((o,id)=>o.visible=id===a.asset_id); document.querySelectorAll('button').forEach(x=>x.classList.remove('active')); b.classList.add('active'); }; c.appendChild(b); }); }
function resize(){ const r=canvas.parentElement.getBoundingClientRect(); renderer.setSize(r.width,r.height,false); camera.aspect=r.width/r.height; camera.updateProjectionMatrix(); }
function animate(){ requestAnimationFrame(animate); controls.update(); renderer.render(scene,camera); }

buildRoom(); targetOpening(); [...PLAN.allowed_assets,...PLAN.conditional_assets].forEach(addAsset); insulationLayer(); text(); buttons(); resize(); animate(); window.addEventListener('resize',resize);
} catch(err) { fail(err); }
</script>
</body>
</html>'''
    return template.replace("__PLAN__", json.dumps(plan, ensure_ascii=False)).replace("__SPATIAL__", json.dumps(spatial, ensure_ascii=False))


def main() -> None:
    plan = read_json(PLAN_PATH)
    spatial = load_spatial()
    HTML_PATH.write_text(build_html(plan, spatial), encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    print(f"Allowed: {plan['summary']['allowed']} | Conditional: {plan['summary']['conditional']} | Blocked: {plan['summary']['blocked']}")


if __name__ == "__main__":
    main()




