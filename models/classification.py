from app import db


class CompanyClassification(db.Model):
    __tablename__ = "company_classifications"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    cuenta = db.Column(db.String(30), nullable=False)
    reporte = db.Column(db.String(10), nullable=False)  # EESS o PYG
    detalle_n1 = db.Column(db.String(100), nullable=True)
    detalle_n2 = db.Column(db.String(100), nullable=True)
