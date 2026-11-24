"use strict";

const $ = id => document.getElementById(id);
const data = JSON.parse($("report-data").textContent);
const {geometry, radio, report_sha256: reportHash} = data;
const {config, tasks, floors} = geometry;
const routeExample = data.route_diagnostic?.example;
const referencePolicy = data.rssi_reference_policy;
const names = {bed:"床", chair:"椅子", plant:"盆栽", sofa:"沙发", toilet:"马桶", tv_monitor:"电视"};
const goalText = {bed:"一张床", chair:"一把椅子", plant:"一盆植物", sofa:"一张沙发", toilet:"一个马桶", tv_monitor:"一台电视"};
const chosen = Object.fromEntries(Object.entries(floors).map(([key, f]) => [key, f.candidates[0].id]));
const taskKey = task => task.task_key ?? task.source_row;
const selectedIndex = new Map(tasks.map((task, index) => [taskKey(task), index + 1]));
const cache = new Map();
let selected = tasks[0];
let projection;
let mapFrame;

function option(select, value, text) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = text;
  select.append(item);
}

function format(value, unit, precision = 1) {
  return value.toFixed(precision) + " " + unit;
}

function coordinate(point) {
  return point.map(value => value.toFixed(2)).join(", ");
}

function bytes(base64) {
  return Uint8Array.from(atob(base64), char => char.charCodeAt(0));
}

function grad(value) {
  const stops = [[-92, 101, 74, 154], [-77, 68, 121, 177], [-67, 44, 163, 147], [-45, 246, 190, 82]];
  if (value < stops[0][0]) return stops[0].slice(1);
  for (let i = 1; i < stops.length; i++) {
    const a = stops[i - 1], b = stops[i];
    if (value <= b[0]) {
      const f = (value - a[0]) / (b[0] - a[0]);
      return [1, 2, 3].map(j => Math.round(a[j] + f * (b[j] - a[j])));
    }
  }
  return stops.at(-1).slice(1);
}

