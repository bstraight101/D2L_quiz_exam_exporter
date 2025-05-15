import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import tempfile
import re

st.set_page_config(page_title="D2L Quiz and Exam CSV Exporter", layout="wide")
st.title("📤 D2L Quiz and Exam CSV Exporter")
st.markdown("""
This app allows faculty to upload `.docx` or `.pdf` files formatted with exam/quiz questions and export a **D2L-compliant CSV**.

### 📝 Input Format Instructions:
1. **Each question must be numbered** (e.g., `1. What is ...`)
2. **Each answer choice must start with a letter** (`A)`, `B)`, etc.)
3. The correct answer must be labeled at the end with a line like: `Answer: C`
4. Separate each question block with **one blank line**

#### ✅ Example:
```
1. What is the capital of France?
A) Berlin
B) Madrid
C) Paris
D) Rome
Answer: C
```

### 🧼 Document Cleanup Tips:
- Use **Ctrl+H** to find and replace `^p^p` with `^p` in Word
- Remove double spaces with **Find:  ␣␣  Replace: ␣**
- Convert PDFs to `.docx` for better accuracy

""")
uploaded_file = st.file_uploader("Upload .docx or .pdf file", type=["docx", "pdf"])

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip() != ""])

def extract_text_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def parse_questions(raw_text):
    questions = []
    blocks = [b.strip() for b in raw_text.split("\n\n") if b.strip()]
    for block in blocks:
        lines = block.split("\n")
        if not lines:
            continue
        q_match = re.match(r"^\d+\.\s*(.+)", lines[0])
        if not q_match:
            continue
        question = q_match.group(1).strip()
        choices = [l.strip() for l in lines[1:] if re.match(r"^[A-D]\)", l)]
        answer_line = next((l for l in lines if l.lower().startswith("answer:")), None)
        if not answer_line or not re.match(r"Answer: [A-Da-d]", answer_line):
            questions.append(("❌ Formatting error in block", block))
            continue
        correct_letter = answer_line.split(":")[1].strip().upper()
        q_rows = [(question, "", "")]
        for choice in choices:
            label = choice[0]
            score = 100 if label == correct_letter else 0
            q_rows.append(("", score, choice))
        questions.append(q_rows)
    return questions

if uploaded_file:
    with st.spinner("Processing file..."):
        ext = uploaded_file.name.split(".")[-1].lower()
        raw_text = ""
        if ext == "docx":
            raw_text = extract_text_from_docx(uploaded_file)
        elif ext == "pdf":
            raw_text = extract_text_from_pdf(uploaded_file)
        else:
            st.error("Unsupported file type.")
        
        all_qs = parse_questions(raw_text)
        error_blocks = [q[1] for q in all_qs if isinstance(q, tuple)]
        valid_qs = [q for q in all_qs if isinstance(q, list)]

        if error_blocks:
            st.warning("Some questions had formatting issues:")
            for e in error_blocks:
                st.code(e)

        if valid_qs:
            rows = [row for group in valid_qs for row in group]
            df = pd.DataFrame(rows, columns=["Question", "Points", "Answer Text"])
            st.success("✅ Parsed questions preview:")
            st.dataframe(df, use_container_width=True)

            tmp_download = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            df.to_csv(tmp_download.name, index=False)
            with open(tmp_download.name, "rb") as f:
                st.download_button("⬇️ Download CSV for D2L", f, file_name="d2l_quiz_export.csv", mime="text/csv")
