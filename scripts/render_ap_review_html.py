#!/usr/bin/env python3
"""Render a self-contained, offline AP placement review page from CPU audit data."""
import argparse
import gzip
import json
from pathlib import Path


def compact_payload(audit, data):
    by_id = {str(row["episode_id"]): row for row in audit["episodes"]}
    tasks = []
    for task in data["tasks"]:
        nodes = task["nodes"]
        candidates = [
            {"node": int(index), "x": nodes[index][0], "z": nodes[index][2], "y": nodes[index][1]}
            for index in task["ap_candidate_nodes"]
        ]
        route = [nodes[index] for index in task["route_nodes"]]
        rssi = task["route_native_rssi_dbm"]
        tasks.append({
            "episode_id": str(task["episode_id"]),
            "trajectory_id": str(task["trajectory_id"]),
            "scene_id": task["scene_id"],
            "instruction": task["instruction"],
            "instruction_sha256": task["instruction_sha256"],
            "start": task["start_position"],
            "goal": task["goal_position"],
            "floor_y": task["floor_y"],
            "route": route,
            "route_rssi_dbm_initial": rssi,
            "route_metrics_initial": task["initial_route_metrics"],
            "ap_candidates": candidates,
            "initial_ap_node": int(task["default_ap_node"]),
            "initial_ap": task["default_ap_position"],
            "navmesh_sha256": task["navmesh_sha256"],
            "wireless_config": task["wireless_config"],
            "grid_preview_error": task["preview_vs_native"],
            "scope_audit": by_id[str(task["episode_id"])],
        })
    return {
        "metadata": data["metadata"],
        "tasks": tasks,
        "scope_summary": audit["metadata"]["statistics"],
        "scope_rows": audit["episodes"],
    }


