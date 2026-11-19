"use strict";
const $ = id => document.getElementById(id);
const D = JSON.parse($("payload").textContent);
const tasks = D.tasks;
const audit = new Map(D.scope.map(row => [String(row.episode_id), row]));
const hashes = D.metadata.source_sha256;
const spec = D.metadata.specification;
const storageKey = "wifinav_ap_review_" + D.metadata.execution_commit + "_" + hashes["configs/benchmark/single_floor_ap_review_v1.json"];
const number = new Intl.NumberFormat("zh-CN");
const sceneName = task => task.scene_id.split("/").at(-2);
const escape = value => String(value ?? "—").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const xyz = position => position.map(value => value.toFixed(3)).join(", ");
const pointFor = (task, node) => node === task.default_ap_node ? task.default_ap_position : task.nodes[node];
const emptyView = () => ({zoom: 1, x: 0, y: 0});
const history = new Map();
let taskIndex = 0, view = emptyView(), showSignal = true, saved = {};
let storageAvailable = true, drag = null, projection, previewCache;
const map = $("map"), chart = $("chart");
const ctx = map.getContext("2d"), plot = chart.getContext("2d");
const current = () => tasks[taskIndex];
const selectedNode = task => saved[task.episode_id] ?? task.default_ap_node;
const changed = task => selectedNode(task) !== task.default_ap_node;
function setDraft(message = "") {
  $("draftStatus").textContent = [
    Object.keys(saved).length + " 个布点已修改",
    storageAvailable ? "浏览器本地草稿" : "请导出保存本页草稿",
    message
  ].filter(Boolean).join(" · ");
}
try {
  const stored = JSON.parse(localStorage.getItem(storageKey) || "{}");
  for (const task of tasks) {
    const node = stored?.[task.episode_id]?.node;
    if (task.ap_candidate_nodes.includes(node) && node !== task.default_ap_node) saved[task.episode_id] = node;
  }
} catch {
  storageAvailable = false;
}
function persist(message) {
  try {
    const compatible = {};
    for (const task of tasks) {
      if (changed(task)) compatible[task.episode_id] = {node: selectedNode(task), position: pointFor(task, selectedNode(task)), changed: true};
    }
    localStorage.setItem(storageKey, JSON.stringify(compatible));
    storageAvailable = true;
  } catch {
    storageAvailable = false;
  }
  setDraft(message);
}
function applyNode(node, remember = true) {
  const task = current(), previous = selectedNode(task);
  if (!task.ap_candidate_nodes.includes(node) || node === previous) return;
  if (remember) {
    const stack = history.get(task.episode_id) || [];
    stack.push(previous);
    history.set(task.episode_id, stack);
  }
  if (node === task.default_ap_node) delete saved[task.episode_id];
  else saved[task.episode_id] = node;
  persist();
  render();
}
function chooseTask(index, scroll = false) {
  taskIndex = index;
  view = emptyView();
  $("hover").hidden = true;
  render();
  if (scroll) $("workspace").scrollIntoView({block: "start"});
}
const sceneGroups = new Map();
for (const task of tasks) {
  const scene = sceneName(task);
  if (!sceneGroups.has(scene)) sceneGroups.set(scene, []);
  sceneGroups.get(scene).push(task);
}
const taskButtons = new Map();
for (const [scene, group] of sceneGroups) {
  const details = document.createElement("details");
  details.className = "scene-group";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = scene;
  details.append(summary);
  const options = document.createElement("optgroup");
  options.label = scene;
  for (const task of group) {
    const button = document.createElement("button");
    const index = tasks.indexOf(task);
    button.onclick = () => chooseTask(index);
    details.append(button);
    taskButtons.set(task, button);
    options.append(new Option("任务 " + task.episode_id, String(index)));
  }
  $("taskNav").append(details);
  $("mobileTask").append(options);
}
$("mobileTask").onchange = event => chooseTask(Number(event.target.value));

