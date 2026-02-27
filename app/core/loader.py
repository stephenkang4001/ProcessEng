"""
데이터 로딩 모듈
CSV 및 Excel 파일을 로드합니다. 인코딩 자동 감지 및 멀티 시트 처리를 지원합니다.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import pandas as pd

ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]


def load_csv(file_obj) -> pd.DataFrame:
    """
    CSV 파일을 로드합니다. 여러 인코딩을 순서대로 시도합니다.

    Parameters
    ----------
    file_obj : file-like object (Streamlit UploadedFile 또는 경로)

    Returns
    -------
    pd.DataFrame
    """
    raw_bytes = file_obj.read()

    for enc in ENCODINGS:
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc)
            if not df.empty:
                return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    raise ValueError(
        "지원되지 않는 파일 인코딩입니다. "
        "UTF-8 또는 EUC-KR(CP949) 형식으로 저장 후 다시 시도해주세요."
    )


def load_excel(
    file_obj, sheet_name: Optional[str] = None
) -> tuple[pd.DataFrame, list[str]]:
    """
    Excel 파일을 로드합니다.

    Returns
    -------
    (DataFrame, 시트명 목록)
    """
    xls = pd.ExcelFile(file_obj)
    sheets = xls.sheet_names
    selected = sheet_name if sheet_name else sheets[0]
    df = pd.read_excel(xls, sheet_name=selected)
    return df, sheets


def load_sample(sample_type: str) -> pd.DataFrame:
    """
    내장 샘플 데이터를 로드합니다.

    Parameters
    ----------
    sample_type : "purchase" | "running_example"
    """
    base_dir = Path(__file__).parent.parent.parent / "sample_data"

    if sample_type == "purchase":
        path = base_dir / "purchase_process.csv"
        return pd.read_csv(path, encoding="utf-8-sig")
    elif sample_type == "running_example":
        path = base_dir / "running_example.csv"
        return pd.read_csv(path, encoding="utf-8")
    else:
        raise ValueError(f"알 수 없는 샘플 타입: {sample_type}")
