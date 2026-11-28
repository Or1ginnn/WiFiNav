"""Connect frozen upstream VLFM to the WiFiNav RGB-D development runner."""
from contextlib import redirect_stdout
from hashlib import sha256
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import numpy as np


VLFM_REVISION = "584ed56008754fde7997d904983607def8328322"
POLICY_ACTIONS = ("stop", "move_forward", "turn_left", "turn_right")
GOALS = ("chair", "bed", "plant", "toilet", "tv_monitor", "sofa")
DEFAULT_CAMERA = {"width": 640, "height": 480, "hfov": 90., "height_m": .88,
                  "depth_min_m": 0., "depth_max_m": 10.}


def normalize_depth(depth, minimum, maximum):
    distance = np.nan_to_num(depth, nan=maximum, posinf=maximum, neginf=minimum)
    return ((np.clip(distance, minimum, maximum) - minimum) / (maximum - minimum)).astype(np.float32)


class VLFM:
    """One isolated policy subprocess per episode."""

    requires_rgb = True

    def __init__(self, camera=None):
        self.camera = camera

    @staticmethod
    def metadata(camera=None):
        path = Path(os.environ["WIFINAV_VLFM_POINTNAV"])
        receipt = Path(os.environ["WIFINAV_VLFM_RECEIPT"])
        sensor = {"width": 640, "height": 480, "hfov": 90., "height_m": .88,
                  "normalized_depth_max_m": DEFAULT_CAMERA["depth_max_m"]}
        if camera is not None:
            sensor.update({key: camera[key] for key in ("width", "height", "hfov", "height_m")})
            sensor["normalized_depth_min_m"] = camera["depth_min_m"]
            sensor["normalized_depth_max_m"] = camera["depth_max_m"]
        return {
            "policy_revision": VLFM_REVISION,
            "pointnav_sha256": sha256(path.read_bytes()).hexdigest(),
            "model_receipt_sha256": sha256(receipt.read_bytes()).hexdigest(),
            "policy_interpreter": os.environ["WIFINAV_VLFM_PYTHON"],
            "sensor": sensor,
        }

    def reset(self):
        env = {**os.environ, "PYTHONPATH": os.environ["WIFINAV_VLFM_PYTHONPATH"]}
        command = [env["WIFINAV_VLFM_PYTHON"], __file__]
        if self.camera is not None:
            command.append(json.dumps(self.camera))
        self.process = subprocess.Popen(
            command,
            cwd=env["WIFINAV_VLFM_WORKDIR"], env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )

    def act(self, obs):
        if obs.rgb is None:
            raise ValueError("VLFM requires a rendered RGB observation")
        if obs.rssi_dbm is not None:
            raise ValueError("The VLFM baseline is frozen in the NoSignal track")
        payload = (GOALS.index(obs.category), np.ascontiguousarray(obs.rgb[:, :, :3]),
                   obs.depth_m, obs.x, obs.z, obs.yaw)
        try:
            # This pipe is exclusively between the evaluation process and
            # its own local worker. No network request can supply a frame.
            pickle.dump(payload, self.process.stdin, protocol=5)
            self.process.stdin.flush()
            action, self.target_observation = pickle.load(self.process.stdout)
        except (BrokenPipeError, EOFError) as error:
            raise RuntimeError(f"VLFM worker closed early, status {self.process.poll()}") from error
        if action not in range(len(POLICY_ACTIONS)):
            raise ValueError(f"Unsupported upstream action {action}")
        return POLICY_ACTIONS[action]

    def close(self):
        process = getattr(self, "process", None)
        if process is None:
            return
        process.stdin.close()
        process.stdout.close()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def worker(camera):
    import torch
    from habitat_baselines.common.tensor_dict import TensorDict
    from vlfm.policy.habitat_policies import HabitatITMPolicyV2, VLFMConfig

    torch.manual_seed(0)
    config = VLFMConfig()
    config.pointnav_policy_path = os.environ["WIFINAV_VLFM_POINTNAV"]
    kwargs = {field: getattr(config, field) for field in config.kwaarg_names}
    minimum, maximum = camera["depth_min_m"], camera["depth_max_m"]
    policy = HabitatITMPolicyV2(camera_height=camera["height_m"], min_depth=minimum, max_depth=maximum,
                               camera_fov=camera["hfov"], image_width=camera["width"],
                               visualize=False, compute_frontiers=True, **kwargs)
    hidden = None
    previous = torch.zeros((1, 1), dtype=torch.long, device="cuda")
    masks = torch.zeros((1, 1), dtype=torch.bool, device="cuda")
    while True:
        try:
            goal, rgb, depth, x, z, yaw = pickle.load(sys.stdin.buffer)
        except EOFError:
            return
        distance = normalize_depth(depth, minimum, maximum)
        inputs = TensorDict({
            "objectgoal": torch.tensor([[goal]], dtype=torch.long),
            "rgb": torch.from_numpy(rgb[None]),
            "depth": torch.from_numpy(distance[None, :, :, None]).to("cuda"),
            "gps": torch.tensor([[-z, x]], dtype=torch.float32),
            "compass": torch.tensor([[yaw]], dtype=torch.float32),
            "heading": torch.tensor([[0.]], dtype=torch.float32),
        })
        with torch.inference_mode():
            result = policy.act(inputs, hidden, previous, masks, deterministic=True)
        previous, hidden = result.actions, result.rnn_hidden_states
        masks.fill_(True)
        target_mask = policy._object_masks
        valid = depth[(target_mask > 0) & np.isfinite(depth) & (depth > 0)] if target_mask is not None else ()
        yield int(previous.item()), {
            "pixels": len(valid), "depth_p25_m": float(np.quantile(valid, .25)) if len(valid) else None,
        }


if __name__ == "__main__":
    camera = json.loads(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAMERA
    protocol = sys.stdout.buffer
    with redirect_stdout(sys.stderr):
        for response in worker(camera):
            pickle.dump(response, protocol, protocol=5)
            protocol.flush()
