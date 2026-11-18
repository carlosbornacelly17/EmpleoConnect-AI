"""Agente 2: clasificador DistilBERT en formato ONNX (carpeta modelo_onnx/); uso: python cargar_modelo_onnx.py"""
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

CARPETA = Path(__file__).parent / "modelo_onnx"

# El tokenizer.json ya incluye minúsculas, WordPiece y los tokens [CLS]/[SEP]
tokenizer = Tokenizer.from_file(str(CARPETA / "tokenizer.json"))
tokenizer.enable_truncation(max_length=512)

sesion = ort.InferenceSession(
    str(CARPETA / "modelo_cv.onnx"), providers=["CPUExecutionProvider"]
)

with open(CARPETA / "label_map.json", encoding="utf-8") as f:
    label_map = json.load(f)  # {"0": "ACCOUNTANT", "1": "ADVOCATE", ...}


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def clasificar(texto: str, k: int = 3) -> list[dict]:
    """Devuelve las k categorías más probables con su probabilidad (0 a 1)."""
    enc = tokenizer.encode(texto)
    entradas = {
        "input_ids": np.array([enc.ids], dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
    }
    logits = sesion.run(["logits"], entradas)[0][0]
    probs = _softmax(logits)
    top = np.argsort(probs)[::-1][:k]
    return [
        {"categoria": label_map[str(i)], "probabilidad": float(probs[i])} for i in top
    ]


if __name__ == "__main__":
    print(f"Modelo ONNX cargado. Categorías: {len(label_map)}")

    texto_prueba = """
    SOFTWARE ENGINEER
    Summary: Experienced software engineer with 5 years of expertise in Python,
    machine learning, and cloud infrastructure.

    Experience:
    Led development of scalable backend systems using Django and AWS.
    Designed and implemented RESTful APIs serving over 1 million requests per day.
    Collaborated with cross-functional teams to deploy microservices architecture.
    Optimized database queries reducing response time by 40 percent.

    Skills: Python, Java, SQL, AWS, Docker, Kubernetes, Machine Learning,
    TensorFlow, Django, REST APIs, Git, Agile methodologies.

    Education: Bachelor of Science in Computer Science.
    """

    print("\nTop 3 predicciones:")
    for r in clasificar(texto_prueba):
        print(f"  {r['categoria']}: {r['probabilidad'] * 100:.2f}%")
