import pandas as pd
from app import db
from sqlalchemy import text


def _sql_fecha_eff(alias: str = "l") -> str:
    return f"""COALESCE(
      NULLIF(TRIM({alias}.fecha), ''),
      (SELECT TRIM(l2.fecha) FROM ledger_entries l2
       WHERE l2.comprobante = {alias}.comprobante
         AND COALESCE(TRIM(l2.fecha), '') <> ''
         AND l2.company_id = {alias}.company_id
       LIMIT 1)
    )"""


def query_balance(company_id: int, fecha_tope: str) -> pd.DataFrame:
    """Balance de 8 columnas hasta fecha_tope (YYYY-MM-DD)."""
    sql = f"""
    WITH movs AS (
        SELECT
            TRIM(cuenta) AS cuenta,
            nombre_cuenta,
            {_sql_fecha_eff('l')} AS fecha_eff,
            COALESCE(CAST(debe AS REAL), 0) AS debe,
            COALESCE(CAST(haber AS REAL), 0) AS haber
        FROM ledger_entries l
        WHERE company_id = :cid
    )
    SELECT
        cuenta,
        COALESCE(MAX(NULLIF(TRIM(nombre_cuenta), '')), '-') AS nombre_cuenta,
        SUM(debe) AS debe,
        SUM(haber) AS haber
    FROM movs
    WHERE fecha_eff <= :fecha
    GROUP BY cuenta
    ORDER BY cuenta
    """
    df = pd.read_sql(text(sql), db.engine, params={"cid": company_id, "fecha": fecha_tope})
    return df


def query_mayor(company_id: int, busqueda: str) -> pd.DataFrame:
    """Libro Mayor filtrado por cuenta/nombre."""
    p = f"%{busqueda.upper()}%"
    sql = f"""
    SELECT
        fecha, comprobante, cuenta, nombre_cuenta,
        ficha, razon_social, documento, doc_referencia,
        COALESCE(CAST(debe AS REAL), 0) AS debe,
        COALESCE(CAST(haber AS REAL), 0) AS haber,
        concepto
    FROM ledger_entries
    WHERE company_id = :cid
      AND (UPPER(cuenta) LIKE :p OR UPPER(nombre_cuenta) LIKE :p
           OR UPPER(razon_social) LIKE :p OR UPPER(concepto) LIKE :p)
    ORDER BY cuenta, fecha, comprobante
    """
    return pd.read_sql(text(sql), db.engine, params={"cid": company_id, "p": p})


def query_analisis_inteligente(company_id: int, busqueda: str) -> pd.DataFrame:
    """Pendientes agrupados por ficha+documento."""
    terminos = [t.strip() for t in busqueda.split(",") if t.strip()]
    if not terminos:
        terminos = ["*"]
    params = {"cid": company_id}
    filtros = []
    for i, t in enumerate(terminos):
        key = f"p{i}"
        params[key] = f"%{t.upper()}%"
        filtros.append(
            f"(UPPER(l.nombre_cuenta) LIKE :{key} OR UPPER(l.razon_social) LIKE :{key} OR UPPER(l.ficha) LIKE :{key} OR UPPER(l.concepto) LIKE :{key})"
        )
    where_clause = " OR ".join(filtros)
    sql = f"""
    WITH saldos_vivos AS (
        SELECT cuenta, ficha, documento
        FROM ledger_entries
        WHERE company_id = :cid
        GROUP BY cuenta, ficha, documento
        HAVING ABS(SUM(COALESCE(CAST(debe AS REAL), 0) - COALESCE(CAST(haber AS REAL), 0))) > 0.1
    )
    SELECT
        l.fecha, l.comprobante, l.cuenta, l.nombre_cuenta,
        l.ficha, l.razon_social, l.documento, l.doc_referencia,
        (COALESCE(CAST(l.debe AS REAL), 0) - COALESCE(CAST(l.haber AS REAL), 0)) AS saldo
    FROM ledger_entries l
    INNER JOIN saldos_vivos sv
        ON l.cuenta = sv.cuenta
       AND COALESCE(l.ficha, '') = COALESCE(sv.ficha, '')
       AND COALESCE(l.documento, '') = COALESCE(sv.documento, '')
    WHERE l.company_id = :cid
      AND ({where_clause})
      AND SUBSTRING(l.cuenta, 1, 1) IN ('1','2','3','4')
    ORDER BY l.fecha, l.comprobante, l.cuenta, l.razon_social
    """
    return pd.read_sql(text(sql), db.engine, params=params)


