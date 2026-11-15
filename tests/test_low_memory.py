"""Low-memory deployment mode: image downscaling (MEDSHIELD_MAX_IMAGE_DIM) and lean Grad-CAM."""

import io

import numpy as np
import pydicom
import torch
from fastapi.testclient import TestClient
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from medshield.api.app import create_app
from medshield.config import Settings, get_settings
from medshield.ml.explainability import GradCAM
from medshield.utils.dicom_helpers import downscale_dataset, extract_pixel_array
from tests._auth import authenticate


def _dataset(arr: np.ndarray, photometric: str = "MONOCHROME2", frames: int = 1) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientID = "LOWMEM-1"
    ds.Modality = "DX"
    ds.Rows, ds.Columns = arr.shape[-3:-1] if photometric == "RGB" else arr.shape[-2:]
    ds.SamplesPerPixel = 3 if photometric == "RGB" else 1
    if photometric == "RGB":
        ds.PlanarConfiguration = 0
    ds.PhotometricInterpretation = photometric
    ds.BitsAllocated = arr.dtype.itemsize * 8
    ds.BitsStored = 12 if arr.dtype == np.uint16 else 8
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = 0
    if frames > 1:
        ds.NumberOfFrames = frames
    ds.PixelData = arr.tobytes()
    return ds


def test_downscale_averages_blocks_and_scales_spacing():
    arr = np.arange(3000 * 2400, dtype=np.uint32).reshape(3000, 2400) % 4096
    arr = arr.astype(np.uint16)
    ds = _dataset(arr)
    ds.PixelSpacing = ["0.139", "0.139"]
    ds.ImagerPixelSpacing = ["0.15", "0.15"]

    factor = downscale_dataset(ds, 1024)

    assert factor == 3
    assert (ds.Rows, ds.Columns) == (1000, 800)
    small = extract_pixel_array(ds)
    assert small.shape == (1000, 800) and small.dtype == np.uint16
    expected = np.rint(arr[:3, :3].astype(np.float32).mean())
    assert small[0, 0] == expected
    assert [float(v) for v in ds.PixelSpacing] == [0.417, 0.417]
    assert [float(v) for v in ds.ImagerPixelSpacing] == [0.45, 0.45]


def test_downscale_is_a_no_op_when_disabled_or_already_small():
    arr = np.random.default_rng(0).integers(0, 255, size=(600, 500), dtype=np.uint8)
    for max_dim in (0, 1024):
        ds = _dataset(arr)
        assert downscale_dataset(ds, max_dim) == 1
        assert ds.PixelData == arr.tobytes()


def test_downscale_handles_color_and_multi_frame():
    rgb = np.random.default_rng(1).integers(0, 255, size=(2048, 2048, 3), dtype=np.uint8)
    ds = _dataset(rgb, photometric="RGB")
    assert downscale_dataset(ds, 1024) == 2
    assert extract_pixel_array(ds).shape == (1024, 1024, 3)

    frames = np.random.default_rng(2).integers(0, 4095, size=(3, 2100, 2100), dtype=np.uint16)
    ds = _dataset(frames, frames=3)
    assert downscale_dataset(ds, 1024) == 3
    assert extract_pixel_array(ds).shape == (3, 700, 700)

    # Result is a valid, re-readable DICOM file
    bio = io.BytesIO()
    pydicom.dcmwrite(bio, ds, enforce_file_format=True)
    assert pydicom.dcmread(io.BytesIO(bio.getvalue())).pixel_array.shape == (3, 700, 700)


def test_max_image_dim_shrinks_stored_studies_on_both_upload_paths(tmp_path):
    settings = Settings(
        storage_path=str(tmp_path / "enc"), require_mtls=False, max_image_dim=1024,
        secret_pepper=b"low-memory-tests-pepper",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = authenticate(TestClient(app))

    big = np.random.default_rng(3).integers(0, 4095, size=(2500, 2500), dtype=np.uint16)
    bio = io.BytesIO()
    pydicom.dcmwrite(bio, _dataset(big), enforce_file_format=True)
    payload = bio.getvalue()

    analyzed = client.post("/api/v1/dashboard/analyze", files={"file": ("big.dcm", payload)})
    assert analyzed.status_code == 200, analyzed.text
    uid = analyzed.json()["anonymous_study_instance_uid"]
    stored = client.get(f"/api/v1/dashboard/studies/{uid}/dicom")
    assert stored.status_code == 200, stored.text
    assert pydicom.dcmread(io.BytesIO(stored.content)).pixel_array.shape == (833, 833)

    stow = client.post("/api/v1/studies", files={"file": ("big.dcm", payload)})
    assert stow.status_code == 201, stow.text


def test_gradcam_matches_full_backprop_reference():
    torch.manual_seed(0)
    model = torch.nn.Sequential(
        torch.nn.Conv2d(1, 4, 3, padding=1), torch.nn.ReLU(),
        torch.nn.Conv2d(4, 8, 3, padding=1), torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool2d(1), torch.nn.Flatten(), torch.nn.Linear(8, 3),
    )
    x = torch.randn(1, 1, 16, 16)

    # Reference: classic Grad-CAM with the whole graph recorded
    acts = {}
    handle = model[2].register_forward_hook(lambda m, i, o: acts.setdefault("a", o))
    score = model(x.clone().requires_grad_(True))[0, 1]
    grads = torch.autograd.grad(score, acts["a"])[0]
    handle.remove()
    cam = torch.relu((grads.mean(dim=(2, 3), keepdim=True) * acts["a"]).sum(dim=1, keepdim=True))
    cam = torch.nn.functional.interpolate(cam, size=(16, 16), mode="bilinear", align_corners=False)
    ref = cam.squeeze().detach().numpy()
    ref = (ref - ref.min()) / (ref.max() - ref.min())

    model.get_last_conv_layer = lambda: model[2]
    heatmap = GradCAM(model).generate_heatmap(x, class_idx=1)

    assert np.allclose(heatmap, ref, atol=1e-6)
    assert not any(p.requires_grad for p in model.parameters())
