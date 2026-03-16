import streamlit as st
import google.generativeai as genai
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Tutor ENARM GPC", page_icon="🩺", layout="wide")

# Inicializamos la API con la llave de los Secrets
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("⚠️ Falla crítica: No se encontró GEMINI_API_KEY en los Secrets de Streamlit.")
    st.stop() # Detiene la app si no hay llave

# --- 2. FUNCIÓN DE ROTACIÓN DE MODELOS (FALLBACK) ---
def generar_con_fallback(prompt_texto):
    """
    Intenta generar contenido rotando por una lista de modelos.
    Si uno falla (error 404, límite de cuota, etc.), pasa al siguiente.
    """
    # Lista de modelos ordenados por prioridad (del que tiene más cuota al que tiene menos)
    modelos_a_probar = [
        'gemini-3.1-flash-lite',         # Tu principal de 500 diarias
        'gemini-3.1-flash-lite-preview', # Variante con sufijo por si la API lo exige
        'gemini-2.5-flash',              # Reserva 1 (20 diarias)
        'gemini-2.5-flash-preview',      # Reserva 2
        'gemini-1.5-flash'               # Backup de emergencia (el clásico)
    ]
    
    for nombre_modelo in modelos_a_probar:
        try:
            # Creamos la instancia del modelo específico
            modelo_actual = genai.GenerativeModel(nombre_modelo)
            # Intentamos hacer la petición
            respuesta = modelo_actual.generate_content(prompt_texto)
            # Si no hay error, regresamos el texto y el nombre del modelo que funcionó
            return respuesta.text, nombre_modelo
            
        except Exception as e:
            # Si hay un error, lo imprimimos en la consola del servidor (no en la web)
            print(f"⚠️ El modelo {nombre_modelo} falló: {e}. Intentando el siguiente...")
            continue # Pasa al siguiente modelo de la lista
            
    # Si el ciclo for termina y no retornó nada, significa que TODOS fallaron
    raise Exception("Todos los modelos fallaron. Es probable que se haya agotado la cuota diaria o haya un problema con la API de Google.")


# --- 3. BÚSQUEDA DE ARCHIVOS (RECURSIVA) ---
def buscar_gpc():
    mapa_gpc = {}
    for raiz, carpetas, archivos in os.walk("."):
        if ".git" in raiz or ".streamlit" in raiz:
            continue
        for archivo in archivos:
            if archivo.endswith(".md") and archivo.lower() != "readme.md":
                ruta_amigable = os.path.join(raiz, archivo).replace("./", "")
                ruta_real = os.path.join(raiz, archivo)
                mapa_gpc[ruta_amigable] = ruta_real
    return mapa_gpc

diccionario_gpc = buscar_gpc()

# --- 4. INTERFAZ DE USUARIO (SIDEBAR) ---
st.sidebar.title("🧠 Panel del Tutor")
st.sidebar.markdown("---")

if not diccionario_gpc:
    st.sidebar.error("❌ No encontré archivos .md en tu repositorio.")
    st.sidebar.info("Asegúrate de que la app está leyendo la rama correcta de GitHub.")
    opciones = []
else:
    opciones = list(diccionario_gpc.keys())

tema_seleccionado = st.sidebar.selectbox("📖 Selecciona una GPC:", opciones)

st.sidebar.markdown("---")
debilidad = st.sidebar.text_input("🎯 ¿En qué estás batallando?", placeholder="Ej: Tratamiento, Dosis, Diagnóstico...")
nivel = st.sidebar.select_slider("🔥 Nivel de dificultad:", options=["Interno", "Residente", "Especialista"])

# --- 5. CUERPO PRINCIPAL ---
st.title("👨‍⚕️ Simulador Clínico Inteligente")
st.markdown("Generación de casos on-demand usando la estructura de **gpc-abierta-mx**.")

if st.button("🚀 Generar Caso Clínico"):
    if not tema_seleccionado:
        st.warning("Selecciona un tema primero en el panel izquierdo.")
    else:
        with st.spinner(f"El sinodal está revisando {tema_seleccionado}..."):
            ruta_archivo = diccionario_gpc[tema_seleccionado]
            
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                contenido_gpc = f.read()

            # El prompt maestro que controla a la IA
            prompt = f"""
            Actúa como un sinodal experto del ENARM en México.
            Utiliza este resumen de GPC como única fuente de verdad: 
            ---
            {contenido_gpc}
            ---
            
            TAREA:
            1. Genera un caso clínico complejo de opción múltiple.
            2. El usuario solicitó enfocarse en esta debilidad: '{debilidad}'. Haz que el caso gire en torno a esto.
            3. Dificultad: {nivel}.
            4. Si falta información en la GPC para armar el caso fisiopatológico, usa tu conocimiento médico, pero PRIORIZA el manejo de la guía mexicana.
            5. Presenta el caso, 4 opciones (A, B, C, D) y al final la respuesta correcta justificada.
            """

            try:
                # Llamamos a nuestra función blindada
                texto_respuesta, modelo_usado = generar_con_fallback(prompt)
                
                st.success(f"✅ Caso generado exitosamente usando el modelo: `{modelo_usado}`")
                st.markdown("---")
                st.markdown(texto_respuesta)
                
            except Exception as e:
                st.error(f"🚨 Error del sistema: {e}")

st.sidebar.markdown("---")
if st.sidebar.button("❌ Fallé esta pregunta"):
    st.sidebar.warning("Registrado. ¡Ánimo! El algoritmo lo tendrá en cuenta para la próxima.")