function raster(width, height, paint) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d"), image = ctx.createImageData(width, height);
  for (let i = 0; i < width * height; i++) {
    const color = paint(i);
    if (color) image.data.set(color, i * 4);
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

function floorLayers(floorId) {
  const key = "map/" + floorId;
  if (cache.has(key)) return cache.get(key);
  const native = floors[floorId].map, packed = bytes(native.walkable_bits);
  const walkable = raster(native.width, native.height, i =>
    (packed[i >> 3] & (128 >> (i % 8))) ? [255, 250, 230, 112] : null);
  const cut = radio.floors[floorId].cutaway;
  const texture = new Image();
  if (cut) {
    texture.onload = scheduleMap;
    texture.src = "data:image/webp;base64," + cut.rgba_webp_base64;
  }
  const layers = {walkable, texture, cut};
  cache.set(key, layers);
  return layers;
}

function signalLayers(floorId, apId) {
  const key = floorId + "/" + apId;
  if (cache.has(key)) return cache.get(key);
  const rf = radio.floors[floorId], entry = rf.candidates[apId];
  const values = new Int8Array(bytes(entry.grid_int8).buffer);
  const packed = bytes(entry.covered_bits);
  const heat = raster(rf.width, rf.height, i => values[i] === -128 ? null : [...grad(values[i]), 183]);
  const borders = [];
  const covered = (x, y) => {
    if (x < 0 || x >= rf.width || y < 0 || y >= rf.height) return false;
    const i = y * rf.width + x;
    return Boolean(packed[i >> 3] & (128 >> (i % 8)));
  };
  for (let y = 0; y < rf.height; y++) for (let x = 0; x < rf.width; x++) {
    if (!covered(x,y)) continue;
    if (!covered(x-1,y)) borders.push([x,y,x,y+1]);
    if (!covered(x+1,y)) borders.push([x+1,y,x+1,y+1]);
    if (!covered(x,y-1)) borders.push([x,y,x+1,y]);
    if (!covered(x,y+1)) borders.push([x,y+1,x+1,y+1]);
  }
  const result = {heat, borders};
  cache.set(key, result);
  return result;
}

function canvasContext(id) {
  const canvas = $(id), box = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  const width = box.width, height = box.height;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  return {ctx, width, height};
}

function marker(ctx, x, y, radius, color, border = "#102e2a", borderWidth = 2) {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = border;
  ctx.lineWidth = borderWidth;
  ctx.stroke();
}

function drawMap() {
  mapFrame = null;
  const floorId = selected.floor, floor = floors[floorId], native = floor.map;
  const rf = radio.floors[floorId], ap = chosen[floorId];
  const {ctx, width, height} = canvasContext("map");
  const {walkable, texture, cut} = floorLayers(floorId);
  const signal = signalLayers(floorId, ap);
  const unit = native.meters_per_pixel, [x0, z0] = native.first_center_xz;
  const mapWidth = unit * native.width, mapHeight = unit * native.height;
  const scale = Math.min((width - 42) / mapWidth, (height - 36) / mapHeight);
  const left = (width - mapWidth * scale) / 2, top = (height - mapHeight * scale) / 2;
  const project = (x, z) => [left + (x - x0 + unit / 2) * scale, top + (z - z0 + unit / 2) * scale];
  projection = project;
  if ($("texture").checked && cut && texture.complete && texture.naturalWidth) {
    const [x, y] = project(...cut.top_left_xz);
    ctx.drawImage(texture, x, y, cut.width * cut.meters_per_pixel * scale, cut.height * cut.meters_per_pixel * scale);
  }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(walkable, left, top, mapWidth * scale, mapHeight * scale);
  const step = rf.grid_step_m;
  const [gridX, gridY] = project(x0 - step / 2, z0 - step / 2);
  const px = step * scale;
  if ($("heat").checked) ctx.drawImage(signal.heat, gridX, gridY, rf.width * px, rf.height * px);
  if ($("edge").checked) {
    ctx.beginPath();
    for (const [a, b, c, d] of signal.borders) {
      ctx.moveTo(gridX + a * px, gridY + b * px);
      ctx.lineTo(gridX + c * px, gridY + d * px);
    }
    ctx.strokeStyle = "#153a34";
    ctx.lineWidth = 2.7;
    ctx.stroke();
    ctx.strokeStyle = "#effce9";
    ctx.lineWidth = 1.15;
    ctx.stroke();
  }
  const reference = referenceEntry(selected), route = reference?.route_xyz ?? selected.route_xyz;
  function trace(points) {
    ctx.beginPath();
    points.forEach(([x, , z], i) => {
      const [a,b] = project(x,z);
      if (i) ctx.lineTo(a,b); else ctx.moveTo(a,b);
    });
  }
  if ($("baseline").checked && (reference?.selected || !$("path").checked)) {
    ctx.save();
    trace(selected.route_xyz);
    ctx.setLineDash([6, 5]);
    ctx.strokeStyle = "#273023";
    ctx.lineWidth = 5;
    ctx.stroke();
    ctx.strokeStyle = "#fff1ac";
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.restore();
  }
  if ($("path").checked) {
    trace(route);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = "#103a34";
    ctx.lineWidth = 6;
    ctx.stroke();
    ctx.strokeStyle = reference ? "#9aeaff" : "#fffbe5";
    ctx.lineWidth = 3;
    ctx.stroke();
    if (routeExample?.task_key === taskKey(selected) && ap === routeExample.ap) {
      ctx.save();
      ctx.beginPath();
      routeExample.path_xyz.forEach(([x, , z], i) => {
        const [a, b] = project(x, z);
        if (i) ctx.lineTo(a, b); else ctx.moveTo(a, b);
      });
      ctx.strokeStyle = "#ba64f2";
      ctx.lineWidth = 3.5;
      ctx.setLineDash([7, 5]);
      ctx.stroke();
      ctx.restore();
    }
  }
  if ($("path").checked || $("baseline").checked) {
    marker(ctx, ...project(route[0][0], route[0][2]), 6, "#28b186");
    marker(ctx, ...project(route.at(-1)[0], route.at(-1)[2]), 7, "#ffd468");
  }
  for (const point of floor.candidates) {
    const [x, , z] = point.xyz, [a,b] = project(x,z);
    if (point.id === ap) {
      marker(ctx, a, b, 10, "#e6534d", "#fff", 3);
      ctx.font = "700 11px system-ui";
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 3.5;
      ctx.strokeText(ap, a + 12, b - 10);
      ctx.fillStyle = "#802924";
      ctx.fillText(ap, a + 12, b - 10);
    } else {
      marker(ctx, a, b, 4.6, "rgba(255,255,255,.87)", "#344c48", 1.5);
    }
  }
  ctx.fillStyle = "#193d36";
  ctx.fillRect(15, height - 19, scale, 2);
  ctx.font = "11px system-ui";
  ctx.fillText("1 m", 16, height - 24);
}

function scheduleMap() {
  if (mapFrame == null) mapFrame = requestAnimationFrame(drawMap);
}

function drawProfile() {
  const reference = referenceEntry(selected);
  const profile = reference?.profile ?? apEntry(selected).tasks[selected.source_row];
  const route = reference?.route_xyz ?? selected.route_xyz;
  const cumulative = [0];
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1], b = route[i];
    cumulative.push(cumulative.at(-1) + Math.hypot(b[0]-a[0], b[1]-a[1], b[2]-a[2]));
  }
  const {ctx, width, height} = canvasContext("profile");
  const left = 48, right = 18, top = 14, bottom = height - 30;
  const minimum = Math.min(-85, Math.floor(profile.minimum_dbm / 5) * 5);
  const maximum = Math.max(-45, Math.ceil(Math.max(...profile.samples_dbm) / 5) * 5);
  const px = value => left + (width - left - right) * value / Math.max(cumulative.at(-1), .01);
  const py = value => top + (bottom - top) * (maximum - value) / (maximum - minimum);
  ctx.font = "11px system-ui";
  for (const level of [...new Set([minimum, config.weak_threshold_dbm, config.outage_threshold_dbm, maximum])]) {
    const y = py(level);
    ctx.beginPath();
    ctx.moveTo(left,y);
    ctx.lineTo(width - right,y);
    ctx.strokeStyle = level === config.weak_threshold_dbm ? "#af7146" : "#e0e8e1";
    ctx.setLineDash(level === config.weak_threshold_dbm ? [5, 4] : []);
    ctx.stroke();
    ctx.fillStyle = "#405c55";
    ctx.fillText(level + " dBm", 5, y + 3);
  }
  ctx.setLineDash([]);
  ctx.beginPath();
  profile.samples_dbm.forEach((value, i) => {
    if (i) ctx.lineTo(px(cumulative[i]),py(value));
    else ctx.moveTo(px(cumulative[i]),py(value));
  });
  ctx.lineWidth = 2.3;
  ctx.strokeStyle = "#176455";
  ctx.stroke();
  marker(ctx, px(cumulative.at(-1)), py(profile.samples_dbm.at(-1)), 3, "#ffd468");
  ctx.fillStyle = "#405c55";
  ctx.fillText("0 m", left, bottom + 17);
  const length = format(profile.length_m, "m");
  ctx.fillText(length, width - right - ctx.measureText(length).width, bottom + 17);
}

