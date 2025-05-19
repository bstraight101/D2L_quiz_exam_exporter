import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import tempfile
import re
import time
import os

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
1.What is the capital of France?
A) Berlin
B) Madrid
C) Paris
D) Rome
Answer: C

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
    total = len(blocks)
    progress = st.progress(0, text="Parsing questions...")

    for i, block in enumerate(blocks):
        lines = block.split("\n")
        if not lines:
            continue

        q_match = re.match(r"^\d+[\.\)\-]\s*(.+)", lines[0])
        if not q_match:
            questions.append(("❌ Invalid question format", block))
            continue

        question = q_match.group(1).strip()
        answer_line = next((l for l in lines if l.lower().startswith("answer:")), None)
        if not answer_line:
            questions.append(("❌ Missing answer line", block))
            continue

        answer_val = answer_line.split(":", 1)[1].strip()
        choices = [l.strip() for l in lines[1:] if re.match(r"^[A-Da-d][\.\)\-]", l)]

        if choices:
            q_rows = [(question, "", "")]
            correct_letter = answer_val.upper()
            for choice in choices:
                label = choice[0].upper()
                score = 100 if label == correct_letter else 0
                q_rows.append(("", score, choice))
        else:
            # fill-in-the-blank
            q_rows = [(question, "", "")]
            q_rows.append(("", 100, answer_val))
        questions.append(q_rows)
        progress.progress((i + 1) / total, text=f"Parsing {i+1}/{total}")
    progress.empty()
    return questions

if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    raw_text = ""
    filename_base = os.path.splitext(uploaded_file.name)[0]

    if ext == "docx":
        raw_text = extract_text_from_docx(uploaded_file)
    elif ext == "pdf":
        raw_text = extract_text_from_pdf(uploaded_file)
    else:
        st.error("Unsupported file type.")
        st.stop()

    st.subheader("📄 Raw Text Preview")
    with st.expander("Click to view extracted text"):
        st.text_area("Extracted Text", value=raw_text, height=300)

    if st.button("🚀 Submit and Process File"):
        with st.spinner("Analyzing questions..."):
            all_qs = parse_questions(raw_text)
            error_blocks = [q[1] for q in all_qs if isinstance(q, tuple)]
            valid_qs = [q for q in all_qs if isinstance(q, list)]

            if error_blocks:
                st.warning("⚠️ Some questions had formatting issues. You can correct them below:")
                for i, block in enumerate(error_blocks):
                    new_text = st.text_area(f"✏️ Fix Block {i+1}", value=block, height=120)
                    if st.button(f"✅ Re-parse Block {i+1}", key=f"fix_{i}"):
                        re_result = parse_questions(new_text)
                        # Replace only if parsing worked
                        if any(isinstance(q, list) for q in re_result):
                            valid_qs.extend([q for q in re_result if isinstance(q, list)])
                            st.success(f"✅ Block {i+1} re-parsed successfully.")
                        else:
                            st.error(f"Still invalid: {new_text}")

            if valid_qs:
                rows = [row for group in valid_qs for row in group]
                df = pd.DataFrame(rows, columns=["Question", "Points", "Answer Text"])
                st.success("✅ Parsed questions preview:")
                st.dataframe(df, use_container_width=True)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    df.to_csv(tmp.name, index=False)
                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            label="⬇️ Download CSV for D2L",
                            data=f,
                            file_name=f"{filename_base}_d2l_export.csv",
                            mime="text/csv"
                        )
