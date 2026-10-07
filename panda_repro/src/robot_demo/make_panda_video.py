"""Render a real-Panda HoRoPose, cycle timing and sensor-fusion demo."""
from __future__ import annotations
import argparse, csv, json, subprocess
from pathlib import Path
import cv2, joblib, numpy as np
from scipy.spatial.transform import Rotation
from .event_store import EventStore
from .faults import extract_features, simulate_cycle

WHITE=(244,247,251); CYAN=(238,205,45); BLUE=(248,155,55); GREEN=(106,214,111)
AMBER=(55,181,250); RED=(77,80,244); MUTED=(165,177,193); DARK=(16,22,31); CARD=(34,44,57)
LABELS=["L0","L2","L3","L4","L6","L7","EE"]

def put(f,t,xy,s=.46,c=WHITE,w=1): cv2.putText(f,t,xy,cv2.FONT_HERSHEY_SIMPLEX,s,c,w,cv2.LINE_AA)
def box(f,a,b,c,alpha=.95):
    o=f.copy(); cv2.rectangle(o,a,b,c,-1); cv2.addWeighted(o,alpha,f,1-alpha,0,f)

def euler(r):
    x=r[:3]/max(np.linalg.norm(r[:3]),1e-9); z=np.cross(x,r[3:]); z/=max(np.linalg.norm(z),1e-9); y=np.cross(z,x)
    return Rotation.from_matrix(np.stack((x,y,z),-1).T).as_euler("xyz",degrees=True)

def timeline(n,fps,hold=24):
    normal=list(range(n))+list(range(n-2,0,-1)); delayed=list(range(n))+[n-1]*hold+list(range(n-2,0,-1))
    idx=np.asarray(normal+delayed); cyc=np.r_[np.zeros(len(normal),int),np.ones(len(delayed),int)]
    return idx,cyc,len(normal)/fps,len(delayed)/fps,len(normal)

def sensors(q,start):
    N=len(q); speed=np.linalg.norm(np.diff(q[:,:7],axis=0,prepend=q[:1,:7]),axis=1); speed/=max(np.percentile(speed,95),1e-6); speed=np.clip(speed,0,1.8)
    blend=np.zeros(N,np.float32); fs=start+int((N-start)*.38); blend[fs:]=np.clip(np.linspace(0,1.35,N-fs),0,1)
    phase=np.linspace(0,30*np.pi,N); rev=np.zeros(N); peak=start+119; rev[max(0,peak-6):min(N,peak+30)]=1
    rng=np.random.default_rng(20260912)
    vib=1.35+1.45*speed+.10*rng.standard_normal(N)+blend*(2.4+1.7*abs(np.sin(phase))+1.7*rev)
    snd=57.8+4*speed+.45*rng.standard_normal(N)+blend*(6.5+4*abs(np.sin(phase*.62))+5.5*rev)
    tmp=37+.5*np.linspace(0,1,N)+blend*np.linspace(0,6.4,N)+.08*rng.standard_normal(N)
    cur=.72+1.15*speed+.05*rng.standard_normal(N)+blend*(.38+.28*rev)
    return {"vibration_mm_s":vib.astype(np.float32),"acoustic_dba":snd.astype(np.float32),"temperature_c":tmp.astype(np.float32),"motor_current_a":cur.astype(np.float32),"fault_blend":blend}