function apEntry(task) {
  return radio.floors[task.floor].candidates[chosen[task.floor]];
}

function referenceEntry(task) {
  return apEntry(task).reference_tasks?.[task.source_row];
}

function drawTaskList() {
  const parent = $("task-list"), scroll = parent.scrollTop, filter = $("floor-filter").value;
  parent.replaceChildren();
  const list = filter === "all" ? tasks : tasks.filter(task => task.floor === filter);
  $("task-summary").textContent = list.length + " 条 · 参考 STOP RSSI";
  for (const task of list) {
    const row = document.createElement("button");
    row.className = "task";
    row.type = "button";
    row.setAttribute("aria-pressed", String(task === selected));
    row.dataset.sourceRow = String(task.source_row);
    const text = document.createElement("span"), caption = document.createElement("small");
    text.textContent = "找" + (names[task.category] || task.category);
    caption.textContent = task.floor + " · 任务 " + selectedIndex.get(taskKey(task)) + " · 源行 " + task.source_row;
    text.append(caption);
    const profile = referenceEntry(task)?.profile ?? apEntry(task).tasks[task.source_row];
    const value = profile.samples_dbm.at(-1);
    const rssi = document.createElement("span");
    rssi.className = value < config.weak_threshold_dbm ? "rssi weak" : "rssi";
    rssi.textContent = format(value, "dBm");
    row.append(text, rssi);
    row.onclick = () => {
      selected = task;
      draw();
      parent.querySelector("[aria-pressed=true]")?.focus({preventScroll:true});
    };
    parent.append(row);
  }
  parent.scrollTop = scroll;
}

