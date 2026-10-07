"""Causal video-aligned what-if signals and learned-normal anomaly detection.

HoRoPose predictions are replay inputs, not commands or healthy ground truth.
Sensor envelopes are synthetic regional channels, not mapped physical J1..J7.
"""
import math
from functools import lru_cache
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge
from engine import FPS, POSE, RECORDING, ROOT, point_distance
from engine_v2 import FAULTS as OLD_FAULTS, DEFAULT_INJECTIONS, rotate, activity_at, reversal_at
from research_pipeline.physics import envelope, sensor_sample, thermal_step

FAULTS = dict(OLD_FAULTS)
FAULTS["encoder_error"] = dict(label="Nghi sai lệch phép đo vị trí", cause="Encoder, đo thị giác hoặc hiệu chuẩn",
    checks=["Đối chiếu encoder với camera đã hiệu chuẩn", "Kiểm tra độ tin cậy và timestamp của hai phép đo"],
    mechanism="Sai lệch đo vị trí giả lập; trạng thái cơ học và cảm biến nhiệt/rung/âm giữ nguyên.")


def validate_injections(items):
    if not isinstance(items, list) or len(items) > 8:
        raise ValueError("Cần 0–8 kịch bản")
    clean = []
    for item in items:
        try:
            fault = str(item["fault"])
            raw_j = item["landmark"]
            j = int(raw_j)
            start = float(item["start_s"])
            duration = float(item["duration_s"])
            intensity = float(item.get("intensity", 1))
            profile = str(item.get("profile", "transient"))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Kịch bản thiếu hoặc sai tham số") from exc
        if (isinstance(raw_j, bool) or raw_j != j or fault not in FAULTS or not 0 <= j < 7 or
            not all(math.isfinite(v) for v in (start,duration,intensity)) or
            not 0 <= start < RECORDING["duration_s"]-.5 or not .5 <= duration <= 10 or
            start+duration > RECORDING["duration_s"] or not .3 <= intensity <= 2 or
            profile not in ("transient","progressive","intermittent")):
            raise ValueError("Kịch bản vượt phạm vi thời gian, mốc, cường độ hoặc kiểu tiến triển")
        clean.append(dict(fault=fault,landmark=j,start_s=start,duration_s=duration,intensity=intensity,profile=profile))
    return clean


def validate_context(seed, load, environment="nominal"):
    if isinstance(seed, bool) or not isinstance(seed, (int,np.integer)) or not 0 <= seed <= 1000000:
        raise ValueError("Seed phải là số nguyên 0–1.000.000")
    if not math.isfinite(load) or not .6 <= load <= 1.4:
        raise ValueError("Tải mô phỏng phải từ 0,6 đến 1,4")
    if environment not in ("nominal","noise","hot","occlusion"):
        raise ValueError("Điều kiện môi trường không hợp lệ")
    return int(seed),float(load)


def covariates(row, sig, load, ambient):
    motion = sig["activity"]
    return [sig["landmark"],motion,load,load*motion,row["t"],row["t"]**2,ambient]


