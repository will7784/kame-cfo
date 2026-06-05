import io
import re
import pandas as pd
from flask import Blueprint, request, render_template, send_file, flash, redirect, url_for, abort
from flask_login import login_required
from sqlalchemy import text
from app import db
from models.company import Company
from models.account_review import AccountReview
from reports.queries import (
    query_balance,
    query_mayor,
    query_analisis_inteligente,
    query_historico,
    query_comprobante,
    query_relacion_grupos,
    query_pendientes_cuenta,
)
from reports.excel import (
    export_balance_excel,
    export_mayor_excel,
    export_analisis_excel,
    export_historico_excel,
    export_comprobante_excel,
    export_relacion_excel,
    export_pendientes_excel,
    export_generic_excel,
)

bp = Blueprint("reports", __name__)


def _get_company(company_id):
    return Company.query.get(company_id) if company_id else None


def _fmt_miles(n):
    try:
        v = float(n)
        if abs(v) < 0.5:
            return "-"
        s = f"{abs(v):,.0f}".replace(",", ".")
        return f"({s})" if v < 0 else s
    except Exception:
        return "-"


# ---------- BALANCE ----------

@bp.route("/reports/balance", methods=["GET"])
@login_required
def report_balance():
    company_id = request.args.get("company_id", type=int)
    fecha = request.args.get("fecha", "").strip()
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    if not fecha:
        from datetime import datetime
        fecha = datetime.now().strftime("%d-%m-%Y")
    try:
        fecha_db = __import__("datetime").datetime.strptime(fecha, "%d-%m-%Y").strftime("%Y-%m-%d")
    except Exception:
        fecha_db = __import__("datetime").datetime.now().strftime("%Y-%m-%d")

    df = query_balance(company_id, fecha_db)
    if not df.empty:
        df["debe"] = pd.to_numeric(df["debe"], errors="coerce").fillna(0.0)
        df["haber"] = pd.to_numeric(df["haber"], errors="coerce").fillna(0.0)
        def classify(row):
            digit = str(row["cuenta"])[0]
            net = float(row["debe"]) - float(row["haber"])
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
        df[["activo", "pasivo", "perdida", "ganancia"]] = df.apply(classify, axis=1)
        summary = {
            "activo": float(df["activo"].sum()),
            "pasivo": float(df["pasivo"].sum()),
            "perdida": float(df["perdida"].sum()),
            "ganancia": float(df["ganancia"].sum()),
        }
    else:
        summary = None
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/balance.html", df=df, company=company, companies=companies, fecha=fecha, summary=summary)


@bp.route("/reports/balance/excel")
@login_required
def report_balance_excel():
    company_id = request.args.get("company_id", type=int)
    fecha = request.args.get("fecha", "").strip()
    if not company_id or not fecha:
        abort(400)
    try:
        fecha_db = __import__("datetime").datetime.strptime(fecha, "%d-%m-%Y").strftime("%Y-%m-%d")
    except Exception:
        fecha_db = fecha
    company = _get_company(company_id)
    output = export_balance_excel(company_id, company, fecha_db)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_balance", company_id=company_id, fecha=fecha))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"balance_{company.slug}_{fecha_db}.xlsx")


# ---------- LIBRO MAYOR ----------

@bp.route("/reports/mayor", methods=["GET"])
@login_required
def report_mayor():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    df = query_mayor(company_id, busqueda)
    if not df.empty:
        df["debe"] = pd.to_numeric(df["debe"], errors="coerce").fillna(0.0)
        df["haber"] = pd.to_numeric(df["haber"], errors="coerce").fillna(0.0)
        df["saldo"] = (df["debe"] - df["haber"]).cumsum()
        summary = {
            "debe": float(df["debe"].sum()),
            "haber": float(df["haber"].sum()),
            "saldo": float(df["debe"].sum() - df["haber"].sum()),
        }
    else:
        summary = None
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/mayor.html", df=df, company=company, companies=companies, busqueda=busqueda, summary=summary)


@bp.route("/reports/mayor/excel")
@login_required
def report_mayor_excel():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        abort(400)
    company = _get_company(company_id)
    output = export_mayor_excel(company_id, company, busqueda)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_mayor", company_id=company_id, busqueda=busqueda))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"mayor_{company.slug}.xlsx")


# ---------- ANÁLISIS INTELIGENTE ----------

@bp.route("/reports/analisis", methods=["GET"])
@login_required
def report_analisis():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    df = query_analisis_inteligente(company_id, busqueda)
    summary = None
    if not df.empty and "saldo" in df.columns:
        summary = {"saldo": float(df["saldo"].sum())}
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/analisis.html", df=df, company=company, companies=companies, busqueda=busqueda, summary=summary)


@bp.route("/reports/analisis/excel")
@login_required
def report_analisis_excel():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        abort(400)
    company = _get_company(company_id)
    output = export_analisis_excel(company_id, company, busqueda)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_analisis", company_id=company_id, busqueda=busqueda))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"analisis_{company.slug}.xlsx")


# ---------- HISTÓRICO COMPLETO ----------