function draw() {
  const floor = floors[selected.floor], ap = apEntry(selected), originalProfile = ap.tasks[selected.source_row];
  const reference = referenceEntry(selected), profile = reference?.profile ?? originalProfile;
  $("map-title").textContent = selected.floor + " · Habitat 楼层地图";
  $("task-instruction").textContent = "任务指令：找" + (goalText[selected.category] ?? selected.category) + "。目标类别 " + selected.category;
  $("map-detail").textContent = "楼层 Y " + format(floor.y, "m", 2) + " · 覆盖边界 " +
    format(config.weak_threshold_dbm, "dBm", 0) + " · 本层采样覆盖 " +
    format(ap.coverage_above_weak * 100, "%", 0);
  $("ap-choice").replaceChildren();
  for (const candidate of floor.candidates) option($("ap-choice"), candidate.id, candidate.id);
  $("ap-choice").value = chosen[selected.floor];
  $("profile-title").textContent = "找" + (names[selected.category] || selected.category) +
    (reference ? " · RSSI 优先参考路线" : " · 参考路线 RSSI");
  $("profile-detail").textContent = "源 episode " + selected.source_episode_id + " · 源行 " + selected.source_row +
    " · 评测器视点 " + selected.stop_object_id + " · AP 底座 XYZ [" +
    coordinate(floor.candidates.find(item => item.id === chosen[selected.floor]).xyz) + "]";
  const metrics = $("metrics");
  metrics.replaceChildren();
  const weakRatio = profile.length_m > 0 ? " · " + format(100 * profile.weak_length_m / profile.length_m, "%", 0) : "";
  const values = [
    ["参考路线长度", format(profile.length_m, "m", 2)],
    ["参考 STOP RSSI", format(profile.samples_dbm.at(-1), "dBm")],
    ["低于 " + format(config.weak_threshold_dbm, "dBm", 0) + " 的路段", format(profile.weak_length_m, "m", 2) + weakRatio],
    ["同层采样视点处于弱区", originalProfile.stop_viewpoints_weak + " / " + originalProfile.stop_viewpoints_sampled],
    ["起点 RSSI", format(profile.samples_dbm[0], "dBm")],
    ["路线最低 RSSI", format(profile.minimum_dbm, "dBm")],
    ["低于 " + format(config.outage_threshold_dbm, "dBm", 0) + " 的路段", format(profile.outage_length_m, "m", 2)],
  ];
  for (const [label, value] of values) {
    const cell = document.createElement("div");
    const key = document.createElement("dt"), item = document.createElement("dd");
    key.textContent = label;
    item.textContent = value;
    cell.append(key, item);
    metrics.append(cell);
  }
  if (reference) {
    const verdict = reference.selected ? "已选用绕行。" : reference.candidate_count ?
      "这批绕行未达到稳定改善条件，沿用几何最短路。" : "本次搜索未找到预算内绕行，沿用几何最短路。";
    $("reference-comparison").hidden = false;
    $("reference-comparison").textContent = "已比较 " + reference.candidate_count + " 条绕行。" + verdict +
      " 几何最短路 " + format(reference.baseline_profile.length_m, "m", 2) + "，当前路线 " + format(profile.length_m, "m", 2) +
      "。弱信号距离 " + format(reference.baseline_profile.weak_length_m, "m", 2) + " → " + format(profile.weak_length_m, "m", 2) +
      "；低于 " + format(config.outage_threshold_dbm, "dBm", 0) + " 的距离 " + format(reference.baseline_profile.outage_length_m, "m", 2) +
      " → " + format(profile.outage_length_m, "m", 2) + "。";
  }
  drawTaskList();
  scheduleMap();
  drawProfile();
}

