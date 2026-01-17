# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

from typing import Dict, Any

import numpy as np
import lz4.block


def decompress(compressed_data: bytes, decomp_size: int) -> bytes:
    return lz4.block.decompress(compressed_data, uncompressed_size=decomp_size)


def bits_to_points(buf: bytes, origin: list, resolution: float = 0.05) -> np.ndarray:
    values = np.frombuffer(bytearray(buf), dtype=np.uint8)
    nonzero_indices = np.nonzero(values)[0]
    points = []

    for index in nonzero_indices:
        byte_value = values[index]
        z = index // 0x800
        n_slice = index % 0x800
        y = n_slice // 0x10
        x_base = (n_slice % 0x10) * 8

        for bit_pos in range(8):
            if byte_value & (1 << (7 - bit_pos)):
                x = x_base + bit_pos
                points.append((x, y, z))

    if len(points) == 0:
        return np.empty((0, 3), dtype=np.float32)

    return np.array(points, dtype=np.float32) * resolution + np.array(
        origin, dtype=np.float32
    )


class LidarDecoderLz4:
    def decode(self, compressed_data: bytes, data: Dict[str, Any]) -> Dict[str, Any]:
        decompressed = decompress(compressed_data, data["src_size"])
        origin = np.array(data.get("origin", [0.0, 0.0, 0.0]), dtype=np.float32)
        resolution = float(data.get("resolution", 0.0))
        points = bits_to_points(decompressed, origin.tolist(), resolution)

        if points.size == 0 or resolution <= 0.0:
            empty = np.empty((0,), dtype=np.float32)
            return {"positions": empty, "uvs": empty, "point_count": 0}

        voxel_points = (points - origin) / resolution
        positions = voxel_points.astype(np.float32).reshape(-1)
        uvs = np.ones((voxel_points.shape[0], 2), dtype=np.float32).reshape(-1)
        return {
            "positions": positions,
            "uvs": uvs,
            "point_count": voxel_points.shape[0],
        }


LidarDecoder = LidarDecoderLz4
