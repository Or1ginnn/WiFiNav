"""CPU train-only scope audit and 20-task AP data. NEVER generates HTML remotely."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
import habitat_sim
import numpy as np
from connectivity_vln.benchmark.single_floor import scope_status,distances,preview_rssi,route_metrics
from connectivity_vln.navigation.weighted_planner import NavmeshRiskPlanner
from connectivity_vln.signal_simulation.route_a import SignalField
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def native_route(pf,raw,tolerance,spacing):
    anchors=[raw['start_position']]+raw['reference_path']+[raw['goals'][0]['position']]
    route=[];floor=raw['start_position'][1]
    for a,b in zip(anchors,anchors[1:]):
        q=habitat_sim.ShortestPath();q.requested_start=np.array(a,dtype=np.float32);q.requested_end=np.array(b,dtype=np.float32)
        if not pf.find_path(q) or not np.isfinite(q.geodesic_distance): return None,'reference_segment_unreachable'
        points=[np.array(p) for p in q.points]
        if any(abs(float(p[1])-floor)>tolerance+1e-4 for p in points): return None,'native_reference_path_leaves_height_scope'
        if not points: return None,'empty_native_reference_path'
        if not route: route.append(points[0])
        for x,y in zip(points,points[1:]):
            count=max(1,int(np.ceil(np.linalg.norm(y-x)/spacing)))
            for k in range(1,count+1):
                p=x+(y-x)*(k/count)
                if np.linalg.norm(p-route[-1])>1e-5:route.append(p)
    if len(route)<2:return None,'zero_length_reference_route'
    return route,None


def graph_for_route(pf,raw,route,spec):
    graph=NavmeshRiskPlanner(pf,float(raw['start_position'][1]),resolution=spec['map_grid_resolution_m'],floor_tolerance=spec['height_tolerance_m'])
    if len(graph.points)>spec['map_max_nodes']:raise RuntimeError('Map node budget exceeded; review configuration instead of silently resampling')
    base_count=len(graph.points);route_nodes=[]
    base=np.asarray(graph.points)
    for point in route:
        # Native reference anchors supplement the display grid so narrow doorways
        # are not silently lost. This is offline layout QA, never an actor map.
        node=len(graph.points);graph.points.append(point);graph.edges.append([])
        near=np.flatnonzero(np.linalg.norm(base[:,[0,2]]-point[[0,2]],axis=1)<=spec['route_attachment_radius_m'])
        for other in near:
            other=int(other)
            if graph._clear(point,graph.points[other]):
                length=float(np.linalg.norm(point-graph.points[other]));graph.edges[node].append((other,length));graph.edges[other].append((node,length))
        if route_nodes:
            other=route_nodes[-1]
            # Both endpoints came from the same validated native navmesh path;
            # retain its sampled polyline edge even when the coarse try_step
            # raster rejects this QA-only connector.
            length=float(np.linalg.norm(point-graph.points[other]));graph.edges[node].append((other,length));graph.edges[other].append((node,length))
        route_nodes.append(node)
    return graph,route_nodes,base_count


def prepare_task(pf,raw,route,spec,wireless):
    graph,route_nodes,base_count=graph_for_route(pf,raw,route,spec)
    points=np.asarray(graph.points);lengths=[float(np.linalg.norm(b-a)) for a,b in zip(route,route[1:])]
    cum=np.r_[0,np.cumsum(lengths)];target_length=cum[-1]*spec['ap_route_progress_fraction']
    i=min(len(route)-2,max(0,int(np.searchsorted(cum,target_length)-1)))
    fraction=(target_length-cum[i])/max(lengths[i],1e-9);center=route[i]+(route[i+1]-route[i])*fraction
    tangent=(route[i+1]-route[i])[[0,2]];norm=float(np.linalg.norm(tangent));perp=np.array([-tangent[1],tangent[0]])/max(norm,1e-9)
    target=center.copy();target[[0,2]]+=perp*spec['ap_preferred_lateral_offset_m']
    reach=distances(graph.edges,route_nodes[0])
    near_route=np.full(base_count,np.inf)
    for r in route:near_route=np.minimum(near_route,np.linalg.norm(points[:base_count,[0,2]]-r[[0,2]],axis=1))
    candidates=[n for n in range(base_count) if np.isfinite(reach[n]) and near_route[n]<=spec['ap_route_corridor_m']]
    if not candidates:raise RuntimeError('No AP floor-proxy candidate for selected task; task is not replaced based on radio quality')
    default=min(candidates,key=lambda n:(float(np.linalg.norm((points[n]-target)[[0,2]])),n))
    config=dict(wireless,layout_id='single_floor_ap_review_'+str(raw['episode_id']),ap_floor_position=points[default].tolist())
    field=SignalField(pf,raw['scene_id'],points[default],config)
    shadow=[field._shadow(p) for p in points]
    approx_dist=distances(graph.edges,default)
    approx=[preview_rssi(p,points[default],d,s,config) for p,d,s in zip(points,approx_dist,shadow)]
    # Native RSSI queries are expensive pathfinder calls. Query the reference
    # route only; a full query at every display-grid node is unnecessary here.
    route_samples=[field.query(points[n],sample_index) for sample_index,n in enumerate(route_nodes)]
    route_values=[float(sample['rssi_truth_dbm']) for sample in route_samples]
    route_measured_values=[float(sample['rssi_measured_dbm']) for sample in route_samples]
    route_preview=[approx[n] for n in route_nodes]
    delta=[abs(a-b) for a,b in zip(route_values,route_preview) if b is not None]
    edges=[[a,b,round(float(length),6)] for a,row in enumerate(graph.edges) for b,length in row if a<b]
    return {'episode_id':str(raw['episode_id']),'trajectory_id':str(raw['trajectory_id']),
        'scene_id':raw['scene_id'],'instruction':raw['instruction']['instruction_text'],
        'instruction_sha256':hashlib.sha256(raw['instruction']['instruction_text'].encode()).hexdigest(),
        'start_position':raw['start_position'],'goal_position':raw['goals'][0]['position'],
        'floor_y':float(raw['start_position'][1]),'nodes':np.round(points,6).tolist(),'edges':edges,
        'route_nodes':route_nodes,'route_lengths_m':lengths,'base_grid_nodes':base_count,
        'default_ap_node':default,'ap_candidate_nodes':candidates,
        'default_ap_position':points[default].tolist(),'route_native_rssi_dbm':np.round(route_values,3).tolist(),
        'route_measured_rssi_dbm':np.round(route_measured_values,3).tolist(),
        'shadow_db':np.round(shadow,6).tolist(),'wireless_config':config,
        'initial_route_metrics':route_metrics(route_values,lengths,config['weak_threshold_dbm'],config['outage_threshold_dbm']),
        'preview_vs_native':{'mean_absolute_db':float(np.mean(delta)) if delta else None,
                             'maximum_absolute_db':max(delta) if delta else None,
                             'grid_unreachable_nodes':sum(v is None for v in approx)},
        'review_status':'draft_unreviewed_not_semantic_or_physical_ground_truth'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    out=args.output_dir.resolve()
    if not out.is_relative_to((PROJECT/'runtime').resolve()):raise ValueError('Use runtime')
    out.mkdir(parents=True,exist_ok=False)
    spec_path=PROJECT/'configs/benchmark/single_floor_ap_review_v1.json';spec=read(spec_path)
    assert spec['source_split']=='train' and spec['task_count']==spec['scene_count']*spec['tasks_per_scene']
    wireless=read(PROJECT/spec['wireless_base_config']);wireless.update(spec['wireless_overrides'])
    paths=read(PROJECT/'configs/data/server_paths.json');source=PROJECT/paths['task_dataset']/'train/train.json.gz';gtfile=source.with_name('train_gt.json.gz')
    with gzip.open(source,'rt') as f:episodes=json.load(f)['episodes']
    with gzip.open(gtfile,'rt') as f:gt=json.load(f)
    rows=[];by_scene=defaultdict(list);row_by_id={}
    for e in episodes:
        if str(e['episode_id']) not in gt:status,reasons,info='excluded',['missing_dense_gt'],{}
        else:status,reasons,info=scope_status(e['instruction']['instruction_text'],e['start_position'],[g['position'] for g in e['goals']],e['reference_path'],gt[str(e['episode_id'])]['locations'],spec['height_tolerance_m'],spec['height_epsilon_m'])
        row={'episode_id':str(e['episode_id']),'trajectory_id':str(e['trajectory_id']),'scene_id':e['scene_id'],
             'scope_status':status,'reasons':reasons,**info,'selection_status':'not_selected_budget' if status=='candidate' else status,
             'native_geometry_check':'not_run'}
        if row['episode_id'] in row_by_id:raise ValueError('Duplicate source episode')
        rows.append(row);row_by_id[row['episode_id']]=row
        if status=='candidate':by_scene[e['scene_id']].append(e)
    print('preliminary_scope',dict(Counter(r['scope_status'] for r in rows)),flush=True)
    selected=[];scene_records=[];scene_count=0
    for scene in sorted(by_scene):
        if len({str(e['trajectory_id']) for e in by_scene[scene]})<spec['tasks_per_scene']:continue
        navmesh=(PROJECT/paths['scene_dataset_root']/scene).with_suffix('.navmesh');pf=habitat_sim.PathFinder()
        if not pf.load_nav_mesh(str(navmesh)):raise RuntimeError('Navmesh missing: '+str(navmesh))
        chosen=[];groups=set()
        for e in sorted(by_scene[scene],key=lambda r:int(r['episode_id'])):
            row=row_by_id[str(e['episode_id'])]
            if str(e['trajectory_id']) in groups:continue
            route,error=native_route(pf,e,spec['height_tolerance_m'],spec['reference_segment_max_spacing_m'])
            row['native_geometry_check']=error or 'passed'
            if error:row['scope_status']='review';row['reasons'].append('native_geometry_review_required:'+error);row['selection_status']='review_geometry';continue
            chosen.append((e,route));groups.add(str(e['trajectory_id']))
            if len(chosen)==spec['tasks_per_scene']:break
        if len(chosen)<spec['tasks_per_scene']:
            scene_records.append({'scene_id':scene,'status':'insufficient_geometry_eligible_tasks'});continue
        wireless=read(PROJECT/spec['wireless_base_config']);wireless.update(spec['wireless_overrides'])
        for e,route in chosen:
            item=prepare_task(pf,e,route,spec,wireless);item['navmesh_sha256']=sha(navmesh);selected.append(item)
            row_by_id[str(e['episode_id'])]['selection_status']='selected'
            print('selected',len(selected),scene,e['episode_id'],len(item['nodes']),'nodes',flush=True)
        scene_count+=1
        if scene_count==spec['scene_count']:break
    if len(selected)!=spec['task_count']:raise RuntimeError('Insufficient tasks; no automatic outcome-based replacement')
    stats={'source_episodes':len(rows),'selected_tasks':len(selected),'selected_source_groups':len({(r['scene_id'],r['trajectory_id']) for r in selected}),
           'selected_scenes':len({r['scene_id'] for r in selected}),
           'scope_counts':dict(Counter(r['scope_status'] for r in rows)),
           'selection_counts':dict(Counter(r['selection_status'] for r in rows)),
           'reason_counts':dict(Counter(reason for r in rows for reason in r['reasons']))}
    metadata={'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT,text=True).strip(),
        'model_calls':0,'model_revision':None,'model_use':'not_applicable_cpu_construction','gpu_rendering':False,'specification':spec,'statistics':stats,'scene_checks':scene_records,
        'source_sha256':{str(p.relative_to(PROJECT)):sha(p) for p in [source,gtfile,spec_path,Path(__file__).resolve(),PROJECT/'src/connectivity_vln/benchmark/single_floor.py',PROJECT/spec['wireless_base_config'],PROJECT/'src/connectivity_vln/navigation/weighted_planner.py',PROJECT/'src/connectivity_vln/signal_simulation/route_a.py']},
        'field_note':'Initial map uses native-navmesh route_a latent proxy. Edited map is a separately labelled grid-geodesic preview; native revalidation required.',
        'not_a_held_out_or_navigation_result':True}
    for name,obj in [('source_scope_audit.json',{'metadata':metadata,'episodes':rows}),('ap_review_data.json',{'metadata':metadata,'tasks':selected})]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    print(json.dumps(stats),flush=True)


if __name__=='__main__':main()