function setAP(id) {
  chosen[selected.floor] = id;
  const ap = apEntry(selected);
  $("map-hint").textContent = selected.floor + " 已用 " + id + " · 可通行采样点覆盖 " +
    format(ap.coverage_above_weak * 100, "%", 0) + " · 本层相关任务已自动更新。";
  draw();
}

$("map").addEventListener("click", event => {
  if (!projection) return;
  const rect = $("map").getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
  let nearest, distance = 16;
  for (const item of floors[selected.floor].candidates) {
    const [a,b] = projection(item.xyz[0], item.xyz[2]), d = Math.hypot(x-a,y-b);
    if (d < distance) {
      nearest = item;
      distance = d;
    }
  }
  if (nearest) setAP(nearest.id);
  else $("map-hint").textContent = "请选择地图上的空心候选点，或从上方下拉菜单选择 AP。";
});

$("ap-choice").onchange = () => setAP($("ap-choice").value);
$("reset").onclick = () => setAP(floors[selected.floor].candidates[0].id);
for (const id of ["heat","edge","path","texture","baseline"]) $(id).onchange = scheduleMap;
option($("floor-filter"), "all", "全部楼层");
const sceneOrder = new Map((geometry.scenes ?? []).map((scene, index) => [scene.scene, index + 1]));
for (const key of Object.keys(floors)) {
  const [scene, layer] = key.split("/");
  const label = sceneOrder.has(scene) ? "场景 " + sceneOrder.get(scene) + " · " + layer : key;
  option($("floor-filter"), key, label);
}
$("floor-filter").onchange = () => {
  const layer = $("floor-filter").value;
  if (layer !== "all" && layer !== selected.floor) selected = tasks.find(task => task.floor === layer);
  draw();
};

$("export").onclick = () => {
  const layouts = Object.entries(chosen).map(([floor, ap]) => ({
    floor: floors[floor].floor_id ?? floor, scene: floors[floor].source_ref ?? geometry.source_ref,
    candidate_id: ap, ap_floor_xyz: floors[floor].candidates.find(item => item.id === ap).xyz
  }));
  const draft = {format:geometry.scene_count > 1 ? "wifinav-objectnav-ap-draft-v2" : "wifinav-objectnav-ap-draft-v1", report_sha256:reportHash,
                 scene:geometry.source_ref, ap_height_above_floor_m:config.ap_height_above_floor_m, layouts};
  const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], {type:"application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "wifinav-objectnav-ap-draft.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("map-hint").textContent = "AP 草稿已导出。";
};

const scope = geometry.split === "train" ? (geometry.scene_count ?? 1) + " 个官方 train 开发场景" : "1 个公开场景";
if (geometry.split === "train") $("scope").textContent = "HM3D ObjectNav v2 官方 train · 开发审阅。中文指令由目标类别生成。地图上的参考路线、目标视点和 RSSI 场供离线验收。";
$("overview").textContent = tasks.length + " 条任务 · " + scope + " · " + Object.keys(floors).length +
  " 个独立单层布局 · 每层在用 1 个 AP";
