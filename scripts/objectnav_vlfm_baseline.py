"""Connect frozen upstream VLFM to the WiFiNav RGB-D development runner."""
from contextlib import redirect_stdout
from hashlib import sha256
import os
from pathlib import Path
import pickle
import subprocess
import sys

import numpy as np


VLFM_REVISION = "584ed56008754fde7997d904983607def8328322"
POLICY_ACTIONS = ("stop", "move_forward", "turn_left", "turn_right")
GOALS = ("chair", "bed", "plant", "toilet", "tv_monitor", "sofa")
MAX_DEPTH_M = 10.


class VLFM:
    """One isolated policy subprocess per episode."""

    requires_rgb = True

    @staticmethod
    def metadata():
        path = Path(os.environ["WIFINAV_VLFM_POINTNAV"])
        receipt = Path(os.environ["WIFINAV_VLFM_RECEIPT"])
        return {
            "policy_revision": VLFM_REVISION,
            "pointnav_sha256": sha256(path.read_bytes()).hexdigest(),
            "model_receipt_sha256": sha256(receipt.read_bytes()).hexdigest(),
            "policy_interpreter": os.environ["WIFINAV_VLFM_PYTHON"],
            "sensor": {"width": 640, "height": 480, "hfov": 90., "height_m": .88,
                       "normalized_depth_max_m": MAX_DEPTH_M},
        }

    def reset(self):
        env = {**os.environ, "PYTHONPATH": os.environ["WIFINAV_VLFM_PYTHONPATH"]}
        self.process = subprocess.Popen(
            [env["WIFINAV_VLFM_PYTHON"], __file__],
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


def worker():
    import torch
    from habitat_baselines.common.tensor_dict import TensorDict
    from vlfm.policy.habitat_policies import HabitatITMPolicyV2, VLFMConfig

    torch.manual_seed(0)
    config = VLFMConfig()
    config.pointnav_policy_path = os.environ["WIFINAV_VLFM_POINTNAV"]
    kwargs = {field: getattr(config, field) for field in config.kwaarg_names}
    policy = HabitatITMPolicyV2(camera_height=.88, min_depth=0., max_depth=MAX_DEPTH_M, camera_fov=90.,
                               image_width=640, visualize=False, compute_frontiers=True, **kwargs)
    hidden = None
    previous = torch.zeros((1, 1), dtype=torch.long, device="cuda")
    masks = torch.zeros((1, 1), dtype=torch.bool, device="cuda")
    while True:
        try:
            goal, rgb, depth, x, z, yaw = pickle.load(sys.stdin.buffer)
        except EOFError:
            return
        distance = np.nan_to_num(depth, nan=MAX_DEPTH_M, posinf=MAX_DEPTH_M, neginf=0.)
        distance = np.clip(distance / MAX_DEPTH_M, 0., 1.).astype(np.float32)
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
    protocol = sys.stdout.buffer
    with redirect_stdout(sys.stderr):
        for response in worker():
            pickle.dump(response, protocol, protocol=5)
            protocol.flush()