function distances(task, start) {
  const neighbors = task.nodes.map(() => []);
  for (const [a, b, weight] of task.edges) {
    neighbors[a].push([b, weight]);
    neighbors[b].push([a, weight]);
  }
  const dist = new Float64Array(task.nodes.length).fill(Infinity);
  dist[start] = 0;
  const queue = [];
  function push(item) {
    let i = queue.length;
    queue.push(item);
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (queue[parent][0] <= item[0]) break;
      queue[i] = queue[parent];
      i = parent;
    }
    queue[i] = item;
  }
  function pop() {
    const result = queue[0], last = queue.pop();
    if (queue.length === 0) return result;
    let i = 0;
    while (2 * i + 1 < queue.length) {
      let child = 2 * i + 1;
      if (child + 1 < queue.length && queue[child + 1][0] < queue[child][0]) child++;
      if (last[0] <= queue[child][0]) break;
      queue[i] = queue[child];
      i = child;
    }
    queue[i] = last;
    return result;
  }
  push([0, start]);
  while (queue.length) {
    const [cost, node] = pop();
    if (cost !== dist[node]) continue;
    for (const [next, weight] of neighbors[node]) {
      const newCost = cost + weight;
      if (newCost < dist[next]) {
        dist[next] = newCost;
        push([newCost, next]);
      }
    }
  }
  return dist;
}

function preview(task) {
  const node = selectedNode(task);
  if (previewCache?.task === task && previewCache.node === node) return previewCache;
  const ap = pointFor(task, node);
  const c = task.wireless_config;
  const dist = distances(task, node);
  const signal = task.nodes.map(([x, , z], index) => {
    if (!Number.isFinite(dist[index])) return null;
    const horizontal = Math.max(1, Math.hypot(x - ap[0], z - ap[2]));
    const excess = Math.max(0, dist[index] - horizontal);
    const loss = Math.min(c.max_obstruction_penalty_db, excess * c.obstruction_db_per_excess_meter);
    return c.reference_rssi_dbm_at_1m - 10 * c.path_loss_exponent * Math.log10(horizontal) - loss + task.shadow_db[index];
  });
  previewCache = {task, node, signal, route: task.route_nodes.map(i => signal[i])};
  return previewCache;
}

