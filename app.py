import streamlit as st
import google.generativeai as genai
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tutor ENARM GPC", page_icon="🩺", layout="wide")

# --- 2. CONEXIÓN CON GEMINI ---
def configurar_ia():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error("⚠️ Error: No se encontró la GEMINI_API_KEY en los Secrets de Streamlit.")
        return None

model = configurar_ia()

# --- 3. BÚSQUEDA DE ARCHIVOS (RECURSIVA) ---
def buscar_gpc():
    mapa_gpc = {}
    # Recorre todas las carpetas del repo
    for raiz, carpetas, archivos in os.walk("."):
        # Ignorar carpetas ocultas de sistema
        if ".git" in raiz or ".streamlit" in raiz:
            continue
        for archivo in archivos:
            if archivo.endswith(".md") and archivo.lower() != "readme.md":
                # Creamos una ruta amigable para el usuario y la ruta real para Python
                ruta_amigable = os.path.join(raiz, archivo).replace("./", "")
                ruta_real = os.path.join(raiz, archivo)
                mapa_gpc[ruta_amigable] = ruta_real
    return mapa_gpc

diccionario_gpc = buscar_gpc()

# --- 4. INTERFAZ DE USUARIO (SIDEBAR) ---
st.sidebar.title("🧠 Panel del Tutor")
st.sidebar.markdown("---")

if not diccionario_gpc:
    st.sidebar.warning("No se encontraron archivos .md en el repositorio.")
    opciones = []
else:
    opciones = list(diccionario_gpc.keys())

tema_seleccionado = st.sidebar.selectbox("📖 Selecciona una GPC:", opciones)

st.sidebar.markdown("---")
debilidad = st.sidebar.text_input("🎯 ¿En qué quieres enfocarte?", placeholder="Ej: Tratamiento, Diagnóstico...")
nivel = st.sidebar.select_slider("🔥 Nivel de dificultad:", options=["Interno", "Residente", "Especialista"])

# --- 5. CUERPO PRINCIPAL ---
st.title("👨‍⚕️ Simulador Clínico Inteligente")
st.info("Este tutor utiliza tus propios resúmenes para generar casos clínicos estilo ENARM.")

if st.button("🚀 Generar Caso Clínico"):
    if not tema_seleccionado:
        st.error("Por favor, selecciona una GPC en la barra lateral.")
    else:
        with st.spinner(f"Analizando {tema_seleccionado}..."):
            # Leer el archivo seleccionado
            ruta_archivo = diccionario_gpc[tema_seleccionado]
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                contenido_gpc = f.read()

            # Prompt maestro
            prompt = f"""
            Actúa como un sinodal experto del ENARM en México.
            Tu fuente de verdad principal es este resumen de GPC:
            ---
            {contenido_gpc}
            ---
            
            TAREA:
            1. Genera un caso clínico complejo de opción múltiple (estilo ENARM).
            2. El usuario quiere enfocarse en: {debilidad}.
            3. Dificultad: {nivel}.
            4. Si la GPC no tiene un dato necesario para la fisiopatología, usa tu conocimiento médico general, pero PRIORIZA las conductas de la GPC.
            5. Presenta el caso, luego 4 opciones (A, B, C, D) y al final la respuesta correcta con una justificación clara basada en la normativa mexicana.
            """

            try:
                response = model.generate_content(prompt)
                st.markdown("---")
                st.markdown(response.text)
                
                # Botón de feedback rápido
                st.session_state.caso_generado = True
            except Exception as e:
                st.error(f"Hubo un problema con la IA: {e}")

# --- 6. LOG DE ERRORES (EL CORAZÓN DEL ESTUDIO) ---
st.sidebar.markdown("---")
if st.sidebar.button("❌ Fallé esta pregunta"):
    st.sidebar.error("Anotado. Reforzaremos este tema en la próxima sesión.")
    # TODO: Aquí podrías guardar esto en un JSON en el futuro para que el sistema "evolucione"