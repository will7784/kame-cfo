# KAME CFO — Checkpoint de Sesión

> Fecha: 2026-06-05 ~01:50 AM (UTC-5)
> Commit: `b38dfa5` en `main`
> Repositorio: https://github.com/will7784/kame-cfo.git

---

## Estado del Proyecto

### Fases completadas
- **Fase 1**: Scaffold Flask + Login + Empresas + Importador Ledger + Vista Ledger + Export Excel
- **Fase 2 (Core Reports)**: Balance 8 Col, Libro Mayor, Análisis Inteligente, Histórico Completo, Comprobante Contable, Relación Grupos, Notas de Cuentas (Reviews)
- **Fase 3 (Informes Gestión)**: EESS, PYG, Libro de Ventas, Clasificación por empresa, Pendientes drill-down

### Stack
- Flask 3.x, Flask-SQLAlchemy, Flask-Login, PostgreSQL (Railway)
- Pandas, XlsxWriter, openpyxl
- Gunicorn (`web: gunicorn app:app`)
- Python 3.13 (sin `runtime.txt`)

---

## Estructura de archivos clave

```
kame-cfo/
├── app.py                      # App factory, db.create_all(), admin seed
├── config.py                   # DATABASE_URL con postgres:// fix
├── models/
│   ├── user.py                 # User (admin will/7784)
│   ├── company.py              # Company
│   ├── ledger.py               # LedgerEntry (fechas como String(10)!)
│   └── classification.py       # CompanyClassification (NUEVO)
├── routes/
│   ├── auth.py
│   ├── companies.py            # + /companies/<id>/config (upload clasificacion)
│   ├── ledger.py
│   └── reports.py              # + /informes/eess, /informes/pyg, /informes/ventas, /pendientes/<cuenta>
├── reports/
│   ├── queries.py              # query_balance, mayor, analisis, historico, comprobante, relacion, pendientes_cuenta
│   └── excel.py                # to_excel_bytes() con XlsxWriter
├── templates/
│   ├── dashboard.html          # Grid de reportes
│   ├── reports/
│   │   ├── balance.html        # Links a drill-down de pendientes
│   │   ├── eess.html           # NUEVO
│   │   ├── pyg.html            # NUEVO
│   │   ├── pendientes.html     # NUEVO
│   │   └── informes.html       # Menú de informes
│   └── companies/
│       └── config.html         # NUEVO — upload clasificacion.xlsx
└── requirements.txt
```

---

## Modelos (resumen)

### LedgerEntry
- `company_id`, `fecha` (String 10), `comprobante`, `cuenta`, `nombre_cuenta`
- `ficha`, `razon_social`, `documento`, `doc_referencia`
- `debe`/`haber` (Numeric 18,2), `concepto`, `proyecto`, `unidad_de_negocio`, `vencimiento` (String 10)

### CompanyClassification
- `company_id`, `cuenta` (String 50), `descripcion`, `reporte`, `detalle_n1`, `detalle_n2`
- Único por `(company_id, cuenta)`

---

## Rutas implementadas (todas con `@login_required`)

| Ruta | Excel export | Notas |
|------|-------------|-------|
| `/reports/balance?company_id=&fecha=` | ✅ `/reports/balance/excel` | Cuentas son links a pendientes |
| `/reports/mayor?company_id=&busqueda=` | ✅ `/reports/mayor/excel` | |
| `/reports/analisis?company_id=&busqueda=` | ✅ `/reports/analisis/excel` | |
| `/reports/historico?company_id=&busqueda=` | ✅ `/reports/historico/excel` | |
| `/reports/comprobante?company_id=&busqueda=` | ✅ `/reports/comprobante/excel` | |
| `/reports/relacion?company_id=&busqueda=` | ✅ `/reports/relacion/excel` | |
| `/reviews` (CRUD notas) | — | |
| `/reports/pendientes/<cuenta>?company_id=&fecha_corte=` | — | Drill-down desde Balance |
| `/reports/informes` | — | Menú EESS/PYG/Ventas |
| `/reports/informes/eess?company_id=&year=` | — | Requiere clasificacion subida |
| `/reports/informes/pyg?company_id=&year=` | — | Requiere clasificacion subida |
| `/reports/informes/ventas?company_id=&year=` | — | |
| `/companies/<id>/config` (POST/GET) | — | Upload clasificacion.xlsx |

---

## Compatibilidad PostgreSQL vs SQLite

| Aspecto | Solución aplicada |
|---------|-------------------|
| Fechas | `String(10)` en vez de `Date` |
| Año filter | `LIKE '2026-%'` |
| Substring | `SUBSTRING(cuenta, 1, 1)` |
| CTE ambiguo | Usar alias `l.cuenta`, `l.ficha` en WHERE |
| Connection string | Reemplazar `postgres://` → `postgresql://` |

---

## Issues conocidas / pendientes

1. **RESET_DB**: Verificar que `RESET_DB=0` o no esté definida en Railway. Si está en `1`, los datos se borran en cada deploy/restart.
2. **EESS/PYG sin clasificación**: Si no hay clasificacion subida, los informes muestran tablas vacías. Se podría mejorar con un mensaje claro.
3. **Libro de Ventas**: Actualmente filtra `cuenta LIKE '411%'` o `nombre_cuenta ILIKE '%venta%'`. Podría necesitar ajuste según el plan de cuentas de cada empresa.
4. **Excel exports para EESS/PYG/Ventas**: No están implementados aún. Se puede agregar fácilmente en `reports/excel.py` + rutas.
5. **Pendientes drill-down**: Solo accesible desde el Balance. Se podría agregar link también desde Mayor, Análisis, etc.

---

## Cómo continuar mañana

1. Verificar que Railway haya hecho deploy de `b38dfa5`
2. Probar upload de `clasificacion.xlsx` en `/companies/<id>/config`
3. Validar que EESS y PYG generen números correctos comparando con el Excel original
4. Implementar Excel export para EESS/PYG/Ventas si se necesita
5. Agregar mejor manejo de errores cuando no hay clasificación

---

## Credenciales de admin (seed)
- Usuario: `will`
- Password: `7784`

## Variable de entorno crítica
- `DATABASE_URL` → debe estar copiada del servicio Postgres al servicio App en Railway