def raw_run(injections, seed=0, load=1., environment="nominal"):
    rng = np.random.default_rng(seed)
    ambient = 33 + float(rng.uniform(-1.2,1.2)) + (4 if environment == "hot" else 0)
    temp = np.full(7,ambient+4.)
    ref_temp = temp.copy()
    rows = []
    for i,observed in enumerate(POSE):
        signals, components = [],[]
        for j in range(7):
            active = {name:0. for name in FAULTS}
            for inj in injections:
                if inj["landmark"] == j:
                    active[inj["fault"]] += envelope(observed["t"],inj["start_s"],inj["duration_s"],inj["profile"])*inj["intensity"]
            motion = activity_at(i,j)
            reverse = reversal_at(i,j)
            base_torque = .8 + 1.8*load*motion
            torque = base_torque + 2.4*active["friction"]*motion + .5*active["bearing"]*motion
            current = .65+torque/2.4
            base_power = .25*(.65+base_torque/2.4)**2+.1*motion
            power = .25*current**2+(.1+2*active["friction"])*motion+.7*active["bearing"]*motion
            temp[j] = thermal_step(temp[j],ambient,power,.25/(1+2*active["thermal"]),1/FPS)
            ref_temp[j] = thermal_step(ref_temp[j],ambient,base_power,.25,1/FPS)
            noise = rng.normal(0,[.04,.35,.035,.055])
            if environment == "noise":
                noise[0] += .13*math.sin(observed["t"]*17)
                noise[1] += 1.8*math.sin(observed["t"]*7)
            values = sensor_sample(motion,torque,temp[j],ambient,load,active,reverse,observed["t"]*4,noise)
            baseline = sensor_sample(motion,base_torque,ref_temp[j],ambient,load,{},reverse,observed["t"]*4,[0]*4)
            keys = ("vibration","sound","current","temperature")
            sig = dict(zip(keys, [round(v,4) for v in values]))
            sig.update(landmark=j,baseline=dict(zip(keys,baseline)),activity=motion,reversal=reverse,
                thermal_state_c=round(temp[j]-ref_temp[j],3),latent={k:round(v,3) for k,v in active.items() if v>0},
                truth=[k for k,v in active.items() if v>.015],hysteresis_gap_px=0.,pose_gap_px=0.,cycle_delay_s=0.,score=0)
            signals.append(sig)
            components.append(active)
        twin = [p[:] if p else None for p in observed["points"]]
        for j,active in enumerate(components):
            lag = min(.95,.68*active["slow"]+.18*active["friction"])
            if lag>.02:
                old = POSE[max(0,i-round(lag*FPS))]["points"]
                for k in range(j,7):
                    if twin[k] and old[k]:
                        twin[k]=old[k][:]
            if active["backlash"]:
                pivot=observed["points"][max(0,j-1)]
                if pivot:
                    for k in range(max(1,j),7):
                        if twin[k]:
                            before=twin[k]
                            twin[k]=rotate(before,pivot,.13*active["backlash"]*(1+.3*signals[j]["reversal"]))
                            signals[j]["hysteresis_gap_px"]=max(signals[j]["hysteresis_gap_px"],point_distance(before,twin[k]))
            if active["encoder_error"] and twin[j]:
                twin[j][0] += 18*active["encoder_error"]
        # Shared synthetic camera measurement noise; observed checkpoint input stays immutable.
        for k,p in enumerate(twin):
            if p:
                twin[k]=[round(v+float(rng.normal(0,.22)),3) for v in p]
                if environment=="occlusion" and 6<observed["t"]<8 and k>=4:
                    twin[k]=None
        for j,sig in enumerate(signals):
            comparisons=[(k,p) for k,p in enumerate(twin) if k>=j and p and observed["points"][k]]
            sig["pose_gap_px"] = max((point_distance(p,observed["points"][k]) for k,p in comparisons),default=0.)
            # Estimate lag from current projected observations and past reference only.
            # No injected lag or latent fault state is used by the detector.
            if comparisons and sig["pose_gap_px"] > 3:
                errors=[]
                for lag_frames in range(0,min(i,round(.95*FPS))+1):
                    old=POSE[i-lag_frames]["points"]
                    distances=[point_distance(p,old[k]) for k,p in comparisons if old[k]]
                    errors.append(float(np.mean(distances)) if distances else float("inf"))
                sig["cycle_delay_s"]=round(int(np.argmin(errors))/FPS,3)
            sig["pose_quality"] = len(comparisons)/max(1,sum(p is not None for p in observed["points"][j:]))
        rows.append(dict(observed,twin_points=twin,signals=signals,max_score=0))
    return rows,ambient


def measured_features(sig):
    # pose_gap is reference-relative in this what-if experiment, not a measured fault.
    return sig["z"]+[sig["pose_gap_px"],sig["cycle_delay_s"]]


@lru_cache(maxsize=1)
def normal_detector():
    train_rows,train_x,train_y=[],[],[]
    for seed in range(10):
        env=("nominal","noise","hot","occlusion")[seed%4]
        load=.65+.075*seed
        rows,ambient=raw_run([],seed+70000,load,env)
        for row in rows:
            for sig in row["signals"]:
                train_rows.append(sig)
                train_x.append(covariates(row,sig,load,ambient))
                train_y.append([sig[k] for k in ("vibration","temperature","sound","current")])
    regression=Ridge(alpha=1.).fit(np.asarray(train_x),np.asarray(train_y))
    residual=np.asarray(train_y)-regression.predict(train_x)
    scale=np.maximum(np.std(residual,axis=0),[.06,.12,.5,.06])
    X=np.c_[residual/scale,np.asarray([[s["pose_gap_px"],s["cycle_delay_s"]] for s in train_rows])]
    isolation=IsolationForest(n_estimators=100,random_state=314,n_jobs=-1).fit(X)
    val_x=[]
    for seed in range(4):
        load=.8+.14*seed
        rows,ambient=raw_run([],90000+seed,load,("nominal","noise","hot","occlusion")[seed])
        contexts=np.asarray([covariates(r,s,load,ambient) for r in rows for s in r["signals"]])
        sensors=np.asarray([[s[k] for k in ("vibration","temperature","sound","current")] for r in rows for s in r["signals"]])
        other=np.asarray([[s["pose_gap_px"],s["cycle_delay_s"]] for r in rows for s in r["signals"]])
        val_x.append(np.c_[(sensors-regression.predict(contexts))/scale,other])
    scores=-isolation.score_samples(np.concatenate(val_x))
    threshold=float(np.quantile(scores,.995))
    spread=max(.025,float(np.std(scores)))
    return regression,scale,isolation,threshold,spread