@bp.route("/reports/historico", methods=["GET"])
@login_required
def report_historico():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    df = query_historico(company_id, busqueda)
    summary = None
    if not df.empty:
        summary = {"registros": len(df)}
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/historico.html", df=df, company=company, companies=companies, busqueda=busqueda, summary=summary)


@bp.route("/reports/historico/excel")
@login_required
def report_historico_excel():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        abort(400)
    company = _get_company(company_id)
    output = export_historico_excel(company_id, company, busqueda)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_historico", company_id=company_id, busqueda=busqueda))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"historico_{company.slug}.xlsx")


# ---------- COMPROBANTE ----------

@bp.route("/reports/comprobante", methods=["GET"])
@login_required
def report_comprobante():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "").strip()
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    df = None
    summary = None
    if busqueda:
        df = query_comprobante(company_id, busqueda)
        if not df.empty:
            summary = {"total": float(df["debe"].sum())}
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/comprobante.html", df=df, company=company, companies=companies, busqueda=busqueda, summary=summary)


@bp.route("/reports/comprobante/excel")
@login_required
def report_comprobante_excel():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "").strip()
    if not company_id or not busqueda:
        abort(400)
    company = _get_company(company_id)
    output = export_comprobante_excel(company_id, company, busqueda)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_comprobante", company_id=company_id, busqueda=busqueda))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"comprobante_{company.slug}.xlsx")


# ---------- RELACIÓN CONCEPTOS/GRUPOS ----------

@bp.route("/reports/relacion", methods=["GET"])
@login_required
def report_relacion():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    df = query_relacion_grupos(company_id, busqueda)
    if not df.empty:
        df["saldo"] = pd.to_numeric(df["debe"], errors="coerce").fillna(0) - pd.to_numeric(df["haber"], errors="coerce").fillna(0)
        summary = {
            "debe": float(df["debe"].sum()),
            "haber": float(df["haber"].sum()),
            "saldo": float(df["saldo"].sum()),
            "registros": len(df),
        }
    else:
        summary = None
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/relacion.html", df=df, company=company, companies=companies, busqueda=busqueda, summary=summary)


@bp.route("/reports/relacion/excel")
@login_required
def report_relacion_excel():
    company_id = request.args.get("company_id", type=int)
    busqueda = request.args.get("busqueda", "*").strip() or "*"
    if not company_id:
        abort(400)
    company = _get_company(company_id)
    output = export_relacion_excel(company_id, company, busqueda)
    if output is None:
        flash("Sin datos", "warning")
        return redirect(url_for("reports.report_relacion", company_id=company_id, busqueda=busqueda))
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"relacion_{company.slug}.xlsx")


# ---------- NOTAS CUENTAS (ACCOUNT REVIEWS) ----------

@bp.route("/reviews", methods=["GET"])
@login_required
def list_reviews():
    company_id = request.args.get("company_id", type=int)
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    reviews = AccountReview.query.filter_by(company_id=company_id).order_by(AccountReview.updated_at.desc()).all()
    companies = Company.query.order_by(Company.name).all()
    return render_template("reviews/list.html", reviews=reviews, company=company, companies=companies)


@bp.route("/reviews/new", methods=["POST"])
@login_required
def create_review():
    company_id = request.form.get("company_id", type=int)
    cuenta = request.form.get("cuenta", "").strip()
    nota = request.form.get("nota", "").strip()
    aprobado = request.form.get("aprobado") == "on"
    if not company_id or not cuenta or len(nota) < 2:
        flash("Cuenta y nota son obligatorios (mínimo 2 caracteres)", "warning")
        return redirect(url_for("reports.list_reviews", company_id=company_id))
    review = AccountReview(
        company_id=company_id,
        cuenta=cuenta,
        aprobado=aprobado,
        nota=nota,
        usuario=__import__("flask_login").current_user.username,
    )
    db.session.add(review)
    db.session.commit()
    flash("Nota guardada", "success")
    return redirect(url_for("reports.list_reviews", company_id=company_id))


@bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    review = AccountReview.query.get_or_404(review_id)
    cid = review.company_id
    db.session.delete(review)
    db.session.commit()
    flash("Nota eliminada", "info")
    return redirect(url_for("reports.list_reviews", company_id=cid))


# ---------- INFORMES EESS / PYG / VENTAS ----------

@bp.route("/reports/informes", methods=["GET"])
@login_required
def report_informes():
    company_id = request.args.get("company_id", type=int)
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    companies = Company.query.order_by(Company.name).all()

    # Periodos disponibles
    from datetime import date
    periods = []
    try:
        p_df = pd.read_sql(text("""
            SELECT DISTINCT SUBSTR(fecha, 1, 4) AS y, SUBSTR(fecha, 6, 2) AS m
            FROM ledger_entries
            WHERE company_id = :cid AND COALESCE(TRIM(fecha), '') <> ''
            ORDER BY y DESC, m DESC
        """), db.engine, params={"cid": company_id})
        for _, r in p_df.iterrows():
            try:
                y, m = int(r["y"]), int(r["m"])
                if 1900 < y < 2100 and 1 <= m <= 12:
                    periods.append((y, m))
            except Exception:
                pass
    except Exception:
        pass

    return render_template("reports/informes.html", company=company, companies=companies, periods=periods)


