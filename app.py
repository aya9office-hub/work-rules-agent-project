from __future__ import annotations
import json
import tempfile
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from analyzer import analyze
from report_builder import build_report
from text_extract import extract_text

load_dotenv()
st.set_page_config(page_title="就業規則 構造チェック", layout="wide")
st.title("就業規則・附属規程 構造チェックツール")
st.caption("目的: 法違反の断定ではなく、規程間の構造的不整合を検出し、Word報告書を作成します。")

uploaded = st.file_uploader(
    "就業規則・附属規程をアップロードしてください",
    type=["docx", "pdf", "txt", "md"],
    accept_multiple_files=True
)

with open("check_rules.json", "r", encoding="utf-8") as f:
    rules = json.load(f)

if st.button("チェックしてWord報告書を作成", type="primary", disabled=not uploaded):
    with st.spinner("規程を解析しています..."):
        docs = {}
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            saved_files = []
            for uf in uploaded:
                path = td_path / uf.name
                path.write_bytes(uf.getvalue())
                saved_files.append(path.name)
                docs[path.name] = extract_text(path)
            findings = analyze(docs, rules)
            report_path = td_path / "就業規則_構造チェック報告書.docx"
            build_report(findings, saved_files, report_path)
            report_bytes = report_path.read_bytes()

    st.success(f"チェック完了: {len(findings)} 件の確認事項")
    st.download_button(
        label="Word報告書をダウンロード",
        data=report_bytes,
        file_name="就業規則_構造チェック報告書.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    st.subheader("検出事項プレビュー")
    st.dataframe(findings, use_container_width=True)
