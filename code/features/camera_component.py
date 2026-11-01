"""
features/camera_component.py
Camera HTML5 - chụp ảnh / quay video.
Luồng lưu: chụp/quay → auto download về máy → user upload qua st.file_uploader.
Không cần postMessage, không cần base64 textarea — đơn giản và chắc chắn.
"""

CAMERA_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
}

.video-wrap { position: relative; width: 100%; }
video {
  width: 100%; border-radius: 12px;
  background: #1e293b;
  max-height: 300px; object-fit: cover;
  display: block;
}

.rec-badge {
  display: none;
  position: absolute; top: 12px; left: 12px;
  background: #ef4444; color: white;
  padding: 3px 12px; border-radius: 20px;
  font-size: .8rem; font-weight: 700;
  animation: blink 1s infinite;
}
@keyframes blink { 50% { opacity: .2; } }

.timer {
  display: none;
  position: absolute; top: 12px; right: 12px;
  background: rgba(0,0,0,.6); color: #fb923c;
  padding: 3px 10px; border-radius: 8px;
  font-size: .9rem; font-weight: 700;
}

/* Buttons */
.controls {
  display: flex; gap: 8px; flex-wrap: wrap;
  justify-content: center; margin-top: 10px;
}
button {
  padding: 9px 20px; border: none; border-radius: 9px;
  font-size: .85rem; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; gap: 6px;
  transition: filter .15s;
}
button:hover:not(:disabled) { filter: brightness(1.15); }
button:disabled { opacity: .4; cursor: not-allowed; }
#btnPhoto  { background: #3b82f6; color: #fff; }
#btnRecord { background: #22c55e; color: #fff; }
#btnStop   { background: #ef4444; color: #fff; display: none; }
#btnSwitch { background: #64748b; color: #fff; }

/* Status */
.status {
  text-align: center; font-size: .82rem;
  margin-top: 8px; min-height: 18px; color: #94a3b8;
}
.status.ok  { color: #4ade80; }
.status.err { color: #f87171; }
.status.rec { color: #fb923c; }

/* Preview gallery */
.gallery {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;
}
.thumb {
  position: relative; width: 80px; height: 80px;
}
.thumb img, .thumb video {
  width: 80px; height: 80px; object-fit: cover;
  border-radius: 8px; border: 2px solid #334155;
}
.thumb .del {
  position: absolute; top: -5px; right: -5px;
  background: #ef4444; color: white; border: none;
  border-radius: 50%; width: 20px; height: 20px;
  font-size: .7rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.dl-hint {
  background: #1e3a5f; border: 1px solid #2563eb;
  border-radius: 8px; padding: 8px 12px;
  font-size: .8rem; color: #93c5fd;
  margin-top: 8px; text-align: center; line-height: 1.5;
}
</style>
</head>
<body>

<div class="video-wrap">
  <video id="video" autoplay playsinline muted></video>
  <span class="rec-badge" id="recBadge">● REC</span>
  <span class="timer" id="timer">00:00</span>
</div>

<div class="controls">
  <button id="btnPhoto">📷 Chụp ảnh</button>
  <button id="btnRecord">🎬 Bắt đầu quay</button>
  <button id="btnStop">⏹ Dừng quay</button>
  <button id="btnSwitch">🔄 Đổi camera</button>
</div>

<div class="status" id="status">Đang khởi động camera...</div>

<!-- Hint hướng dẫn -->
<div class="dl-hint" id="dlHint" style="display:none">
  ✅ File đã tự động tải về máy.<br>
  📁 Upload file vừa tải lên ô <b>"Chọn ảnh/video"</b> bên dưới để lưu vào ký ức.
</div>

<!-- Thumbnail preview -->
<div class="gallery" id="gallery"></div>

<canvas id="canvas" style="display:none"></canvas>

<script>
const MAX_SEC  = 60;
let stream     = null;
let recorder   = null;
let chunks     = [];
let facing     = 'environment';
let elapsed    = 0;
let tickId     = null;
let fileCount  = 0;

const video    = document.getElementById('video');
const canvas   = document.getElementById('canvas');
const status   = document.getElementById('status');
const recBadge = document.getElementById('recBadge');
const timer    = document.getElementById('timer');
const gallery  = document.getElementById('gallery');
const dlHint   = document.getElementById('dlHint');
const btnPhoto  = document.getElementById('btnPhoto');
const btnRecord = document.getElementById('btnRecord');
const btnStop   = document.getElementById('btnStop');
const btnSwitch = document.getElementById('btnSwitch');

/* ── Khởi động camera ───────────────────────────────────────────── */
async function startCamera() {
  try {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: true,
    });
    video.srcObject = stream;
    setStatus('✅ Camera sẵn sàng', 'ok');
    [btnPhoto, btnRecord, btnSwitch].forEach(b => b.disabled = false);
  } catch (e) {
    setStatus('❌ Không truy cập được camera: ' + e.message, 'err');
    [btnPhoto, btnRecord].forEach(b => b.disabled = true);
  }
}

function setStatus(msg, cls = '') {
  status.textContent = msg;
  status.className   = 'status ' + cls;
}

/* ── Auto download helper ───────────────────────────────────────── */
function autoDownload(url, filename) {
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 1000);
  dlHint.style.display = 'block';
}

/* ── Chụp ảnh ───────────────────────────────────────────────────── */
btnPhoto.onclick = () => {
  canvas.width  = video.videoWidth  || 1280;
  canvas.height = video.videoHeight || 720;
  canvas.getContext('2d').drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    fileCount++;
    const url      = URL.createObjectURL(blob);
    const filename = `tripsmart_photo_${Date.now()}.jpg`;

    // Preview
    addThumb(url, 'image');

    // Download
    autoDownload(url, filename);
    setStatus(`📷 Đã chụp ảnh! File "${filename}" đã tải về.`, 'ok');
  }, 'image/jpeg', 0.88);
};

