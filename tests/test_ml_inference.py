from pathlib import Path
import numpy as np
import pytest
import torch
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from PIL import Image

from medshield.ml.preprocessor import DICOMPreprocessor
from medshield.ml.model import build_thoracic_model, TorchXRayVisionClassifier, TARGET_PATHOLOGIES
from medshield.ml.explainability import GradCAM
from medshield.ml.inference_engine import InferenceEngine

def create_synthetic_xray_dicom(inverted: bool = False) -> Dataset:
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    file_meta.MediaStorageSOPInstanceUID = "2.25.1029384756"
    
    ds = Dataset()
    ds.file_meta = file_meta
    
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME1" if inverted else "MONOCHROME2"
    ds.Modality = "DX"
    ds.StudyInstanceUID = "2.25.1029384756"
    
    # Create synthetic chest x-ray like array (two lung fields as dark ovals on brighter background)
    arr = np.full((512, 512), 3000, dtype=np.uint16)
    # Left lung
    y, x = np.ogrid[:512, :512]
    left_mask = ((x - 180) / 70)**2 + ((y - 250) / 140)**2 <= 1
    right_mask = ((x - 330) / 70)**2 + ((y - 250) / 140)**2 <= 1
    arr[left_mask] = 800
    arr[right_mask] = 800
    
    ds.PixelData = arr.tobytes()
    return ds

def test_preprocessor_shape_and_normalization():
    preprocessor = DICOMPreprocessor(target_size=(224, 224))
    ds = create_synthetic_xray_dicom(inverted=False)
    
    tensor, original_img = preprocessor.process(ds)
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == torch.float32
    assert isinstance(original_img, Image.Image)
    assert original_img.size == (224, 224)

def test_preprocessor_monochrome1_inversion():
    preprocessor = DICOMPreprocessor(target_size=(224, 224))
    ds_mono2 = create_synthetic_xray_dicom(inverted=False)
    ds_mono1 = create_synthetic_xray_dicom(inverted=True)
    
    t_mono2, _ = preprocessor.process(ds_mono2)
    t_mono1, _ = preprocessor.process(ds_mono1)
    
    # Inverted monochrome1 should be normalized similarly to monochrome2
    assert t_mono1.shape == t_mono2.shape

    # XRV normalization mode check
    xrv_preprocessor = DICOMPreprocessor(target_size=(224, 224), normalization="xrv")
    t_xrv_mono2, pil_mono2 = xrv_preprocessor.process(ds_mono2)
    t_xrv_mono1, pil_mono1 = xrv_preprocessor.process(ds_mono1)
    assert t_xrv_mono1.shape == t_xrv_mono2.shape == (1, 3, 224, 224)
    assert t_xrv_mono1.min().item() >= -1024.0 - 1e-4
    assert t_xrv_mono1.max().item() <= 1024.0 + 1e-4
    assert pil_mono1.size == (224, 224)

def test_model_forward_pass_predictions():
    model = build_thoracic_model(pretrained=False)
    model.eval()
    
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        preds = model(dummy_input)
        
    assert preds.shape == (1, 5) # 5 target pathologies
    # Sigmoid outputs must be in [0.0, 1.0]
    assert (preds >= 0.0).all() and (preds <= 1.0).all()

def test_gradcam_heatmap_generation():
    model = build_thoracic_model(pretrained=False)
    model.eval()
    
    gradcam = GradCAM(model, target_layer_name=model.get_last_conv_layer_name())
    dummy_input = torch.randn(1, 3, 224, 224)
    
    # Generate CAM for class index 0 (Pneumonia)
    heatmap = gradcam.generate_heatmap(dummy_input, class_idx=0)
    assert isinstance(heatmap, np.ndarray)
    assert heatmap.shape == (224, 224)
    assert 0.0 <= heatmap.min() and heatmap.max() <= 1.0

def test_inference_engine_end_to_end():
    model = build_thoracic_model(pretrained=False)
    engine = InferenceEngine(model=model)
    
    ds = create_synthetic_xray_dicom()
    result = engine.predict(ds)
    
    assert result["study_instance_uid"] == "2.25.1029384756"
    assert "predictions" in result
    assert len(result["predictions"]) == 5
    
    for pred in result["predictions"]:
        assert pred["pathology"] in TARGET_PATHOLOGIES
        assert 0.0 <= pred["probability"] <= 1.0
        assert "triage_urgency" in pred
        assert pred["triage_urgency"] in ["STAT_CRITICAL", "ELEVATED", "ROUTINE"]
        assert pred["is_positive"] == (pred["probability"] >= 0.5)
        assert 0.0 <= pred["raw_score"] <= 1.0
        assert 0.0 < pred["operating_threshold"] < 1.0
    assert "not a calibrated probability" in result["score_semantics"]


def test_scores_are_threshold_normalized_for_torchxrayvision():
    """0.5 must coincide with the model's operating threshold on the raw sigmoid output."""
    import pydicom
    engine = InferenceEngine()
    for sample in ("patient_01_pneumonia", "patient_03_cardiomegaly"):
        for pred in engine.predict(pydicom.dcmread(f"test_samples/{sample}.dcm"))["predictions"]:
            raw, thr, score = pred["raw_score"], pred["operating_threshold"], pred["probability"]
            assert thr < 0.2                      # tuned thresholds are low (rare findings)
            assert (raw >= thr) == (score >= 0.5) == pred["is_positive"]