function canvasSize(canvas, context) {
  const {width, height} = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const pixelWidth = Math.max(1, Math.round(width * ratio));
  const pixelHeight = Math.max(1, Math.round(height * ratio));
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  return {width, height};
}
const colors = {good: "#98ccbe", weak: "#efd28c", outage: "#bc8bc1", missing: "#bdc8d0", floor: "#d4e0e4"};
function coverageColor(rssi, config) {
  if (rssi === null) return colors.missing;
  if (rssi < config.outage_threshold_dbm) return colors.outage;
  if (rssi < config.weak_threshold_dbm) return colors.weak;
  return colors.good;
}
function drawMap() {
  const task = current();
  const {width, height} = canvasSize(map, ctx);
  if (width <= 0 || height <= 0) return;
  const anchors = [...task.route_nodes, ...task.ap_candidate_nodes].map(i => task.nodes[i]);
  const xs = anchors.map(p => p[0]), zs = anchors.map(p => p[2]);
  const left = Math.min(...xs), right = Math.max(...xs);
  const top = Math.min(...zs), bottom = Math.max(...zs);
  const scale = Math.min(width / (right - left + 3), height / (bottom - top + 3)) * view.zoom;
  projection = ([x, , z]) => [
    width / 2 + view.x + (x - (left + right) / 2) * scale,
    height / 2 + view.y + (z - (top + bottom) / 2) * scale
  ];
  const {signal} = preview(task);
  const cell = spec.map_grid_resolution_m * scale;
  for (let i = 0; i < task.base_grid_nodes; i++) {
    const [x, y] = projection(task.nodes[i]);
    if (x < -cell || y < -cell || x > width + cell || y > height + cell) continue;
    ctx.fillStyle = showSignal ? coverageColor(signal[i], task.wireless_config) : colors.floor;
    ctx.fillRect(x - cell / 2, y - cell / 2, cell + .35, cell + .35);
  }
  function circle(x, y, radius, fill, stroke, strokeWidth) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.strokeStyle = stroke;
    ctx.lineWidth = strokeWidth;
    ctx.stroke();
  }
  for (const i of task.ap_candidate_nodes) {
    const [x, y] = projection(task.nodes[i]);
    circle(x, y, Math.min(3.5, Math.max(1.6, cell * .22)), "#f8fffc", "#17685f", 1);
  }
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();
  for (const [i, node] of task.route_nodes.entries()) {
    const p = projection(task.nodes[node]);
    if (i === 0) ctx.moveTo(...p);
    else ctx.lineTo(...p);
  }
  ctx.lineWidth = 7;
  ctx.strokeStyle = "#ffffff";
  ctx.stroke();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#0f4b84";
  ctx.stroke();
  function marker(position, label, fill, outline, side) {
    const [x, y] = projection(position);
    circle(x, y, 6, fill, outline, 2.5);
    ctx.font = "600 12px sans-serif";
    const labelWidth = ctx.measureText(label).width;
    const tx = Math.min(width - labelWidth - 7, Math.max(6, x + (side === "left" ? -labelWidth - 11 : 10)));
    const ty = Math.min(height - 6, Math.max(14, y - 8));
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 4;
    ctx.strokeText(label, tx, ty);
    ctx.fillStyle = "#103145";
    ctx.fillText(label, tx, ty);
  }
  marker(task.start_position, "起点", "#0c4659", "#fff", "left");
  marker(task.goal_position, "目标", "#0c4659", "#fff", "right");
  if (changed(task)) marker(task.default_ap_position, "初始 AP", "#fff", "#74429c", "left");
  marker(pointFor(task, selectedNode(task)), "当前 AP", "#ab4817", "#fff", "right");
  const bar = [5, 2, 1, .5, .2].find(m => m * scale <= 110) || .2;
  ctx.fillStyle = "#fff";
  ctx.fillRect(8, height - 37, bar * scale + 20, 29);
  ctx.fillStyle = "#213c4c";
  ctx.fillRect(15, height - 17, bar * scale, 2);
  ctx.font = "11px sans-serif";
  ctx.fillText(bar + " m", 15, height - 22);
}
function routeSummary(values, lengths, config) {
  if (values.some(value => value === null)) return null;
  let weak = 0, outage = 0;
  for (const [i, length] of lengths.entries()) {
    const midpoint = (values[i] + values[i + 1]) / 2;
    if (midpoint < config.weak_threshold_dbm) weak += length;
    if (midpoint < config.outage_threshold_dbm) outage += length;
  }
  return {minimum_dbm: Math.min(...values), weak_length_m: weak, outage_length_m: outage};
}
function drawChart() {
  const task = current(), config = task.wireless_config;
  const edited = changed(task), showNoise = $("showNoise").checked;
  const baseline = task.route_native_rssi_dbm, noise = task.route_measured_rssi_dbm;
  const trial = edited ? preview(task).route : [];
  const distance = [0];
  for (const length of task.route_lengths_m) distance.push(distance.at(-1) + length);
  const {width, height} = canvasSize(chart, plot);
  const left = 46, right = width - 20, top = 24, bottom = height - 28;
  const values = [config.weak_threshold_dbm, config.outage_threshold_dbm, ...baseline, ...trial.filter(n => n !== null), ...(showNoise ? noise : [])];
  const high = Math.ceil((Math.max(...values) + 1) / 10) * 10;
  const low = Math.floor((Math.min(...values) - 1) / 10) * 10;
  const x = n => left + n / distance.at(-1) * (right - left);
  const y = n => top + (high - n) / (high - low) * (bottom - top);
  plot.fillStyle = "#faf0db";
  plot.fillRect(left, y(config.weak_threshold_dbm), right - left, y(config.outage_threshold_dbm) - y(config.weak_threshold_dbm));
  plot.fillStyle = "#f3e7f4";
  plot.fillRect(left, y(config.outage_threshold_dbm), right - left, bottom - y(config.outage_threshold_dbm));
  plot.font = "11px sans-serif";
  for (let value = low; value <= high; value += 10) {
    plot.strokeStyle = "#dce5e9";
    plot.beginPath();
    plot.moveTo(left, y(value));
    plot.lineTo(right, y(value));
    plot.stroke();
    plot.textAlign = "right";
    plot.fillStyle = "#405968";
    plot.fillText(value, left - 6, y(value) + 4);
  }
  for (let i = 0; i <= 4; i++) {
    const d = distance.at(-1) * i / 4;
    plot.textAlign = i === 0 ? "left" : i === 4 ? "right" : "center";
    plot.fillText(d.toFixed(1) + " m", x(d), height - 8);
  }
  plot.textAlign = "left";
  plot.fillText("dBm", 8, 12);
  function series(samples, color, dash = []) {
    plot.beginPath();
    let pen = false;
    samples.forEach((value, i) => {
      if (value === null) {
        pen = false;
        return;
      }
      if (pen) plot.lineTo(x(distance[i]), y(value));
      else plot.moveTo(x(distance[i]), y(value));
      pen = true;
    });
    plot.lineWidth = 2;
    plot.setLineDash(dash);
    plot.strokeStyle = color;
    plot.stroke();
    plot.setLineDash([]);
  }
  if (showNoise) series(noise, "#74429c", [3, 3]);
  series(baseline, "#165d85");
  if (edited) series(trial, "#ab4817", [6, 3]);
  $("noiseKey").hidden = !showNoise;
  $("previewKey").hidden = !edited;
  function summarize(label, metrics) {
    if (!metrics || metrics.available === false) return "<p>" + label + " · 路线数据缺失</p>";
    return "<p><strong>" + label + "</strong> · 最低 " + metrics.minimum_dbm.toFixed(1) +
      " dBm · 弱信号 " + metrics.weak_length_m.toFixed(2) + " m · 断连 " + metrics.outage_length_m.toFixed(2) + " m</p>";
  }
  $("routeMetrics").innerHTML = summarize("初始 AP · 原生代理", task.initial_route_metrics) +
    (edited ? summarize("草稿 AP · 网格估计", routeSummary(trial, task.route_lengths_m, config)) : "");
}

