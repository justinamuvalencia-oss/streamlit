import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard de Tickets", layout="wide", page_icon="")

DATA_FILE = "Tickets.xlsx"


@st.cache_data
def load_data(path):
    sol = pd.read_excel(path, sheet_name="Solicitudes")
    inc = pd.read_excel(path, sheet_name="Incidentes")

    sol = sol.rename(columns={
        "Unidad organizativa": "Unidad Organizativa",
        "Categoría": "Categoria",
        "Descricion": "Descripcion",
    })
    sol["Tipo"] = "Solicitud"
    sol["Subcategoria"] = None

    inc = inc.rename(columns={
        "Servicios": "Servicio",
        "Fecha Modificación": "Fecha de Modificación",
    })
    inc["Tipo"] = "Incidente"

    common_cols = [
        "Ticket", "Tipo", "Origen", "Asunto", "Estado", "Cliente",
        "Unidad Organizativa", "Servicio", "Categoria", "Subcategoria",
        "Urgencia", "Equipo", "Propietario", "Creado el", "Fecha de solucion",
        "Infringido ANS Respuesta", "Infringido ANS Solucion",
        "Tiempo Reportado", "Fecha de Modificación", "Contrato Cliente",
    ]

    df = pd.concat([sol[common_cols], inc[common_cols]], ignore_index=True)

    df["Tiempo Reportado (h)"] = (
        df["Tiempo Reportado"].astype(str).str.replace(",", ".", regex=False)
        .astype(float) / 60
    )

    df["Urgencia"] = df["Urgencia"].fillna("Sin definir").replace("", "Sin definir")
    df["Creado el"] = pd.to_datetime(df["Creado el"])
    df["Mes"] = df["Creado el"].dt.to_period("M").dt.to_timestamp()

    estados_cerrados = ["Cerrado", "Resuelto", "Cancelado"]
    df["Abierto"] = ~df["Estado"].isin(estados_cerrados)

    return df


df = load_data(DATA_FILE)

# ---------------- SIDEBAR: FILTROS ----------------
st.sidebar.header("Filtros")

tipo_sel = st.sidebar.multiselect(
    "Tipo", options=sorted(df["Tipo"].unique()), default=list(df["Tipo"].unique())
)

min_date = df["Creado el"].min().date()
max_date = df["Creado el"].max().date()
fecha_sel = st.sidebar.date_input(
    "Rango de fechas", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

equipo_sel = st.sidebar.multiselect("Equipo", options=sorted(df["Equipo"].dropna().unique()))
estado_sel = st.sidebar.multiselect("Estado", options=sorted(df["Estado"].dropna().unique()))
urgencia_sel = st.sidebar.multiselect("Urgencia", options=sorted(df["Urgencia"].dropna().unique()))

f = df[df["Tipo"].isin(tipo_sel)]

if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
    f = f[(f["Creado el"].dt.date >= fecha_sel[0]) & (f["Creado el"].dt.date <= fecha_sel[1])]

if equipo_sel:
    f = f[f["Equipo"].isin(equipo_sel)]
if estado_sel:
    f = f[f["Estado"].isin(estado_sel)]
if urgencia_sel:
    f = f[f["Urgencia"].isin(urgencia_sel)]

st.sidebar.markdown(f"**{len(f):,} tickets** después de filtros")

# ---------------- HEADER ----------------
st.title("Dashboard de Mesa de Servicio")
st.caption("Solicitudes e Incidentes")

# ---------------- KPIs ----------------
total = len(f)
cerrados = f["Estado"].isin(["Cerrado", "Resuelto"]).sum()
pct_cerrados = (cerrados / total * 100) if total else 0
incumplidos = int(f["Infringido ANS Solucion"].sum())
pct_incumplido = (incumplidos / total * 100) if total else 0
tiempo_prom = f["Tiempo Reportado (h)"].mean() if total else 0
abiertos = int(f["Abierto"].sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total tickets", f"{total:,}")
k2.metric("Resueltos / Cerrados", f"{pct_cerrados:.1f}%")
k3.metric("Incumplimiento SLA", f"{pct_incumplido:.1f}%", delta=f"{incumplidos} tickets", delta_color="inverse")
k4.metric("Tiempo prom. resolución", f"{tiempo_prom:.1f} h")
k5.metric("Tickets abiertos", f"{abiertos:,}")

st.divider()

# ---------------- TABS ----------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["Resumen general", "Carga por equipo", "Clientes y categorías", "Cumplimiento SLA"]
)

with tab1:
    c1, c2 = st.columns([2, 1])

    with c1:
        por_mes = f.groupby(["Mes", "Tipo"]).size().reset_index(name="Tickets")
        fig = px.line(por_mes, x="Mes", y="Tickets", color="Tipo", markers=True,
                      title="Tickets creados por mes")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        por_urgencia = f["Urgencia"].value_counts().reset_index()
        por_urgencia.columns = ["Urgencia", "Tickets"]
        fig = px.pie(por_urgencia, names="Urgencia", values="Tickets",
                     title="Distribución por urgencia", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    por_estado = f["Estado"].value_counts().reset_index()
    por_estado.columns = ["Estado", "Tickets"]
    fig = px.bar(por_estado, x="Estado", y="Tickets", title="Tickets por estado", text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    por_equipo = f["Equipo"].value_counts().reset_index()
    por_equipo.columns = ["Equipo", "Tickets"]
    fig = px.bar(por_equipo.sort_values("Tickets"), x="Tickets", y="Equipo", orientation="h",
                 title="Tickets por equipo", text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

    tiempo_equipo = (
        f.groupby("Equipo")["Tiempo Reportado (h)"].mean()
        .reset_index().sort_values("Tiempo Reportado (h)")
    )
    fig = px.bar(tiempo_equipo, x="Tiempo Reportado (h)", y="Equipo", orientation="h",
                 title="Tiempo promedio de resolución por equipo (horas)", text_auto=".1f")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    c1, c2 = st.columns(2)
    with c1:
        top_clientes = f["Cliente"].value_counts().head(10).reset_index()
        top_clientes.columns = ["Cliente", "Tickets"]
        fig = px.bar(top_clientes.sort_values("Tickets"), x="Tickets", y="Cliente", orientation="h",
                     title="Top 10 clientes con más tickets", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        top_cat = f["Categoria"].value_counts().head(10).reset_index()
        top_cat.columns = ["Categoria", "Tickets"]
        fig = px.bar(top_cat.sort_values("Tickets"), x="Tickets", y="Categoria", orientation="h",
                     title="Top 10 categorías", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    incumplidos_df = f[f["Infringido ANS Solucion"] == True]
    st.subheader(f"Tickets con SLA de solución incumplido ({len(incumplidos_df)})")

    por_equipo_sla = f.groupby("Equipo")["Infringido ANS Solucion"].mean().reset_index()
    por_equipo_sla["Infringido ANS Solucion"] *= 100
    por_equipo_sla.columns = ["Equipo", "% Incumplimiento"]
    fig = px.bar(por_equipo_sla.sort_values("% Incumplimiento"), x="% Incumplimiento", y="Equipo",
                 orientation="h", title="% de incumplimiento de SLA por equipo", text_auto=".1f")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        incumplidos_df[[
            "Ticket", "Tipo", "Cliente", "Equipo", "Urgencia",
            "Creado el", "Fecha de solucion", "Tiempo Reportado (h)"
        ]].sort_values("Creado el", ascending=False),
        use_container_width=True,
        hide_index=True,
    )