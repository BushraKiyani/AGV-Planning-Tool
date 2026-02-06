from __future__ import annotations

from pathlib import Path
from typing import Iterator, Union

import pandas as pd

PathLike = Union[str, Path]

def iter_inputs(input_path: PathLike) -> Iterator[Path]:
    p = Path(input_path)
    if p.is_file():
        yield p
        return
    if p.is_dir():
        pdfs = sorted(p.glob("*.pdf"))
        pdf_stems = {f.stem for f in pdfs}

        # yield PDFs first
        for f in pdfs:
            yield f

        # yield TXTs only if no same-stem PDF exists
        for f in sorted(p.glob("*.txt")):
            if f.stem not in pdf_stems:
                yield f
        return

    raise FileNotFoundError(str(p))


def write_output_table(df: pd.DataFrame, out_path: PathLike) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