@bp.route("/reports/eess", methods=["GET"])
@login_required
def report_eess():
    company_id = request.args.get("company_id", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not company_id or not year or not month:
        flash("Selecciona empresa y período", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))
    company = _get_company(company_id)

    from models.classification import CompanyClassification
    cf = pd.read_sql(
        CompanyClassification.query.filter_by(company_id=company_id, reporte="EESS").statement,
        db.engine
    )
    if cf.empty:
        flash("No hay clasificación EESS cargada para esta empresa", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))

    from datetime import date
    end_iso = date(year, month, 1).isoformat()[:8] + str(__import__('calendar').monthrange(year, month)[1])
    bal = query_eess(company_id, end_iso)
    if bal.empty:
        flash("No hay datos contables para ese período", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))

    work = cf.merge(bal, how="left", on="cuenta")
    work["saldo"] = pd.to_numeric(work["saldo"], errors="coerce").fillna(0.0)
    work["detalle_n1"] = work.get("detalle_n1", "").astype(str).str.strip()
    work["detalle_n2"] = work.get("detalle_n2", "").astype(str).str.strip()

    # Agrupar por detalle_n1
    grouped = work.groupby("detalle_n1", dropna=False)["saldo"].sum().reset_index()
    grouped = grouped[grouped["detalle_n1"] != ""]
    grouped["saldo_fmt"] = grouped["saldo"].apply(lambda x: _fmt_miles(x))

    pyg_ref = query_pyg_ytd(company_id, end_iso)
    total_activo = float(grouped[grouped["detalle_n1"].str.contains("activo", case=False, na=False)]["saldo"].sum())
    total_pasivo = float(grouped[grouped["detalle_n1"].str.contains("pasivo", case=False, na=False)]["saldo"].sum())
    total_patrimonio = float(grouped[grouped["detalle_n1"].str.contains("patrimonio", case=False, na=False)]["saldo"].sum()) + pyg_ref

    summary = {
        "activo": total_activo,
        "pasivo": total_pasivo,
        "patrimonio": total_patrimonio,
        "pyg_ref": pyg_ref,
        "cuadre": total_activo - (total_pasivo + total_patrimonio),
    }
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/eess.html", grouped=grouped, company=company, companies=companies,
                           year=year, month=month, summary=summary)


@bp.route("/reports/pyg", methods=["GET"])
@login_required
def report_pyg():
    company_id = request.args.get("company_id", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not company_id or not year or not month:
        flash("Selecciona empresa y período", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))
    company = _get_company(company_id)

    from models.classification import CompanyClassification
    cf = pd.read_sql(
        CompanyClassification.query.filter_by(company_id=company_id, reporte="PYG").statement,
        db.engine
    )
    if cf.empty:
        flash("No hay clasificación PYG cargada para esta empresa", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))

    from datetime import date
    start_iso = date(year, month, 1).isoformat()
    end_iso = date(year, month, __import__('calendar').monthrange(year, month)[1]).isoformat()
    bal = query_pyg(company_id, start_iso, end_iso)
    if bal.empty:
        flash("No hay movimientos en ese mes", "warning")
        return redirect(url_for("reports.report_informes", company_id=company_id))

    work = cf.merge(bal, how="left", on="cuenta")
    work["monto"] = pd.to_numeric(work["monto"], errors="coerce").fillna(0.0)
    work["detalle_n1"] = work.get("detalle_n1", "").astype(str).str.strip()
    work["detalle_n2"] = work.get("detalle_n2", "").astype(str).str.strip()

    grouped = work.groupby("detalle_n1", dropna=False)["monto"].sum().reset_index()
    grouped = grouped[grouped["detalle_n1"] != ""]
    grouped["monto_fmt"] = grouped["monto"].apply(lambda x: _fmt_miles(x))

    neto = float(grouped["monto"].sum())
    summary = {"neto": neto}
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/pyg.html", grouped=grouped, company=company, companies=companies,
                           year=year, month=month, summary=summary)


@bp.route("/reports/pendientes/<cuenta>", methods=["GET"])
@login_required
def report_pendientes_cuenta(cuenta):
    company_id = request.args.get("company_id", type=int)
    fecha_corte = request.args.get("fecha_corte", "").strip()
    if not company_id:
        flash("Selecciona una empresa", "warning")
        return redirect(url_for("main.dashboard"))
    company = _get_company(company_id)
    if not fecha_corte:
        from datetime import datetime
        fecha_corte = datetime.now().strftime("%Y-%m-%d")
    df = query_pendientes_cuenta(company_id, cuenta, fecha_corte)
    summary = None
    if not df.empty:
        summary = {"saldo": float(df["Saldo Pendiente"].sum())}
    companies = Company.query.order_by(Company.name).all()
    return render_template("reports/pendientes.html", df=df, cuenta=cuenta, company=company,
                           companies=companies, fecha_corte=fecha_corte, summary=summary)