function facts(rows) {
  return rows.map(([key, value]) => "<dt>" + escape(key) + "</dt><dd>" + escape(value) + "</dd>").join("");
}
function render() {
  const task = current(), row = audit.get(String(task.episode_id)), node = selectedNode(task);
  const edited = changed(task), metrics = task.initial_route_metrics;
  $("mobileTask").value = String(taskIndex);
  for (const [entry, button] of taskButtons) {
    button.setAttribute("aria-current", String(entry === task));
    button.innerHTML = "任务 " + escape(entry.episode_id) + (changed(entry) ? "<small>已改</small>" : "");
  }
  $("sceneLabel").textContent = sceneName(task) + " · 路径组 " + task.trajectory_id;
  $("taskTitle").textContent = "任务 " + task.episode_id;
  $("instruction").textContent = task.instruction;
  $("editBadge").textContent = edited ? "草稿 · 待原生复核" : "初始布局";
  $("editBadge").classList.toggle("edited", edited);
  $("apFacts").innerHTML = [
    ["当前", pointFor(task, node), node],
    ["初始", task.default_ap_position, task.default_ap_node]
  ].map(([label, position, index]) => '<div class="ap-box"><strong>' + label + ' AP · 节点 ' + index +
    '</strong><code>X, Y, Z<br>' + xyz(position) + '</code></div>').join("");
  $("taskFacts").innerHTML = facts([
    ["源数据集", "R2R-CE train"],
    ["参考路线", metrics.length_m.toFixed(2) + " m · " + task.route_nodes.length + " 个采样点"],
    ["源高度跨度", row.height_range_m.toFixed(3) + " m"],
    ["原生路线", row.native_geometry_check === "passed" ? "可达，符合楼层容差" : row.native_geometry_check],
    ["起点 XYZ", xyz(task.start_position)],
    ["目标 XYZ", xyz(task.goal_position)],
    ["网格与原生路线差异", "初始 AP 平均 " + task.preview_vs_native.mean_absolute_db.toFixed(2) + " dB，最大 " +
      task.preview_vs_native.maximum_absolute_db.toFixed(2) + " dB"],
    ["Navmesh SHA256", task.navmesh_sha256]
  ]);
  if ($("candidateSelect").dataset.task !== task.episode_id) {
    $("candidateSelect").dataset.task = task.episode_id;
    $("candidateSelect").replaceChildren(...task.ap_candidate_nodes.map(index =>
      new Option("节点 " + index + " · " + xyz(pointFor(task, index)), String(index))
    ));
  }
  $("candidateSelect").value = String(node);
  $("undo").disabled = !history.get(task.episode_id)?.length;
  $("resetOne").disabled = !edited;
  const {weak_threshold_dbm: weak, outage_threshold_dbm: outage} = task.wireless_config;
  $("coverageLegend").innerHTML = [
    [colors.good, "正常 ≥ " + weak],
    [colors.weak, "偏弱 " + outage + " 至 < " + weak],
    [colors.outage, "断连 < " + outage],
    [colors.missing, "网格不可达"]
  ].map(([fill, label]) => '<span><i class="swatch" style="background:' + fill + '"></i>' + label + '</span>').join("") + "<span>单位 dBm</span>";
  $("coverageLegend").hidden = !showSignal;
  drawMap();
  drawChart();
  if ($("layouts").open) renderLayouts();
}
function setLayer(signal) {
  showSignal = signal;
  $("signalLayer").setAttribute("aria-pressed", String(signal));
  $("floorLayer").setAttribute("aria-pressed", String(!signal));
  $("coverageLegend").hidden = !signal;
  drawMap();
}
$("signalLayer").onclick = () => setLayer(true);
$("floorLayer").onclick = () => setLayer(false);
$("fit").onclick = () => { view = emptyView(); drawMap(); };
function zoom(factor) {
  view.zoom = Math.max(.45, Math.min(7, view.zoom * factor));
  drawMap();
}
$("zoomIn").onclick = () => zoom(1.3);
$("zoomOut").onclick = () => zoom(1 / 1.3);
$("candidateSelect").onchange = event => applyNode(Number(event.target.value));
$("resetOne").onclick = () => applyNode(current().default_ap_node);
$("undo").onclick = () => {
  const stack = history.get(current().episode_id);
  if (stack?.length) applyNode(stack.pop(), false);
};
$("showNoise").onchange = drawChart;
function closestCandidate(x, y) {
  let best = null, bestDistance = 12 ** 2;
  for (const node of current().ap_candidate_nodes) {
    const [nx, ny] = projection(current().nodes[node]);
    const squared = (nx - x) ** 2 + (ny - y) ** 2;
    if (squared < bestDistance) {
      bestDistance = squared;
      best = node;
    }
  }
  return best;
}
const localPoint = event => {
  const box = map.getBoundingClientRect();
  return [event.clientX - box.left, event.clientY - box.top];
};
map.onpointerdown = event => {
  if (event.button !== 0 || drag) return;
  drag = {pointer: event.pointerId, startX: event.clientX, startY: event.clientY, x: view.x, y: view.y, moved: false};
  $("hover").hidden = true;
  map.setPointerCapture(event.pointerId);
};
map.onpointermove = event => {
  if (drag) {
    if (event.pointerId !== drag.pointer) return;
    const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
    drag.moved ||= Math.hypot(dx, dy) > 4;
    if (drag.moved) {
      map.classList.add("dragging");
      view.x = drag.x + dx;
      view.y = drag.y + dy;
      drawMap();
    }
    return;
  }
  const [x, y] = localPoint(event), node = closestCandidate(x, y), tip = $("hover");
  tip.hidden = node === null;
  if (node !== null) {
    tip.textContent = "候选 " + node + " · 点击设为 AP";
    tip.style.left = Math.max(4, Math.min(map.clientWidth - tip.offsetWidth - 4, x + 10)) + "px";
    tip.style.top = Math.max(4, y - 35) + "px";
  }
};
function finishPointer(event, click) {
  if (!drag || drag.pointer !== event.pointerId) return;
  const moved = drag.moved;
  drag = null;
  map.classList.remove("dragging");
  if (click && !moved) {
    const node = closestCandidate(...localPoint(event));
    if (node !== null) applyNode(node);
  }
}
map.onpointerup = event => finishPointer(event, true);
map.onpointercancel = event => finishPointer(event, false);
map.onlostpointercapture = event => finishPointer(event, false);
map.onpointerleave = () => { $("hover").hidden = true; };

