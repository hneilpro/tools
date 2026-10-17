"""Single-page drag-and-drop UI for the image scrubber."""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image Scrubber</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #101014; color: #e8e8ec; min-height: 100vh;
         display: flex; flex-direction: column; align-items: center; padding: 32px 16px; }
  h1 { margin: 0 0 6px; font-size: 1.6rem; }
  p.sub { margin: 0 0 24px; color: #9a9aa5; }
  #drop { width: min(640px, 100%); border: 2px dashed #4a4a58; border-radius: 14px;
          padding: 48px 24px; text-align: center; cursor: pointer;
          background: #17171d; transition: border-color .15s, background .15s; }
  #drop.hover { border-color: #7aa2ff; background: #1b1e2a; }
  #drop input { display: none; }
  .opts { width: min(640px, 100%); margin: 18px 0; display: flex; gap: 10px; align-items: center;
          background: #17171d; border: 1px solid #2a2a34; border-radius: 10px; padding: 12px 16px; }
  .opts input[type=checkbox] { width: 18px; height: 18px; accent-color: #7aa2ff; }
  .opts label { cursor: pointer; }
  .opts small { display: block; color: #9a9aa5; margin-top: 2px; }
  #go { width: min(640px, 100%); padding: 13px; font-size: 1rem; border: 0; border-radius: 10px;
        background: #7aa2ff; color: #0c0e16; font-weight: 700; cursor: pointer; }
  #go:disabled { background: #3a3a46; color: #8a8a96; cursor: default; }
  #status { width: min(640px, 100%); margin: 14px 0; color: #9a9aa5; min-height: 1.4em; }
  #results { width: min(640px, 100%); display: flex; flex-direction: column; gap: 10px; }
  .card { background: #17171d; border: 1px solid #2a2a34; border-radius: 10px;
          padding: 12px 14px; display: flex; align-items: center; gap: 12px; }
  .card img { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; background: #000; }
  .card .meta { flex: 1; min-width: 0; }
  .card .meta b { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card .meta span { color: #9a9aa5; font-size: .85rem; }
  .card a { color: #7aa2ff; text-decoration: none; font-weight: 600; white-space: nowrap; }
  .err { color: #ff9a9a; }
  #all { display: none; margin-top: 6px; color: #7aa2ff; font-weight: 600; }
</style>
</head>
<body>
  <h1>Image Scrubber</h1>
  <p class="sub">Drop images in — every bit of metadata (EXIF, GPS, camera info) is stripped locally.</p>

  <div id="drop">
    <div><strong>Drag &amp; drop images here</strong></div>
    <div style="margin-top:6px;color:#9a9aa5">or click to browse — JPG, PNG, WebP, TIFF, BMP</div>
    <input id="file" type="file" accept="image/*" multiple>
  </div>

  <div class="opts">
    <input id="rmbg" type="checkbox">
    <label for="rmbg">Remove background
      <small>Tiny on-device AI (~5MB model, CPU only). Needs <code>pip install rembg onnxruntime</code> — first run downloads the model once.</small>
    </label>
  </div>

  <div class="opts">
    <input id="rename" type="checkbox">
    <label for="rename">Scrub filenames too
      <small>Renames every output to today's date plus a sequence: 2026-10-17-image001.png, 2026-10-17-image002.png, …</small>
    </label>
  </div>

  <div class="opts">
    <input id="aitag" type="checkbox">
    <label for="aitag">Tag as AI-generated content
      <small>Adds a small "AI-generated" marker to the cleaned file (EXIF comment / PNG text).</small>
    </label>
  </div>

  <button id="go" disabled>Scrub 0 files</button>
  <div id="status"></div>
  <div id="results"></div>
  <a id="all" href="#">Download all as zip</a>

<script>
const TOKEN = new URLSearchParams(location.search).get("token") || "";
const drop = document.getElementById("drop");
const input = document.getElementById("file");
const go = document.getElementById("go");
const status = document.getElementById("status");
const results = document.getElementById("results");
const allLink = document.getElementById("all");
let files = [];
let batchId = null;

drop.addEventListener("click", () => input.click());
["dragenter","dragover"].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault(); drop.classList.add("hover");
}));
["dragleave","drop"].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault(); drop.classList.remove("hover");
}));
drop.addEventListener("drop", ev => addFiles(ev.dataTransfer.files));
input.addEventListener("change", () => addFiles(input.files));

function addFiles(list) {
  for (const f of list) {
    if (f.type.startsWith("image/") && !files.some(x => x.name === f.name && x.size === f.size))
      files.push(f);
  }
  render();
}
function render() {
  go.disabled = files.length === 0;
  go.textContent = "Scrub " + files.length + " file" + (files.length === 1 ? "" : "s");
  status.textContent = files.length ? files.map(f => f.name).join(", ") : "";
}
function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({"X-Tool-Token": TOKEN}, opts.headers || {});
  return fetch(path, opts);
}
go.addEventListener("click", async () => {
  if (!files.length) return;
  go.disabled = true;
  status.textContent = "Scrubbing…";
  results.innerHTML = "";
  allLink.style.display = "none";
  const fd = new FormData();
  files.forEach(f => fd.append("files", f, f.name));
  fd.append("ai_tag", document.getElementById("aitag").checked ? "1" : "0");
  fd.append("remove_bg", document.getElementById("rmbg").checked ? "1" : "0");
  fd.append("rename_files", document.getElementById("rename").checked ? "1" : "0");
  try {
    const r = await api("/api/clean", {method: "POST", body: fd});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
    batchId = j.batch;
    status.textContent = j.summary;
    j.items.forEach(it => {
      const d = document.createElement("div");
      d.className = "card";
      if (it.ok) {
        d.innerHTML = '<img alt=""><div class="meta"><b></b><span></span></div><a>Download</a>';
        d.querySelector("img").src = "/api/download?batch=" + encodeURIComponent(batchId)
          + "&id=" + encodeURIComponent(it.id) + "&token=" + encodeURIComponent(TOKEN);
        d.querySelector("b").textContent = it.out_filename;
        d.querySelector("span").textContent = it.note + " (" + it.size[0] + "x" + it.size[1] + ")";
        d.querySelector("a").href = d.querySelector("img").src;
        d.querySelector("a").download = it.out_filename;
      } else {
        d.innerHTML = '<div class="meta"><b></b><span class="err"></span></div>';
        d.querySelector("b").textContent = it.filename;
        d.querySelector("span").textContent = it.error;
      }
      results.appendChild(d);
    });
    const okCount = j.items.filter(i => i.ok).length;
    if (okCount > 1) {
      allLink.style.display = "inline";
      allLink.href = "/api/download-all?batch=" + encodeURIComponent(batchId)
        + "&token=" + encodeURIComponent(TOKEN);
    }
    files = [];
    render();
  } catch (e) {
    status.innerHTML = '<span class="err">Failed: ' + e.message + "</span>";
    go.disabled = false;
  }
});
</script>
</body>
</html>
"""
