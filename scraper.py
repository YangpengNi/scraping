import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

BASE_URL = "https://scrapeme.live/"

SHOP_URL = urljoin(
    BASE_URL,
    "product-category/pokemon/",
)

ROBOTS_URL = urljoin(
    BASE_URL,
    "robots.txt",
)

OUTPUT_PATH = (
    Path(__file__).parent
    / "data"
    / "pokemon.csv"
)

USER_AGENT = (
    "ProyectoEducativoPokemonScraping/1.0 "
    "(uso académico)"
)

REQUEST_DELAY = 1.0

# Primero prueba con 20.
# Después puedes usar 100 o None para descargar todo.
MAX_PRODUCTS = 20


# ---------------------------------------------------------
# CREAR LA CONEXIÓN
# ---------------------------------------------------------

def crear_sesion():
    """
    Crea una sesión HTTP con cabeceras y reintentos.
    """

    session = requests.Session()

    reintentos = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    adaptador = HTTPAdapter(
        max_retries=reintentos
    )

    session.mount(
        "https://",
        adaptador,
    )

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "es,en;q=0.8",
        }
    )

    return session


# ---------------------------------------------------------
# COMPROBAR ROBOTS.TXT
# ---------------------------------------------------------

def obtener_robots(session):
    """
    Descarga y analiza robots.txt.
    """

    response = session.get(
        ROBOTS_URL,
        timeout=20,
    )

    time.sleep(REQUEST_DELAY)

    if response.status_code == 404:
        print(
            "El sitio no tiene robots.txt."
        )
        return None

    response.raise_for_status()

    robots = RobotFileParser()
    robots.set_url(ROBOTS_URL)

    robots.parse(
        response.text.splitlines()
    )

    return robots


# ---------------------------------------------------------
# DESCARGAR UNA PÁGINA
# ---------------------------------------------------------

def descargar_pagina(
    session,
    robots,
    url,
):
    """
    Comprueba robots.txt, descarga una página
    y convierte el HTML con BeautifulSoup.
    """

    if robots is not None:
        permitido = robots.can_fetch(
            USER_AGENT,
            url,
        )

        if not permitido:
            raise PermissionError(
                f"robots.txt no permite acceder a {url}"
            )

    response = session.get(
        url,
        timeout=20,
    )

    response.raise_for_status()

    time.sleep(REQUEST_DELAY)

    soup = BeautifulSoup(
        response.content,
        "html.parser",
    )

    return soup


# ---------------------------------------------------------
# CONVERTIR TEXTO EN NÚMERO
# ---------------------------------------------------------

def extraer_numero(
    texto,
    valor_defecto=None,
):
    """
    Extrae el primer número de un texto.

    Ejemplos:
    £63.00       -> 63.0
    254 in stock -> 254
    13.2 kg      -> 13.2
    """

    coincidencia = re.search(
        r"\d+(?:[.,]\d+)?",
        texto,
    )

    if coincidencia is None:
        return valor_defecto

    numero_texto = coincidencia.group()

    numero_texto = numero_texto.replace(
        ",",
        ".",
    )

    return float(numero_texto)


# ---------------------------------------------------------
# EXTRAER UNA FICHA INDIVIDUAL
# ---------------------------------------------------------

def extraer_detalle_pokemon(
    soup,
    producto_url,
    imagen_url,
    fecha_extraccion,
):
    """
    Extrae los datos de la ficha individual
    de un Pokémon.
    """

    nombre_tag = soup.select_one(
        "h1.product_title"
    )

    precio_tag = soup.select_one(
        "div.summary p.price"
    )

    stock_tag = soup.select_one(
        "p.stock"
    )

    sku_tag = soup.select_one(
        "span.sku"
    )

    descripcion_tag = soup.select_one(
        "div.woocommerce-product-details__short-description"
    )

    peso_tag = soup.select_one(
        "tr.woocommerce-product-attributes-item--weight td"
    )

    if nombre_tag is None:
        raise ValueError(
            f"No se encontró el nombre en {producto_url}"
        )

    if precio_tag is None:
        raise ValueError(
            f"No se encontró el precio en {producto_url}"
        )

    nombre = nombre_tag.get_text(
        strip=True
    )

    precio_texto = precio_tag.get_text(
        " ",
        strip=True,
    )

    precio = extraer_numero(
        precio_texto
    )

    if stock_tag is not None:
        stock_texto = stock_tag.get_text(
            " ",
            strip=True,
        )
    else:
        stock_texto = "0"

    stock = extraer_numero(
        stock_texto,
        valor_defecto=0,
    )

    if sku_tag is not None:
        sku = sku_tag.get_text(
            strip=True
        )
    else:
        sku = "Sin SKU"

    if descripcion_tag is not None:
        descripcion = descripcion_tag.get_text(
            " ",
            strip=True,
        )
    else:
        descripcion = ""

    if peso_tag is not None:
        peso_texto = peso_tag.get_text(
            " ",
            strip=True,
        )

        peso_kg = extraer_numero(
            peso_texto
        )
    else:
        peso_kg = None

    categorias = []

    for enlace in soup.select(
        "span.posted_in a"
    ):
        categoria = enlace.get_text(
            strip=True
        )

        if categoria.lower() != "pokemon":
            categorias.append(
                categoria
            )

    if categorias:
        categoria_final = " / ".join(
            categorias
        )
    else:
        categoria_final = "Sin clasificar"

    etiquetas = []

    for enlace in soup.select(
        "span.tagged_as a"
    ):
        etiquetas.append(
            enlace.get_text(strip=True)
        )

    etiquetas_texto = ", ".join(
        etiquetas
    )

    pokemon = {
        "nombre": nombre,
        "precio_gbp": precio,
        "stock": int(stock),
        "sku": sku,
        "categoria": categoria_final,
        "etiquetas": etiquetas_texto,
        "descripcion": descripcion,
        "peso_kg": peso_kg,
        "imagen_url": imagen_url,
        "url": producto_url,
        "fecha_extraccion": fecha_extraccion,
    }

    return pokemon


