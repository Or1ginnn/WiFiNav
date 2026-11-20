"""Read the binary Matterport semantic triangle mesh with NumPy."""

import numpy as np


def read_ply(path):
    # The Habitat MP3D semantic mesh is a binary triangle PLY. Validate this
    # variant strictly before mapping records to avoid guessing field offsets.
    with path.open("rb") as handle:
        header = []
        for line in handle:
            header.append(line.decode("ascii").strip())
            if header[-1] == "end_header":
                break
            if len(header) > 40:
                raise ValueError("Unrecognized semantic PLY header")
        offset = handle.tell()
    if (len(header) != 13 or header[:2] != ["ply", "format binary_little_endian 1.0"]
            or not header[2].startswith("element vertex ")
            or header[3:9] != ["property float x", "property float y", "property float z",
                               "property uchar red", "property uchar green", "property uchar blue"]
            or not header[9].startswith("element face ")
            or header[10:] != ["property list uchar int vertex_indices", "property int object_id", "end_header"]):
        raise ValueError("Unexpected MP3D semantic PLY format")
    n_vertices, n_faces = int(header[2].split()[-1]), int(header[9].split()[-1])
    vertex_type = np.dtype([("xyz", "<f4", (3,)), ("color", "u1", (3,))])
    face_type = np.dtype([("count", "u1"), ("indices", "<i4", (3,)), ("object", "<i4")])
    vertices = np.memmap(path, dtype=vertex_type, mode="r", offset=offset, shape=(n_vertices,))
    offset += n_vertices * vertex_type.itemsize
    if path.stat().st_size != offset + n_faces * face_type.itemsize:
        raise ValueError("Expected packed triangular face records")
    faces = np.memmap(path, dtype=face_type, mode="r", offset=offset, shape=(n_faces,))
    if not np.all(faces["count"] == 3):
        raise ValueError("Expected triangular mesh faces")
    return vertices["xyz"], faces
