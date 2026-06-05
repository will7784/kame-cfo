import pandas as pd
from datetime import datetime, date


def _safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "<na>", "nat"):
        return ""
    return s


def normalizar_texto(txt):
    import unicodedata
    import re
    if not isinstance(txt, str):
        return str(txt)
    txt = txt.lower()
    txt = "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))
    txt = re.sub(r"[^a-z0-9]+", "_", txt)
    txt = re.sub(r"_+", "_", txt).strip("_")
    return txt


def parse_kame_excel(file_path, sheet_name=0):
    path = str(file_path or "").strip()
    lower = path.lower()
    if lower.endswith(".csv"):
        last_err = None
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(path, sep=";", encoding=enc, header=0, dtype=str)
                break
            except Exception as e:
                last_err = e
        else:
            raise last_err
    else:
        df = pd.read_excel(path, sheet_name=sheet_name, header=0)

    # Normalizar columnas
    df.columns = [normalizar_texto(c) for c in df.columns]

    # Alias defensivos
    if "razon_social" not in df.columns:
        alt = [c for c in df.columns if ("social" in c and "raz" in c)]
        if alt:
            df = df.rename(columns={alt[0]: "razon_social"})

    # Combinar Tipo + Comprobante
    if "tipo" in df.columns and "comprobante" in df.columns:
        df["comprobante"] = df["tipo"].astype(str).str[0].str.lower() + df["comprobante"].astype(str)

    # Proyecto / Unidad de Negocio
    if "unidad_de_negocio" in df.columns:
        df["proyecto"] = df["unidad_de_negocio"]

    # Normalizar Fecha a ISO
    if "fecha" in df.columns:
        fecha_dt = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
        if fecha_dt.isna().any():
            if "comprobante" in df.columns:
                by_comp = fecha_dt.groupby(df["comprobante"]).transform("first")
                fecha_dt = fecha_dt.fillna(by_comp)
            fecha_dt = fecha_dt.ffill()
        df["fecha"] = fecha_dt.dt.strftime("%Y-%m-%d")

    # Validaciones básicas
    required_cols = ["cuenta", "nombre_cuenta", "debe", "haber"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")

    # doc_referencia
    df["doc_referencia"] = df.get("documento", pd.Series([""] * len(df))).astype(str)

    # Convertir numéricos
    for col in ["debe", "haber", "saldo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce").fillna(0)

    # Asegurar columnas extras existan
    for col in ["ficha", "razon_social", "documento", "concepto", "proyecto", "unidad_de_negocio", "vencimiento"]:
        if col not in df.columns:
            df[col] = ""

    # Convertir a lista de dicts para bulk insert
    records = []
    for _, row in df.iterrows():
        fecha_val = row.get("fecha")
        venc_val = row.get("vencimiento")
        fecha_str = None
        if pd.notna(fecha_val) and str(fecha_val).strip() not in ("", "nan", "None", "NaT"):
            try:
                fecha_str = datetime.strptime(str(fecha_val), "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                fecha_str = None
        venc_str = None
        if pd.notna(venc_val) and str(venc_val).strip() not in ("", "nan", "None", "NaT"):
            try:
                venc_str = datetime.strptime(str(venc_val), "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                venc_str = None

        record = {
            "fecha": fecha_str,
            "comprobante": _safe_str(row.get("comprobante")),
            "cuenta": _safe_str(row.get("cuenta")),
            "nombre_cuenta": _safe_str(row.get("nombre_cuenta")),
            "ficha": _safe_str(row.get("ficha")),
            "razon_social": _safe_str(row.get("razon_social")),
            "documento": _safe_str(row.get("documento")),
            "doc_referencia": _safe_str(row.get("doc_referencia")),
            "debe": float(row.get("debe", 0) or 0),
            "haber": float(row.get("haber", 0) or 0),
            "concepto": _safe_str(row.get("concepto")),
            "proyecto": _safe_str(row.get("proyecto")),
            "unidad_de_negocio": _safe_str(row.get("unidad_de_negocio")),
            "vencimiento": venc_str,
        }
        records.append(record)

    return records