def robot_overlay(f,pred,raw,gt,fault):
    org=np.array([0.,66.]); sc=np.array([840/640,630/480]); p=pred*sc+org; r=raw*sc+org; g=gt*sc+org; glow=f.copy()
    for j in range(6):
        c=RED if fault and j in {2,3} else CYAN; a=tuple(np.rint(p[j]).astype(int)); b=tuple(np.rint(p[j+1]).astype(int))
        cv2.line(glow,a,b,c,22,cv2.LINE_AA); cv2.line(f,a,b,c,4,cv2.LINE_AA)
    cv2.addWeighted(glow,.18,f,.82,0,f)
    for x in g: cv2.circle(f,tuple(np.rint(x).astype(int)),5,GREEN,1,cv2.LINE_AA)
    for x in r: cv2.circle(f,tuple(np.rint(x).astype(int)),2,BLUE,-1,cv2.LINE_AA)
    for j,x in enumerate(p):
        xy=tuple(np.rint(x).astype(int)); c=RED if fault and j==3 else CYAN; cv2.circle(f,xy,9,c,-1,cv2.LINE_AA); cv2.circle(f,xy,3,WHITE,-1); put(f,LABELS[j],(xy[0]+10,xy[1]-7),.36)
    a=np.rint(p[3]).astype(int); cv2.line(f,tuple(a),(a[0]-55,a[1]+54),WHITE,1,cv2.LINE_AA); x,y=a[0]-115,a[1]+54
    for off,name,c in [(0,"ACC",RED),(40,"MIC",AMBER),(80,"TMP",CYAN)]: box(f,(x+off,y-17),(x+off+36,y+5),c,.97); put(f,name,(x+off+4,y-2),.27,DARK)

def joint_bars(f,q,gt):
    put(f,"JOINT ANGLES q1...q7",(862,145),.38,MUTED)
    for j in range(7):
        col,row=j//4,j%4; x=862+col*202; y=169+row*31; v=float(q[j]); ref=float(gt[j]); put(f,f"q{j+1}",(x,y+13),.34)
        cv2.rectangle(f,(x+29,y+3),(x+136,y+14),(62,73,88),-1); end=x+29+int(107*np.clip((v+180)/360,0,1)); cv2.rectangle(f,(x+29,y+3),(end,y+14),CYAN,-1)
        mark=x+29+int(107*np.clip((ref+180)/360,0,1)); cv2.line(f,(mark,y),(mark,y+17),GREEN,1); put(f,f"{v:+5.1f}",(x+140,y+13),.32)

def trace(f,v,i,y,title,unit,th,c):
    x,w,h=852,414,48; box(f,(x,y),(x+w,y+h),CARD,.96); now=float(v[i]); alert=now>=th; put(f,title,(x+10,y+18),.30,MUTED); put(f,f"{now:5.1f} {unit}",(x+304,y+18),.34,RED if alert else GREEN)
    hist=v[max(0,i-100):i+1]; lo=min(float(v.min()),th*.72); hi=max(float(v.max()),th*1.12); xs=np.linspace(x+9,x+w-9,max(2,len(hist))); ys=y+h-5-np.clip((hist-lo)/(hi-lo),0,1)*24
    if len(hist)==1: ys=np.repeat(ys,2)
    cv2.polylines(f,[np.c_[xs,ys].astype(np.int32)],False,RED if alert else c,2,cv2.LINE_AA); ty=int(y+h-5-np.clip((th-lo)/(hi-lo),0,1)*24); cv2.line(f,(x+9,ty),(x+w-9,ty),(82,93,108),1)

def save_csv(path,fps,idx,cyc,p,err,s):
    fields=["frame","time_s","source_frame","cycle","kp_error_px"]+[f"q{j}_pred_deg" for j in range(1,8)]+[f"q{j}_reference_deg" for j in range(1,8)]+["root_x_m","root_y_m","root_z_m"]+list(s)
    with path.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for i,k in enumerate(idx):
            row={"frame":i,"time_s":i/fps,"source_frame":int(p["scene_id"][k]),"cycle":int(cyc[i]+1),"kp_error_px":float(err[k]),"root_x_m":float(p["translation_smooth"][k,0]),"root_y_m":float(p["translation_smooth"][k,1]),"root_z_m":float(p["translation_smooth"][k,2])}
            for j in range(7): row[f"q{j+1}_pred_deg"]=float(np.rad2deg(p["q_calibrated"][k,j])); row[f"q{j+1}_reference_deg"]=float(np.rad2deg(p["gt_q"][k,j]))
            row.update({n:float(v[i]) for n,v in s.items()}); w.writerow(row)