def load_json(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>R2R-Conn 单层任务与 AP 布局校正</title>
<style>
:root{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#17212b;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.top{background:#152b3c;color:white;padding:20px 26px}.top h1{margin:0 0 5px;font-size:23px}.top p{margin:4px 0;color:#d5e0e8}.wrap{max-width:1500px;margin:auto;padding:18px;display:grid;grid-template-columns:335px minmax(500px,1fr);gap:16px}.card{background:white;border:1px solid #dbe2e8;border-radius:10px;padding:15px;box-shadow:0 2px 7px #1c31430b}.side{display:flex;flex-direction:column;gap:12px}.main{display:flex;flex-direction:column;gap:12px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}select,button{font:inherit;padding:8px 10px;border:1px solid #c9d3dc;border-radius:6px;background:#fff;color:#17212b}button{cursor:pointer}button:hover{background:#eaf2f7}button.primary{background:#176b87;color:white;border-color:#176b87}button:disabled{opacity:.5;cursor:not-allowed}h2{font-size:17px;margin:0 0 10px}h3{font-size:15px;margin:12px 0 5px}.muted{color:#566674;font-size:13px}.warn{padding:10px;background:#fff7df;border-left:4px solid #dda82c;border-radius:4px;font-size:13px}.good{padding:10px;background:#eef8f3;border-left:4px solid #42a476;border-radius:4px;font-size:13px}.kv{display:grid;grid-template-columns:115px 1fr;gap:5px;font-size:13px}.kv b{font-weight:600}.mono{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px;overflow-wrap:anywhere}.list{max-height:260px;overflow:auto}.list button{display:block;text-align:left;width:100%;margin:3px 0;font-size:12px}.list button.selected{border-color:#176b87;background:#e8f4f7}.canvasbox{position:relative;height:min(64vh,700px);min-height:420px;border:1px solid #ccd6de;background:#fbfcfd;border-radius:7px;overflow:hidden}canvas{width:100%;height:100%;display:block;cursor:crosshair}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#3d4c58}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}.chart{height:170px;width:100%}.chart canvas{cursor:default}.tag{display:inline-block;border-radius:12px;background:#eaf0f4;padding:2px 8px;font-size:12px}.tablewrap{max-height:260px;overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border-bottom:1px solid #e0e6eb;padding:5px 7px;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#f2f5f7}.hide{display:none}.scope-badge{font-size:11px;border-radius:4px;padding:2px 5px;background:#f8e6e2}.footer{max-width:1500px;margin:0 auto 20px;padding:0 18px;color:#53616d;font-size:12px}@media(max-width:900px){.wrap{grid-template-columns:1fr}.canvasbox{height:55vh;min-height:350px}}
</style></head><body><header class="top"><h1>R2R-Conn：单层任务筛选与 AP 布局校正</h1><p>开发审阅批次 · 20 个任务 / 5 个场景 · 原始任务和排除记录保留</p><p>离线单文件报告；修改仅保存在此浏览器或导出的本地 JSON 中，不会上传。</p></header>
<div class="wrap"><aside class="side"><section class="card"><h2>任务选择</h2><div class="row"><select id="taskSelect" style="flex:1"></select></div><p id="taskTitle" class="muted"></p><div class="kv" id="taskFacts"></div><h3>原始指令</h3><div id="instruction"></div><h3>AP 校正</h3><div class="kv" id="apFacts"></div><p class="muted">在右侧地图点击绿色合法候选点，AP 会吸附到该可达 navmesh 点。不能放在墙内或任意坐标。</p><div class="row"><button id="resetOne">恢复本任务初始 AP</button><button id="resetAll">全部恢复</button></div></section>
<section class="card"><h2>本地校正文件</h2><div class="row"><button id="export" class="primary">导出 AP 修改 JSON</button><label><button id="importBtn">导入 JSON</button><input id="importFile" type="file" accept="application/json" class="hide"></label></div><p class="muted">浏览器自动保存草稿。导出文件可留作人工确认记录；改点后仍须用 Habitat 原生 navmesh/RSSI 场复核，再冻结新 layout 版本。</p><div id="draftStatus" class="muted"></div></section>
<section class="card"><h2>单层筛选审计</h2><div id="scopeStats" class="kv"></div><p class="muted">显式上下楼、源路径/密集 GT 高度超界按规则排除；歧义指令进入复核。关键词和高度规则只是范围筛选，不能替代人工语义/视觉复核。被排除源任务没有删除。</p><button id="toggleScope">查看排除与待复核记录</button><div id="scopeTable" class="tablewrap hide"></div></section>
<section class="card"><h2>生成来源</h2><div class="kv" id="sourceFacts"></div></section></aside>
<main class="main"><section class="card"><div class="row" style="justify-content:space-between"><h2>任务路线与合法 AP 候选位置</h2><span id="editBadge" class="tag"></span></div><div class="canvasbox"><canvas id="map"></canvas></div><div class="legend"><span><i class="dot" style="background:#237b9d"></i>原参考路线</span><span><i class="dot" style="background:#54a56b"></i>合法 AP 候选点</span><span><i class="dot" style="background:#de7d2c"></i>初始 AP</span><span><i class="dot" style="background:#be3d4b"></i>当前 AP</span><span><i class="dot" style="background:#232d36"></i>起点 / 目标</span></div><p class="muted">图只显示路线与经 navmesh 验证的 AP 候选点，不是建筑平面图。滚轮缩放，拖动平移；点击绿色点修改位置。没有墙体/房间语义标注。</p></section>
<section class="card"><h2>初始 AP 下的参考路线 RSSI（原生代理查询）</h2><canvas id="chart" class="chart"></canvas><p id="radioNote" class="muted"></p><div id="routeMetrics" class="kv"></div></section>
<section class="card"><h2>20 个任务的 AP 位置清单</h2><p class="muted">当前表格同步显示初始或你在本机草稿中选择的位置；每个任务是一种独立布局实例。</p><div id="layoutTable" class="tablewrap"></div></section>
<section class="card"><h2>任务筛选与排除清单</h2><p class="muted">源 train split 中全部 episode 均记录状态、原因与高度证据；人工复核状态未被自动规则代替。</p><div id="allRows" class="tablewrap"></div></section></main></div><div class="footer">范围：MP3D + R2R-CE train 的开发审阅样本；AP 场为对数距离 + navmesh 测地绕行代理 + 空间阴影/观测噪声。修改 AP 后的 RSSI 数值不是实时重算值，需导出并用服务器 Habitat 原生场景复核。该报告不是导航结果、held-out benchmark 或物理 WiFi 覆盖图。</div>
<script id="payload" type="application/json">__PAYLOAD__</script><script>
const D=JSON.parse(document.getElementById('payload').textContent), tasks=D.tasks;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key='wifinav_ap_review_'+D.metadata.execution_commit+'_'+D.metadata.source_sha256['configs/benchmark/single_floor_ap_review_v1.json'];
let saved={},storageAvailable=true;try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(_){saved={};storageAvailable=false}
const sel=document.getElementById('taskSelect'), map=document.getElementById('map'), ctx=map.getContext('2d'), chart=document.getElementById('chart'), cctx=chart.getContext('2d');
let ti=0, view={scale:1,dx:0,dy:0,drag:false,last:null};
tasks.forEach((t,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${t.episode_id} · ${t.scene_id}`;sel.append(o)});
function current(){return tasks[ti]}function choice(t){return saved[t.episode_id]||{node:t.initial_ap_node,position:t.initial_ap}}
function persist(){try{localStorage.setItem(key,JSON.stringify(saved));storageAvailable=true}catch(_){storageAvailable=false}document.getElementById('draftStatus').textContent=storageAvailable?`本地草稿：${Object.keys(saved).length} / ${tasks.length} 个任务已修改；最近保存 ${new Date().toLocaleString()}`:'此浏览器禁止本地存储；当前页面内修改仍可导出 JSON 保存。'}
function xyz(p){return p.map(v=>Number(v).toFixed(3)).join(', ')+' m'}
function facts(){const t=current(),a=choice(t),r=t.scope_audit,m=t.route_metrics_initial;
document.getElementById('taskTitle').innerHTML=`<span class="tag">${esc(t.scene_id)}</span> <span class="tag">episode ${esc(t.episode_id)}</span> <span class="tag">路径组 ${esc(t.trajectory_id)}</span>`;
document.getElementById('taskFacts').innerHTML=`<b>范围状态</b><span>${esc(r.scope_status)} · ${esc(r.reasons.join(', ')||'无自动排除原因')}</span><b>源 split</b><span>train</span><b>高度范围</b><span>${Number(r.height_range_m||0).toFixed(3)} m</span><b>起点 X,Y,Z</b><span class="mono">${xyz(t.start)}</span><b>目标 X,Y,Z</b><span class="mono">${xyz(t.goal)}</span><b>参考路径</b><span>${m.length_m.toFixed(2)} m · ${t.route.length} 个采样点</span><b>候选 AP</b><span>${t.ap_candidates.length}</span><b>Navmesh SHA256</b><span class="mono">${t.navmesh_sha256}</span>`;
document.getElementById('instruction').textContent=t.instruction;
document.getElementById('apFacts').innerHTML=`<b>初始坐标</b><span class="mono">${t.initial_ap.map(v=>Number(v).toFixed(3)).join(', ')}</span><b>当前坐标</b><span class="mono">${a.position.map(v=>Number(v).toFixed(3)).join(', ')}</span><b>楼层代理高度</b><span>${Number(a.position[1]).toFixed(3)} m</span><b>节点编号</b><span>${a.node}</span><b>修改状态</b><span>${saved[t.episode_id]?'待原生复核':'初始候选'}</span>`;
document.getElementById('editBadge').textContent=saved[t.episode_id]?'已修改 · 待原生复核':'初始 AP';
document.getElementById('radioNote').textContent=`初始 AP 的 native route_a RSSI；阈值 weak=${t.wireless_config.weak_threshold_dbm} dBm / outage=${t.wireless_config.outage_threshold_dbm} dBm。坐标改动后不沿用这组值作为新位置真值。`;
document.getElementById('routeMetrics').innerHTML=`<b>弱信号路径长度</b><span>${m.available?m.weak_length_m.toFixed(2)+' m':'不可用'}</span><b>断连路径长度</b><span>${m.available?m.outage_length_m.toFixed(2)+' m':'不可用'}</span><b>断连长度比例</b><span>${m.outage_length_ratio==null?'不可用':(100*m.outage_length_ratio).toFixed(1)+'%'}</span><b>路线最低 RSSI</b><span>${m.minimum_dbm==null?'不可用':m.minimum_dbm.toFixed(1)+' dBm'}</span><b>改点后状态</b><span>${saved[t.episode_id]?'RSSI 待重新计算':'当前曲线匹配初始 AP'}</span>`;
drawMap();drawChart();drawLayoutTable()}
function resize(c,context){const r=c.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=Math.max(1,Math.floor(r.width*d));c.height=Math.max(1,Math.floor(r.height*d));context.setTransform(d,0,0,d,0,0);return {w:r.width,h:r.height}}
function projectSetup(t,w,h){const all=t.route.concat(t.ap_candidates.map(p=>[p.x,p.y,p.z]));let xmin=Infinity,xmax=-Infinity,zmin=Infinity,zmax=-Infinity;for(const p of all){xmin=Math.min(xmin,p[0]);xmax=Math.max(xmax,p[0]);zmin=Math.min(zmin,p[2]);zmax=Math.max(zmax,p[2])}let pad=30;let k=Math.min((w-2*pad)/Math.max(xmax-xmin,.5),(h-2*pad)/Math.max(zmax-zmin,.5))*view.scale;let cx=(xmin+xmax)/2,cz=(zmin+zmax)/2;return p=>({x:w/2+(p[0]-cx)*k+view.dx,y:h/2+(p[2]-cz)*k+view.dy})}
function drawMap(){const {w,h}=resize(map,ctx),t=current(),tr=projectSetup(t,w,h);ctx.clearRect(0,0,w,h);ctx.fillStyle='#fbfcfd';ctx.fillRect(0,0,w,h);
ctx.fillStyle='#54a56b';for(const p of t.ap_candidates){const q=tr([p.x,p.y,p.z]);ctx.beginPath();ctx.arc(q.x,q.y,2.1,0,Math.PI*2);ctx.fill()}
ctx.strokeStyle='#237b9d';ctx.lineWidth=3;ctx.beginPath();t.route.forEach((p,i)=>{let q=tr(p);if(i)ctx.lineTo(q.x,q.y);else ctx.moveTo(q.x,q.y)});ctx.stroke();
function marker(p,color,label,r){const q=tr(p);ctx.fillStyle=color;ctx.beginPath();ctx.arc(q.x,q.y,r,0,Math.PI*2);ctx.fill();ctx.fillStyle='#18242d';ctx.font='12px sans-serif';ctx.fillText(label,q.x+7,q.y-7)}
marker(t.start,'#232d36','START',5);marker(t.goal,'#232d36','GOAL',5);marker(t.initial_ap,'#de7d2c','initial',6);marker(choice(t).position,'#be3d4b','current',7);map._transform=tr}
function drawChart(){const {w,h}=resize(chart,cctx),t=current(),v=t.route_rssi_dbm_initial;cctx.clearRect(0,0,w,h);let left=42,right=12,top=10,bottom=24,min=-100,max=-35;cctx.strokeStyle='#e0e6eb';cctx.fillStyle='#596975';cctx.font='11px sans-serif';[-100,-85,-75,-67,-50,-35].forEach(y=>{let yy=top+(max-y)/(max-min)*(h-top-bottom);cctx.beginPath();cctx.moveTo(left,yy);cctx.lineTo(w-right,yy);cctx.stroke();cctx.fillText(y,left-35,yy+4)});let x=i=>left+i/Math.max(1,v.length-1)*(w-left-right),y=a=>top+(max-a)/(max-min)*(h-top-bottom);cctx.strokeStyle='#176b87';cctx.lineWidth=2;cctx.beginPath();v.forEach((a,i)=>{if(i)cctx.lineTo(x(i),y(a));else cctx.moveTo(x(i),y(a))});cctx.stroke();[-75,-67].forEach((a,j)=>{cctx.setLineDash([5,4]);cctx.strokeStyle=j?'#bc8a27':'#bd5961';cctx.beginPath();cctx.moveTo(left,y(a));cctx.lineTo(w-right,y(a));cctx.stroke();cctx.setLineDash([])})}
function drawLayoutTable(){document.getElementById('layoutTable').innerHTML='<table><thead><tr><th># / Task</th><th>Scene</th><th>Scope</th><th>AP X,Y,Z (m)</th><th>Position state</th><th>Candidates</th></tr></thead><tbody>'+tasks.map((t,i)=>{const a=choice(t);return `<tr><td><button data-task="${i}">${esc(t.episode_id)} · ${esc(t.trajectory_id)}</button></td><td>${esc(t.scene_id)}</td><td>${esc(t.scope_audit.scope_status)}</td><td class="mono">${a.position.map(v=>Number(v).toFixed(3)).join(', ')}</td><td>${saved[t.episode_id]?'edited · needs recheck':'initial'}</td><td>${t.ap_candidates.length}</td></tr>`}).join('')+'</tbody></table>';document.getElementById('layoutTable').onclick=e=>{const b=e.target.closest('[data-task]');if(!b)return;ti=Number(b.dataset.task);sel.value=ti;view={scale:1,dx:0,dy:0,drag:false,last:null};facts()}}
sel.onchange=()=>{ti=Number(sel.value);view={scale:1,dx:0,dy:0,drag:false,last:null};facts()};
document.getElementById('resetOne').onclick=()=>{delete saved[current().episode_id];persist();facts()};document.getElementById('resetAll').onclick=()=>{saved={};persist();facts()};
map.addEventListener('click',e=>{if(view.didDrag){view.didDrag=false;return}const r=map.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top,t=current(),tr=map._transform;let best=null,bd=Infinity;for(const p of t.ap_candidates){let q=tr([p.x,p.y,p.z]),d=(q.x-x)**2+(q.y-y)**2;if(d<bd){best=p;bd=d}}if(best&&bd<30**2){saved[t.episode_id]={node:best.node,position:[best.x,best.y,best.z],changed:true};persist();facts()}});
map.addEventListener('wheel',e=>{e.preventDefault();view.scale=Math.max(.5,Math.min(8,view.scale*(e.deltaY<0?1.15:.87)));drawMap()},{passive:false});map.addEventListener('pointerdown',e=>{view.drag=true;view.last=[e.clientX,e.clientY];view.didDrag=false;map.setPointerCapture(e.pointerId)});map.addEventListener('pointermove',e=>{if(!view.drag)return;let dx=e.clientX-view.last[0],dy=e.clientY-view.last[1];if(Math.abs(dx)+Math.abs(dy)>2)view.didDrag=true;view.dx+=dx;view.dy+=dy;view.last=[e.clientX,e.clientY];drawMap()});map.addEventListener('pointerup',()=>{view.drag=false});
document.getElementById('export').onclick=()=>{let payload={format:'wifinav-ap-review-edits-v1',created_at:new Date().toISOString(),execution_commit:D.metadata.execution_commit,source_sha256:D.metadata.source_sha256,specification:D.metadata.specification,changes:tasks.map(t=>({episode_id:t.episode_id,trajectory_id:t.trajectory_id,scene_id:t.scene_id,initial_ap_node:t.initial_ap_node,initial_ap_position:t.initial_ap,selected_ap_node:choice(t).node,selected_ap_position:choice(t).position,changed:!!saved[t.episode_id],native_revalidation_required:!!saved[t.episode_id]}))};let a=document.createElement('a'),blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});a.href=URL.createObjectURL(blob);a.download='single_floor_ap_review_edits_v1.json';a.click();URL.revokeObjectURL(a.href)};
document.getElementById('importBtn').onclick=()=>document.getElementById('importFile').click();document.getElementById('importFile').onchange=async e=>{try{let x=JSON.parse(await e.target.files[0].text());if(x.format!=='wifinav-ap-review-edits-v1'||x.execution_commit!==D.metadata.execution_commit)throw Error('格式或源码版本不匹配');saved={};for(const c of x.changes||[])if(c.changed){const t=tasks.find(t=>t.episode_id===String(c.episode_id));if(!t||!t.ap_candidates.some(p=>p.node===c.selected_ap_node))throw Error('导入位置不是合法 AP 候选点');saved[t.episode_id]={node:c.selected_ap_node,position:c.selected_ap_position,changed:true}}persist();facts();alert('已导入本地草稿；所有修改仍需原生复核')}catch(err){alert('导入失败：'+err.message)}e.target.value=''};
function scopeHTML(rows){let data=rows.filter(x=>x.scope_status!=='candidate'||x.selection_status==='not_selected_budget');return '<table><thead><tr><th>Episode</th><th>Scene</th><th>状态</th><th>原因</th><th>高度范围</th></tr></thead><tbody>'+data.map(r=>`<tr><td>${esc(r.episode_id)}</td><td>${esc(r.scene_id)}</td><td>${esc(r.scope_status)}</td><td>${esc(r.reasons.join(', ')||r.selection_status)}</td><td>${r.height_range_m==null?'—':Number(r.height_range_m).toFixed(3)+' m'}</td></tr>`).join('')+'</tbody></table>'}
document.getElementById('toggleScope').onclick=()=>{let e=document.getElementById('scopeTable');e.classList.toggle('hide');e.innerHTML=scopeHTML(D.scope_rows)};
document.getElementById('allRows').innerHTML='<table><thead><tr><th>Episode</th><th>Scene</th><th>Group</th><th>范围</th><th>选择</th><th>原因 / 高度</th></tr></thead><tbody>'+D.scope_rows.map(r=>`<tr><td>${esc(r.episode_id)}</td><td>${esc(r.scene_id)}</td><td>${esc(r.trajectory_id)}</td><td>${esc(r.scope_status)}</td><td>${esc(r.selection_status)}</td><td>${esc(r.reasons.join(', ')||'—')} · ${r.height_range_m==null?'':Number(r.height_range_m).toFixed(3)+' m'}</td></tr>`).join('')+'</tbody></table>';
const s=D.scope_summary;document.getElementById('scopeStats').innerHTML=Object.entries(s.scope_counts||{}).map(([k,v])=>`<b>${k}</b><span>${v}</span>`).join('')+`<b>选中任务</b><span>${s.selected_tasks}</span><b>选中场景</b><span>${s.selected_scenes}</span><b>源 episode</b><span>${s.source_episodes}</span>`;
document.getElementById('sourceFacts').innerHTML=`<b>代码版本</b><span class="mono">${D.metadata.execution_commit}</span><b>任务源 SHA256</b><span class="mono">${D.metadata.source_sha256['data/datasets/R2R_VLNCE_v1-3_preprocessed/train/train.json.gz']}</span><b>GT SHA256</b><span class="mono">${D.metadata.source_sha256['data/datasets/R2R_VLNCE_v1-3_preprocessed/train/train_gt.json.gz']}</span><b>无线代理</b><span>${D.metadata.specification.wireless_overrides.reference_rssi_dbm_at_1m} dBm @1m · n=${D.metadata.specification.wireless_overrides.path_loss_exponent} · seed ${D.metadata.specification.wireless_overrides.seed}</span><b>AP 规则</b><span>${D.metadata.specification.ap_route_progress_fraction*100}% 路程、侧向偏移目标 ${D.metadata.specification.ap_preferred_lateral_offset_m} m 后吸附合法点</span><b>构建时间</b><span>${D.metadata.created_at_utc}</span>`;
window.addEventListener('resize',()=>{drawMap();drawChart()});persist();facts();
</script></body></html>'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    audit = load_json(a.audit)
    data = load_json(a.data)
    payload = json.dumps(compact_payload(audit, data), ensure_ascii=False, separators=(",", ":"))
    # JSON is placed in a script element; escape its closing-tag delimiter.
    payload = payload.replace("</", "<\\/")
    page = PAGE.replace("__PAYLOAD__", payload)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(a.output.resolve()), "bytes": a.output.stat().st_size,
                      "tasks": len(data["tasks"]), "source_episodes": len(audit["episodes"])}))


if __name__ == "__main__":
    main()
