"""
Component 3: PDF Parser
Architecture doc Section 4.2, step 2a.
"""

import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF bytes. Returns stripped text string."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except ImportError:
        # Fallback: try PyPDF2 for older installs
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text.strip()
        except ImportError:
            raise RuntimeError(
                "PDF parsing library not available. "
                "Install pypdf: pip install pypdf"
            )
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}")
