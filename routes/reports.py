import io
from flask import Blueprint, request, send_file, abort
from flask_login import login_required
from app import db
from models.company import Company
from models.ledger import LedgerEntry
import xlsxwriter

bp = Blueprint("reports", __name__)


@bp.route("/reports/ledger-excel")
@login_required
def export_ledger_excel():
    company_id = request.args.get("company_id", type=int)
    search = request.args.get("search", "").strip()
    if not company_id:
        abort(400)

    company = Company.query.get(company_id)
    if not company:
        abort(404)

    query = LedgerEntry.query.filter_by(company_id=company_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                LedgerEntry.cuenta.ilike(like),
                LedgerEntry.nombre_cuenta.ilike(like),
                LedgerEntry.razon_social.ilike(like),
                LedgerEntry.comprobante.ilike(like),
            )
        )

    entries = query.order_by(LedgerEntry.fecha.desc().nullslast(), LedgerEntry.id).all()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    # Formatos
    f_corp = workbook.add_format({"bold": True, "font_size": 14, "align": "center"})
    f_info = workbook.add_format({"bold": True, "font_size": 10, "align": "center"})
    f_header = workbook.add_format({"bold": True, "bg_color": "#2C3E50", "font_color": "white", "border": 1})
    f_num = workbook.add_format({"num_format": '#,##0;[Red](#,##0)', "border": 1})
    f_text = workbook.add_format({"border": 1})
    f_total = workbook.add_format({"bold": True, "num_format": '#,##0;[Red](#,##0)', "border": 1, "bg_color": "#F2F2F2"})
    f_total_text = workbook.add_format({"bold": True, "border": 1, "bg_color": "#F2F2F2"})

    ws = workbook.add_worksheet("Ledger")
    ws.freeze_panes(6, 0)

    # Cabecera corporativa
    headers = ["Fecha", "Comprobante", "Cuenta", "Nombre Cuenta", "Ficha", "Razón Social", "Documento", "Debe", "Haber", "Concepto"]
    num_cols = len(headers)
    col_letter = xlsxwriter.utility.xl_col_to_name(num_cols - 1)
    ws.merge_range(f"A1:{col_letter}1", "REPORTE LEDGER CONTABLE", f_corp)
    ws.merge_range(f"A2:{col_letter}2", f"EMPRESA: {company.name}", f_info)
    ws.merge_range(f"A3:{col_letter}3", f"RUT: {company.rut}", f_info)
    ws.merge_range(f"A4:{col_letter}4", f"REGISTROS: {len(entries)}", f_info)

    # Encabezados de tabla
    for i, h in enumerate(headers):
        ws.write(5, i, h, f_header)
        ws.set_column(i, i, 18)
    ws.set_column(9, 9, 40)  # Concepto más ancho

    # Datos
    t_debe = t_haber = 0
    for row_num, e in enumerate(entries):
        r = row_num + 6
        ws.write(r, 0, str(e.fecha) if e.fecha else "", f_text)
        ws.write(r, 1, e.comprobante or "", f_text)
        ws.write(r, 2, e.cuenta or "", f_text)
        ws.write(r, 3, e.nombre_cuenta or "", f_text)
        ws.write(r, 4, e.ficha or "", f_text)
        ws.write(r, 5, e.razon_social or "", f_text)
        ws.write(r, 6, e.documento or "", f_text)
        ws.write(r, 7, float(e.debe or 0), f_num)
        ws.write(r, 8, float(e.haber or 0), f_num)
        ws.write(r, 9, e.concepto or "", f_text)
        t_debe += float(e.debe or 0)
        t_haber += float(e.haber or 0)

    # Totales
    total_row = 6 + len(entries)
    ws.write(total_row, 0, "TOTAL", f_total_text)
    for c in range(1, 7):
        ws.write_blank(total_row, c, None, f_total_text)
    ws.write(total_row, 7, t_debe, f_total)
    ws.write(total_row, 8, t_haber, f_total)
    ws.write_blank(total_row, 9, None, f_total_text)

    # Autofiltro
    ws.autofilter(5, 0, total_row, num_cols - 1)

    workbook.close()
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"ledger_{company.slug}.xlsx",
    )
