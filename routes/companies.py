from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app import db
from models.company import Company
from models.ledger import LedgerEntry
from models.classification import CompanyClassification
import pandas as pd
import re
import os

bp = Blueprint("companies", __name__)


def _slug_from_rut(rut):
    clean = re.sub(r"[^0-9Kk]", "", str(rut or "")).upper()
    return clean or "empresa"


@bp.route("/companies")
@login_required
def list_companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    return render_template("companies.html", companies=companies)


@bp.route("/companies/new", methods=["POST"])
@login_required
def create_company():
    rut = request.form.get("rut", "").strip()
    name = request.form.get("name", "").strip()
    if not rut or not name:
        flash("RUT y Nombre son obligatorios", "warning")
        return redirect(url_for("companies.list_companies"))
    slug = _slug_from_rut(rut)
    existing = Company.query.filter_by(slug=slug).first()
    if existing:
        flash("Ya existe una empresa con ese RUT", "warning")
        return redirect(url_for("companies.list_companies"))
    company = Company(rut=rut, name=name, slug=slug)
    db.session.add(company)
    db.session.commit()
    flash(f"Empresa {name} creada", "success")
    return redirect(url_for("companies.list_companies"))


@bp.route("/companies/<int:company_id>/delete", methods=["POST"])
@login_required
def delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    LedgerEntry.query.filter_by(company_id=company.id).delete()
    CompanyClassification.query.filter_by(company_id=company.id).delete()
    db.session.delete(company)
    db.session.commit()
    flash(f"Empresa {company.name} eliminada", "info")
    return redirect(url_for("companies.list_companies"))


@bp.route("/companies/<int:company_id>/clasificacion", methods=["POST"])
@login_required
def upload_clasificacion(company_id):
    company = Company.query.get_or_404(company_id)
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No se seleccionó archivo", "warning")
        return redirect(url_for("companies.list_companies"))

    try:
        df = pd.read_excel(file)
        if "Cuenta Descripcion" in df.columns and "cuenta" not in df.columns:
            raw = df["Cuenta Descripcion"].astype(str).fillna("")
            df["cuenta"] = raw.str.extract(r"^\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", expand=False).fillna("")
            if (df["cuenta"] == "").all():
                df["cuenta"] = raw.str.split().str[0].fillna("")

        keep = [c for c in ["cuenta", "Reporte", "Detalle N1", "Detalle N2"] if c in df.columns]
        if not keep:
            flash("El archivo no tiene las columnas esperadas", "error")
            return redirect(url_for("companies.list_companies"))

        df = df[keep].copy()
        df["cuenta"] = df.get("cuenta", "").astype(str).str.strip()
        df["Reporte"] = df.get("Reporte", "").astype(str).str.strip().str.upper()
        df["Detalle N1"] = df.get("Detalle N1", "").astype(str).str.strip()
        df["Detalle N2"] = df.get("Detalle N2", "").astype(str).str.strip()
        df = df[df["cuenta"] != ""]

        CompanyClassification.query.filter_by(company_id=company_id).delete()
        records = []
        for _, row in df.iterrows():
            records.append({
                "company_id": company_id,
                "cuenta": row["cuenta"],
                "reporte": row["Reporte"],
                "detalle_n1": row["Detalle N1"],
                "detalle_n2": row["Detalle N2"],
            })
        if records:
            db.session.execute(db.insert(CompanyClassification), records)
            db.session.commit()
        flash(f"Clasificación cargada: {len(records)} cuentas", "success")
    except Exception as e:
        flash(f"Error al procesar clasificación: {e}", "error")
    return redirect(url_for("companies.list_companies"))