def create_synthetic_dicom_with_pattern(pattern: str = "blank") -> Dataset:
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    file_meta.MediaStorageSOPInstanceUID = f"2.25.{abs(hash(pattern)) % 100000000}"
    
    ds = Dataset()
    ds.file_meta = file_meta
    ds.Rows = 256
    ds.Columns = 256
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Modality = "DX"
    ds.StudyInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    
    if pattern == "blank":
        arr = np.zeros((256, 256), dtype=np.uint8)
    elif pattern == "lesion":
        arr = np.full((256, 256), 40, dtype=np.uint8)
        y, x = np.ogrid[:256, :256]
        mask = ((x - 128) ** 2 + (y - 128) ** 2) <= 30 ** 2
        arr[mask] = 240
    else:
        arr = np.random.RandomState(42).randint(0, 255, (256, 256), dtype=np.uint8)
        
    ds.PixelData = arr.tobytes()
    return ds


def test_torchxrayvision_loads_local_weights_with_op_threshs():
    model = TorchXRayVisionClassifier()
    assert model.is_real_weights is True
    assert model.input_normalization == "xrv"
    assert getattr(model.model, "op_threshs", None) is not None


def test_xrv_preprocessor_range_and_spatial_alignment():
    preprocessor = DICOMPreprocessor(target_size=(224, 224), normalization="xrv")
    ds = create_synthetic_xray_dicom(inverted=False)
    tensor, pil_img = preprocessor.process(ds)
    
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == torch.float32
    assert tensor.min().item() >= -1024.0 - 1e-4
    assert tensor.max().item() <= 1024.0 + 1e-4
    assert tensor.max().item() > tensor.min().item()
    assert pil_img.size == (224, 224)


def test_inference_engine_produces_distinct_predictions_across_samples():
    engine = InferenceEngine()
    
    # 1. Test distinct synthetic inputs
    ds_blank = create_synthetic_dicom_with_pattern("blank")
    ds_lesion = create_synthetic_dicom_with_pattern("lesion")
    
    res_blank = engine.predict(ds_blank)
    res_lesion = engine.predict(ds_lesion)
    
    probs_blank = np.array([p["probability"] for p in res_blank["predictions"]])
    probs_lesion = np.array([p["probability"] for p in res_lesion["predictions"]])
    
    # Assert distinct probability vectors across different synthetic patterns
    assert float(np.max(np.abs(probs_blank - probs_lesion))) >= 0.15
    
    # Verify non-zero Grad-CAM spatial spread
    hm_lesion = engine.gradcam.generate_heatmap(engine.preprocessor.process(ds_lesion)[0], class_idx=0)
    assert float(hm_lesion.std()) > 0.01

    # 2. Test real DICOM samples if present
    sample_files = [
        Path("test_samples/patient_01_pneumonia.dcm"),
        Path("test_samples/patient_02_effusion.dcm"),
        Path("test_samples/patient_03_cardiomegaly.dcm"),
    ]
    existing_samples = [p for p in sample_files if p.exists()]
    if len(existing_samples) >= 2:
        results = [engine.predict(pydicom.dcmread(p)) for p in existing_samples]
        prob_vecs = [np.array([p["probability"] for p in r["predictions"]]) for r in results]
        
        # Verify max absolute difference across distinct patient samples is >= 0.15
        max_diff = max(
            float(np.max(np.abs(prob_vecs[i] - prob_vecs[j])))
            for i in range(len(prob_vecs))
            for j in range(i + 1, len(prob_vecs))
        )
        assert max_diff >= 0.15, f"Expected distinct predictions across patient samples, got max diff {max_diff}"
        
        # Verify real sample Grad-CAM heatmap has spatial variation
        hm_real = engine.gradcam.generate_heatmap(engine.preprocessor.process(pydicom.dcmread(existing_samples[0]))[0], class_idx=0)
        assert float(hm_real.std()) > 0.01




def test_gradcam_is_not_corrupted_by_concurrent_predictions():
    import threading
    import pydicom
    engine = InferenceEngine()
    ds_a = pydicom.dcmread("test_samples/patient_01_pneumonia.dcm")
    ds_b = pydicom.dcmread("test_samples/patient_03_cardiomegaly.dcm")
    tensor_a, _ = engine.preprocessor.process(ds_a)
    reference = engine.gradcam.generate_heatmap(tensor_a, class_idx=0)

    stop = threading.Event()

    def hammer_predict():
        while not stop.is_set():
            engine.predict(ds_b)

    workers = [threading.Thread(target=hammer_predict) for _ in range(2)]
    for t in workers:
        t.start()
    try:
        for _ in range(6):
            heatmap = engine.gradcam.generate_heatmap(tensor_a, class_idx=0)
            np.testing.assert_allclose(heatmap, reference, atol=1e-4)
    finally:
        stop.set()
        for t in workers:
            t.join()


def test_build_thoracic_model_respects_architecture_setting():
    import pytest as _pytest
    from medshield.ml.model import ThoracicClassifier
    assert isinstance(build_thoracic_model(architecture="efficientnet_v2_s"), ThoracicClassifier)
    assert isinstance(build_thoracic_model(architecture="torchxrayvision"), TorchXRayVisionClassifier)
    with _pytest.raises(ValueError):
        build_thoracic_model(architecture="resnet9000")


def test_routers_share_a_single_inference_engine():
    from medshield.api.routes import dashboard, inference
    assert dashboard._dashboard_engine is inference._shared_engine
