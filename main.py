import streamlit as st
import fitz  # PyMuPDF
from docx import Document
import csv
import tempfile
import re
import os

st.set_page_config(page_title="D2L Quiz Exporter", layout="wide")
st.title("📤 D2L Quiz and Exam CSV Exporter")

st.markdown("""
Upload a `.docx` or `.pdf` file to export a **D2L-compatible quiz CSV**.

### ✅ Formatting Guide:
- Separate each question with **no extra space needed**
- Each block should end with `Answer: X` (where X is A–D)
- Example:
What is the capital of France?
Berlin
Madrid
Paris
Rome
Answer: C
""")

uploaded_file = st.file_uploader("Upload your quiz file", type=["docx", "pdf"])

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip() != ""])

def extract_text_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def robust_block_parser(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    blocks = []
    block = []

    for line in lines:
        block.append(line)
        if re.match(r"(?i)^answer[:\s]?", line):  # End of a question
            blocks.append("\n".join(block))
            block = []
    return blocks

def parse_to_d2l_format(raw_text):
    blocks = robust_block_parser(raw_text)
    rows = []
    rows.append(["//MULTIPLE CHOICE QUESTION TYPE"])
    rows.append(["//Options must include text in column3"])

    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 3:
            continue

        answer_line = next((l for l in lines if re.match(r"(?i)^answer[:\s]?", l)), None)
        if not answer_line:
            continue

        answer_match = re.search(r"(?i)^answer[:\s]*([A-Da-d])", answer_line)
        if not answer_match:
            continue

        correct_letter = answer_match.group(1).upper()
        try:
            answer_index = lines.index(answer_line)
        except ValueError:
            continue

        question = lines[0]
        choices = lines[1:answer_index]

        rows.append(["NewQuestion", "MC"])
        rows.append(["QuestionText", question])

        for idx, choice in enumerate(choices):
            label = chr(65 + idx)
            score = "100" if label == correct_letter else "0"
            rows.append(["Option", score, choice])

        rows.append([])  # Blank line between questions

    return rows

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

    st.subheader("📄 Preview Extracted Text")
    with st.expander("Show raw extracted content"):
        st.text_area("Raw Text", value=raw_text, height=300)

    if st.button("🚀 Generate D2L CSV"):
        with st.spinner("Parsing and generating CSV..."):
            d2l_rows = parse_to_d2l_format(raw_text)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                with open(tmp.name, "w", newline='') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerows(d2l_rows)

                with open(tmp.name, "rb") as f:
                    st.download_button(
                        label="⬇️ Download D2L Quiz CSV",
                        data=f,
                        file_name=f"{filename_base}_D2L_quiz.csv",
                        mime="text/csv"
                    )
            st.success("✅ CSV created successfully!")