function renderLayouts() {
  $("layoutTable").innerHTML = "<table><thead><tr><th>任务</th><th>场景</th><th>初始 AP XYZ（m）</th><th>当前 AP XYZ（m）</th><th>状态</th></tr></thead><tbody>" +
    tasks.map((task, i) => "<tr><td><button data-task='" + i + "'>" + escape(task.episode_id) +
      "</button></td><td>" + escape(sceneName(task)) + "</td><td><code>" + xyz(task.default_ap_position) +
      "</code></td><td><code>" + xyz(pointFor(task, selectedNode(task))) + "</code></td><td>" +
      (changed(task) ? "草稿 · 待复核" : "初始") + "</td></tr>").join("") + "</tbody></table>";
}
$("layouts").ontoggle = () => { if ($("layouts").open) renderLayouts(); };
$("layoutTable").onclick = event => {
  const button = event.target.closest("button[data-task]");
  if (button) chooseTask(Number(button.dataset.task), true);
};

const reasonLabels = {
  explicit_vertical_instruction: "明确垂直移动指令",
  ambiguous_vertical_language_requires_review: "楼梯或楼层相关用语待确认",
  height_variation_requires_single_floor_review: "高度超出单层容差",
  invalid_source_positions: "源坐标无效",
  missing_dense_gt: "缺少密集轨迹"
};
const statusLabels = {excluded: "排除", candidate: "候选", review: "待复核", selected: "已入选"};
let pageIndex = 0;
function renderAudit() {
  if (!$("audit").open) return;
  const status = $("scopeFilter").value, query = $("scopeQuery").value.trim().toLowerCase();
  const rows = D.scope.filter(row => {
    const matchesStatus = !status || (status === "selected" ? row.selection_status === status : row.scope_status === status);
    if (!matchesStatus || !query) return matchesStatus;
    return row.episode_id === query || [row.scene_id, row.instruction, row.vertical_phrase, ...row.reasons]
      .some(value => value?.toLowerCase().includes(query));
  });
  const perPage = 30;
  const pages = Math.max(1, Math.ceil(rows.length / perPage));
  pageIndex = Math.min(pageIndex, pages - 1);
  $("scopeCount").textContent = number.format(rows.length) + " 条 · 第 " + (pageIndex + 1) + " / " + pages + " 页";
  $("previousPage").disabled = pageIndex === 0;
  $("nextPage").disabled = pageIndex >= pages - 1;
  $("scopeTable").innerHTML = "<table><thead><tr><th>任务 / 场景</th><th>筛选</th><th>原指令与证据</th><th>高度跨度</th><th>原生路线检查</th></tr></thead><tbody>" +
    rows.slice(pageIndex * perPage, (pageIndex + 1) * perPage).map(row => {
      const status = row.selection_status === "selected" ? "selected" : row.scope_status;
      const reasons = row.reasons.map(reason => reasonLabels[reason] || reason).concat(row.vertical_phrase || []);
      const check = {not_run: "未检查", passed: "通过"}[row.native_geometry_check] || row.native_geometry_check;
      return "<tr><td>" + escape(row.episode_id) + "<br><code>" + escape(sceneName(row)) +
        "</code></td><td>" + escape(statusLabels[status]) + "</td><td>" + escape(row.instruction) +
        (reasons.length ? "<br><span class='muted'>" + escape(reasons.join(" · ")) + "</span>" : "") +
        "</td><td>" + (row.height_range_m == null ? "—" : row.height_range_m.toFixed(3) + " m") +
        "</td><td>" + escape(check) + "</td></tr>";
    }).join("") + "</tbody></table>";
}
$("audit").ontoggle = renderAudit;
$("scopeQuery").oninput = $("scopeFilter").onchange = () => { pageIndex = 0; renderAudit(); };
$("previousPage").onclick = () => { pageIndex--; renderAudit(); };
$("nextPage").onclick = () => { pageIndex++; renderAudit(); };
document.querySelector('a[href="#audit"]').onclick = () => { $("audit").open = true; };

