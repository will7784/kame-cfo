from app import db


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    fecha = db.Column(db.String(10), nullable=True)
    comprobante = db.Column(db.String(50), nullable=True)
    cuenta = db.Column(db.String(30), nullable=False)
    nombre_cuenta = db.Column(db.String(200), nullable=True)
    ficha = db.Column(db.String(30), nullable=True)
    razon_social = db.Column(db.String(200), nullable=True)
    documento = db.Column(db.String(50), nullable=True)
    doc_referencia = db.Column(db.String(50), nullable=True)
    debe = db.Column(db.Numeric(18, 2), default=0)
    haber = db.Column(db.Numeric(18, 2), default=0)
    concepto = db.Column(db.Text, nullable=True)
    proyecto = db.Column(db.String(100), nullable=True)
    unidad_de_negocio = db.Column(db.String(100), nullable=True)
    vencimiento = db.Column(db.String(10), nullable=True)