# ---------------------------------------------------------
# RECORRER EL CATÁLOGO
# ---------------------------------------------------------

def extraer_catalogo():
    """
    Recorre las páginas del catálogo y abre
    la ficha individual de cada Pokémon.
    """

    datos = []

    urls_visitadas = set()

    pagina_url = SHOP_URL

    numero_pagina = 1

    fecha_extraccion = datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )

    session = crear_sesion()

    robots = obtener_robots(
        session
    )

    while pagina_url is not None:
        print(
            f"Procesando página {numero_pagina}"
        )

        soup = descargar_pagina(
            session,
            robots,
            pagina_url,
        )

        productos = soup.select(
            "li.product"
        )

        if not productos:
            raise ValueError(
                "No se encontraron productos "
                f"en {pagina_url}"
            )

        for producto in productos:
            enlace = producto.select_one(
                "a.woocommerce-LoopProduct-link, "
                "a.woocommerce-loop-product__link"
            )

            if enlace is None:
                continue

            producto_url = urljoin(
                pagina_url,
                enlace["href"],
            )

            if producto_url in urls_visitadas:
                continue

            imagen_tag = producto.select_one(
                "img"
            )

            imagen_url = ""

            if imagen_tag is not None:
                imagen_url = (
                    imagen_tag.get("data-src")
                    or imagen_tag.get("src")
                    or ""
                )

                imagen_url = urljoin(
                    pagina_url,
                    imagen_url,
                )

            detalle_soup = descargar_pagina(
                session,
                robots,
                producto_url,
            )

            pokemon = extraer_detalle_pokemon(
                detalle_soup,
                producto_url,
                imagen_url,
                fecha_extraccion,
            )

            datos.append(
                pokemon
            )

            urls_visitadas.add(
                producto_url
            )

            print(
                f"{len(datos):03d} - "
                f"{pokemon['nombre']}"
            )

            if MAX_PRODUCTS is not None:
                if len(datos) >= MAX_PRODUCTS:
                    session.close()
                    return datos

        siguiente = soup.select_one(
            "a.next.page-numbers, a.next"
        )

        if siguiente is not None:
            pagina_url = urljoin(
                pagina_url,
                siguiente["href"],
            )
        else:
            pagina_url = None

        numero_pagina += 1

    session.close()

    return datos


# ---------------------------------------------------------
# LIMPIAR Y GUARDAR EL CSV
# ---------------------------------------------------------

def validar_y_guardar(datos):
    """
    Convierte los datos en un DataFrame,
    comprueba su calidad y crea el CSV.
    """

    if not datos:
        raise ValueError(
            "No se ha extraído ningún Pokémon."
        )

    df = pd.DataFrame(
        datos
    )

    df["nombre"] = (
        df["nombre"]
        .str.strip()
    )

    df["categoria"] = (
        df["categoria"]
        .str.strip()
    )

    df["precio_gbp"] = pd.to_numeric(
        df["precio_gbp"],
        errors="raise",
    )

    df["stock"] = pd.to_numeric(
        df["stock"],
        errors="raise",
    ).astype(
        "int64"
    )

    df["peso_kg"] = pd.to_numeric(
        df["peso_kg"],
        errors="coerce",
    )

    df["fecha_extraccion"] = pd.to_datetime(
        df["fecha_extraccion"],
        utc=True,
        errors="raise",
    )

    df = df.drop_duplicates(
        subset="url"
    )

    df = df.reset_index(
        drop=True
    )

    columnas_obligatorias = [
        "nombre",
        "precio_gbp",
        "stock",
        "categoria",
        "url",
    ]

    hay_vacios = (
        df[columnas_obligatorias]
        .isna()
        .any()
        .any()
    )

    if hay_vacios:
        raise ValueError(
            "Hay datos vacíos en columnas obligatorias."
        )

    precios_correctos = (
        df["precio_gbp"] > 0
    ).all()

    if not precios_correctos:
        raise ValueError(
            "Se encontraron precios incorrectos."
        )

    stock_correcto = (
        df["stock"] >= 0
    ).all()

    if not stock_correcto:
        raise ValueError(
            "Se encontraron valores de stock incorrectos."
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    return df


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

def main():
    """
    Ejecuta todas las partes del scraper.
    """

    print("Iniciando scraper...")
    print()

    datos = extraer_catalogo()

    df = validar_y_guardar(
        datos
    )

    print()
    print("Scraping terminado.")
    print(f"Archivo: {OUTPUT_PATH}")
    print(f"Pokémon extraídos: {len(df)}")

    precio_medio = df[
        "precio_gbp"
    ].mean()

    stock_total = df[
        "stock"
    ].sum()

    print(
        f"Precio medio: £{precio_medio:.2f}"
    )

    print(
        f"Stock total: {stock_total}"
    )


if __name__ == "__main__":
    main()