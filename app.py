import streamlit as st
import google.generativeai as genai
import os
import json
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tutor ENARM GPC", page_icon="🩺", layout="wide")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("⚠️ Falla crítica: No se encontró GEMINI_API_KEY en los Secrets.")
    st.stop()

# --- 2. MANEJO DE ESTADO (MEMORIA DE LA APP) ---
# Aquí guardamos el caso actual y si ya lo calificamos para que no se borre
if "caso_actual" not in st.session_state:
    st.session_state.caso_actual = None
if "evaluado" not in st.session_state:
    st.session_state.evaluado = False

def limpiar_estado():
    # Esta función borra el caso viejo si seleccionas otro tema
    st.session_state.caso_actual = None
    st.session_state.evaluado = False

# --- 3. FUNCIÓN DE ROTACIÓN DE MODELOS ---
def generar_con_fallback(prompt_texto):
    modelos_a_probar = [
        'gemini-3.1-flash-lite',
        'gemini-3.1-flash-lite-preview',
        'gemini-2.5-flash',
        'gemini-1.5-flash'
    ]
    for nombre_modelo in modelos_a_probar:
        try:
            modelo = genai.GenerativeModel(nombre_modelo)
            respuesta = modelo.generate_content(prompt_texto)
            return respuesta.text, nombre_modelo
        except Exception as e:
            print(f"⚠️ {nombre_modelo} falló. Intentando el siguiente...")
            continue
    raise Exception("Todos los modelos fallaron.")

# --- 4. BÚSQUEDA DE ARCHIVOS (UI LIMPIA) ---
def buscar_gpc():
    mapa_gpc = {}
    for raiz, carpetas, archivos in os.walk("."):
        if ".git" in raiz or ".streamlit" in raiz:
            continue
        for archivo in archivos:
            if archivo.endswith(".md") and archivo.lower() != "readme.md":
                # Limpiamos el nombre: "Preeclampsia.md" -> "Preeclampsia"
                nombre_limpio = archivo.replace(".md", "")
                
                # Para evitar confusiones si tienes dos archivos con el mismo nombre, 
                # le ponemos la carpeta padre al lado sutilmente. Ej: "Sepsis (Pediatría)"
                carpeta_padre = os.path.basename(raiz)
                if carpeta_padre and carpeta_padre != ".":
                    nombre_mostrar = f"{nombre_limpio}  —  [{carpeta_padre}]"
                else:
                    nombre_mostrar = nombre_limpio
                    
                ruta_real = os.path.join(raiz, archivo)
                mapa_gpc[nombre_mostrar] = ruta_real
    return mapa_gpc

diccionario_gpc = buscar_gpc()

# --- 5. INTERFAZ DE USUARIO (SIDEBAR) ---
st.sidebar.title("🧠 Panel del Tutor")
st.sidebar.markdown("---")

if not diccionario_gpc:
    st.sidebar.error("❌ No encontré archivos .md.")
    opciones = []
else:
    # Ordenamos alfabéticamente para que se vea más pro
    opciones = sorted(list(diccionario_gpc.keys()))

# Si el usuario cambia de tema, limpiamos la pantalla
tema_seleccionado = st.sidebar.selectbox("📖 Selecciona una GPC:", opciones, on_change=limpiar_estado)

st.sidebar.markdown("---")
debilidad = st.sidebar.text_input("🎯 ¿En qué estás batallando?", placeholder="Ej: Tratamiento, Dosis...")
nivel = st.sidebar.select_slider("🔥 Dificultad:", options=["Interno", "Residente", "Especialista"])

# --- 6. GENERACIÓN DEL CASO (JSON) ---
st.title("👨‍⚕️ Simulador Clínico Interactivo")

if st.sidebar.button("🚀 Generar Caso Nuevo"):
    with st.spinner(f"Creando caso seriado de {tema_seleccionado}..."):
        ruta_archivo = diccionario_gpc[tema_seleccionado]
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido_gpc = f.read()

        # Le exigimos a la IA que devuelva un formato JSON estructurado
        prompt = f"""
        Eres un sinodal del ENARM. Basado en esta GPC: {contenido_gpc}.
        Genera un caso clínico seriado de 1 a 3 preguntas. Dificultad: {nivel}. Enfoque: {debilidad}.
        
        DEVUELVE ÚNICAMENTE UN OBJETO JSON VÁLIDO con esta estructura exacta, sin texto extra antes ni después:
        {{
            "historia_clinica": "Paciente de X años acude a urgencias...",
            "preguntas": [
                {{
                    "id": 1,
                    "texto": "¿Cuál es el diagnóstico más probable?",
                    "opciones": ["A) Opción 1", "B) Opción 2", "C) Opción 3", "D) Opción 4"],
                    "respuesta_correcta": "A) Opción 1",
                    "justificacion": "Según la GPC, la presencia de X indica..."
                }}
            ]
        }}
        """
        
        try:
            texto_crudo, mod = generar_con_fallback(prompt)
            # Limpiamos el texto por si la IA le pone comillas raras de markdown (```json ... ```)
            texto_limpio = re.sub(r'```json\n|```\n?', '', texto_crudo).strip()
            
            # Convertimos el string a un diccionario de Python real
            st.session_state.caso_actual = json.loads(texto_limpio)
            st.session_state.evaluado = False
            
        except json.JSONDecodeError:
            st.error("🚨 La IA no devolvió un formato válido. Intenta generarlo de nuevo.")
        except Exception as e:
            st.error(f"🚨 Error: {e}")

# --- 7. RENDERIZADO DEL CASO INTERACTIVO ---
if st.session_state.caso_actual:
    caso = st.session_state.caso_actual
    
    st.markdown("### 📋 Historia Clínica")
    st.info(caso["historia_clinica"])
    st.markdown("---")
    
    # Creamos un formulario para que el usuario responda
    with st.form("formulario_enarm"):
        respuestas_usuario = {}
        
        # Iteramos sobre las preguntas que generó la IA (pueden ser 1, 2 o 3)
        for i, preg in enumerate(caso["preguntas"]):
            st.markdown(f"**Pregunta {i+1}:** {preg['texto']}")
            # st.radio crea las opciones interactivas
            respuestas_usuario[i] = st.radio("Selecciona tu respuesta:", preg["opciones"], key=f"rad_{i}")
            st.markdown("<br>", unsafe_allow_html=True) # Espacio visual
            
        # Botón para calificar
        submit = st.form_submit_button("✅ Calificar mis respuestas")
        
        if submit:
            st.session_state.evaluado = True

    # --- 8. RETROALIMENTACIÓN ---
    if st.session_state.evaluado:
        st.markdown("## 📊 Resultados")
        
        for i, preg in enumerate(caso["preguntas"]):
            correcta = preg["respuesta_correcta"]
            elegida = respuestas_usuario[i]
            
            # Comparamos si la opción que eligió es igual a la correcta
            if elegida == correcta:
                st.success(f"**Pregunta {i+1}: CORRECTA 🎉**")
            else:
                st.error(f"**Pregunta {i+1}: INCORRECTA ❌**")
                st.write(f"Tu respuesta: `{elegida}`")
                
            st.write(f"**Respuesta correcta:** `{correcta}`")
            st.write(f"**Justificación de la GPC:** {preg['justificacion']}")
            st.markdown("---")