/* ── Quay video ─────────────────────────────────────────────────── */
btnRecord.onclick = () => {
  if (!stream) return;
  chunks = [];
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9' : 'video/webm';
  recorder = new MediaRecorder(stream, { mimeType: mime });
  recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = onStop;
  recorder.start(500);

  // UI
  btnRecord.style.display = 'none';
  btnStop.style.display   = 'flex';
  btnPhoto.disabled       = true;
  recBadge.style.display  = 'block';
  timer.style.display     = 'block';
  elapsed = 0; updateTimer();
  tickId = setInterval(() => {
    elapsed++;
    updateTimer();
    if (elapsed >= MAX_SEC) btnStop.click();
  }, 1000);
  setStatus('🔴 Đang quay... Bấm Dừng khi xong.', 'rec');
};

btnStop.onclick = () => {
  if (recorder && recorder.state !== 'inactive') recorder.stop();
};

function onStop() {
  clearInterval(tickId);
  const blob     = new Blob(chunks, { type: 'video/webm' });
  const url      = URL.createObjectURL(blob);
  fileCount++;
  const filename = `tripsmart_video_${Date.now()}.webm`;

  addThumb(url, 'video');
  autoDownload(url, filename);
  setStatus(`🎬 Đã quay xong! File "${filename}" đã tải về.`, 'ok');

  // Restore UI
  btnRecord.style.display = 'flex';
  btnStop.style.display   = 'none';
  btnPhoto.disabled       = false;
  recBadge.style.display  = 'none';
  timer.style.display     = 'none';
}

function updateTimer() {
  const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  const lm = String(Math.floor(MAX_SEC / 60)).padStart(2, '0');
  const ls = String(MAX_SEC % 60).padStart(2, '0');
  timer.textContent = `${m}:${s} / ${lm}:${ls}`;
}

/* ── Thumbnail preview ──────────────────────────────────────────── */
function addThumb(url, kind) {
  const wrap = document.createElement('div');
  wrap.className = 'thumb';
  const el = document.createElement(kind === 'image' ? 'img' : 'video');
  el.src = url;
  if (kind === 'video') { el.controls = true; el.muted = true; }
  const del = document.createElement('button');
  del.className = 'del'; del.textContent = '×';
  del.onclick = () => wrap.remove();
  wrap.appendChild(el);
  wrap.appendChild(del);
  gallery.appendChild(wrap);
}

/* ── Đổi camera ─────────────────────────────────────────────────── */
btnSwitch.onclick = () => {
  facing = facing === 'environment' ? 'user' : 'environment';
  startCamera();
};

startCamera();
</script>
</body>
</html>
"""

def get_camera_html(height: int = 480) -> str:
    return CAMERA_HTML