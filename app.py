import streamlit as st
import google.generativeai as genai
import os
import json
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tutor ENARM IA", page_icon="🩺", layout="wide")

# --- 2. CONFIGURACIÓN DE IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ Falla crítica: No se encontró GEMINI_API_KEY en los Secrets.")
    st.stop()

def generar_con_fallback(prompt_texto):
    """Mecanismo de respaldo para rotar modelos si uno falla o se queda sin cuota."""
    modelos_a_probar = [
        'gemini-3.1-flash-lite',
        'gemini-3.1-flash-lite-preview',
        'gemini-1.5-flash'
    ]
    for nombre_modelo in modelos_a_probar:
        try:
            modelo = genai.GenerativeModel(nombre_modelo)
            respuesta = modelo.generate_content(prompt_texto)
            return respuesta.text, nombre_modelo
        except Exception as e:
            print(f"⚠️ {nombre_modelo} falló: {e}. Intentando el siguiente...")
            continue
    raise Exception("Todos los modelos fallaron. Revisa tu cuota o conexión.")

# --- 3. SISTEMA DE BASE DE DATOS LOCAL (JSON) ---
ARCHIVO_HISTORIAL = "historial_enarm.json"

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"aciertos": 0, "errores": 0, "temas": {}}

def guardar_historial(datos):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4)

if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()

def registrar_respuesta(tema, es_correcta):
    hist = st.session_state.historial
    if es_correcta:
        hist["aciertos"] += 1
    else:
        hist["errores"] += 1
    
    if tema not in hist["temas"]:
        hist["temas"][tema] = {"aciertos": 0, "errores": 0}
    
    if es_correcta:
        hist["temas"][tema]["aciertos"] += 1
    else:
        hist["temas"][tema]["errores"] += 1
        
    guardar_historial(hist)
    # Refrescar la variable de sesión para que la gráfica se actualice de inmediato
    st.session_state.historial = hist

# --- 4. ESTADO DEL SIMULADOR ---
if "caso_actual" not in st.session_state:
    st.session_state.caso_actual = None
if "evaluado" not in st.session_state:
    st.session_state.evaluado = False

def limpiar_estado():
    st.session_state.caso_actual = None
    st.session_state.evaluado = False

# --- 5. BÚSQUEDA DE ARCHIVOS GPC ---
def buscar_gpc():
    mapa = {}
    for raiz, carpetas, archivos in os.walk("."):
        if ".git" in raiz or ".streamlit" in raiz: 
            continue
        for arch in archivos:
            if arch.endswith(".md") and arch.lower() != "readme.md":
                nombre = arch.replace(".md", "")
                carpeta_padre = os.path.basename(raiz)
                if carpeta_padre and carpeta_padre != ".":
                    nombre_mostrar = f"{nombre} — [{carpeta_padre}]"
                else:
                    nombre_mostrar = nombre
                mapa[nombre_mostrar] = os.path.join(raiz, arch)
    return mapa

diccionario_gpc = buscar_gpc()

# --- 6. INTERFAZ: SIDEBAR ---
st.sidebar.title("⚙️ Configuración ENARM")

if not diccionario_gpc:
    st.sidebar.error("❌ No encontré archivos .md.")
    opciones = []
else:
    opciones = sorted(list(diccionario_gpc.keys()))

tema_seleccionado = st.sidebar.selectbox("📖 Selecciona Tema:", opciones, on_change=limpiar_estado)

st.sidebar.markdown("---")
dificultad_bloom = st.sidebar.radio("🧠 Nivel Cognitivo (Bloom):", [
    "Bajo (Recordar - Memoria pura)",
    "Medio (Aplicar - Cuadro clínico directo)",
    "Alto (Analizar/Evaluar - ¿Qué hacer a continuación?)"
], index=2)

debilidad = st.sidebar.text_input("🎯 Foco específico (Opcional):", placeholder="Ej: Dosis, estándar de oro...")

# --- 7. PESTAÑAS DE NAVEGACIÓN ---
tab1, tab2 = st.tabs(["📝 Simulador Clínico", "📊 Mi Rendimiento"])

