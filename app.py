import streamlit as st
import google.generativeai as genai
import os
import json
import re

st.set_page_config(page_title="Tutor ENARM IA", page_icon="🩺", layout="wide")

# --- 1. CONFIGURACIÓN DE IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ Falla crítica: No se encontró GEMINI_API_KEY en los Secrets.")
    st.stop()

def generar_con_fallback(prompt_texto):
    modelos_a_probar = ['gemini-3.1-flash-lite', 'gemini-3.1-flash-lite-preview', 'gemini-1.5-flash']
    for nombre_modelo in modelos_a_probar:
        try:
            modelo = genai.GenerativeModel(nombre_modelo)
            respuesta = modelo.generate_content(prompt_texto)
            return respuesta.text, nombre_modelo
        except Exception as e:
            continue
    raise Exception("Todos los modelos fallaron. Revisa tu cuota o conexión.")

# --- 2. BASE DE DATOS LOCAL: EL "LIBRO DE REGISTROS" ---
ARCHIVO_HISTORIAL = "historial_enarm.json"

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"aciertos": 0, "errores": 0, "temas": {}}

def guardar_historial(datos):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4)

if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()

def registrar_respuesta(tema, concepto, es_correcta):
    hist = st.session_state.historial
    if es_correcta: hist["aciertos"] += 1
    else: hist["errores"] += 1
    
    if tema not in hist["temas"]:
        hist["temas"][tema] = {"aciertos": 0, "errores": 0, "conceptos_clave": {}}
    
    # Registro general del tema
    if es_correcta: hist["temas"][tema]["aciertos"] += 1
    else: hist["temas"][tema]["errores"] += 1
    
    # Registro específico del "Micro-tema" (ej. Escala de Padua)
    if concepto not in hist["temas"][tema]["conceptos_clave"]:
        hist["temas"][tema]["conceptos_clave"][concepto] = {"aciertos": 0, "errores": 0}
        
    if es_correcta:
        hist["temas"][tema]["conceptos_clave"][concepto]["aciertos"] += 1
    else:
        hist["temas"][tema]["conceptos_clave"][concepto]["errores"] += 1
        
    guardar_historial(hist)
    st.session_state.historial = hist

# --- 3. ESTADO REACTIVO DEL SIMULADOR ---
if "caso_actual" not in st.session_state: st.session_state.caso_actual = None
if "evaluado" not in st.session_state: st.session_state.evaluado = False
if "fue_correcta" not in st.session_state: st.session_state.fue_correcta = False
if "respuesta_usuario" not in st.session_state: st.session_state.respuesta_usuario = ""

def limpiar_estado():
    st.session_state.caso_actual = None
    st.session_state.evaluado = False
    st.session_state.fue_correcta = False
    st.session_state.respuesta_usuario = ""

# --- 4. BÚSQUEDA DE ARCHIVOS GPC ---
def buscar_gpc():
    mapa = {}
    for raiz, carpetas, archivos in os.walk("."):
        if ".git" in raiz or ".streamlit" in raiz: continue
        for arch in archivos:
            if arch.endswith(".md") and arch.lower() != "readme.md":
                nombre = arch.replace(".md", "")
                mapa[f"{nombre} — [{os.path.basename(raiz)}]"] = os.path.join(raiz, arch)
    return mapa

diccionario_gpc = buscar_gpc()

# --- 5. INTERFAZ: SIDEBAR ---
st.sidebar.title("⚙️ Configuración ENARM")
opciones = sorted(list(diccionario_gpc.keys())) if diccionario_gpc else []
tema_seleccionado = st.sidebar.selectbox("📖 Selecciona Tema:", opciones, on_change=limpiar_estado)
tema_limpio = tema_seleccionado.split(" — ")[0] if tema_seleccionado else ""

st.sidebar.markdown("---")
dificultad_bloom = st.sidebar.radio("🧠 Nivel Cognitivo:", ["Bajo", "Medio", "Alto"], index=2)

# MAGIA SDE: Buscamos en qué ha fallado este usuario para inyectarlo en el prompt
conceptos_debiles = []
if tema_seleccionado and tema_limpio in st.session_state.historial["temas"]:
    conceptos = st.session_state.historial["temas"][tema_limpio]["conceptos_clave"]
    # Ordenamos los conceptos por cantidad de errores
    conceptos_debiles = sorted(conceptos.keys(), key=lambda k: conceptos[k]["errores"], reverse=True)[:3]

debilidad_automatica = ", ".join(conceptos_debiles) if conceptos_debiles else "Ninguna registrada aún"
st.sidebar.info(f"🚨 IA enfocada en tus debilidades: **{debilidad_automatica}**")

# --- 6. PESTAÑAS DE NAVEGACIÓN ---
tab1, tab2 = st.tabs(["📝 Simulador Clínico", "📊 Mi Rendimiento (Micro-temas)"])

