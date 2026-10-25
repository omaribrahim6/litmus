import { STEPS, VERSION, initialState, advance, back, restore, record } from './flow.mjs';
const $ = id => document.getElementById(id);
const KEY = `litmus-demo-${VERSION}`;
let state = initialState();
try { state = restore(JSON.parse(localStorage.getItem(KEY))); } catch { /* Rehearsal works without storage. */ }
let start = null, stream = null, cameraRequest = 0;
const savedFrames = new Map();
function render() {
  const step = STEPS[state.step];
  $('headline').textContent = step.headline; $('detail').textContent = step.detail;
  $('cue').textContent = step.cue; $('note').textContent = step.note;
  $('step-label').textContent = `STEP ${state.step + 1} / ${STEPS.length} · ${step.title}`;
  $('steps').replaceChildren(...STEPS.map((s, i) => { const el = document.createElement('div'); el.className = `step ${i === state.step ? 'active' : i < state.step ? 'done' : ''}`; if (i === state.step) el.setAttribute('aria-current', 'step'); const n = document.createElement('span'); n.className = 'step-number'; n.textContent = i < state.step ? '✓' : String(i + 1); el.append(n, document.createTextNode(s.title)); return el; }));
  $('next').textContent = step.action; $('back').disabled = state.step === 0;
  $('comparison').hidden = state.step < 4; $('analysis').hidden = state.step < 4; $('next-experiment').hidden = state.step < 5;
  $('liquid-a').classList.toggle('reacted', state.step >= 3); $('liquid-b').classList.toggle('reacted', state.step >= 3);
  $('timeline').replaceChildren(...(state.events.length ? state.events.map(e => { const li = document.createElement('li'), time = document.createElement('time'); time.textContent = new Date(e.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); li.append(time, document.createTextNode(e.text)); return li; }) : [Object.assign(document.createElement('li'), { textContent: 'Ready. Begin when you are.', className: 'empty' })]));
  $('event-count').textContent = `${state.events.length} presenter markers`;
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* Storage is optional. */ }
}
function download(name, content, type) { const url = URL.createObjectURL(new Blob([content], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
function exportRecord() { download('litmus-hot-water-DEMO.json', JSON.stringify({ ...record(state), saved_camera_frames: [...savedFrames.keys()], camera_frame_note: 'Frames are separate local downloads, not analyzed by this demo.' }, null, 2), 'application/json'); }
function next() { if ($('reset-dialog').open) return; if (state.step === STEPS.length - 1) { exportRecord(); return; } if (start === null) start = Date.now(); state = advance(state); render(); }
function previous() { if ($('reset-dialog').open) return; state = back(state); render(); }
$('next').addEventListener('click', next); $('back').addEventListener('click', previous); $('export').addEventListener('click', exportRecord);
$('reset').addEventListener('click', () => $('reset-dialog').showModal());
$('reset-dialog').addEventListener('close', () => { if ($('reset-dialog').returnValue === 'reset') { state = initialState(); start = null; savedFrames.clear(); $('elapsed').textContent = '00:00'; $('evidence').hidden = true; $('evidence-toggle').setAttribute('aria-expanded', 'false'); render(); } });
$('evidence-toggle').addEventListener('click', () => { $('evidence').hidden = !$('evidence').hidden; $('evidence-toggle').setAttribute('aria-expanded', String(!$('evidence').hidden)); });
document.addEventListener('keydown', e => { if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || $('reset-dialog').open || /INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName) || e.target.isContentEditable) return; if ([' ', 'ArrowRight'].includes(e.key)) { e.preventDefault(); next(); } if (e.key === 'ArrowLeft') { e.preventDefault(); previous(); } if (e.key.toLowerCase() === 'f') { (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => {}); } });
setInterval(() => { if (start === null) return; const seconds = Math.floor((Date.now() - start) / 1000); $('elapsed').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; }, 1000);
function stopCamera(message = 'Illustration selected. Presentation controls still work.') { cameraRequest++; if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; $('camera').srcObject = null; $('camera').hidden = true; $('illustration').hidden = false; $('camera-select').hidden = true; $('capture').hidden = true; $('camera-toggle').textContent = 'Use live camera'; $('source-label').textContent = 'Illustration · not camera footage'; $('scene-tag').textContent = 'Expected appearance · illustrative'; $('camera-message').textContent = message; }
async function startCamera(deviceId) {
  if (!navigator.mediaDevices?.getUserMedia) { $('camera-message').textContent = 'Camera unavailable. Use the illustration or open this page in a camera-enabled HTTPS browser.'; return; }
  stopCamera('Waiting for camera permission…'); const request = ++cameraRequest;
  $('camera-toggle').disabled = true;
  try {
    const incoming = await navigator.mediaDevices.getUserMedia({ audio: false, video: deviceId ? { deviceId: { exact: deviceId }, width: { ideal: 1280 } } : { width: { ideal: 1280 }, facingMode: 'environment' } });
    if (request !== cameraRequest) { incoming.getTracks().forEach(t => t.stop()); return; }
    stream = incoming; $('camera').srcObject = stream; await $('camera').play();
    $('camera').hidden = false; $('illustration').hidden = true; $('capture').hidden = false;
    $('camera-toggle').textContent = 'Use illustration'; $('source-label').textContent = 'Live browser camera · preview only'; $('scene-tag').textContent = 'Live preview · prepared narrative stays separate'; $('camera-message').textContent = 'Camera on this device. This does not connect to the Pi remotely.';
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput');
    $('camera-select').replaceChildren(...devices.map((d, i) => new Option(d.label || `Camera ${i + 1}`, d.deviceId)));
    $('camera-select').value = stream.getVideoTracks()[0].getSettings().deviceId || ''; $('camera-select').hidden = devices.length < 2;
    stream.getVideoTracks()[0].addEventListener('ended', () => { if (request === cameraRequest) stopCamera('Camera disconnected. Illustration restored; presentation can continue.'); });
  } catch { if (request === cameraRequest) stopCamera('Camera unavailable or permission denied. Illustration restored; presentation can continue.'); }
  finally { $('camera-toggle').disabled = false; }
}
$('camera-toggle').addEventListener('click', () => stream ? stopCamera() : startCamera());
$('camera-select').addEventListener('change', e => startCamera(e.target.value));
$('capture').addEventListener('click', () => { const video = $('camera'); if (!stream || !video.videoWidth) return; const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight; canvas.getContext('2d').drawImage(video, 0, 0); const name = `litmus-camera-step-${state.step + 1}-${Date.now()}.jpg`; canvas.toBlob(blob => { if (!blob) return; const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); savedFrames.set(name, true); setTimeout(() => URL.revokeObjectURL(url), 1000); $('camera-message').textContent = 'Camera frame saved locally. It has not been analyzed.'; }, 'image/jpeg', .9); });
window.addEventListener('pagehide', () => { if (stream) stream.getTracks().forEach(t => t.stop()); });
window.addEventListener('offline', () => $('offline').textContent = 'Offline · presentation still works');
window.addEventListener('online', () => $('offline').textContent = 'Ready · waits for you');
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
render();
