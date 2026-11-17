from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

CSV_PATH = (
    Path(__file__).parent
    / "data"
    / "pokemon.csv"
)

st.set_page_config(
    page_title="Dashboard Pokémon",
    page_icon="⚡",
    layout="wide",
)


# ---------------------------------------------------------
# CARGAR LOS DATOS
# ---------------------------------------------------------

@st.cache_data
def cargar_datos():
    """
    Lee el CSV y comprueba los tipos de las columnas.
    """

    df = pd.read_csv(
        CSV_PATH,
        parse_dates=["fecha_extraccion"],
    )

    df["precio_gbp"] = pd.to_numeric(
        df["precio_gbp"],
        errors="coerce",
    )

    df["stock"] = pd.to_numeric(
        df["stock"],
        errors="coerce",
    )

    df["peso_kg"] = pd.to_numeric(
        df["peso_kg"],
        errors="coerce",
    )

    df["categoria"] = (
        df["categoria"]
        .fillna("Sin clasificar")
    )

    df = df.dropna(
        subset=[
            "nombre",
            "precio_gbp",
            "stock",
        ]
    )

    return df


# ---------------------------------------------------------
# TÍTULO
# ---------------------------------------------------------

st.title("⚡ Dashboard de Pokémon")

st.write(
    "Aplicación interactiva para explorar los datos "
    "extraídos de ScrapeMe."
)


# ---------------------------------------------------------
# COMPROBAR EL CSV
# ---------------------------------------------------------

if not CSV_PATH.exists():
    st.error(
        "No se encuentra data/pokemon.csv. "
        "Ejecuta primero: python scraper.py"
    )

    st.stop()


df = cargar_datos()


if df.empty:
    st.error(
        "El archivo CSV no contiene datos válidos."
    )

    st.stop()


# ---------------------------------------------------------
# FILTROS LATERALES
# ---------------------------------------------------------

st.sidebar.header("Filtros")


# Filtro de categorías

categorias = sorted(
    df["categoria"].unique()
)

categorias_seleccionadas = (
    st.sidebar.multiselect(
        "Categorías",
        options=categorias,
        default=categorias,
    )
)


# Filtro de precios

precio_minimo = float(
    df["precio_gbp"].min()
)

precio_maximo = float(
    df["precio_gbp"].max()
)


if precio_minimo < precio_maximo:
    rango_precio = st.sidebar.slider(
        "Rango de precio (£)",
        min_value=precio_minimo,
        max_value=precio_maximo,
        value=(
            precio_minimo,
            precio_maximo,
        ),
        step=1.0,
    )
else:
    rango_precio = (
        precio_minimo,
        precio_maximo,
    )

    st.sidebar.info(
        f"Todos tienen el mismo precio: "
        f"£{precio_minimo:.2f}"
    )


# Filtro de stock

stock_maximo = int(
    df["stock"].max()
)


if stock_maximo > 0:
    stock_minimo = st.sidebar.slider(
        "Stock mínimo",
        min_value=0,
        max_value=stock_maximo,
        value=0,
    )
else:
    stock_minimo = 0


# Buscador por nombre

nombre_buscado = st.sidebar.text_input(
    "Buscar por nombre",
    placeholder="Ejemplo: Pikachu",
)


# ---------------------------------------------------------
# APLICAR LOS FILTROS
# ---------------------------------------------------------

mascara = (
    df["categoria"].isin(
        categorias_seleccionadas
    )
    & df["precio_gbp"].between(
        rango_precio[0],
        rango_precio[1],
    )
    & df["stock"].ge(
        stock_minimo
    )
    & df["nombre"].str.contains(
        nombre_buscado,
        case=False,
        na=False,
        regex=False,
    )
)

filtrado = df.loc[
    mascara
].copy()


if filtrado.empty:
    st.warning(
        "No hay Pokémon que cumplan "
        "los filtros seleccionados."
    )

    st.stop()


# ---------------------------------------------------------
# INDICADORES PRINCIPALES
# ---------------------------------------------------------

st.subheader("Resumen")


columna1, columna2, columna3, columna4 = (
    st.columns(4)
)


columna1.metric(
    "Pokémon encontrados",
    len(filtrado),
)


columna2.metric(
    "Categorías",
    filtrado["categoria"].nunique(),
)


precio_medio = filtrado[
    "precio_gbp"
].mean()


columna3.metric(
    "Precio medio",
    f"£{precio_medio:.2f}",
)


stock_total = filtrado[
    "stock"
].sum()


columna4.metric(
    "Stock total",
    f"{int(stock_total):,}",
)


# ---------------------------------------------------------
# FECHA DE EXTRACCIÓN
# ---------------------------------------------------------

ultima_extraccion = df[
    "fecha_extraccion"
].max()


if pd.notna(ultima_extraccion):
    st.caption(
        "Última extracción: "
        f"{ultima_extraccion.strftime('%d/%m/%Y %H:%M UTC')}"
    )


# ---------------------------------------------------------
# GRÁFICO 1: PRECIO MEDIO POR CATEGORÍA
# ---------------------------------------------------------

st.subheader(
    "Precio medio por categoría"
)