def local_images(p, predictions):
    """Resolve original absolute build paths to the RGB files in this package."""
    dataset=next((parent/"data"/"panda_realsense" for parent in predictions.resolve().parents
                  if (parent/"data"/"panda_realsense").is_dir()),None)
    if dataset is None: raise FileNotFoundError("Panda data/panda_realsense directory not found")
    paths=[]
    for original in p["image_path"]:
        path=Path(str(original))
        if not path.is_file(): path=dataset/path.name
        if not path.is_file(): raise FileNotFoundError(f"Missing Panda RGB frame: {path}")
        paths.append(path)
    return paths

def create(predictions:Path,output:Path,fault_model:Path,events:Path,fps=30.):
    z=np.load(predictions,allow_pickle=False); p={k:z[k] for k in z.files}; images=[cv2.imread(str(x)) for x in local_images(p,predictions)]
    if any(x is None for x in images): raise RuntimeError("Missing Panda RGB frame")
    idx,cyc,baseline,observed,start=timeline(len(images),fps); s=sensors(p["q_calibrated"][idx],start); err=np.linalg.norm(p["keypoints_2d_smooth"]-p["gt_keypoints_2d"],axis=2).mean(1)
    b=joblib.load(fault_model); fc=simulate_cycle("gearbox_backlash",faulty_joint=3,steps=96,seed=0); feat,_=extract_features(fc,feature_schema=b.get("feature_schema","legacy_v1")); label=str(b["cause_model"].predict(feat[None])[0]); joint=int(b["joint_model"].predict(feat[None])[0]); conf=float(np.max(b["cause_model"].predict_proba(feat[None])[0]))
    store=EventStore(events); eid=store.add_event("PANDA-REAL-RS-HOROPOSE","cycle-0002",observed,label,joint,conf,{"signals_are_simulated":True,"timing_anomaly_is_injected":True,"camera_pose_is_checkpoint_inference":True,"baseline_cycle_s":baseline,"observed_cycle_s":observed}); store.add_feedback(eid,"gearbox_backlash",3,"Demo technician confirmed J4 reducer backlash","confirmed")
    output.parent.mkdir(parents=True,exist_ok=True); avi=output.with_suffix(".source.avi"); writer=cv2.VideoWriter(str(avi),cv2.VideoWriter_fourcc(*"MJPG"),fps,(1280,720))
    for i,k in enumerate(idx):
        f=np.zeros((720,1280,3),np.uint8); f[66:696,:840]=cv2.resize(images[k],(840,630)); f[:,840:]=DARK; blend=float(s["fault_blend"][i]); cycle=int(cyc[i])
        if cycle==0: status,sc="NORMAL REFERENCE CYCLE",GREEN
        elif blend<.22: status,sc="CYCLE TIME DEVIATION",AMBER
        elif blend<.72: status,sc="MULTIMODAL ANOMALY",RED
        else: status,sc="FAULT LOCALIZED: J4",RED
        robot_overlay(f,p["keypoints_2d_smooth"][k],p["keypoints_2d"][k],p["gt_keypoints_2d"][k],blend>=.22); box(f,(0,0),(840,66),DARK,.93)
        put(f,"REAL FRANKA PANDA | HOROPOSE ECCV 2024 CHECKPOINT",(18,29),.52,WHITE,2); put(f,"AI temporal",(18,54),.34,CYAN); put(f,"raw",(120,54),.34,BLUE); put(f,"dataset GT (evaluation only)",(168,54),.34,GREEN); put(f,"Public checkpoint predicts q1...q7 + root 6D pose per RGB frame",(18,714),.36)
        box(f,(852,10),(1267,55),sc,.98); put(f,status,(866,40),.50,DARK,2); put(f,"POSE / CYCLE",(855,80),.34,MUTED); put(f,f"cycle {(baseline if cycle==0 else observed):.2f}s   ref {baseline:.2f}s",(855,103),.43,AMBER if cycle else GREEN); put(f,f"GT eval {err[k]:.1f}px",(1080,80),.31,CYAN)
        t=p["translation_smooth"][k]; r=euler(p["rotation_6d_smooth"][k]); put(f,f"root L4 XYZ {t[0]:+.2f} {t[1]:+.2f} {t[2]:+.2f} m",(855,124),.31); put(f,f"RPY {r[0]:+.0f} {r[1]:+.0f} {r[2]:+.0f} deg",(1080,103),.30)
        joint_bars(f,np.rad2deg(p["q_calibrated"][k,:7]),np.rad2deg(p["gt_q"][k,:7])); trace(f,s["vibration_mm_s"],i,298,"VIBRATION / RUNG J4","mm/s",4.5,CYAN); trace(f,s["acoustic_dba"],i,351,"ACOUSTIC / AM THANH","dBA",68,AMBER); trace(f,s["temperature_c"],i,404,"TEMPERATURE / NHIET","C",42,AMBER); trace(f,s["motor_current_a"],i,457,"MOTOR CURRENT / DONG","A",2.25,CYAN)
        box(f,(852,516),(1267,706),CARD,.97); put(f,"SENSOR-FUSION DIAGNOSIS",(866,540),.36,MUTED)
        if cycle==0: put(f,"Normal reference learned",(866,569),.48,GREEN,2); put(f,"HoRoPose q + RGB timing stable",(866,595),.34)
        elif blend<.22: put(f,"+10.1% cycle delay captured",(866,569),.46,AMBER,2); put(f,"Opening synchronized evidence window",(866,595),.34)
        elif blend<.72: put(f,"RGB timing + ACC + MIC + TEMP",(866,569),.39,RED); put(f,"Cross-modal evidence accumulating...",(866,595),.34)
        else:
            put(f,label.upper(),(866,569),.49,RED,2); put(f,f"likely J{joint+1} | confidence {conf*100:.1f}%",(866,595),.37); put(f,f"event #{eid} saved with evidence window",(866,621),.35,CYAN)
            if i>len(idx)-42: put(f,"TECHNICIAN: CONFIRMED J4 BACKLASH",(866,650),.38,GREEN); put(f,"verified label retained for retraining",(866,674),.33)
        put(f,"Sensors + fault + delay are simulated for demo",(866,696),.29,MUTED); writer.write(f)
    writer.release(); import imageio_ffmpeg; ff=imageio_ffmpeg.get_ffmpeg_exe(); subprocess.run([ff,"-y","-i",str(avi),"-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); avi.unlink()
    save_csv(output.with_name("panda_multimodal_timeseries.csv"),fps,idx,cyc,p,err,s); metrics=json.loads(predictions.with_name("panda_pose_metrics.json").read_text())
    result={"video":str(output),"frames":len(idx),"fps":fps,"duration_s":len(idx)/fps,"robot":"Franka Emika Panda","real_rgb_source":"DREAM panda-3cam_realsense","pose_backend":"HoRoPose ECCV 2024 public panda_realsense checkpoint","checkpoint_epoch":metrics["checkpoint_epoch"],"strict_state_dict_load":metrics["strict_state_dict_load"],"keypoint_error_px_temporal":metrics["keypoint_error_px_temporal"],"joint_mae_deg_calibrated":metrics["joint_mae_deg_calibrated"],"baseline_cycle_s":baseline,"injected_delayed_cycle_s":observed,"diagnosis":label,"predicted_joint":joint+1,"diagnosis_confidence":conf,"event_id":eid,"real_vs_simulated":{"real":["RGB Panda frames","checkpoint q/6D pose/keypoints"],"simulated":["cycle hold/delay","vibration","sound","temperature","motor current","fault label"]}}
    output.with_name("panda_horopose_demo_summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8"); return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--predictions",type=Path,default=Path("artifacts/panda_pose_predictions.npz")); ap.add_argument("--output",type=Path,default=Path("artifacts/panda_horopose_health_demo.mp4")); ap.add_argument("--fault-model",type=Path,default=Path("artifacts/fault_model.joblib")); ap.add_argument("--events",type=Path,default=Path("artifacts/events.db")); a=ap.parse_args(); print(json.dumps(create(a.predictions,a.output,a.fault_model,a.events),indent=2))
if __name__=="__main__": main()
