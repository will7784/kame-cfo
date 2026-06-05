import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app import db
from models.company import Company
from models.ledger import LedgerEntry
from parsers.kame import parse_kame_excel
from werkzeug.utils import secure_filename
import re

bp = Blueprint("ledger", __name__)


def _clean_path(path):
    path = path.strip()
    if path.startswith("& "):
        path = path[2:].strip()
    while (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
        path = path[1:-1].strip()
    return path


@bp.route("/ledger")
@login_required
def view_ledger():
    company_id = request.args.get("company_id", type=int)
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 50

    company = None
    if company_id:
        company = Company.query.get(company_id)

    query = LedgerEntry.query
    if company_id:
        query = query.filter_by(company_id=company_id)
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

    pagination = query.order_by(LedgerEntry.fecha.desc().nullslast(), LedgerEntry.id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    companies = Company.query.order_by(Company.name).all()
    return render_template(
        "ledger.html",
        pagination=pagination,
        companies=companies,
        company=company,
        search=search,
    )


@bp.route("/ledger/import", methods=["POST"])
@login_required
def import_ledger():
    company_id = request.form.get("company_id", type=int)
    if not company_id:
        flash("Selecciona una empresa primero", "warning")
        return redirect(url_for("ledger.view_ledger"))

    company = Company.query.get(company_id)
    if not company:
        flash("Empresa no encontrada", "error")
        return redirect(url_for("ledger.view_ledger"))

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No se seleccionó archivo", "warning")
        return redirect(url_for("ledger.view_ledger"))

    # Guardar temporalmente
    filename = secure_filename(file.filename)
    tmp_path = os.path.join(current_app.instance_path, filename)
    os.makedirs(current_app.instance_path, exist_ok=True)
    file.save(tmp_path)

    try:
        records = parse_kame_excel(tmp_path)
        if not records:
            flash("El archivo no contiene registros válidos", "warning")
            return redirect(url_for("ledger.view_ledger", company_id=company_id))

        # Borrar años presentes en el upload (misma lógica que SQLite pero en PostgreSQL)
        incoming_years = set()
        for r in records:
            f = r.get("fecha")
            if f and len(str(f)) >= 4:
                try:
                    y = int(str(f)[:4])
                    if 1900 < y < 2100:
                        incoming_years.add(str(y))
                except ValueError:
                    pass

        if incoming_years:
            # Borrar entries del company_id cuyo año de fecha esté en incoming_years
            # Usamos SQL directo por eficiencia
            years_list = list(incoming_years)
            # Construimos OR de condiciones LIKE 'YYYY%'
            conditions = " OR ".join([f"fecha LIKE '{y}-%%'" for y in years_list])
            db.session.execute(
                db.text(f"DELETE FROM ledger_entries WHERE company_id = :cid AND ({conditions})"),
                {"cid": company_id},
            )
            # También borrar filas sin fecha de comprobantes presentes
            comps = list({r["comprobante"] for r in records if r.get("comprobante")})
            if comps:
                chunk = 800
                for i in range(0, len(comps), chunk):
                    chunk_vals = comps[i : i + chunk]
                    db.session.execute(
                        db.text(
                            """
                            DELETE FROM ledger_entries
                            WHERE company_id = :cid
                              AND (fecha IS NULL OR TRIM(COALESCE(fecha::text, '')) = '')
                              AND comprobante IN :comps
                            """
                        ),
                        {"cid": company_id, "comps": tuple(chunk_vals)},
                    )

        # Insertar bulk
        for r in records:
            r["company_id"] = company_id
        db.session.execute(db.insert(LedgerEntry), records)
        db.session.commit()
        flash(f"Importados {len(records)} registros para {company.name}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al importar: {e}", "error")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return redirect(url_for("ledger.view_ledger", company_id=company_id))
