import io
import pandas as pd
import xlsxwriter
from reports.queries import (
    query_balance,
    query_mayor,
    query_analisis_inteligente,
    query_historico,
    query_comprobante,
    query_relacion_grupos,
    query_pendientes_cuenta,
)


def _add_corp_header(ws, workbook, headers, title, company, extra_rows=None):
    f_corp = workbook.add_format({"bold": True, "font_size": 14, "align": "center"})
    f_info = workbook.add_format({"bold": True, "font_size": 10, "align": "center"})
    col_letter = xlsxwriter.utility.xl_col_to_name(len(headers) - 1)
    ws.merge_range(f"A1:{col_letter}1", title, f_corp)
    ws.merge_range(f"A2:{col_letter}2", f"EMPRESA: {company.name if company else 'N/A'}", f_info)
    if extra_rows:
        for i, txt in enumerate(extra_rows, start=3):
            ws.merge_range(f"A{i}:{col_letter}{i}", txt, f_info)
    return 4 + (len(extra_rows) if extra_rows else 0)


def export_balance_excel(company_id, company, fecha_db):
    df = query_balance(company_id, fecha_db)
    if df.empty:
        return None
    df["debe"] = pd.to_numeric(df["debe"], errors="coerce").fillna(0.0)
    df["haber"] = pd.to_numeric(df["haber"], errors="coerce").fillna(0.0)
    df["saldo_deudor"] = df.apply(lambda x: max(0, x["debe"] - x["haber"]), axis=1)
    df["saldo_acreedor"] = df.apply(lambda x: max(0, x["haber"] - x["debe"]), axis=1)
    def clasificar(row):
        digit = str(row["cuenta"])[0]
        net = row["debe"] - row["haber"]
        a = p = per = gan = 0
        if digit in ["1", "2"]:
            if net >= 0:
                a = net
            else:
                p = abs(net)
        else:
            if net >= 0:
                per = net
            else:
                gan = abs(net)
        return pd.Series([a, p, per, gan])
    df[["activo", "pasivo", "perdida", "ganancia"]] = df.apply(clasificar, axis=1)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Balance")
    headers = ["Cuenta", "Descripción", "Debe", "Haber", "S. Deudor", "S. Acreedor", "Activo", "Pasivo", "Pérdida", "Ganancia"]
    start = _add_corp_header(ws, workbook, headers, "BALANCE GENERAL TRIBUTARIO (8 COLUMNAS)", company,
                              [f"RUT: {company.rut if company else ''}", f"PERÍODO HASTA: {fecha_db}"])
    f_header = workbook.add_format({"bold": True, "bg_color": "#2C3E50", "font_color": "white", "border": 1, "align": "center"})
    f_num = workbook.add_format({"num_format": '"$" #,##0;[Red]"$" (#,##0)', "border": 1})
    f_border = workbook.add_format({"border": 1})
    f_total = workbook.add_format({"bold": True, "num_format": '"$" #,##0;[Red]"$" (#,##0)', "border": 1, "bg_color": "#2C3E50", "font_color": "white"})
    for i, h in enumerate(headers):
        ws.write(start, i, h, f_header)
        ws.set_column(i, i, 15 if i != 1 else 45)
    for r, row in df.iterrows():
        ws.write(start + 1 + r, 0, row["cuenta"], f_border)
        ws.write(start + 1 + r, 1, row["nombre_cuenta"], f_border)
        for c in range(2, 10):
            ws.write(start + 1 + r, c, row[headers[c].lower().replace(". ", "_").replace(" ", "_")], f_num)
    total_row = start + 1 + len(df)
    ws.write(total_row, 0, "SUMAS TOTALES", f_total)
    for c in range(2, 10):
        col_letter = xlsxwriter.utility.xl_col_to_name(c)
        ws.write_formula(total_row, c, f"=SUM({col_letter}{start + 2}:{col_letter}{total_row})", f_total)
    workbook.close()
    output.seek(0)
    return output