def query_historico(company_id: int, busqueda: str) -> pd.DataFrame:
    """Histórico completo con columna pendiente."""
    terminos = [t.strip() for t in busqueda.split(",") if t.strip()]
    if not terminos:
        terminos = ["*"]
    params = {"cid": company_id}
    filtros = []
    for i, t in enumerate(terminos):
        key = f"p{i}"
        params[key] = f"%{t.upper()}%"
        filtros.append(
            f"(UPPER(l.nombre_cuenta) LIKE :{key} OR UPPER(l.razon_social) LIKE :{key} OR UPPER(l.ficha) LIKE :{key} OR UPPER(l.concepto) LIKE :{key})"
        )
    where_clause = " OR ".join(filtros)
    sql = f"""
    WITH saldos_doc AS (
        SELECT cuenta, ficha, documento,
               SUM(COALESCE(CAST(debe AS REAL), 0) - COALESCE(CAST(haber AS REAL), 0)) AS saldo_neto
        FROM ledger_entries
        WHERE company_id = :cid
        GROUP BY cuenta, ficha, documento
    )
    SELECT
        l.fecha, l.comprobante, l.cuenta, l.nombre_cuenta,
        l.ficha, l.razon_social, l.documento, l.doc_referencia, l.vencimiento,
        (COALESCE(CAST(l.debe AS REAL), 0) - COALESCE(CAST(l.haber AS REAL), 0)) AS saldo,
        CASE WHEN ABS(s.saldo_neto) > 0.1 THEN 'si' ELSE 'no' END AS pendiente,
        COALESCE(CAST(l.debe AS REAL), 0) AS debe,
        COALESCE(CAST(l.haber AS REAL), 0) AS haber,
        l.concepto
    FROM ledger_entries l
    JOIN saldos_doc s
      ON l.cuenta = s.cuenta
     AND COALESCE(l.ficha, '') = COALESCE(s.ficha, '')
     AND COALESCE(l.documento, '') = COALESCE(s.documento, '')
    WHERE l.company_id = :cid
      AND ({where_clause})
      AND SUBSTRING(l.cuenta, 1, 1) IN ('1','2','3','4')
    ORDER BY l.cuenta, l.fecha
    """
    return pd.read_sql(text(sql), db.engine, params=params)


def query_comprobante(company_id: int, busqueda: str) -> pd.DataFrame:
    """Asiento contable completo por comprobante."""
    sql = f"""
    SELECT
        {_sql_fecha_eff('l')} AS fecha,
        comprobante, cuenta, nombre_cuenta,
        ficha, razon_social, documento, vencimiento,
        COALESCE(CAST(debe AS REAL), 0) AS debe,
        COALESCE(CAST(haber AS REAL), 0) AS haber,
        concepto
    FROM ledger_entries l
    WHERE company_id = :cid
      AND comprobante LIKE :p
    ORDER BY comprobante, cuenta
    """
    return pd.read_sql(text(sql), db.engine, params={"cid": company_id, "p": f"%{busqueda}%"})


def query_relacion_grupos(company_id: int, busqueda: str) -> pd.DataFrame:
    """Relación de movimientos filtrados por cuenta/concepto."""
    pattern = busqueda.upper().replace("*", "%")
    if "%" not in pattern:
        pattern = f"%{pattern}%"
    sql = f"""
    SELECT
        {_sql_fecha_eff('l')} AS fecha,
        comprobante, cuenta, nombre_cuenta,
        ficha, razon_social,
        COALESCE(NULLIF(TRIM(COALESCE(documento, '')), ''), NULLIF(TRIM(COALESCE(doc_referencia, '')), ''), '-') AS doc_referencia,
        COALESCE(CAST(debe AS REAL), 0) AS debe,
        COALESCE(CAST(haber AS REAL), 0) AS haber,
        concepto
    FROM ledger_entries l
    WHERE company_id = :cid
      AND (UPPER(COALESCE(cuenta, '')) LIKE :p
           OR UPPER(COALESCE(nombre_cuenta, '')) LIKE :p
           OR UPPER(COALESCE(concepto, '')) LIKE :p)
    ORDER BY cuenta, fecha, comprobante
    """
    return pd.read_sql(text(sql), db.engine, params={"cid": company_id, "p": pattern})


def query_pendientes_cuenta(company_id: int, cuenta: str, fecha_corte: str) -> pd.DataFrame:
    """Documentos pendientes por cuenta específica hasta fecha_corte."""
    sql = """
    SELECT
        ficha AS "Auxiliar",
        razon_social,
        COALESCE(
            NULLIF(TRIM(COALESCE(documento, '')), ''),
            NULLIF(TRIM(COALESCE(doc_referencia, '')), ''),
            '-'
        ) AS "Documento Ref.",
        SUM(COALESCE(CAST(debe AS REAL), 0) - COALESCE(CAST(haber AS REAL), 0)) AS "Saldo Pendiente"
    FROM ledger_entries
    WHERE company_id = :cid
      AND TRIM(cuenta) = TRIM(:cuenta)
      AND fecha <= :fecha
    GROUP BY ficha, razon_social, COALESCE(
        NULLIF(TRIM(COALESCE(documento, '')), ''),
        NULLIF(TRIM(COALESCE(doc_referencia, '')), ''),
        '-'
    )
    HAVING ABS(SUM(COALESCE(CAST(debe AS REAL), 0) - COALESCE(CAST(haber AS REAL), 0))) > 0.1
    ORDER BY ficha, razon_social
    """
    return pd.read_sql(text(sql), db.engine, params={"cid": company_id, "cuenta": cuenta, "fecha": fecha_corte})
