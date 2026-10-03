"""PaddleOCR adapter for scanned pages and standalone images."""
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock

from app.core.config import get_settings


def _disable_paddlex_pir() -> None:
    """Patch PaddleX to keep the legacy IR path off the incompatible PIR/oneDNN runtime.

    The important part is to avoid importing PaddleX eagerly during app startup. The
    runtime is configured before the PaddleOCR model loader runs so the model factory sees
    the compatibility flags while the library is still being initialized.
    """
    try:
        from paddlex.inference.models import PaddlePredictorOption

        if getattr(PaddlePredictorOption, "_copilot_compat_patched", False):
            return

        original_get_default_config = PaddlePredictorOption._get_default_config
        original_device_type_setter = PaddlePredictorOption.device_type.fset

        def _patched_get_default_config(self, model_name):
            config = original_get_default_config(self, model_name)
            config["enable_new_ir"] = False
            config["run_mode"] = "paddle"
            return config

        def _patched_device_type_setter(self, device_type):
            original_device_type_setter(self, device_type)
            os.environ["FLAGS_enable_pir_api"] = "0"
            os.environ["FLAGS_use_onednn"] = "0"
            os.environ["FLAGS_use_mkldnn"] = "0"

        PaddlePredictorOption._get_default_config = _patched_get_default_config
        PaddlePredictorOption.device_type = property(
            PaddlePredictorOption.device_type.fget,
            _patched_device_type_setter,
            PaddlePredictorOption.device_type.fdel,
            PaddlePredictorOption.device_type.__doc__,
        )
        PaddlePredictorOption._copilot_compat_patched = True
    except Exception:  # pragma: no cover - some Paddle versions do not expose this class at import time
        pass


def _configure_paddle_runtime() -> None:
    """Disable the incompatible Paddle native execution paths before model setup.

    The runtime is notorious for re-enabling PIR and oneDNN during PaddleX initialization,
    so these flags are applied as early as possible and the PaddleX config is patched before
    the OCR predictor is created.
    """
    os.environ.setdefault("PADDLE_PDX_EAGER_INIT", "False")
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
    os.environ["FLAGS_enable_pir_api"] = "0"
    os.environ["FLAGS_enable_new_ir"] = "0"
    os.environ["FLAGS_use_onednn"] = "0"
    os.environ["FLAGS_use_mkldnn"] = "0"

    try:
        import paddle

        paddle.set_flags({
            "FLAGS_enable_pir_api": False,
            "FLAGS_enable_new_ir": False,
            "FLAGS_use_onednn": False,
            "FLAGS_use_mkldnn": False,
        })
    except Exception:  # pragma: no cover - runtime-specific guard, should never crash app startup
        pass

    _disable_paddlex_pir()


_configure_paddle_runtime()
settings = get_settings()

_reader = None
_load_attempted = False
_load_error: str | None = None
_reader_lock = Lock()


@dataclass
class OCRSpan:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]


def _ensure_modelscope_stub() -> None:
    """ModelScope triggers a broken Torch import path on some Windows stacks.

    PaddleOCR imports paddlex, which imports modelscope during module initialization.
    On this environment, that import path fails before OCR ever starts. A tiny stub keeps
    the import chain alive while leaving the actual OCR model loading to PaddleOCR itself.
    """
    try:
        import modelscope  # noqa: F401
        return
    except Exception:
        pass

    import sys
    import types

    modelscope = types.ModuleType("modelscope")
    hub = types.ModuleType("modelscope.hub")
    errors = types.ModuleType("modelscope.hub.errors")

    class _DummyModelScopeError(Exception):
        pass

    errors.NotFoundError = _DummyModelScopeError
    errors.HubError = _DummyModelScopeError
    hub.errors = errors
    modelscope.hub = hub

    sys.modules.setdefault("modelscope", modelscope)
    sys.modules.setdefault("modelscope.hub", hub)
    sys.modules.setdefault("modelscope.hub.errors", errors)


def _get_reader():
    """Lazily construct and cache the PaddleOCR pipeline once per process."""
    global _reader, _load_attempted, _load_error

    with _reader_lock:
        if _reader is not None:
            return _reader
        if _load_attempted:
            return None

        _load_attempted = True
        try:
            _configure_paddle_runtime()
            _ensure_modelscope_stub()
            from paddleocr import PaddleOCR

            _reader = PaddleOCR(
                lang=settings.paddleocr_language,
                device=settings.paddleocr_device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            return _reader
        except Exception as exc:  # noqa: BLE001 — OCR load failures shouldn't crash document processing
            _load_error = str(exc)
            print(f"[ocr_paddle] Failed to load PaddleOCR: {exc}")
            return None


def is_available() -> bool:
    return _get_reader() is not None


def load_error() -> str | None:
    return _load_error


def _result_data(result) -> Mapping:
    data = getattr(result, "json", result)
    if callable(data):
        data = data()
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, Mapping):
        data = data.get("res", data)
    return data if isinstance(data, Mapping) else {}


def _normalize_bbox(box, width: int, height: int) -> tuple[float, float, float, float]:
    if not hasattr(box[0], "__len__"):
        left, upper, right, lower = box
    else:
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        left, right = min(xs), max(xs)
        upper, lower = min(ys), max(ys)

    if width:
        left, right = left / width, right / width
    if height:
        upper, lower = upper / height, lower / height
    return (float(left), float(upper), float(right), float(lower))


def run_ocr(image_path: str, merge_level: str | None = None) -> list[OCRSpan]:
    """Run PaddleOCR and return recognized text spans in reading order."""
    reader = _get_reader()
    if reader is None:
        raise RuntimeError(f"PaddleOCR is not available: {_load_error or 'not loaded'}")

    from PIL import Image
    with Image.open(image_path) as img:
        width, height = img.size

    spans: list[OCRSpan] = []
    for result in reader.predict(image_path):
        data = _result_data(result)
        texts = data.get("rec_texts") or []
        scores = data.get("rec_scores")
        boxes = data.get("rec_boxes")
        if boxes is None:
            boxes = data.get("rec_polys")
        if boxes is None:
            boxes = data.get("dt_polys")
        if boxes is None:
            boxes = []

        for index, text in enumerate(texts):
            if not text or index >= len(boxes):
                continue
            confidence = scores[index] if scores is not None and index < len(scores) else 1.0
            spans.append(OCRSpan(
                text=str(text),
                confidence=float(confidence),
                bbox=_normalize_bbox(boxes[index], width, height),
            ))
    return spans


def ocr_page_text(image_path: str, merge_level: str | None = None) -> str:
    """Run OCR on one image and join recognized lines into a text blob."""
    spans = run_ocr(image_path, merge_level=merge_level)
    return "\n".join(span.text for span in spans)