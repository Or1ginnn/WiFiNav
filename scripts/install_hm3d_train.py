#!/usr/bin/env python3
"""Install the HM3D v0.2 scenes referenced by the official ObjectNav train split."""
import argparse
import fcntl
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import re
import struct
import tarfile
import tempfile

from download_hm3d_train import ARCHIVES, ROOT as ARCHIVE_ROOT


PROJECT = Path(__file__).resolve().parents[1]
SCENES = PROJECT / "data/scene_datasets/hm3d_v0.2"
EPISODES = PROJECT / "data/_manifests/hm3d_objectnav_v2_episodes.json"
RECEIPT = PROJECT / "data/_manifests/hm3d_objectnav_v2_train_install.json"
ROOT_CONFIG = "hm3d_annotated_basis.scene_dataset_config.json"
TRAIN_CONFIG = "hm3d_annotated_train_basis.scene_dataset_config.json"
BUFFER_SIZE = 8 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(BUFFER_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_scene_files(scene_refs):
    geometry, annotations = [], []
    for ref in scene_refs:
        match = re.fullmatch(r"hm3d_v0\.2/train/(\d{5}-([A-Za-z0-9]+))/\2\.basis\.glb", ref)
        if not match:
            raise ValueError(f"Unexpected ObjectNav train scene reference: {ref}")
        scene_folder, scan = match.groups()
        geometry.extend(f"{scene_folder}/{scan}.{suffix}" for suffix in ("basis.glb", "basis.navmesh"))
        annotations.extend(f"{scene_folder}/{scan}.{suffix}" for suffix in ("semantic.glb", "semantic.txt"))
    if len(set(geometry)) != len(geometry):
        raise ValueError("Repeated geometry reference in the episode manifest.")
    return geometry, annotations


def verify_archives(archive_root, manifest):
    expected = manifest["files"]
    if set(expected) != set(ARCHIVES):
        raise ValueError("The manifest must describe all three official train archives.")
    names = {}
    for name in ARCHIVES:
        canonical = archive_root / name
        partial = archive_root / (name + ".part")
        if canonical.exists() and partial.exists():
            raise ValueError(f"Both archive names exist for {name}")
        path = canonical if canonical.exists() else partial
        record = expected[name]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != record["bytes"]:
            raise ValueError(f"Missing or incomplete archive: {path}")
        if sha256(path) != record["sha256"]:
            raise ValueError(f"SHA256 mismatch: {path}")
        names[name] = path
        print(f"Verified archive {name}, {record['bytes']:,} bytes", flush=True)
    for name, path in names.items():
        canonical = archive_root / name
        if path != canonical:
            path.rename(canonical)
        names[name] = canonical
    return names


def extract_files(archive, members, destinations):
    picked = {}
    wanted = set(members)
    for member in archive.getmembers():
        if member.name in wanted:
            if member.name in picked or not member.isfile() or not member.size:
                raise ValueError(f"Unexpected tar member: {member.name}")
            picked[member.name] = member
    if picked.keys() != wanted:
        raise ValueError(f"Missing requested files: {sorted(wanted - picked.keys())[:5]}")
    for name, member in picked.items():
        path = destinations[name]
        path.parent.mkdir(exist_ok=True, parents=True)
        digest = hashlib.sha256()
        with archive.extractfile(member) as source, path.open("xb") as sink:
            for block in iter(lambda: source.read(BUFFER_SIZE), b""):
                digest.update(block)
                sink.write(block)
        stat = path.stat()
        if stat.st_size != member.size or stat.st_nlink != 1:
            raise ValueError(f"Unexpected extracted file: {path}")
        if path.suffix == ".glb":
            with path.open("rb") as f:
                magic, version, length = struct.unpack("<4sII", f.read(12))
            if (magic, version, length) != (b"glTF", 2, stat.st_size):
                raise ValueError(f"Invalid GLB header: {path}")
        if path.name.endswith(".semantic.txt"):
            with path.open(encoding="utf-8") as f:
                if not f.readline().startswith("HM3D Semantic"):
                    raise ValueError(f"Invalid annotation descriptor: {path}")
        yield name, {"bytes": stat.st_size, "sha256": digest.hexdigest()}


def check_habitat(staging, scene_refs):
    import habitat
    from habitat.config.default_structured_configs import DatasetConfig
    import habitat_sim

    navmeshes = 0
    for ref in scene_refs:
        scene = staging / Path(ref).relative_to("hm3d_v0.2")
        finder = habitat_sim.PathFinder()
        if not finder.load_nav_mesh(str(scene.with_suffix(".navmesh"))) or not finder.is_loaded:
            raise ValueError(f"Habitat could not read {scene}")
        navmeshes += 1

    scan = Path(scene_refs[0]).name.removesuffix(".basis.glb")
    dataset_config = DatasetConfig(
        type="ObjectNav-v1", split="train",
        data_path="data/datasets/objectnav/hm3d/v2/{split}/{split}.json.gz",
        scenes_dir="data/scene_datasets", content_scenes=[scan],
    )
    dataset = habitat.make_dataset(dataset_config.type, config=dataset_config)
    if not dataset.episodes or {ep.scene_id for ep in dataset.episodes} != {"data/scene_datasets/" + scene_refs[0]}:
        raise ValueError("The checked ObjectNav shard did not match the installed scene.")
    sim_config = habitat_sim.SimulatorConfiguration()
    sim_config.scene_id = str(staging / Path(scene_refs[0]).relative_to("hm3d_v0.2"))
    sim_config.scene_dataset_config_file = str(staging / ROOT_CONFIG)
    sim_config.create_renderer = False
    sim_config.enable_physics = False
    with habitat_sim.Simulator(habitat_sim.Configuration(sim_config, [habitat_sim.agent.AgentConfiguration()])) as sim:
        semantic_objects = len(sim.semantic_scene.objects)
        if (not semantic_objects or not sim.pathfinder.is_loaded
                or not sim.pathfinder.is_navigable(dataset.episodes[0].start_position)):
            raise ValueError("The headless scene did not load with semantics and a navigable start.")
    return {"habitat_lab": habitat.__version__, "habitat_sim": habitat_sim.__version__,
            "navmeshes_loaded": navmeshes, "checked_scene": scene_refs[0],
            "parsed_episode_count": len(dataset.episodes), "semantic_objects": semantic_objects}


def install(archive_root, manifest, scene_refs):
    parent = SCENES / "train"
    existing_config = SCENES / ROOT_CONFIG
    if parent.exists() or parent.is_symlink() or RECEIPT.exists():
        raise FileExistsError("The train scene directory or install receipt already exists.")
    if not existing_config.is_file() or existing_config.is_symlink():
        raise ValueError("Expected the independent official root config already in the project.")
    geometry, annotations = expected_scene_files(scene_refs)
    archives = verify_archives(archive_root, manifest)
    staging = Path(tempfile.mkdtemp(prefix="stage_", dir=archive_root))
    train = staging / "train"
    inputs = [
        (ARCHIVES[0], [ROOT_CONFIG, TRAIN_CONFIG], {ROOT_CONFIG: staging / ROOT_CONFIG, TRAIN_CONFIG: train / TRAIN_CONFIG}),
        (ARCHIVES[1], geometry, {name: train / name for name in geometry}),
        (ARCHIVES[2], annotations, {name: train / name for name in annotations}),
    ]
    files = {}
    for name, members, destinations in inputs:
        with tarfile.open(archives[name], "r:") as archive:
            for member, metadata in extract_files(archive, members, destinations):
                files[str(destinations[member].relative_to(staging))] = metadata
        print(f"Extracted compatible files from {name}", flush=True)
    if files[ROOT_CONFIG]["sha256"] != sha256(existing_config):
        raise ValueError("Official scene root configuration differs from the installed copy.")
    config = json.loads(existing_config.read_text())
    stage_paths = config["stages"]["paths"][".glb"]
    for ref in scene_refs:
        relative = str(Path(ref).relative_to("hm3d_v0.2"))
        if not any(fnmatchcase(relative, pattern) for pattern in stage_paths):
            raise ValueError(f"Root config does not cover {ref}")
    verified = check_habitat(staging, scene_refs)
    result = {"scene_count": len(scene_refs), "installation": "data/scene_datasets/hm3d_v0.2/train",
              "archive_root": str(archive_root.relative_to(PROJECT)),
              "archive_manifest": manifest, "files": files, "habitat_validation": verified}
    pending = staging / "receipt.json"
    pending.write_text(json.dumps(result, indent=2) + "\n")
    train.rename(parent)
    pending.rename(RECEIPT)
    print(json.dumps(verified, ensure_ascii=False), flush=True)
    print(f"Installed {len(scene_refs)} train scenes, receipt: {RECEIPT}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ARCHIVE_ROOT / "local_archives.json")
    args = parser.parse_args()
    path = args.manifest.resolve()
    if ARCHIVE_ROOT.resolve() not in path.parents:
        parser.error("The manifest must be inside the project train import directory.")
    manifest = json.loads(path.read_text())
    scene_refs = json.loads(EPISODES.read_text())["splits"]["train"]["scene_refs"]
    if not scene_refs or len(scene_refs) != len(set(scene_refs)):
        parser.error("The official train scene references must be nonempty and unique.")
    with (ARCHIVE_ROOT / "install.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "HM3D installation is already in progress.\n")
        install(ARCHIVE_ROOT, manifest, scene_refs)


if __name__ == "__main__":
    main()