const audit = geometry.scope_audit.reduce((counts, row) => {
  counts[row.status] = (counts[row.status] || 0) + 1;
  return counts;
}, {});
const sourceScope = geometry.scene_count > 1 ? "官方 train 场景分片" : "场景 " + geometry.source_ref.split("/").at(-2);
$("audit").textContent = sourceScope + "。几何抽审 " + geometry.scope_audit.length +
  " 行，选入 " + (audit.selected || 0) + " 行。合格未选 " + (audit.eligible || 0) +
  " 行，尚无同层见证或起点不满足规则 " +
  ((audit.no_verified_same_floor_viewpoint || 0) + (audit.start_outside_floor || 0)) + " 行。";
$("config").textContent = "多墙传播 · AP 高 " + format(config.ap_height_above_floor_m, "m", 2) +
  " · 接收高 " + format(config.rx_height_above_floor_m, "m", 2) + " · 1 米参考 " +
  format(config.reference_rss_1m_dbm, "dBm", 0) + " · 低信号阈值 " +
  format(config.weak_threshold_dbm, "dBm", 0) + " · 现场实测待校准。";
$("hashes").textContent = "代码 " + data.radio_commit.slice(0, 7) + " · 报告 SHA256 " + reportHash;
if (referencePolicy) {
  $("path-label").textContent = "RSSI 优先路线（蓝线）";
  $("baseline-layer").hidden = false;
  $("reference-policy").hidden = false;
  $("reference-policy").textContent = "RSSI 优先路线固定起点、停止视点和楼层。长度最多增加 " +
    format(100 * (referencePolicy.max_length_ratio - 1), "%", 0) + "。先比较低于 " + format(config.weak_threshold_dbm, "dBm", 0) +
    " 的距离，再比较低于 " + format(config.outage_threshold_dbm, "dBm", 0) + " 的距离及总长度。两种采样步长均须确认改善。";
}
const partialMeshes = (geometry.scenes ?? []).filter(s => s.mesh_faces.faces_with_unannotated_black > 0);
if (partialMeshes.length) {
  $("mesh-audit").hidden = false;
  $("mesh-audit").textContent = partialMeshes.map(s => s.scene + " 含未标注几何面 " +
    format(100 * s.mesh_faces.faces_with_unannotated_black / s.mesh_faces.faces, "%")).join("；") +
    "。无标签的表面无法确定材质或遮挡类型，其 RSSI 结果需谨慎解读。";
}
if (data.route_diagnostic) {
  $("route-audit").hidden = false;
  const {tasks: audited, tested, passed} = data.route_diagnostic;
  let evidence = audited + " 条任务筛查，共比较 " + tested + " 条预算内绕行，" + passed + " 条在两种采样步长下均减少 ≥0.50 m 弱信号路段。";
  if (routeExample) {
    const [a] = routeExample.baseline, [b] = routeExample.alternate;
    evidence += " 示例 " + routeExample.task_key + "，固定 " + routeExample.ap + "。最短路 " + format(a.length_m, "m", 2) +
      "、弱信号 " + format(a.weak_motion_s, "s", 1) + "。紫色虚线绕行 " + format(b.length_m, "m", 2) +
      "、弱信号 " + format(b.weak_motion_s, "s", 1) + "。时间按 0.25 m/s 的匀速移动换算。这是离线选路诊断。";
    $("route-show").hidden = false;
    $("route-show").onclick = () => {
      selected = tasks.find(task => taskKey(task) === routeExample.task_key);
      $("floor-filter").value = selected.floor;
      $("path").checked = true;
      setAP(routeExample.ap);
      $("map").scrollIntoView({block:"center"});
    };
  }
  $("route-evidence").textContent = evidence;
}
if (!Object.values(radio.floors).some(f => f.cutaway)) $("texture").parentElement.hidden = true;
new ResizeObserver(() => {
  scheduleMap();
  drawProfile();
}).observe($("map"));
draw();
