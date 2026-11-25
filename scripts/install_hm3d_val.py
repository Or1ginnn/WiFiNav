#!/usr/bin/env python3
"""Validate and install the official HM3D v0.2 archives for ObjectNav val."""
import argparse
import fcntl
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re
import tarfile
import tempfile

from install_hm3d_train import EPISODES, PROJECT, ROOT_CONFIG, SCENES, extract_files, sha256


ARCHIVE_ROOT = PROJECT / "runtime/data_imports/hm3d_val_v0.2"
ARCHIVES = {
    kind: f"hm3d-val-{kind}-v0.2.tar" for kind in ("habitat", "semantic-annots", "semantic-configs")
}
VAL_CONFIG = "hm3d_annotated_val_basis.scene_dataset_config.json"
RECEIPT = EPISODES.with_name("hm3d_objectnav_v2_val_install.json")


def install(archives):
    import habitat_sim

    refs = json.loads(EPISODES.read_text())["splits"]["val"]["scene_refs"]
    if not refs or len(refs) != len(set(refs)):
        raise ValueError("Expected unique official val scene references")
    wanted = {"habitat": [], "semantic-annots": [], "semantic-configs": [ROOT_CONFIG, VAL_CONFIG]}
    for ref in refs:
        match = re.fullmatch(r"hm3d_v0\.2/val/(\d{5}-([A-Za-z0-9]+))/\2\.basis\.glb", ref)
        if not match:
            raise ValueError(f"Unexpected official val scene reference: {ref}")
        folder, scan = match.groups()
        wanted["habitat"].extend(f"{folder}/{scan}{ext}" for ext in (".basis.glb", ".basis.navmesh"))
        wanted["semantic-annots"].extend(f"{folder}/{scan}{ext}" for ext in (".semantic.glb", ".semantic.txt"))
    if RECEIPT.exists():
        raise FileExistsError(RECEIPT)
    inputs = {}
    staged = Path(tempfile.mkdtemp(prefix="stage_", dir=archives))
    files = {}
    for kind, name in ARCHIVES.items():
        source = archives / name
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(source)
        inputs[name] = {"bytes": source.stat().st_size, "sha256": sha256(source)}
        destinations = {member: staged / ("val" if member != ROOT_CONFIG else "") / member for member in wanted[kind]}
        with tarfile.open(source, "r:") as archive:
            for member, record in extract_files(archive, wanted[kind], destinations):
                files[str(destinations[member].relative_to(staged))] = record

    root_config = SCENES / ROOT_CONFIG
    if files[ROOT_CONFIG]["sha256"] != sha256(root_config):
        raise ValueError("Official root configuration and installed configuration differ")
    paths = json.loads(root_config.read_text())["stages"]["paths"][".glb"]
    for ref in refs:
        relative = Path(ref).relative_to("hm3d_v0.2")
        if not any(fnmatchcase(str(relative), pattern) for pattern in paths):
            raise ValueError(f"Installed scene configuration does not cover {ref}")
        finder = habitat_sim.PathFinder()
        if not finder.load_nav_mesh(str((staged / relative).with_suffix(".navmesh"))) or not finder.is_loaded:
            raise ValueError(f"Habitat could not load {ref}")

    # Compare existing assets before moving any staged file. The known public
    # sample stays at its current path when it matches the authorized archive.
    pending = []
    for name, record in files.items():
        destination = SCENES / name
        if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents if parent != PROJECT):
            raise ValueError(f"Symlink in val installation target: {destination}")
        if destination.exists():
            if not destination.is_file() or destination.stat().st_nlink != 1 or sha256(destination) != record["sha256"]:
                raise ValueError(f"Existing asset differs from the official archive: {destination}")
        else:
            pending.append(name)

    for name in pending:
        destination = SCENES / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Refuse concurrent replacement. The lock serializes this installer.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        (staged / name).rename(destination)
    receipt = {"scene_count": len(refs), "archive_inputs": inputs, "files": files,
               "new_files": len(pending), "habitat_sim": habitat_sim.__version__}
    with RECEIPT.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    print(f"Validated all {len(refs)} official val scenes. Wrote {RECEIPT}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, default=ARCHIVE_ROOT)
    args = parser.parse_args()
    archives = args.archives.resolve()
    if (PROJECT / "runtime/data_imports") not in archives.parents:
        parser.error("Archives must be staged below runtime/data_imports")
    for name in ARCHIVES.values():
        if not (archives / name).is_file():
            parser.error(f"Missing archive: {archives / name}")
    with (archives / "install.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install(archives)


if __name__ == "__main__":
    main()
