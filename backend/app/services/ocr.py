import io

import cv2
import numpy as np
import pytesseract
from PIL import Image


def decode_image(data: bytes) -> np.ndarray | None:
    buffer = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def deskew(binary: np.ndarray) -> np.ndarray:
    coords = np.column_stack(np.where(binary < 128))
    if len(coords) < 50:
        return binary
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.3 or abs(angle) > 10:
        return binary
    height, width = binary.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(binary, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.shape[1] < 1600:
        scale = 1600 / gray.shape[1]
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return deskew(binary)


def read_text(image: np.ndarray) -> tuple[str, float]:
    processed = preprocess(image)
    pil = Image.fromarray(processed)
    try:
        detail = pytesseract.image_to_data(pil, config="--psm 6", output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(pil, config="--psm 6")
    except pytesseract.TesseractError:
        return "", 0.0
    confidences = [float(c) for c, word in zip(detail["conf"], detail["text"]) if str(word).strip() and float(c) >= 0]
    mean = sum(confidences) / len(confidences) / 100 if confidences else 0.0
    return text, round(mean, 3)


def pixmap_to_image(png_bytes: bytes) -> np.ndarray:
    return cv2.cvtColor(np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB")), cv2.COLOR_RGB2BGR)
