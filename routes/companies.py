from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from models.company import Company
import re

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
