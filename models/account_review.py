from app import db


class AccountReview(db.Model):
    __tablename__ = "account_reviews"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    cuenta = db.Column(db.String(30), nullable=False)
    fecha_balance = db.Column(db.String(10), nullable=False, default="GLOBAL")
    aprobado = db.Column(db.Boolean, default=False)
    nota = db.Column(db.Text, nullable=False, default="")
    usuario = db.Column(db.String(80), nullable=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (db.UniqueConstraint("company_id", "cuenta", "fecha_balance"),)
