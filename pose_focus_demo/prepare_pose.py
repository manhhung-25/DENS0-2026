"""Diagnostic extraction of visible cyan markers from the rendered clip.

This is image analysis of a pre-annotated video, not a new HoRoPose inference.
"""
import json
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
ROOT.mkdir(exist_ok=True)
SOURCE = Path(os.environ.get("DENSO_SOURCE_VIDEO", str(ROOT.parent / "panda_repro" / "artifacts" / "panda_horopose_health_demo.mp4")))
NAMES = ["L0 / đế", "L2 / vai", "L3 / khuỷu dưới", "L4 / khuỷu trên", "L6 / cẳng tay", "L7 / cổ tay", "EE / bộ kẹp"]
SEED_FRAME = 150
SEEDS = np.array([[540,639],[545,461],[664,334],[644,300],[472,192],[442,142],[383,183]],dtype=float)
CROP_X,CROP_Y,CROP_W,CROP_H = 0,68,840,646


def detect(frame):
    b,g,r=[frame[:,:,i].astype(np.int16) for i in range(3)]
    mask=np.uint8((b-r>65)&(g-r>50)&(b>150))*255
    mask[:85,:]=0;mask[:,840:]=0
    cnt,hier=cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    pts=[]
    if hier is None:
        return np.empty((0,2),dtype=float)
    for i,c in enumerate(cnt):
        if hier[0][i][3]<0:
            continue
        area=cv2.contourArea(c)
        if not 18<area<70:
            continue
        mo=cv2.moments(c)
        if mo["m00"]<=0:
            continue
        x,y=mo["m10"]/mo["m00"],mo["m01"]/mo["m00"]
        if 520<x<650 and 325<y<385:  # source video's ACC/MC/TMP annotation boxes
            continue
        pts.append((x,y))
    return np.array(pts,dtype=float).reshape((-1,2))


def track(frames, candidate_lists):
    output=[None]*len(frames)
    output[SEED_FRAME]=[(*p,1.0) for p in SEEDS]
    for direction in (1,-1):
        previous=SEEDS.copy()
        rng=range(SEED_FRAME+direction,len(frames),direction) if direction==1 else range(SEED_FRAME-1,-1,-1)
        for i in rng:
            cand=candidate_lists[i]
            row=[None]*len(NAMES)
            used=set()
            def choose(j, valid, cost):
                choices=[(cost(p),k) for k,p in enumerate(cand) if k not in used and valid(p)]
                if not choices:return None
                k=min(choices)[1];used.add(k);previous[j]=cand[k]
                row[j]=(float(cand[k,0]),float(cand[k,1]),1.0)
                return cand[k]
            for j,limit in enumerate((18,25,32,42)):
                choose(j,lambda p,j=j,limit=limit:np.linalg.norm(p-SEEDS[j])<limit,
                       lambda p,j=j:np.linalg.norm(p-SEEDS[j]))
            l4=np.array(row[3][:2]) if row[3] else SEEDS[3]
            l6=choose(4,lambda p:170<np.linalg.norm(p-l4)<235 and p[0]<l4[0]-80 and p[1]<l4[1]+20,
                      lambda p:abs(np.linalg.norm(p-l4)-200)+.12*np.linalg.norm(p-previous[4]))
            if l6 is not None:
                l7=choose(5,lambda p:40<np.linalg.norm(p-l6)<85 and p[0]<l6[0]+5 and p[1]<l6[1]+15,
                          lambda p:abs(np.linalg.norm(p-l6)-57)+.12*np.linalg.norm(p-previous[5]))
                if l7 is not None:
                    choose(6,lambda p:45<np.linalg.norm(p-l7)<100 and p[0]<l7[0]-25,
                           lambda p:abs(np.linalg.norm(p-l7)-72)+.12*np.linalg.norm(p-previous[6]))
            output[i]=row
    # A few kitchen highlights resemble cyan rings around L6. Mark isolated
    # assignments that disagree with the local trajectory as missing.
    cleaned = [[p for p in row] for row in output]
    for i, row in enumerate(output):
        p = row[4]
        if p is None:
            continue
        neighbours = [output[k][4][:2] for k in range(max(0, i-4), min(len(output), i+5)) if output[k][4] is not None]
        if len(neighbours) >= 4:
            center = np.median(np.asarray(neighbours), axis=0)
            if np.linalg.norm(np.asarray(p[:2]) - center) > 15:
                cleaned[i][4] = None
    return cleaned


def main():
    cap=cv2.VideoCapture(str(SOURCE))
    fps=cap.get(cv2.CAP_PROP_FPS)
    frames=[]
    while True:
        ok,f=cap.read()
        if not ok:break
        frames.append(f)
    cap.release()
    if abs(fps-30)>.01 or len(frames)<300:
        raise ValueError(f"Unexpected source video: {len(frames)} frames at {fps} fps")
    candidates=[detect(f) for f in frames]
    tracked=track(frames,candidates)
    # Preserve original footage and its existing cyan annotations. Cropping removes
    # only the synthetic sensor dashboard at the right of the source file.
    diagnostic_video=ROOT/"robot_from_overlay.mp4"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(SOURCE),"-vf",f"crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y}","-an","-c:v","libx264","-crf","18","-preset","fast","-pix_fmt","yuv420p",str(diagnostic_video)],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-ss","5","-i",str(diagnostic_video),"-frames:v","1",str(ROOT/"poster_from_overlay.jpg")],check=True)
    records=[]
    for i,row in enumerate(tracked):
        points=[]
        for p in row:
            points.append(None if p is None else [round(p[0]-CROP_X,1),round(p[1]-CROP_Y,1)])
        coverage=sum(p is not None for p in points)
        records.append({"t":round(i/fps,4),"points":points,"coverage":coverage})
    payload={"source":"Cropped Panda HoRoPose repro video; 2D points extracted from rendered cyan overlay",
             "fps":fps,"duration_s":round(len(frames)/fps,4),"frame_count":len(frames),
             "width":CROP_W,"height":CROP_H,"landmarks":NAMES,
             "method":"Color segmentation + contour-hole detection + temporal nearest-neighbor tracking of the cyan pose markers already burned into the source video. Not independent HoRoPose inference.",
             "frames":records}
    (ROOT/"pose_recording_from_overlay.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("frames",len(frames),"duration",len(frames)/fps,"coverage_mean",round(sum(x["coverage"] for x in records)/len(records),2))
    for t in (0,3,5,9,12,15):
        q=records[min(len(records)-1,int(t*fps))]
        print(t,q["coverage"],q["points"])


if __name__=="__main__":main()