with tab1:
    st.title("Simulador de Casos ENARM")
    
    # Generador
    if st.button("🚀 Generar Nuevo Caso", type="primary") and tema_seleccionado:
        limpiar_estado() # Limpiamos antes de generar
        with st.spinner("El sinodal está creando un caso..."):
            with open(diccionario_gpc[tema_seleccionado], "r", encoding="utf-8") as f: contenido = f.read()

            prompt = f"""
            Eres un creador de reactivos ENARM. Usa la GPC: {contenido}
            Crea 1 pregunta. Nivel Bloom: {dificultad_bloom}.
            
            ATENCIÓN: El usuario ha fallado previamente en estos sub-temas: {debilidad_automatica}.
            Intenta centrar el caso clínico en alguno de esos conceptos si es posible.
            
            DEVUELVE SOLO UN JSON EXACTO:
            {{
                "historia_clinica": "Paciente...",
                "pregunta": "¿Qué procede?",
                "opciones": ["A) ...", "B) ...", "C) ...", "D) ..."],
                "respuesta_correcta": "A) ...",
                "concepto_clave": "Nombre corto de lo que evalúas (ej. Escala de Padua, Dosis Inicial, Criterio Hospitalización)",
                "justificacion": "Análisis y reglas de descarte..."
            }}
            """
            try:
                texto_crudo, mod = generar_con_fallback(prompt)
                texto_limpio = re.sub(r'```json\n|```\n?', '', texto_crudo).strip()
                st.session_state.caso_actual = json.loads(texto_limpio)
            except Exception as e:
                st.error("🚨 Error al generar JSON. Intenta de nuevo.")

    # Renderizado y Evaluación
    if st.session_state.caso_actual:
        caso = st.session_state.caso_actual
        st.info(caso.get("historia_clinica", ""))
        
        pregunta_texto = caso.get("pregunta", caso.get("texto", "¿Diagnóstico?"))
        opciones = caso.get("opciones", ["A", "B", "C", "D"])
        respuesta_correcta = caso.get("respuesta_correcta", "A")
        justificacion = caso.get("justificacion", "")
        concepto_clave = caso.get("concepto_clave", "Concepto General")

        # Mostramos sutilmente qué micro-tema se está evaluando
        st.caption(f"📌 Evaluando: *{concepto_clave}*")

        with st.form("examen"):
            st.write(f"**{pregunta_texto}**")
            respuesta_usuario = st.radio("Selecciona tu respuesta:", opciones)
            submit = st.form_submit_button("✅ Calificar")
            
            if submit and respuesta_usuario:
                st.session_state.evaluado = True
                st.session_state.respuesta_usuario = respuesta_usuario
                
                # Validación segura
                es_correcta = respuesta_usuario[:2].strip() == respuesta_correcta[:2].strip() or respuesta_usuario == respuesta_correcta
                st.session_state.fue_correcta = es_correcta
                
                # Registramos en el libro de fallos con el micro-tema
                registrar_respuesta(tema_limpio, concepto_clave, es_correcta)
                st.rerun() # Refresca instantáneamente para mostrar resultados
                
        # Mostrar retroalimentación si ya se evaluó (incluso si cambian widgets)
        if st.session_state.evaluado:
            st.markdown("---")
            if st.session_state.fue_correcta:
                st.success("✅ **¡Correcto!**")
            else:
                st.error("❌ **Incorrecto**")
                st.write(f"Tu respuesta: `{st.session_state.respuesta_usuario}`")
            
            st.write(f"**Respuesta Correcta:** `{respuesta_correcta}`")
            st.write(f"**Análisis del Sinodal:** {justificacion}")
            
            # EL BOTÓN MÁGICO PARA CONTINUAR FLUIDO
            if st.button("🔄 Generar Siguiente Caso", type="secondary"):
                limpiar_estado()
                st.rerun()

with tab2:
    st.title("📊 Libro de Puntos Débiles")
    hist = st.session_state.historial
    
    if hist["aciertos"] + hist["errores"] == 0:
        st.info("Aún no tienes historial.")
    else:
        st.markdown("### 🔬 Disección de tus Errores por Concepto")
        
        # Iteramos sobre el "libro de registros" para extraer los micro-temas
        for tema, stats_tema in hist["temas"].items():
            st.markdown(f"#### 📘 {tema}")
            
            # Revisamos si hay conceptos clave registrados
            if "conceptos_clave" in stats_tema:
                for concepto, stats_concepto in stats_tema["conceptos_clave"].items():
                    err = stats_concepto["errores"]
                    aci = stats_concepto["aciertos"]
                    
                    if err > aci:
                        st.error(f"**{concepto}:** {err} fallos | {aci} aciertos ⚠️ (Prioridad Alta)")
                    elif err > 0:
                        st.warning(f"**{concepto}:** {err} fallos | {aci} aciertos (En progreso)")
                    else:
                        st.success(f"**{concepto}:** {err} fallos | {aci} aciertos ✅ (Dominado)")
            else:
                st.write("Sin micro-temas registrados aún.")
            st.markdown("---")