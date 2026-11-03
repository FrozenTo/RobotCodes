const $ = (id) => document.getElementById(id);
let gridData = {};
let selected = null;
let fromCell = null;
let toCell = null;
let currentConfig = {};

function log(message, kind='info') {
  const t = new Date().toLocaleTimeString();
  const prefix = kind === 'error' ? 'ERROR' : kind === 'ok' ? 'OK' : 'INFO';
  $('log').textContent += `[${t}] ${prefix}: ${message}\n`;
  $('log').scrollTop = $('log').scrollHeight;
}

async function api(url, options={}) {
  const res = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function n(v, digits=2) { return v == null ? '—' : Number(v).toFixed(digits); }

function renderGrid() {
  const grid = $('grid'); grid.innerHTML = '';
  $('lettersAxis').innerHTML = '<span></span>' + 'ABCDEFGHIJ'.split('').map(x => `<span>${x}</span>`).join('');
  // CSS grid top row is 5, bottom row is 1 so the robot is visually at the top.
  $('rowAxis').innerHTML = [5,4,3,2,1].map(r => `<span>${r}</span>`).join('');
  for (const row of [5,4,3,2,1]) {
    for (const letter of 'ABCDEFGHIJ') {
      const name = `${letter}${row}`;
      const c = gridData[name];
      const b = document.createElement('button');
      b.className = 'cell';
      if (c?.blocked) b.classList.add('blocked');
      if (name === selected) b.classList.add('selected');
      if (name === fromCell) b.classList.add('from');
      if (name === toCell) b.classList.add('to');
      b.innerHTML = `<span>${name}</span>${c?.label ? `<small>${escapeHtml(c.label)}</small>` : ''}`;
      b.title = c ? `${name}  X ${n(c.x)}  Y ${n(c.y)}${c.blocked ? '  BLOCKED' : ''}` : name;
      b.onclick = () => selectCell(name);
      grid.appendChild(b);
    }
  }
}

function escapeHtml(s) { return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

function selectCell(name) {
  selected = name;
  const c = gridData[name];
  $('selectedName').textContent = name;
  $('selectedXY').textContent = `X ${n(c.x)} · Y ${n(c.y)}${c.blocked ? ' · BLOCKED' : ''}`;
  $('cellLabel').value = c.label || '';
  $('cellRole').value = c.role || '';
  $('pickZ').value = c.pick_z ?? '';
  $('placeZ').value = c.place_z ?? '';
  $('blockedCell').checked = !!c.blocked;
  ['moveAboveBtn','setFromBtn','setToBtn','saveCellBtn'].forEach(id => $(id).disabled = false);
  $('pickBtn').disabled = !!c.blocked || c.pick_z == null;
  $('placeBtn').disabled = !!c.blocked || c.place_z == null;
  renderGrid();
}

function updateTransfer() {
  $('fromName').textContent = fromCell || '—';
  $('toName').textContent = toCell || '—';
  $('transferBtn').disabled = !(fromCell && toCell && fromCell !== toCell && gridData[fromCell]?.pick_z != null && gridData[toCell]?.place_z != null && !gridData[fromCell]?.blocked && !gridData[toCell]?.blocked);
  renderGrid();
}

async function loadGrid() {
  const arr = await api('/api/grid');
  gridData = Object.fromEntries(arr.map(c => [c.name, c]));
  renderGrid();
  if (selected) selectCell(selected);
  updateTransfer();
}

async function refreshState() {
  try {
    const s = await api('/api/state');
    currentConfig = s.config;
    $('safeZLabel').textContent = n(s.config.safe_z, 0).replace('-', '−');
    $('robotPill').textContent = `Robot: ${s.online ? 'online' : 'offline'}`;
    $('robotPill').className = `pill ${s.online ? '' : 'danger'}`;
    $('busyPill').textContent = s.runtime.busy ? 'Busy' : 'Idle';
    $('busyPill').className = `pill ${s.runtime.busy ? 'danger' : 'neutral'}`;
    const p = s.pose;
    const spans = $('posePanel').querySelectorAll('b');
    if (p) [0,1,2,3].forEach(i => spans[i].textContent = n(p[i]));
    if (!$('robotIp').matches(':focus')) $('robotIp').value = s.config.robot_ip || '';
    if (!$('safeZ').matches(':focus')) $('safeZ').value = s.config.safe_z;
    if (!$('speedFactor').matches(':focus')) $('speedFactor').value = s.config.speed_factor;
    if (!$('gridPitch').matches(':focus')) $('gridPitch').value = s.config.grid_pitch;
    if (!$('gridX1').matches(':focus')) $('gridX1').value = s.config.grid_x_row1;
    if (!$('gridYA').matches(':focus')) $('gridYA').value = s.config.grid_y_colA;
    if (!$('cameraUrl').matches(':focus')) $('cameraUrl').value = s.config.camera_stream_url || '';
    if (!$('usbCameraIndex').matches(':focus')) $('usbCameraIndex').value = s.config.usb_camera_index ?? 0;
    if (!$('usbCameraWidth').matches(':focus')) $('usbCameraWidth').value = s.config.usb_camera_width ?? 1280;
    if (!$('usbCameraHeight').matches(':focus')) $('usbCameraHeight').value = s.config.usb_camera_height ?? 720;
    if (!$('usbCameraFps').matches(':focus')) $('usbCameraFps').value = s.config.usb_camera_fps ?? 15;
    if (!$('assemblyZGlass').matches(':focus')) $('assemblyZGlass').value = s.config.assembly_z_glass ?? -150.21;
    if (!$('assemblyZAtomGlass').matches(':focus')) $('assemblyZAtomGlass').value = s.config.assembly_z_atom_glass ?? -140.59;
    if (!$('assemblyZFullPick').matches(':focus')) $('assemblyZFullPick').value = s.config.assembly_z_full_pick ?? s.config.assembly_z_full ?? -122.92;
    if (!$('assemblyZFullPlace').matches(':focus')) $('assemblyZFullPlace').value = s.config.assembly_z_full_place ?? -125.52;
    if (!$('assemblyR').matches(':focus')) $('assemblyR').value = s.config.assembly_r ?? -50.18;
    $('glassZLabel').textContent = n(s.config.assembly_z_glass ?? -150.21);
    $('atomGlassZLabel').textContent = n(s.config.assembly_z_atom_glass ?? -140.59);
    $('fullPickZLabel').textContent = n(s.config.assembly_z_full_pick ?? s.config.assembly_z_full ?? -122.92);
    $('fullPlaceZLabel').textContent = n(s.config.assembly_z_full_place ?? -125.52);
    $('assemblyRLabel').textContent = `${n(s.config.assembly_r ?? -50.18)}°`.replace('-', '−');
    updateCamera(s.config.camera_stream_url || '');
    updateUsbCamera();
  } catch (e) { log(e.message, 'error'); }
}

let lastCameraUrl = null;

function cameraStreamCandidates(value) {
  let raw = String(value || '').trim();
  if (!raw) return [];
  if (!/^https?:\/\//i.test(raw)) raw = 'http://' + raw;
  try {
    const u = new URL(raw);
    // If the user supplied a specific non-root path, assume it is already the stream URL.
    if (u.pathname && u.pathname !== '/' && u.pathname !== '/capture') return [u.toString()];
    const host = u.hostname.includes(':') ? `[${u.hostname}]` : u.hostname;
    const protocol = u.protocol || 'http:';
    // Espressif/Seeed CameraWebServer: control page on 80, MJPEG stream on 81.
    // /stream on port 80 is kept as a fallback for custom firmware variants.
    return [
      `${protocol}//${host}:81/stream`,
      `${protocol}//${host}/stream`
    ];
  } catch (_) {
    return [];
  }
}

function updateCamera(url, force=false) {
  if (!force && url === lastCameraUrl) return;
  lastCameraUrl = url;
  const img = $('cameraImage');
  const empty = $('cameraEmpty');
  const crosshair = document.querySelector('.crosshair');
  const candidates = cameraStreamCandidates(url);
  if (!candidates.length) {
    img.removeAttribute('src'); img.style.display='none'; empty.style.display='block'; crosshair.style.display='none'; return;
  }

  let attempt = 0;
  empty.style.display='none';
  img.style.display='block';
  crosshair.style.display='block';

  const tryNext = () => {
    if (attempt >= candidates.length) {
      img.style.display='none';
      crosshair.style.display='none';
      empty.textContent='Camera stream unavailable. Close the XIAO control-page stream, then press Reload.';
      empty.style.display='block';
      return;
    }
    const streamUrl = candidates[attempt++];
    img.onerror = tryNext;
    img.onload = () => {
      empty.style.display='none';
      img.style.display='block';
      crosshair.style.display='block';
    };
    // Load MJPEG directly from the XIAO. No Flask proxy is needed.
    img.src = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${Date.now()}`;
  };
  tryNext();
}

let lastUsbCameraKey = null;
function updateUsbCamera(force=false) {
  const img = $('usbCameraImage'), empty = $('usbCameraEmpty');
  const key = `${$('usbCameraIndex')?.value || 0}:${$('usbCameraWidth')?.value || 1280}:${$('usbCameraHeight')?.value || 720}:${$('usbCameraFps')?.value || 15}`;
  if (!force && key === lastUsbCameraKey && img.src) return;
  lastUsbCameraKey = key;
  empty.style.display = 'none';
  img.style.display = 'block';
  img.onerror = () => {
    img.style.display = 'none';
    empty.style.display = 'block';
    empty.textContent = 'USB camera stream unavailable. Check camera index / connection.';
  };
  img.onload = () => { img.style.display='block'; empty.style.display='none'; };
  img.src = `/camera/usb/stream?t=${Date.now()}`;
}

async function run(label, fn) {
  try { log(label); await fn(); log(`${label} complete`, 'ok'); await refreshState(); }
  catch(e) { log(`${label}: ${e.message}`, 'error'); alert(e.message); }
}

$('moveAboveBtn').onclick = () => selected && run(`Move above ${selected}`, () => api(`/api/move/above/${selected}`, {method:'POST'}));
$('pickBtn').onclick = () => selected && run(`Pick from ${selected}`, () => api(`/api/move/pick/${selected}`, {method:'POST'}));
$('placeBtn').onclick = () => selected && run(`Place at ${selected}`, () => api(`/api/move/place/${selected}`, {method:'POST'}));
$('setFromBtn').onclick = () => { if(selected){ fromCell=selected; updateTransfer(); log(`FROM = ${selected}`); }};
$('setToBtn').onclick = () => { if(selected){ toCell=selected; updateTransfer(); log(`TO = ${selected}`); }};
$('transferBtn').onclick = () => run(`Transfer ${fromCell} → ${toCell}`, () => api('/api/move/transfer', {method:'POST', body:JSON.stringify({source:fromCell,destination:toCell})}));
$('enableBtn').onclick = () => run('Enable robot', () => api('/api/robot/enable', {method:'POST'}));
$('disableBtn').onclick = () => run('Disable robot', () => api('/api/robot/disable', {method:'POST'}));
$('stopBtn').onclick = () => run('STOP', () => api('/api/robot/stop', {method:'POST'}));
$('suctionOnBtn').onclick = () => run('Suction ON', () => api('/api/tool/suction', {method:'POST', body:JSON.stringify({on:true})}));
$('suctionOffBtn').onclick = () => run('Suction OFF', () => api('/api/tool/suction', {method:'POST', body:JSON.stringify({on:false})}));
$('blowBtn').onclick = () => run('Blow pulse', () => api('/api/tool/blow', {method:'POST'}));


async function applyPresetTo(field, key, fallback) {
  if (!selected) { alert('Select a cell first.'); return; }
  const value = Number(currentConfig?.[key] ?? fallback);
  const isPick = field === 'pickZ';
  $(field).value = value.toFixed(2);

  // Presets are trusted measured assembly heights, so save them immediately.
  // This avoids the confusing preset -> Save cell -> Pick/Place sequence.
  const payload = {
    label: $('cellLabel').value,
    role: $('cellRole').value,
    pick_z: isPick ? value : $('pickZ').value,
    place_z: isPick ? $('placeZ').value : value,
    blocked: $('blockedCell').checked
  };

  try {
    await api(`/api/cell/${selected}`, {
      method:'POST',
      body:JSON.stringify(payload)
    });
    log(`${selected}: ${isPick ? 'Pick' : 'Place'} Z saved = ${value.toFixed(2)}`, 'ok');
    await loadGrid();
  } catch(e) {
    log(e.message, 'error');
    alert(e.message);
  }
}
$('glassToPick').onclick = () => applyPresetTo('pickZ', 'assembly_z_glass', -150.21);
$('glassToPlace').onclick = () => applyPresetTo('placeZ', 'assembly_z_glass', -150.21);
$('atomGlassToPick').onclick = () => applyPresetTo('pickZ', 'assembly_z_atom_glass', -140.59);
$('atomGlassToPlace').onclick = () => applyPresetTo('placeZ', 'assembly_z_atom_glass', -140.59);
$('fullToPick').onclick = () => applyPresetTo('pickZ', 'assembly_z_full_pick', -122.92);
$('fullToPlace').onclick = () => applyPresetTo('placeZ', 'assembly_z_full_place', -125.52);

$('saveCellBtn').onclick = async () => {
  if(!selected) return;
  try {
    await api(`/api/cell/${selected}`, {method:'POST', body:JSON.stringify({label:$('cellLabel').value, role:$('cellRole').value, pick_z:$('pickZ').value, place_z:$('placeZ').value, blocked:$('blockedCell').checked})});
    log(`Saved ${selected}`, 'ok'); await loadGrid();
  } catch(e) { log(e.message,'error'); alert(e.message); }
};


$('testRobotBtn').onclick = async () => {
  const box = $('connectionResult');
  try {
    // Save the IP first so the test uses exactly what is currently typed in Settings.
    await api('/api/settings', {method:'POST', body:JSON.stringify({robot_ip:$('robotIp').value.trim()})});
    box.textContent = 'Testing…';
    log(`Testing MG400 at ${$('robotIp').value.trim()}`);
    const r = await api('/api/robot/test', {method:'POST'});
    const pose = r.pose ? ` · Pose X ${n(r.pose[0])}, Y ${n(r.pose[1])}, Z ${n(r.pose[2])}, R ${n(r.pose[3])}` : '';
    const warning = r.get_pose_warning ? ` · ${r.get_pose_warning}` : '';
    box.textContent = `Connected: dashboard ${r.dashboard_port} (${r.dashboard_tcp.ms} ms), motion ${r.motion_port} (${r.motion_tcp.ms} ms)${pose}${warning}`;
    log(`Robot connection OK at ${r.ip}`, 'ok');
    await refreshState();
  } catch(e) {
    box.textContent = `Connection failed: ${e.message}`;
    log(`Robot connection test failed: ${e.message}`, 'error');
  }
};

$('testCameraBtn').onclick = async () => {
  const box = $('cameraResult');
  try {
    await api('/api/settings', {method:'POST', body:JSON.stringify({camera_stream_url:$('cameraUrl').value.trim()})});
    box.textContent = 'Testing…';
    const r = await api('/api/camera/test', {method:'POST'});
    box.textContent = `Camera OK · stream ${r.stream_url}`;
    log(`Camera OK: ${r.stream_url}`, 'ok');
    lastCameraUrl=null; updateCamera($('cameraUrl').value.trim(), true);
  } catch(e) {
    box.textContent = `Camera failed: ${e.message}`;
    log(`Camera test failed: ${e.message}`, 'error');
  }
};

$('openCameraBtn').onclick = () => {
  let value = $('cameraUrl').value.trim();
  if (!value) value = 'http://192.168.4.1';
  if (!/^https?:\/\//i.test(value)) value = 'http://' + value;
  try {
    const u = new URL(value);
    window.open(`${u.protocol}//${u.hostname}${u.port && u.port !== '81' ? ':'+u.port : ''}/`, '_blank');
  } catch(e) { alert('Invalid camera address'); }
};

$('testUsbCameraBtn').onclick = async () => {
  const box = $('usbCameraResult');
  box.textContent = 'Testing USB camera...';
  try {
    const r = await api('/api/camera/usb/test', {method:'POST', body:JSON.stringify({index:Number($('usbCameraIndex').value || 0)})});
    box.textContent = `USB camera ${r.index} OK · ${r.width}×${r.height} · JPEG ${Math.round(r.jpeg_bytes/1024)} KB`;
    log(`USB camera ${r.index} connected (${r.width}×${r.height})`, 'ok');
    lastUsbCameraKey = null;
    updateUsbCamera(true);
  } catch(e) {
    box.textContent = `USB camera failed: ${e.message}`;
    log(`USB camera test failed: ${e.message}`, 'error');
  }
};

$('saveSettingsBtn').onclick = async () => {
  try {
    await api('/api/settings', {method:'POST', body:JSON.stringify({robot_ip:$('robotIp').value.trim(), safe_z:$('safeZ').value, speed_factor:$('speedFactor').value, grid_pitch:$('gridPitch').value, grid_x_row1:$('gridX1').value, grid_y_colA:$('gridYA').value, camera_stream_url:$('cameraUrl').value, usb_camera_index:$('usbCameraIndex').value, usb_camera_width:$('usbCameraWidth').value, usb_camera_height:$('usbCameraHeight').value, usb_camera_fps:$('usbCameraFps').value, assembly_z_glass:$('assemblyZGlass').value, assembly_z_atom_glass:$('assemblyZAtomGlass').value, assembly_z_full_pick:$('assemblyZFullPick').value, assembly_z_full_place:$('assemblyZFullPlace').value, assembly_z_full:$('assemblyZFullPick').value, assembly_r:$('assemblyR').value})});
    log('Settings saved', 'ok'); lastCameraUrl=null; await loadGrid(); await refreshState();
  } catch(e) { log(e.message,'error'); alert(e.message); }
};

$('reloadCamera').onclick = () => { lastCameraUrl=null; updateCamera($('cameraUrl').value.trim(), true); };
$('reloadUsbCamera').onclick = () => { lastUsbCameraKey=null; updateUsbCamera(true); };
$('clearLog').onclick = () => $('log').textContent = '';

(async function init(){
  await loadGrid(); await refreshState();
  log('Website loaded. Real MG400 control is active.');
  setInterval(refreshState, 1500);
})();
