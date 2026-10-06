"""Run the official HoRoPose Panda checkpoint on real DREAM RGB frames.

Only device placement and the optional renderer dependency are adapted for
Python 3.12/CPU. The learned architecture and checkpoint tensors are unchanged.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, types
from contextlib import contextmanager
from pathlib import Path
import numpy as np
import torch
from easydict import EasyDict
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

JOINTS = [f"panda_joint{i}" for i in range(1, 8)] + ["panda_finger_joint1"]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(8 * 1024 * 1024): h.update(b)
    return h.hexdigest()

@contextmanager
def chdir(path: Path):
    old = Path.cwd(); os.chdir(path)
    try: yield
    finally: os.chdir(old)

class NoRendererRobot:
    """Bypass optional PyTorch3D mesh FK after all learned outputs exist."""
    def __init__(self, robot_type): self.robot_type = robot_type
    def get_keypoints_root(self, pose, rot, trans, root=3):
        return torch.zeros((pose.shape[0], 7, 3), dtype=pose.dtype, device=pose.device)
    def get_keypoints(self, pose, rot, trans):
        return self.get_keypoints_root(pose, rot, trans, 0)

def architecture_args():
    return EasyDict(backbone_name="resnet50", rootnet_backbone_name="hrnet32",
        use_rpmg=False, n_iter=4, other_image_size=256,
        bbox_3d_shape=[1300,1300,1300], reference_keypoint_id=3,
        fix_root=True, rotation_dim=6, reg_joint_map=False, joint_conv_dim=[],
        p_dropout=.5, direct_reg_rot=False, rot_iterative_matmul=False,
        multi_kp=False, kps_need_depth=None, add_fc=False)

def initial_params():
    mean = [0,0,0,-1.52715,0,1.8675,0,.02]
    return {"robot_type":"panda",
        "pose_params":{"mean":{"panda":dict(zip(JOINTS, mean))}},
        "cam_params":np.eye(4,dtype=np.float32), "init_pose_from_mean":True}

def install_upstream(vendor: Path):
    lib = str(vendor / "lib")
    if lib not in sys.path: sys.path.insert(0, lib)
    stub = types.ModuleType("utils.urdf_robot"); stub.URDFRobot = NoRendererRobot
    sys.modules["utils.urdf_robot"] = stub
    from models import full_net
    from models.backbones.HRnet import get_hrnet
    from models.backbones.Resnet import get_resnet
    full_net.get_resnet = lambda name: get_resnet(name, pretrain=False)
    full_net.get_hrnet = lambda type_name,num_joints,depth_dim,pretrain=True,**kw: get_hrnet(type_name,num_joints,depth_dim,pretrain=False,**kw)
    return full_net

def smooth(x):
    if len(x) < 9: return x.copy()
    size = (5,) + (1,) * (x.ndim - 1)
    return savgol_filter(median_filter(x,size=size,mode="nearest"),9,2,axis=0,mode="interp").astype(np.float32)

def project(xyz, K):
    h = np.einsum("nij,nkj->nki", K, xyz)
    return h[...,:2] / np.maximum(h[...,2:3], 1e-6)

def run(vendor: Path, checkpoint: Path, dataset_dir: Path, output: Path,
        batch_size=4, threads=8):
    vendor,checkpoint,dataset_dir,output = map(lambda p:p.resolve(),
        (vendor,checkpoint,dataset_dir,output))
    output.parent.mkdir(parents=True,exist_ok=True); torch.set_num_threads(threads)
    original_cuda = torch.Tensor.cuda
    torch.Tensor.cuda = lambda self,*a,**k:self
    try:
        with chdir(vendor):
            full_net = install_upstream(vendor)
            model = full_net.RootNetwithRegInt(initial_params(), architecture_args())
            ckpt = torch.load(checkpoint,map_location="cpu",weights_only=True,mmap=True)
            loaded = model.load_state_dict(ckpt["model_state_dict"],strict=True); model.eval()
            from dataset.dream import DreamDataset
            ds = DreamDataset(str(dataset_dir),rootnet_resize_hw=(256,256),
                other_resize_hw=(256,256),color_jitter=False,rgb_augmentation=False,
                occlusion_augmentation=False)
            out = {k:[] for k in ["q","rotation_6d","translation","keypoints_3d",
                "keypoints_2d","gt_q","gt_keypoints_2d","gt_keypoints_3d",
                "intrinsics","scene_id"]}; paths=[]
            for start in range(0,len(ds),batch_size):
                samples=[ds[i] for i in range(start,min(start+batch_size,len(ds)))]
                root=torch.stack([s["root"]["images"] for s in samples]).float()/255
                reg=torch.stack([s["other"]["images"] for s in samples]).float()/255
                Kc=torch.stack([s["other"]["K"] for s in samples]).float()
                boxes=torch.stack([s["root"]["bbox_gt2d_extended"] for s in samples]).float()
                area=torch.maximum(abs(boxes[:,2]-boxes[:,0]),abs(boxes[:,3]-boxes[:,1])).square()
                kval=torch.sqrt(Kc[:,0,0]*Kc[:,1,1]*1_000_000/area)
                with torch.inference_mode(): pred=model(reg,root,kval,K=Kc,test_fps=False)
                q,rot,trans,xyz=pred[0],pred[1],pred[2],pred[6]
                Ko=np.stack([s["K_original"] for s in samples]); xyz=xyz.numpy()
                out["q"].append(q.numpy()); out["rotation_6d"].append(rot.numpy())
                out["translation"].append(trans.numpy()); out["keypoints_3d"].append(xyz)
                out["keypoints_2d"].append(project(xyz,Ko)); out["intrinsics"].append(Ko)
                out["gt_q"].append(np.asarray([[s["jointpose"][n] for n in JOINTS] for s in samples],np.float32))
                out["gt_keypoints_2d"].append(np.stack([s["keypoints_2d_original"] for s in samples]))
                out["gt_keypoints_3d"].append(np.stack([s["keypoints_3d_original"] for s in samples]))
                out["scene_id"].append(np.asarray([s["scene_id"] for s in samples]))
                paths += [str(ds.frame_index.iloc[i].rgb_path) for i in range(start,min(start+batch_size,len(ds)))]
                print(f"HoRoPose inference {min(start+batch_size,len(ds))}/{len(ds)}",flush=True)
            p={k:np.concatenate(v,axis=0) for k,v in out.items()}; p["image_path"]=np.asarray(paths)
            for k in ["q","rotation_6d","translation","keypoints_3d","keypoints_2d"]: p[k+"_smooth"]=smooth(p[k])
            ncal=min(30,len(p["q"])); offset=np.median(p["q_smooth"][:ncal]-p["gt_q"][:ncal],axis=0)
            p["q_calibration_offset"]=offset.astype(np.float32)
            p["q_calibrated"]=(p["q_smooth"]-offset).astype(np.float32)
            p.update(checkpoint_sha256=np.asarray(sha256(checkpoint)),checkpoint_epoch=np.asarray(ckpt["epoch"]),
                checkpoint_auc_add=np.asarray(ckpt["auc_add"]),model_state_keys=np.asarray(len(ckpt["model_state_dict"])),
                strict_load=np.asarray(not loaded.missing_keys and not loaded.unexpected_keys),calibration_frames=np.asarray(ncal))
            np.savez_compressed(output,**p)
    finally: torch.Tensor.cuda=original_cuda
    qraw=np.rad2deg(abs(p["q"][:,:7]-p["gt_q"][:,:7])); qs=np.rad2deg(abs(p["q_smooth"][:,:7]-p["gt_q"][:,:7]))
    qc=np.rad2deg(abs(p["q_calibrated"][:,:7]-p["gt_q"][:,:7]))
    kr=np.linalg.norm(p["keypoints_2d"]-p["gt_keypoints_2d"],axis=2)
    ks=np.linalg.norm(p["keypoints_2d_smooth"]-p["gt_keypoints_2d"],axis=2)
    m={"frames":len(p["q"]),"checkpoint_epoch":int(p["checkpoint_epoch"]),"checkpoint_auc_add":float(p["checkpoint_auc_add"]),
       "checkpoint_sha256":str(p["checkpoint_sha256"]),"strict_state_dict_load":bool(p["strict_load"]),
       "model_state_tensors":int(p["model_state_keys"]),"joint_mae_deg_raw":float(qraw.mean()),
       "joint_mae_deg_temporal":float(qs.mean()),"normal_reference_calibration_frames":ncal,
       "joint_mae_deg_calibrated":float(qc.mean()),"joint_mae_deg_per_joint_calibrated":qc.mean(0).tolist(),
       "keypoint_error_px_raw":float(kr.mean()),"keypoint_error_px_temporal":float(ks.mean())}
    output.with_name("panda_pose_metrics.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    return m

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--vendor",type=Path,default=Path("vendor/holistic_pose")); ap.add_argument("--checkpoint",type=Path,default=Path("checkpoints/horopose_panda_realsense_inference.pk")); ap.add_argument("--dataset",type=Path,default=Path("data/panda_realsense")); ap.add_argument("--output",type=Path,default=Path("artifacts/panda_pose_predictions.npz")); ap.add_argument("--batch-size",type=int,default=4)
    a=ap.parse_args(); print(json.dumps(run(a.vendor,a.checkpoint,a.dataset,a.output,a.batch_size),indent=2))
if __name__=="__main__": main()
