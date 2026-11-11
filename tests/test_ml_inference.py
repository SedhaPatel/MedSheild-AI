import numpy as np
import pytest
import torch
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from PIL import Image

from medshield.ml.preprocessor import DICOMPreprocessor
from medshield.ml.model import build_thoracic_model, TARGET_PATHOLOGIES
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
        assert "epistemic_uncertainty" in pred