const sourceFiles = Object.keys(hashes).filter(key => key.endsWith(".json.gz") || key.includes("configs/benchmark/single_floor_ap_review"));
$("export").onclick = () => {
  const payload = {
    format: "wifinav-ap-review-edits-v1",
    created_at: new Date().toISOString(),
    execution_commit: D.metadata.execution_commit,
    source_sha256: hashes,
    specification: spec,
    changes: tasks.map(task => ({
      episode_id: task.episode_id, trajectory_id: task.trajectory_id, scene_id: task.scene_id,
      navmesh_sha256: task.navmesh_sha256,
      initial_ap_node: task.default_ap_node, initial_ap_position: task.default_ap_position,
      selected_ap_node: selectedNode(task), selected_ap_position: pointFor(task, selectedNode(task)),
      changed: changed(task), native_revalidation_required: changed(task)
    }))
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "wifinav-ap-review-edits.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$("importBtn").onclick = () => $("importFile").click();
function importEdits(data) {
  if (data.format !== "wifinav-ap-review-edits-v1" ||
      !sourceFiles.every(key => hashes[key] === data.source_sha256?.[key]) ||
      !Array.isArray(data.changes) || data.changes.length !== tasks.length) {
    throw Error("来源、配置或任务数不匹配");
  }
  const samePosition = (a, b) => Array.isArray(a) && a.length === 3 &&
    a.every((v, i) => Number.isFinite(v) && Math.abs(v - b[i]) <= 1e-5);
  const imported = {}, seen = new Set();
  for (const edit of data.changes) {
    const task = tasks.find(x => x.episode_id === String(edit.episode_id));
    if (!task || seen.has(task) || task.scene_id !== edit.scene_id ||
        task.trajectory_id !== String(edit.trajectory_id) ||
        (edit.navmesh_sha256 && edit.navmesh_sha256 !== task.navmesh_sha256) ||
        task.default_ap_node !== edit.initial_ap_node ||
        !samePosition(edit.initial_ap_position, task.default_ap_position) ||
        !task.ap_candidate_nodes.includes(edit.selected_ap_node) ||
        !samePosition(edit.selected_ap_position, pointFor(task, edit.selected_ap_node))) {
      throw Error("任务 " + edit.episode_id + " 的布局或候选坐标不匹配");
    }
    seen.add(task);
    if (edit.selected_ap_node !== task.default_ap_node) imported[task.episode_id] = edit.selected_ap_node;
  }
  // Keep the current draft intact until every imported row has passed validation.
  saved = imported;
  history.clear();
  persist("已导入");
  render();
}
$("importFile").onchange = async event => {
  try {
    const file = event.target.files[0];
    if (file) importEdits(JSON.parse(await file.text()));
  } catch (error) {
    setDraft("导入失败 · " + error.message);
  } finally {
    event.target.value = "";
  }
};
const stats = D.metadata.statistics, radio = tasks[0].wireless_config;
$("taskCount").textContent = number.format(tasks.length);
$("sceneCount").textContent = number.format(sceneGroups.size);
$("excludedCount").textContent = number.format(stats.scope_counts.excluded || 0);
$("reviewCount").textContent = number.format(stats.scope_counts.review || 0);
$("sourceFacts").innerHTML = facts([
  ["构建提交", D.metadata.execution_commit],
  ["构建时间（UTC）", D.metadata.created_at_utc],
  ["源任务总数", number.format(stats.source_episodes)],
  ["默认放置规则", "路线 " + spec.ap_route_progress_fraction * 100 + "% 处，侧向目标 " +
    spec.ap_preferred_lateral_offset_m + " m，吸附到距路线 " + spec.ap_route_corridor_m + " m 内的可达候选"],
  ["可走网格", spec.map_grid_resolution_m + " m"],
  ["无线代理", radio.reference_rssi_dbm_at_1m + " dBm @ 1 m，损耗指数 " + radio.path_loss_exponent +
    "，绕行惩罚 " + radio.obstruction_db_per_excess_meter + " dB/m（上限 " + radio.max_obstruction_penalty_db + " dB）"],
  ["阴影 / 噪声", "阴影 σ " + radio.spatial_shadow_sigma_db + " dB / " + radio.spatial_shadow_cell_m +
    " m；观测噪声 σ " + radio.observation_noise_sigma_db + " dB；种子 " + radio.seed],
  ...sourceFiles.map(key => [key.split("/").at(-1) + " SHA256", hashes[key]])
]);
const resizeObserver = new ResizeObserver(() => { drawMap(); drawChart(); });
resizeObserver.observe($("mapStage"));
resizeObserver.observe(chart.parentElement);
setDraft();
render();
