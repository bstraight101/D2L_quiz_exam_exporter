import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
import tempfile
import re
import os

st.set_page_config(page_title="D2L Quiz and Exam CSV Exporter", layout="wide")
st.title("📤 D2L Quiz and Exam CSV Exporter")

st.markdown("""
This app allows faculty to upload `.docx` or `.pdf` files formatted with exam/quiz questions and export a **D2L-compliant CSV**.

### 📝 Input Format Instructions:
- Each question must be followed by 2+ answer choices.
- The correct answer must be labeled on the last line of each block as `Answer C` or `Answer: C`.
- Separate each question block with **one blank line**.

#### ✅ Example:
Which is not a suggestion for doing an impromptu speech?  
Pre-Planning  
Be positive  
Never apologize for mistakes  
Read a written speech  
Answer: D
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

def enhanced_parse_questions(raw_text):
    questions = []
    blocks = [b.strip() for b in raw_text.split("\n\n") if b.strip()]
    total = len(blocks)
    progress = st.progress(0, text="Parsing questions...")

    for i, block in enumerate(blocks):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 3:
            questions.append(("❌ Too few lines to parse", block))
            continue

        answer_line = next((l for l in lines if re.match(r"(?i)^answer[:\s]", l)), None)
        if not answer_line:
            questions.append(("❌ Missing answer line", block))
            continue

        answer_match = re.search(r"(?i)^answer[:\s]*([A-Da-d])", answer_line)
        if not answer_match:
            questions.append(("❌ Could not extract answer letter", block))
            continue

        correct_letter = answer_match.group(1).upper()

        try:
            answer_index = lines.index(answer_line)
        except ValueError:
            questions.append(("❌ Couldn't locate answer line index", block))
            continue

        question = lines[0]
        choice_lines = lines[1:answer_index]

        if len(choice_lines) < 2:
            questions.append(("❌ Not enough answer choices", block))
            continue

        q_rows = [(question, "", "")]
        for j, choice in enumerate(choice_lines):
            label = chr(65 + j)  # A, B, C, D
            full_choice = f"{label}) {choice}"
            score = 100 if label == correct_letter else 0
            q_rows.append(("", score, full_choice))
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
            all_qs = enhanced_parse_questions(raw_text)
            error_blocks = [q[1] for q in all_qs if isinstance(q, tuple)]
            valid_qs = [q for q in all_qs if isinstance(q, list)]

            if error_blocks:
                st.warning("⚠️ Some questions had formatting issues. You can correct them below:")
                for i, block in enumerate(error_blocks):
                    new_text = st.text_area(f"✏️ Fix Block {i+1}", value=block, height=120)
                    if st.button(f"✅ Re-parse Block {i+1}", key=f"fix_{i}"):
                        re_result = enhanced_parse_questions(new_text)
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