with tab1:
    st.title("Simulador de Casos ENARM")
    st.markdown("Generación interactiva basada en **gpc-abierta-mx**.")
    
    if st.button("🚀 Generar Caso de este Tema"):
        if not tema_seleccionado:
            st.warning("Selecciona una GPC primero.")
        else:
            with st.spinner("El sinodal está creando un caso con trampa..."):
                ruta_archivo = diccionario_gpc[tema_seleccionado]
                with open(ruta_archivo, "r", encoding="utf-8") as f:
                    contenido = f.read()

                prompt = f"""
                Eres un creador de reactivos para el ENARM. Usa la GPC: {contenido}
                Crea 1 pregunta de caso clínico.
                
                REGLAS ESTRICTAS:
                - Nivel de Taxonomía de Bloom: {dificultad_bloom}.
                - Enfoque solicitado por el usuario: {debilidad}.
                - Si es nivel Medio/Alto, NO preguntes teoría. Pregunta "¿Cuál es el estudio inicial?", "¿Cuál es el estándar de oro?", o "¿Cuál es el siguiente paso?".
                - Usa distractores que parezcan correctos pero que no sean la primera línea de la GPC.
                
                DEVUELVE SOLO UN JSON VÁLIDO con esta estructura exacta (sin comillas markdown de código):
                {{
                    "historia_clinica": "Paciente...",
                    "pregunta": "¿Cuál es el siguiente paso en el manejo?",
                    "opciones": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "respuesta_correcta": "A) ...",
                    "justificacion": "Análisis del Meta-Juego y GPC..."
                }}
                """
                
                try:
                    texto_crudo, mod = generar_con_fallback(prompt)
                    texto_limpio = re.sub(r'```json\n|```\n?', '', texto_crudo).strip()
                    st.session_state.caso_actual = json.loads(texto_limpio)
                    st.session_state.evaluado = False
                    st.success(f"Caso generado con: `{mod}`")
                except json.JSONDecodeError:
                    st.error("🚨 La IA no devolvió un JSON válido. Intenta de nuevo.")
                except Exception as e:
                    st.error(f"🚨 Error del sistema: {e}")

    # --- 8. RENDERIZADO BLINDADO DEL CASO ---
    if st.session_state.caso_actual:
        caso = st.session_state.caso_actual
        
        historia = caso.get("historia_clinica", "Error: La IA no generó la historia.")
        st.info(historia)
        
        # Extracción defensiva de datos
        pregunta_texto = caso.get("pregunta", caso.get("texto", "¿Cuál es tu diagnóstico?"))
        opciones = caso.get("opciones", ["A", "B", "C", "D"])
        respuesta_correcta = caso.get("respuesta_correcta", "A")
        justificacion = caso.get("justificacion", "La IA no dio justificación.")

        # Por si la IA manda una lista llamada "preguntas"
        if "preguntas" in caso and isinstance(caso["preguntas"], list) and len(caso["preguntas"]) > 0:
            primera = caso["preguntas"][0]
            pregunta_texto = primera.get("pregunta", primera.get("texto", pregunta_texto))
            opciones = primera.get("opciones", opciones)
            respuesta_correcta = primera.get("respuesta_correcta", respuesta_correcta)
            justificacion = primera.get("justificacion", justificacion)

        with st.form("examen"):
            st.write(f"**{pregunta_texto}**")
            
            if isinstance(opciones, list) and len(opciones) > 0:
                respuesta_usuario = st.radio("Selecciona tu respuesta:", opciones)
            else:
                st.error("Error en las opciones. Genera otro caso.")
                respuesta_usuario = None
                
            submit = st.form_submit_button("✅ Calificar")
            
            if submit and respuesta_usuario:
                st.session_state.evaluado = True
                
                # Validación flexible: compara los primeros 2 caracteres ("A)" vs "A)") o el string completo
                es_correcta = respuesta_usuario[:2].strip() == respuesta_correcta[:2].strip() or respuesta_usuario == respuesta_correcta
                
                # Extraemos solo el nombre limpio del tema para la gráfica (quitamos lo que está entre corchetes)
                tema_limpio = tema_seleccionado.split(" — ")[0]
                registrar_respuesta(tema_limpio, es_correcta)
                
        if st.session_state.evaluado:
            st.markdown("---")
            if es_correcta:
                st.success("✅ **¡Correcto!**")
            else:
                st.error("❌ **Incorrecto**")
                st.write(f"Tu respuesta: `{respuesta_usuario}`")
            
            st.write(f"**Respuesta Correcta:** `{respuesta_correcta}`")
            st.write(f"**Análisis del Sinodal:** {justificacion}")

with tab2:
    st.title("📊 Dashboard Analítico ENARM")
    hist = st.session_state.historial
    
    total_preguntas = hist["aciertos"] + hist["errores"]
    
    if total_preguntas == 0:
        st.info("Aún no tienes historial. ¡Resuelve tu primer caso!")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Casos Resueltos", total_preguntas)
        col2.metric("Aciertos", hist["aciertos"])
        efectividad = round((hist["aciertos"] / total_preguntas) * 100, 1)
        col3.metric("Efectividad Global", f"{efectividad}%")
        
        st.markdown("### 🎯 Desempeño por Tema (GPC)")
        
        datos_grafica = {"Aciertos": {}, "Errores": {}}
        for t, stats in hist["temas"].items():
            datos_grafica["Aciertos"][t] = stats["aciertos"]
            datos_grafica["Errores"][t] = stats["errores"]
            
        st.bar_chart(datos_grafica)
        
        st.markdown("### 🚨 Temas Prioritarios a Repasar")
        temas_con_errores = False
        for t, stats in hist["temas"].items():
            if stats["errores"] > stats["aciertos"]:
                st.error(f"🔥 {t}: {stats['errores']} errores vs {stats['aciertos']} aciertos")
                temas_con_errores = True
                
        if not temas_con_errores:
            st.success("¡Excelente! Tienes más aciertos que errores en todos los temas evaluados hasta ahora.")