resumen_categorias = (
    filtrado
    .groupby(
        "categoria",
        as_index=False,
    )
    .agg(
        precio_medio=(
            "precio_gbp",
            "mean",
        ),
        cantidad=(
            "nombre",
            "count",
        ),
    )
    .nlargest(
        15,
        "precio_medio",
    )
    .sort_values(
        "precio_medio"
    )
)


figura_categorias = px.bar(
    resumen_categorias,
    x="precio_medio",
    y="categoria",
    orientation="h",
    color="cantidad",
    text_auto=".2f",
    labels={
        "precio_medio": "Precio medio (£)",
        "categoria": "Categoría",
        "cantidad": "Cantidad",
    },
    title=(
        "Las 15 categorías con "
        "mayor precio medio"
    ),
)


st.plotly_chart(
    figura_categorias,
    use_container_width=True,
)


# ---------------------------------------------------------
# GRÁFICO 2: PRECIO Y STOCK
# ---------------------------------------------------------

st.subheader(
    "Relación entre precio y stock"
)


figura_stock = px.scatter(
    filtrado,
    x="precio_gbp",
    y="stock",
    color="categoria",
    hover_name="nombre",
    hover_data={
        "peso_kg": True,
        "precio_gbp": ":.2f",
        "stock": True,
    },
    labels={
        "precio_gbp": "Precio (£)",
        "stock": "Stock disponible",
        "categoria": "Categoría",
        "peso_kg": "Peso (kg)",
    },
    title=(
        "¿Los Pokémon más caros "
        "tienen menos stock?"
    ),
)


st.plotly_chart(
    figura_stock,
    use_container_width=True,
)


# ---------------------------------------------------------
# GRÁFICO 3: DISTRIBUCIÓN DE PRECIOS
# ---------------------------------------------------------

st.subheader(
    "Distribución de precios"
)


figura_precios = px.histogram(
    filtrado,
    x="precio_gbp",
    nbins=20,
    labels={
        "precio_gbp": "Precio (£)",
        "count": "Número de Pokémon",
    },
    title="Distribución de los precios",
)


figura_precios.update_layout(
    bargap=0.05
)


st.plotly_chart(
    figura_precios,
    use_container_width=True,
)


# ---------------------------------------------------------
# ANÁLISIS DE LOS RESULTADOS
# ---------------------------------------------------------

st.subheader(
    "Interpretación de los resultados"
)


correlacion = filtrado[
    "precio_gbp"
].corr(
    filtrado["stock"]
)


if pd.isna(correlacion):
    st.info(
        "No hay suficientes datos para calcular "
        "la relación entre precio y stock."
    )
else:
    valor_absoluto = abs(
        correlacion
    )

    if valor_absoluto < 0.20:
        intensidad = "muy débil"
    elif valor_absoluto < 0.40:
        intensidad = "débil"
    elif valor_absoluto < 0.70:
        intensidad = "moderada"
    else:
        intensidad = "fuerte"

    if correlacion > 0:
        direccion = "positiva"
    elif correlacion < 0:
        direccion = "negativa"
    else:
        direccion = "nula"

    st.write(
        f"La correlación entre precio y stock "
        f"es **{correlacion:.2f}**. "
        f"La relación es **{intensidad} "
        f"y {direccion}**."
    )


categoria_mas_cara = (
    resumen_categorias.iloc[-1]
)


st.write(
    "La categoría con mayor precio medio "
    f"es **{categoria_mas_cara['categoria']}**, "
    "con un precio medio de "
    f"**£{categoria_mas_cara['precio_medio']:.2f}**."
)


st.info(
    "Los datos de ScrapeMe son datos de prueba. "
    "Las conclusiones sirven para practicar análisis, "
    "pero no representan un mercado real."
)


# ---------------------------------------------------------
# TABLA INTERACTIVA
# ---------------------------------------------------------

st.subheader(
    "Pokémon encontrados"
)


tabla = filtrado[
    [
        "imagen_url",
        "nombre",
        "categoria",
        "precio_gbp",
        "stock",
        "peso_kg",
        "sku",
        "url",
    ]
].rename(
    columns={
        "imagen_url": "Imagen",
        "nombre": "Nombre",
        "categoria": "Categoría",
        "precio_gbp": "Precio",
        "stock": "Stock",
        "peso_kg": "Peso",
        "sku": "SKU",
        "url": "Ficha",
    }
)


st.dataframe(
    tabla,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Imagen": st.column_config.ImageColumn(
            "Imagen"
        ),
        "Precio": st.column_config.NumberColumn(
            "Precio",
            format="£%.2f",
        ),
        "Stock": st.column_config.NumberColumn(
            "Stock",
            format="%d",
        ),
        "Peso": st.column_config.NumberColumn(
            "Peso",
            format="%.1f kg",
        ),
        "Ficha": st.column_config.LinkColumn(
            "Ficha",
            display_text="Abrir",
        ),
    },
)


# ---------------------------------------------------------
# DESCARGAR LOS RESULTADOS FILTRADOS
# ---------------------------------------------------------

csv_filtrado = filtrado.to_csv(
    index=False
).encode(
    "utf-8-sig"
)


st.download_button(
    label="Descargar resultados filtrados",
    data=csv_filtrado,
    file_name="pokemon_filtrados.csv",
    mime="text/csv",
)