def hypothesis(sig):
    v,temp,sound,current=sig["z"]
    if sig["pose_quality"]<.6:
        return "unknown"
    if sig["cycle_delay_s"]>=.3 and sig["pose_gap_px"]>8:
        return "slow"
    if sig["pose_gap_px"]>12:
        return "backlash"  # position error is ambiguous; label remains a hypothesis
    if current>3 and temp>2 and sound>2:
        return "friction"
    if v>3 and sound>3:
        return "bearing"
    if temp>3:
        return "thermal"
    if v>3 and abs(sound)<2 and abs(current)<2:
        return "sensor_drift"
    return "unknown"


def generate(injections,seed=0,load=1.,environment="nominal"):
    injections=validate_injections(injections)
    seed,load=validate_context(seed,load,environment)
    rows,ambient=raw_run(injections,seed,load,environment)
    regression,scale,isolation,threshold,spread=normal_detector()
    flattened=[s for r in rows for s in r["signals"]]
    contexts=np.asarray([covariates(r,s,load,ambient) for r in rows for s in r["signals"]])
    expected=regression.predict(contexts)
    for sig,pred in zip(flattened,expected):
        sig["z"]=[float(v) for v in ((np.asarray([sig[k] for k in ("vibration","temperature","sound","current")])-pred)/scale)[:3]]
        # Existing UI assumes three z values; current residual is separate.
        sig["current_z"]=(sig["current"]-pred[3])/scale[3]
        sig["learned_expected"]={k:float(v) for k,v in zip(("vibration","temperature","sound","current"),pred)}
    X=np.asarray([s["z"]+[s["current_z"],s["pose_gap_px"],s["cycle_delay_s"]] for s in flattened])
    scores=-isolation.score_samples(X)
    for sig,value in zip(flattened,scores):
        sig["ai_raw_score"]=float(value)
        sig["ai_score"]=round(100/(1+math.exp(-float(np.clip((value-threshold)/spread,-30,30)))))
        sig["ai_alarm"] = bool(value>=threshold and sig["pose_quality"]>=.6)
        sig["score"]=sig["ai_score"]
        rule=max(sig["z"][0]/3,sig["z"][1]/3,sig["z"][2]/3,sig["pose_gap_px"]/12)
        sig["rule_score"]=round(100*(1-math.exp(-.65*max(0,rule))))
    for row in rows:
        row["max_score"]=max(s["score"] for s in row["signals"])
    incidents=[]
    for j in range(7):
        consecutive=0
        event=None
        for i,row in enumerate(rows):
            sig=row["signals"][j]
            consecutive=consecutive+1 if sig["ai_alarm"] else 0
            if consecutive==3:
                name=hypothesis(dict(sig,z=sig["z"]+[sig["current_z"]]))
                info=FAULTS.get(name,dict(label="Bất thường chưa xác định nguyên nhân",cause="Chưa đủ bằng chứng đa nguồn",
                    checks=["Đo lại bằng cảm biến độc lập", "Kiểm tra tải, chương trình, camera và môi trường"]))
                event=dict(id="",start_s=rows[i-2]["t"],detected_s=row["t"],end_s=row["t"],peak_s=row["t"],landmark=j,
                    fault=name,label=info["label"],cause=info["cause"],checks=info["checks"],score=sig["score"],
                    evidence={k:sig[k] for k in ("z","pose_gap_px","cycle_delay_s")},status="AI trên tín hiệu mô phỏng — cần xác nhận")
                incidents.append(event)
            if event and sig["ai_alarm"]:
                event["end_s"]=row["t"]
                if sig["score"]>event["score"]:
                    event.update(score=sig["score"],peak_s=row["t"],evidence={k:sig[k] for k in ("z","pose_gap_px","cycle_delay_s")})
            if not sig["ai_alarm"]:
                event=None
    incidents.sort(key=lambda x:(x["detected_s"],x["landmark"]))
    for n,event in enumerate(incidents,1):
        event["id"]=f"AI3-{n}"
    return dict(duration_s=RECORDING["duration_s"],fps=FPS,landmarks=RECORDING["landmarks"],faults=FAULTS,
        injections=injections,seed=seed,load=load,environment=environment,timeline=rows,incidents=incidents,
        context=dict(ambient_c=ambient),
        method=dict(name="shared-surrogate + learned-normal v3",version="3.0.0",detector="Ridge normal envelope + IsolationForest residuals; 3 consecutive frames",
            score="0..100 transformed anomaly score, not failure probability; threshold 50",
            training="10 normal synthetic replay sessions; 4 independent normal validation sessions; no fault labels",
            delay="nearest past reference projection, not injected lag",sensor_sample="shared physics.sensor_sample; aggregate envelopes only"),
        mapping=dict(joints=[f"J{k+1}" for k in range(7)],landmarks=RECORDING["landmarks"],
            relation="Landmark regions and mechanical joints are independent selectors; no 1:1 assignment asserted"),
        provenance=dict(video="500-frame RGB DREAM replay, 120 unique frames",pose=RECORDING["method"],
            sensors="all condition channels are synthetic; shared lumped surrogate is not OEM-calibrated",
            validation="synthetic normal calibration only; no measured faults; no field accuracy"))
