"use strict";

const $ = id => document.getElementById(id);
const canvas = $("paper");
const ctx = canvas.getContext("2d");
const state = {
  width: 360, height: 235, margin: 12,
  strokes: [], undo: [], redo: [], tool: "pen", active: null,
  drawingId: null, revision: null, dirty: false,
  gallery: [], mouseDown: false,
  paletteId: "fiorello-sketch-12-v1", markerColors: [], markerColorMap: {}, selectedColor: "black"
};
const colors = { ink: "#1e293b", active: "#2563eb", guide: "#c1c9d6" };

function clone(o) { return JSON.parse(JSON.stringify(o)); }
function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }
function dist(a,b) { return Math.hypot(a[0]-b[0], a[1]-b[1]); }
function notice(message, type="") {
  $("feedback").textContent = message;
  $("feedback").className = "feedback " + type;
}
function markDirty() {
  state.dirty = true;
  updateStats(false);
}
function markSaved() {
  state.dirty = false;
  updateStats(true);
}
function snapshot() {
  state.undo.push(clone(state.strokes));
  if (state.undo.length > 40) state.undo.shift();
  state.redo.length = 0;
}
function setTool(tool) {
  state.tool = tool;
  document.querySelectorAll("[data-tool]").forEach(b => b.classList.toggle("active", b.dataset.tool === tool));
  canvas.style.cursor = tool === "erase" ? "not-allowed" : "crosshair";
}
function colorHex(colorId) {
  return state.markerColorMap[colorId]?.hex || colors.ink;
}
function colorName(colorId) {
  return state.markerColorMap[colorId]?.name || "Black";
}
function setColor(colorId) {
  if (!state.markerColorMap[colorId]) return;
  state.selectedColor = colorId;
  $("selectedColorName").textContent = colorName(colorId);
  document.querySelectorAll(".color-choice").forEach(btn => {
    const selected = btn.dataset.color === colorId;
    btn.classList.toggle("selected", selected);
    btn.setAttribute("aria-checked", selected ? "true" : "false");
  });
  render();
}
function buildColorPalette() {
  const root = $("colorPalette");
  root.replaceChildren();
  for (const color of state.markerColors) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "color-choice";
    btn.dataset.color = color.id;
    btn.style.setProperty("--marker-color", color.hex);
    btn.title = color.name;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-label", color.name + " marker");
    btn.addEventListener("click", () => setColor(color.id));
    root.appendChild(btn);
  }
  setColor(state.selectedColor);
}
function usedColorCount() {
  return new Set(state.strokes.map(s => s.color || "black")).size;
}
function updateStats(saved=true) {
  const count = state.strokes.length;
  const colorCount = count ? usedColorCount() : 0;
  const colorText = colorCount === 1 ? "1 color" : `${colorCount} colors`;
  $("canvasStats").textContent = `${count} strokes · ${colorText}${saved ? "" : " · Unsaved changes"}`;
}
function pagePoint(event) {
  const rect = canvas.getBoundingClientRect();
  const rawX = (event.clientX - rect.left) / rect.width * state.width;
  const rawY = (event.clientY - rect.top) / rect.height * state.height;
  return [clamp(rawX, state.margin, state.width - state.margin),
          clamp(rawY, state.margin, state.height - state.margin)];
}
function insidePage(event) {
  const rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width * state.width;
  const y = (event.clientY - rect.top) / rect.height * state.height;
  return x >= state.margin && x <= state.width - state.margin &&
         y >= state.margin && y <= state.height - state.margin;
}
function makeShape(tool, a, b) {
  if (tool === "line") return [a,b];
  const l=Math.min(a[0],b[0]), r=Math.max(a[0],b[0]);
  const t=Math.min(a[1],b[1]), bt=Math.max(a[1],b[1]);
  if (tool === "rectangle") return [[l,t],[r,t],[r,bt],[l,bt],[l,t]];
  if (tool === "ellipse") {
    const cx=(l+r)/2, cy=(t+bt)/2, rx=(r-l)/2, ry=(bt-t)/2;
    const count=Math.max(24,Math.min(190,Math.ceil(Math.PI*(rx+ry)/2)));
    return Array.from({length: count + 1}, (_,i)=>
      [cx + rx*Math.cos(2*Math.PI*i/count),cy + ry*Math.sin(2*Math.PI*i/count)]);
  }
  return [a,b];
}
function distanceToSegment(p,a,b) {
  const dx=b[0]-a[0],dy=b[1]-a[1], len=dx*dx+dy*dy;
  const t=len>0 ? clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/len,0,1):0;
  return dist(p,[a[0]+dx*t,a[1]+dy*t]);
}
function eraseAt(p) {
  let best=7, index=-1;
  state.strokes.forEach((stroke,i)=> {
    if (stroke.points.length === 1) {
      const d=dist(p,stroke.points[0]);
      if (d<best) {best=d;index=i;}
    }
    for(let j=1;j<stroke.points.length;j++) {
      const d=distanceToSegment(p,stroke.points[j-1],stroke.points[j]);
      if(d<best){best=d;index=i;}
    }
  });
  if(index>=0){snapshot();state.strokes.splice(index,1);markDirty();render();}
}
function onDown(e) {
  if(e.button !== 0 && e.pointerType === "mouse") return;
  if(!insidePage(e)) return;
  e.preventDefault();
  const p=pagePoint(e);
  if(state.tool === "erase") {eraseAt(p);return;}
  state.active={shape:state.tool, color:state.selectedColor, points:[p], start:p};
  state.mouseDown=true;
  canvas.setPointerCapture(e.pointerId);
  render();
}
function onMove(e) {
  if(!state.mouseDown || !state.active) return;
  const p=pagePoint(e);
  if(state.tool === "pen") {
    const points=state.active.points;
    if(dist(points[points.length-1],p)>=0.85 && points.length < 1999) points.push(p);
  } else {
    state.active.points=makeShape(state.tool,state.active.start,p);
  }
  render();
}
function onUp(e) {
  if(!state.active || !state.mouseDown) return;
  onMove(e);
  let points=state.active.points;
  if(state.tool === "pen") {
    const p=pagePoint(e);
    if (dist(points[points.length-1],p)>.3 && points.length<2000) points.push(p);
    if(points.length===1){
      const x=points[0][0],y=points[0][1];
      points.push([x+.6<=state.width-state.margin ? x+.6 : x-.6,y]);
    }
  }
  snapshot();
  state.strokes.push({shape:state.tool,color:state.active.color || state.selectedColor,points:points.map(p=>[+p[0].toFixed(3),+p[1].toFixed(3)])});
  state.active=null;
  state.mouseDown=false;
  markDirty();
  render();
}
function renderStroke(stroke,color,lineWidth=1.3) {
  const pts=stroke.points;
  if(!pts.length)return;
  ctx.beginPath();
  ctx.moveTo(pts[0][0],pts[0][1]);
  for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i][0],pts[i][1]);
  ctx.lineCap="round";ctx.lineJoin="round";ctx.strokeStyle=color;ctx.lineWidth=lineWidth;
  ctx.stroke();
}
function render() {
  const rect=canvas.getBoundingClientRect();
  if(rect.width<20 || rect.height<20)return;
  // We use world millimeters in the canvas, not screenshot pixels.
  const dpr=window.devicePixelRatio||1;
  const w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));
  if(canvas.width!==w || canvas.height!==h){canvas.width=w;canvas.height=h;}
  ctx.setTransform(w/state.width,0,0,h/state.height,0,0);
  ctx.fillStyle="#fff";ctx.fillRect(0,0,state.width,state.height);
  ctx.save();
  ctx.strokeStyle="#eff2f7";ctx.lineWidth=.3;
  for(let x=20;x<state.width;x+=20){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,state.height);ctx.stroke();}
  for(let y=20;y<state.height;y+=20){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(state.width,y);ctx.stroke();}
  ctx.restore();
  ctx.strokeStyle=colors.guide;ctx.lineWidth=.55;ctx.setLineDash([3,2.5]);
  ctx.strokeRect(state.margin,state.margin,state.width-2*state.margin,state.height-2*state.margin);
  ctx.setLineDash([]);
  for(const s of state.strokes)renderStroke(s,colorHex(s.color || "black"));
  if(state.active)renderStroke(state.active,colorHex(state.active.color || state.selectedColor),1.5);
}
function replaceDrawing(strokes,name,id=null,revision=null,author="") {
  state.strokes=strokes;state.active=null;state.mouseDown=false;
  state.undo=[];state.redo=[];state.drawingId=id;state.revision=revision;
  $("drawingName").value=name;
  $("authorName").value=author;
  $("updateBtn").disabled=!id;
  markSaved();render();
}
function undo() {
  if(!state.undo.length)return;
  state.redo.push(clone(state.strokes));state.strokes=state.undo.pop();
  markDirty();render();
}
function redo() {
  if(!state.redo.length)return;
  state.undo.push(clone(state.strokes));state.strokes=state.redo.pop();
  markDirty();render();
}
function safeToDiscard(){return !state.dirty||confirm("You have unsaved changes. Discard them?");}
function drawingData() {
  return {format:"xarm850-freehand-v1",palette:state.paletteId,name:$("drawingName").value.trim(),author:$("authorName").value.trim(),
          width_mm:state.width,height_mm:state.height,strokes:state.strokes};
}
async function api(url, options={}) {
  const res=await fetch(url,{cache:"no-store",...options});
  const data=await res.json();
  if(!res.ok)throw new Error(data.error || `Server error ${res.status}`);
  return data;
}
async function save(asNew) {
  const data=drawingData();
  if(!data.name){notice("Please enter a drawing name.","error");$("drawingName").focus();return;}
  if(!data.strokes.length){notice("Draw something before saving.","error");return;}
  const isNew=asNew||!state.drawingId;
  try {
    if(!isNew)data.revision=state.revision;
    const url=isNew?"/api/drawings":`/api/drawings/${state.drawingId}`;
    const result=await api(url,{method:isNew?"POST":"PUT",
                  headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
    state.drawingId=result.id;state.revision=result.revision;
    $("updateBtn").disabled=false;
    markSaved();
    notice(`Saved “${data.name}” on the server PC! Other computers can open it.`,"good");
    await refreshGallery();
  }catch(err){notice("Save failed: "+err.message,"error");}
}
function downloadJson(data, filename="xarm_drawing.json"){
  // Deliberately omit private server metadata: compatible with the Tkinter app.
  const payload={format:data.format,palette:data.palette || state.paletteId,width_mm:data.width_mm,height_mm:data.height_mm,strokes:data.strokes};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob);const a=document.createElement("a");
  a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function validateImported(data){
  if(data?.format!=="xarm850-freehand-v1"||!Array.isArray(data.strokes))
    throw new Error("This is not a compatible xArm freehand drawing JSON");
  const sw=Number(data.width_mm),sh=Number(data.height_mm);
  if(!(sw>0&&sh>0)||!Number.isFinite(sw)||!Number.isFinite(sh))throw new Error("Invalid source paper size");
  if(data.strokes.length>1500)throw new Error("Too many strokes");
  const sx=state.width/sw,sy=state.height/sh;
  return data.strokes.map((s,i)=>{
    if(!["pen","line","rectangle","ellipse"].includes(s.shape)||!Array.isArray(s.points)||
       !s.points.length||s.points.length>2000)throw new Error(`Stroke ${i+1} is invalid`);
    const pts=s.points.map(p=>{
      if(!Array.isArray(p)||p.length!==2||p.some(v=>typeof v!=="number"||!Number.isFinite(v)))
        throw new Error("A drawing point is invalid");
      const x=p[0]*sx,y=p[1]*sy;
      if(x<state.margin-.001||x>state.width-state.margin+.001||
         y<state.margin-.001||y>state.height-state.margin+.001)
        throw new Error(`Stroke ${i+1} crosses the paper safety margin`);
      return [+x.toFixed(3),+y.toFixed(3)];
    });
    const color=s.color ?? "black";
    if(typeof color!=="string" || !state.markerColorMap[color])
      throw new Error(`Stroke ${i+1} uses an unknown marker color`);
    return {shape:s.shape,color,points:pts};
  });
}
async function openDrawing(id){
  if(!safeToDiscard())return;
  try{
    const data=await api(`/api/drawings/${id}`);
    const strokes=validateImported(data);
    replaceDrawing(strokes,data.name||"Untitled",data.id,data.revision,data.author||"");
    notice(`Opened “${data.name}”. You can save changes or save a new copy.`,"good");
    renderGallery();
    window.scrollTo({top:0,behavior:"smooth"});
  }catch(err){notice("Open failed: "+err.message,"error");}
}
function formatDate(s){
  if(!s)return"Unknown time";
  const d=new Date(s);
  return Number.isNaN(d.getTime())?s:d.toLocaleString(undefined,{dateStyle:"medium",timeStyle:"short"});
}
function renderGallery(){
  const root=$("gallery");root.replaceChildren();
  const term=$("search").value.trim().toLowerCase();
  const items=state.gallery.filter(item=>item.name.toLowerCase().includes(term));
  if(!items.length){
    const p=document.createElement("p");p.className="empty";
    p.textContent=term?"No drawings match your search.":"No drawings saved yet. Be the first!";
    root.appendChild(p);return;
  }
  items.forEach(item=>{
    const card=document.createElement("article");card.className="gallery-item";
    if(item.id===state.drawingId)card.classList.add("current");
    const title=document.createElement("strong");title.textContent=item.name;
    const meta=document.createElement("small");
    const colorCount=Array.isArray(item.colors)?item.colors.length:0;
    const colorMeta=colorCount?` · ${colorCount} ${colorCount===1?"color":"colors"}`:"";
    meta.textContent=`${item.author ? "By " + item.author + " · " : ""}${item.strokes} strokes${colorMeta} · ${formatDate(item.updated_at)}`;
    const buttons=document.createElement("div");buttons.className="gallery-buttons";
    const open=document.createElement("button");open.textContent="Open / edit";
    open.addEventListener("click",()=>openDrawing(item.id));
    const download=document.createElement("a");download.textContent="Download JSON";
    download.href=`/api/drawings/${item.id}/download`;
    buttons.append(open,download);card.append(title,meta,buttons);root.appendChild(card);
  });
}
async function refreshGallery(){
  try{state.gallery=(await api("/api/drawings")).drawings;renderGallery();}
  catch(err){notice("Gallery unavailable: "+err.message,"error");}
}
async function init(){
  try{
    const config=await api("/api/config");
    state.width=config.width_mm;state.height=config.height_mm;state.margin=config.margin_mm;
    state.paletteId=config.palette || "fiorello-sketch-12-v1";
    state.markerColors=Array.isArray(config.marker_colors)?config.marker_colors:[];
    state.markerColorMap=Object.fromEntries(state.markerColors.map(c=>[c.id,c]));
    state.selectedColor=state.markerColorMap[config.default_color]?config.default_color:(state.markerColors[0]?.id || "black");
    buildColorPalette();
    canvas.style.aspectRatio=`${state.width}/${state.height}`;
    $("paperSize").textContent=`${state.width} × ${state.height} mm`;
    document.querySelector(".paper-bottom strong").textContent=`${state.margin} mm safety margin`;
    $("connectionStatus").textContent="Connected to drawing server";
    notice("Ready. Your browser creates vector strokes; Save stores them on the server PC.");
    render();await refreshGallery();
  }catch(err){
    $("connectionStatus").textContent="Server unreachable";
    notice("Cannot connect to drawing server: "+err.message,"error");
  }
}

canvas.addEventListener("pointerdown",onDown);
canvas.addEventListener("pointermove",onMove);
canvas.addEventListener("pointerup",onUp);
canvas.addEventListener("pointercancel",e=>{state.active=null;state.mouseDown=false;render();});
window.addEventListener("resize",()=>render());
window.addEventListener("beforeunload",e=>{if(state.dirty){e.preventDefault();e.returnValue="";}});
document.querySelectorAll("[data-tool]").forEach(btn=>btn.addEventListener("click",()=>setTool(btn.dataset.tool)));
$("undoBtn").addEventListener("click",undo);
$("redoBtn").addEventListener("click",redo);
$("clearBtn").addEventListener("click",()=>{
  if(state.strokes.length && confirm("Clear all strokes on this canvas?")){
    snapshot();state.strokes=[];markDirty();render();
  }
});
$("newBtn").addEventListener("click",()=>{
  if(safeToDiscard()){replaceDrawing([],"My drawing");setColor(state.markerColorMap.black?"black":state.selectedColor);notice("New blank drawing. Nothing has been saved yet.");renderGallery();}
});
$("saveNewBtn").addEventListener("click",()=>save(true));
$("updateBtn").addEventListener("click",()=>save(false));
$("downloadBtn").addEventListener("click",()=>{
  if(!state.strokes.length){notice("Nothing to download.","error");return;}
  downloadJson(drawingData());notice("Downloaded JSON that the desktop xArm drawing app can open.","good");
});
$("drawingName").addEventListener("input",markDirty);
$("authorName").addEventListener("input",markDirty);
$("refreshBtn").addEventListener("click",refreshGallery);
$("search").addEventListener("input",renderGallery);
$("importBtn").addEventListener("click",()=>$("importFile").click());
$("importFile").addEventListener("change",async(e)=>{
  const file=e.target.files[0];if(!file)return;
  try{
    const json=JSON.parse(await file.text());
    const strokes=validateImported(json);
    if(!safeToDiscard())return;
    replaceDrawing(strokes,(json.name || file.name.replace(/\.json$/i,"")),null,null,json.author||"");
    markDirty();renderGallery();notice(`Imported ${strokes.length} strokes. Save as new to store on server.`,"good");
  }catch(err){notice("Import failed: "+err.message,"error");}
  finally{e.target.value="";}
});
window.addEventListener("keydown",e=>{
  const writing=e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"&&!writing){e.preventDefault();undo();}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="y"&&!writing){e.preventDefault();redo();}
  if(!writing && !e.ctrlKey && !e.altKey && !e.metaKey){
    const t={p:"pen",l:"line",r:"rectangle",e:"ellipse"}[e.key.toLowerCase()];if(t)setTool(t);
  }
});
// The library changes when other people save; refresh it while students are working.
setInterval(refreshGallery,25000);
init();