def export_mayor_excel(company_id, company, busqueda):
    df = query_mayor(company_id, busqueda)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Libro Mayor")
    headers = ["Comprobante", "Fecha", "Ficha/RUT", "Razón Social", "Documento", "Concepto", "Debe", "Haber", "Saldo"]
    start = _add_corp_header(ws, workbook, headers, "LIBRO MAYOR CONTABLE", company,
                              [f"RUT: {company.rut if company else ''}"])
    f_header = workbook.add_format({"bold": True, "bg_color": "#2C3E50", "font_color": "white", "border": 1, "align": "center"})
    f_num = workbook.add_format({"num_format": '"$" #,##0;[Red]"$" (#,##0)', "border": 1})
    f_text = workbook.add_format({"border": 1})
    f_total = workbook.add_format({"bold": True, "num_format": '"$" #,##0;[Red]"$" (#,##0)', "border": 1, "bg_color": "#D5D8DC"})
    f_acc = workbook.add_format({"bold": True, "bg_color": "#FAD7A0", "border": 1})
    for i, h in enumerate(headers):
        ws.write(start, i, h, f_header)
    current_row = start + 1
    for account, g in df.groupby("cuenta"):
        ws.merge_range(current_row, 0, current_row, 8, f"CUENTA: {account} {g.iloc[0]['nombre_cuenta']}", f_acc)
        current_row += 1
        running = 0
        sub_debe = sub_haber = 0
        for _, row in g.iterrows():
            d = float(row["debe"])
            h = float(row["haber"])
            running += (d - h)
            sub_debe += d
            sub_haber += h
            ws.write(current_row, 0, row["comprobante"], f_text)
            ws.write(current_row, 1, str(row["fecha"]) if row["fecha"] else "", f_text)
            ws.write(current_row, 2, row["ficha"] or "", f_text)
            ws.write(current_row, 3, row["razon_social"] or "", f_text)
            ws.write(current_row, 4, row["documento"] or "", f_text)
            ws.write(current_row, 5, row["concepto"] or "", f_text)
            ws.write(current_row, 6, d, f_num)
            ws.write(current_row, 7, h, f_num)
            ws.write(current_row, 8, running, f_num)
            current_row += 1
        ws.write(current_row, 0, "TOTAL CUENTA", f_total)
        for i in range(1, 6):
            ws.write_blank(current_row, i, None, f_total)
        ws.write(current_row, 6, sub_debe, f_total)
        ws.write(current_row, 7, sub_haber, f_total)
        ws.write(current_row, 8, running, f_total)
        current_row += 2
    workbook.close()
    output.seek(0)
    return output


def export_analisis_excel(company_id, company, busqueda):
    df = query_analisis_inteligente(company_id, busqueda)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Analisis")
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, "ANÁLISIS INTELIGENTE (PENDIENTES)", company)
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def export_historico_excel(company_id, company, busqueda):
    df = query_historico(company_id, busqueda)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Historico")
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, "HISTÓRICO COMPLETO", company)
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def export_comprobante_excel(company_id, company, busqueda):
    df = query_comprobante(company_id, busqueda)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Comprobante")
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, "COMPROBANTE CONTABLE", company)
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def export_relacion_excel(company_id, company, busqueda):
    df = query_relacion_grupos(company_id, busqueda)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Relacion")
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, "RELACIÓN CONCEPTOS/GRUPOS", company)
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def export_pendientes_excel(company_id, company, cuenta, acc_name, fecha_corte):
    df = query_pendientes_cuenta(company_id, cuenta, fecha_corte)
    if df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Pendientes")
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, f"DOCUMENTOS PENDIENTES - {cuenta}", company,
                              [f"CUENTA: {acc_name}", f"FECHA CORTE: {fecha_corte}"])
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def export_generic_excel(title, df, company, sheet_name="data"):
    if df is None or df.empty:
        return None
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet(sheet_name)
    headers = list(df.columns)
    start = _add_corp_header(ws, workbook, headers, title, company)
    _write_df_to_sheet(ws, workbook, df, headers, start)
    workbook.close()
    output.seek(0)
    return output


def _write_df_to_sheet(ws, workbook, df, headers, start_row):
    f_header = workbook.add_format({"bold": True, "bg_color": "#2C3E50", "font_color": "white", "border": 1})
    f_num = workbook.add_format({"num_format": '#,##0;[Red](#,##0)', "border": 1})
    f_text = workbook.add_format({"border": 1})
    for i, h in enumerate(headers):
        ws.write(start_row, i, h, f_header)
        ws.set_column(i, i, 18)
    for r, row in df.iterrows():
        for c, h in enumerate(headers):
            val = row[h]
            fmt = f_num if isinstance(val, (int, float)) else f_text
            ws.write(start_row + 1 + r, c, val if pd.notna(val) else "", fmt)
