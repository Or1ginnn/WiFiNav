"""Standalone pilot diagnostic plot from saved reports; never fed to agents."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch_dir
    report = json.loads((batch / "pilot_report.json").read_text())
    ids = [e["episode_id"] for e in report["episodes"]]
    layouts = ["start", "near", "far"]
    heat = np.full((len(ids), len(layouts)), np.nan)
    for row in report["cases"]:
        if row["communication"]:
            heat[ids.index(row["episode_id"]), layouts.index(row["layout_id"])] = 100*row["communication"]["outage_ratio"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 6), gridspec_kw={"width_ratios":[1,1.4]})
    colors = ["#297c58" if e["success"] else "#b85252" for e in report["episodes"]]
    axes[0].barh(range(len(ids)), [e["spl"] for e in report["episodes"]], color=colors)
    axes[0].set_yticks(range(len(ids)))
    axes[0].set_yticklabels(ids)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 1)
    axes[0].set_xlabel("SPL (green=success; red=failure)")
    axes[0].set_ylabel("Fixed source episode ID")
    axes[0].set_title("10 NoSignal rollouts")
    image = axes[1].imshow(heat, aspect="auto", vmin=0, vmax=100, cmap="YlOrRd")
    axes[1].set_yticks(range(len(ids)))
    axes[1].set_yticklabels(ids)
    axes[1].set_xticks(range(len(layouts)))
    axes[1].set_xticklabels(layouts)
    axes[1].set_title("30 AP replays: outage % of motion time")
    for i in range(len(ids)):
        for j in range(len(layouts)):
            text = f"{heat[i,j]:.1f}" if np.isfinite(heat[i,j]) else "missing"
            axes[1].text(j, i, text, ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(image, ax=axes[1], label="Outage time (%)")
    fig.suptitle("R2R-Conn development pilot: known geometry, proxy radio field")
    fig.text(0.5, 0.01, "All selected episodes retained. AP replays are not independent navigation samples. Oracle benefit untested.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(batch / "pilot_overview.png", dpi=160)
    fig.savefig(batch / "pilot_overview.pdf")
    plt.close(fig)
    print(batch / "pilot_overview.png")


if __name__ == "__main__":
    main()
