import streamlit as st
import google.generativeai as genai
import os
import json
import re

st.set_page_config(page_title="Tutor ENARM IA", page_icon="🩺", layout="wide")

# --- 1. CONFIGURACIÓN DE IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("⚠️ Falla crítica: No se encontró GEMINI_API_KEY en los Secrets.")
    st.stop()

# --- 2. SISTEMA DE BASE DE DATOS LOCAL (JSON) ---
ARCHIVO_HISTORIAL = "historial_enarm.json"

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"aciertos": 0, "errores": 0, "temas": {}}

def guardar_historial(datos):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4)

if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()

def registrar_respuesta(tema, es_correcta):
    hist = st.session_state.historial
    # Actualizar totales
    if es_correcta:
        hist["aciertos"] += 1
    else:
        hist["errores"] += 1
    
    # Actualizar por tema
    if tema not in hist["temas"]:
        hist["temas"][tema] = {"aciertos": 0, "errores": 0}
    
    if es_correcta:
        hist["temas"][tema]["aciertos"] += 1
    else:
        hist["temas"][tema]["errores"] += 1
        
    guardar_historial(hist)

# --- 3. ESTADO DEL SIMULADOR ---
if "caso_actual" not in st.session_state:
    st.session_state.caso_actual = None
if "evaluado" not in st.session_state:
    st.session_state.evaluado = False

# --- 4. BÚSQUEDA DE ARCHIVOS ---
def buscar_gpc():
    mapa = {}
    for raiz, carpetas, archivos in os.walk("."):
        if ".git" in raiz or ".streamlit" in raiz: continue
        for arch in archivos:
            if arch.endswith(".md") and arch.lower() != "readme.md":
                nombre = arch.replace(".md", "")
                mapa[nombre] = os.path.join(raiz, arch)
    return mapa

diccionario_gpc = buscar_gpc()

# --- 5. INTERFAZ: SIDEBAR ---
st.sidebar.title("⚙️ Configuración ENARM")
tema_seleccionado = st.sidebar.selectbox("📖 Selecciona Tema:", sorted(list(diccionario_gpc.keys())))

# Clasificación Taxonomía de Bloom
dificultad_bloom = st.sidebar.radio("🧠 Nivel Cognitivo (Bloom):", [
    "Bajo (Recordar/Comprender - Memoria)",
    "Medio (Aplicar - Casos clínicos directos)",
    "Alto (Analizar/Evaluar - ¿Qué hacer a continuación?)"
], index=2) # Por defecto en ALTO

# --- 6. PESTAÑAS DE NAVEGACIÓN ---
tab1, tab2 = st.tabs(["📝 Simulador Clínico", "📊 Mi Rendimiento"])

with tab1:
    st.title("Simulador de Casos ENARM")
    
    if st.button("🚀 Generar Caso de este Tema"):
        with st.spinner("El sinodal está creando un caso con trampa..."):
            with open(diccionario_gpc[tema_seleccionado], "r", encoding="utf-8") as f:
                contenido = f.read()

            prompt = f"""
            Eres un creador de reactivos para el ENARM. Usa la GPC: {contenido}
            Crea 1 pregunta de caso clínico.
            
            REGLAS ESTRICTAS DEL ENARM:
            - Nivel de Taxonomía de Bloom: {dificultad_bloom}.
            - Si es nivel Medio/Alto, NO preguntes teoría. Pregunta "¿Cuál es el estudio inicial?", "¿Cuál es el estándar de oro?", o "¿Cuál es el manejo definitivo/siguiente paso?".
            - Usa distractores que parezcan correctos pero que no sean la primera línea de la GPC.
            
            DEVUELVE SOLO UN JSON (sin comillas markdown) con esta estructura:
            {{
                "historia_clinica": "Paciente...",
                "pregunta": "¿Cuál es el siguiente paso en el manejo?",
                "opciones": ["A) ", "B) ", "C) ", "D) "],
                "respuesta_correcta": "A) ",
                "justificacion": "Explicación heurística y médica"
            }}
            """
            
            try:
                modelo = genai.GenerativeModel('gemini-3.1-flash-lite') # o el que uses
                resp = modelo.generate_content(prompt)
                texto_limpio = re.sub(r'```json\n|```\n?', '', resp.text).strip()
                st.session_state.caso_actual = json.loads(texto_limpio)
                st.session_state.evaluado = False
            except Exception as e:
                st.error(f"Error generando el JSON: {e}")

    # Renderizar el caso
    if st.session_state.caso_actual:
        caso = st.session_state.caso_actual
        st.info(caso["historia_clinica"])
        
        with st.form("examen"):
            st.write(f"**{caso['pregunta']}**")
            respuesta_usuario = st.radio("Selecciona tu respuesta:", caso["opciones"])
            submit = st.form_submit_button("Calificar")
            
            if submit:
                st.session_state.evaluado = True
                es_correcta = respuesta_usuario == caso["respuesta_correcta"]
                # GUARDAR EN LA BASE DE DATOS LOCAL
                registrar_respuesta(tema_seleccionado, es_correcta)
                
        if st.session_state.evaluado:
            st.markdown("---")
            if respuesta_usuario == caso["respuesta_correcta"]:
                st.success("✅ ¡Correcto!")
            else:
                st.error("❌ Incorrecto")
                st.write(f"Tu respuesta: `{respuesta_usuario}`")
            
            st.write(f"**Respuesta Correcta:** `{caso['respuesta_correcta']}`")
            st.write(f"**Análisis:** {caso['justificacion']}")

with tab2:
    st.title("📊 Dashboard Analítico ENARM")
    hist = st.session_state.historial
    
    total_preguntas = hist["aciertos"] + hist["errores"]
    
    if total_preguntas == 0:
        st.info("Aún no tienes historial. ¡Resuelve tu primer caso!")
    else:
        # Métricas Generales
        col1, col2, col3 = st.columns(3)
        col1.metric("Casos Resueltos", total_preguntas)
        col2.metric("Aciertos", hist["aciertos"])
        efectividad = round((hist["aciertos"] / total_preguntas) * 100, 1)
        col3.metric("Efectividad Global", f"{efectividad}%")
        
        st.markdown("### 🎯 Desempeño por Tema (GPC)")
        
        # Crear datos para la gráfica
        datos_grafica = {"Aciertos": {}, "Errores": {}}
        for t, stats in hist["temas"].items():
            datos_grafica["Aciertos"][t] = stats["aciertos"]
            datos_grafica["Errores"][t] = stats["errores"]
            
        st.bar_chart(datos_grafica)
        
        st.markdown("### 🚨 Temas Prioritarios a Repasar")
        # Mostrar los temas donde hay más errores que aciertos
        for t, stats in hist["temas"].items():
            if stats["errores"] > stats["aciertos"]:
                st.error(f"🔥 {t}: {stats['errores']} errores vs {stats['aciertos']} aciertos")