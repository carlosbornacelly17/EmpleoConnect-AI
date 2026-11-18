"""Extracción de texto de hojas de vida (PDF / Word) subidas desde Streamlit."""

import os
import tempfile

import pymupdf4llm
from docx import Document


def extraer_texto_para_rag(uploaded_file) -> str:
    """Extrae texto de un archivo subido (.pdf o .docx)."""
    nombre = uploaded_file.name
    ext = os.path.splitext(nombre)[1].lower()

    # Archivo temporal, porque pymupdf4llm y python-docx necesitan una ruta
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    try:
        if ext == ".pdf":
            texto = pymupdf4llm.to_markdown(tmp_path)
            return texto.strip()

        elif ext == ".docx":
            doc = Document(tmp_path)
            parrafos = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(parrafos)

        else:
            raise ValueError("Formato no soportado. Sube un archivo .pdf o .docx")

    finally:
        os.remove(tmp_path)
