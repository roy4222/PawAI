"""Tests for face identity model persistence helpers."""
import pickle

import numpy as np

from face_perception.face_identity_node import (
    load_model,
    load_model_npz,
    save_model_npz,
)


def make_model():
    return {
        "embeddings": {
            "roy": [
                np.array([0.1, 0.2, 0.3], dtype=np.float32),
                np.array([0.4, 0.5, 0.6], dtype=np.float32),
            ],
            "sim": [
                np.array([0.7, 0.8, 0.9], dtype=np.float32),
            ],
        },
        "centroids": {
            "roy": np.array([0.25, 0.35, 0.45], dtype=np.float32),
            "sim": np.array([0.7, 0.8, 0.9], dtype=np.float32),
        },
        "counts": {
            "roy": 2,
            "sim": 1,
        },
    }


def assert_model_equal(actual, expected):
    assert set(actual.keys()) == {"embeddings", "centroids", "counts"}
    assert actual["counts"] == expected["counts"]
    assert set(actual["embeddings"]) == set(expected["embeddings"])
    assert set(actual["centroids"]) == set(expected["centroids"])

    for name, expected_embeddings in expected["embeddings"].items():
        actual_embeddings = actual["embeddings"][name]
        assert len(actual_embeddings) == len(expected_embeddings)
        for actual_embedding, expected_embedding in zip(
            actual_embeddings, expected_embeddings
        ):
            assert actual_embedding.dtype == np.float32
            np.testing.assert_array_equal(actual_embedding, expected_embedding)

    for name, expected_centroid in expected["centroids"].items():
        actual_centroid = actual["centroids"][name]
        assert actual_centroid.dtype == np.float32
        np.testing.assert_array_equal(actual_centroid, expected_centroid)


def test_npz_save_then_load_round_trips_model(tmp_path):
    model = make_model()
    model_path = tmp_path / "model_sface.npz"

    save_model_npz(model, model_path)
    loaded = load_model_npz(model_path)

    assert_model_equal(loaded, model)


def test_npz_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    model = make_model()
    model_path = tmp_path / "model_sface.pkl"
    npz_path = model_path.with_suffix(".npz")

    save_model_npz(model, model_path)

    assert npz_path.exists()
    assert not model_path.exists()
    assert not list(tmp_path.glob("*.tmp"))
    with np.load(npz_path, allow_pickle=False) as data:
        assert {"names", "counts", "embedding_counts", "embeddings", "centroids"} <= set(
            data.files
        )
    assert_model_equal(load_model_npz(npz_path), model)


def test_load_model_falls_back_to_legacy_pickle_when_only_pickle_exists(tmp_path):
    model = make_model()
    model_path = tmp_path / "model_sface.pkl"
    with model_path.open("wb") as f:
        pickle.dump(model, f)

    loaded = load_model(model_path)
