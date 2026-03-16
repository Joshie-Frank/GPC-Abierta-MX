import streamlit as st
import google.generativeai as genai
import os

# --- CONFIGURACIÓN DE LA IA ---
# Sacaremos la API KEY de los "Secrets" de Streamlit para que sea seguro
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Falta la API Key de Gemini. Configúrala en los Secrets de Streamlit.")

st.set_page_config(page_title="Tutor ENARM Inteligente", page_icon="🩺")

st.title("🩺 Tutor de GPC Personalizado")
st.markdown("Generación de casos clínicos *on-demand* basada en tus propios resúmenes.")

# --- LÓGICA DE ARCHIVOS ---
# Buscamos todos los archivos .md en tu carpeta (ajusta el nombre de tu carpeta)
def buscar_resumenes():
    # Buscamos archivos .md en el repo. 
    # Si tus archivos están en la raíz, deja '.'
    archivos = [f for f in os.listdir('.') if f.endswith('.md')]
    return archivos

lista_gpc = buscar_resumenes()

# --- INTERFAZ ---
with st.sidebar:
    st.header("Configuración de Estudio")
    seleccion = st.selectbox("Elige una GPC para practicar:", lista_gpc)
    
    # Aquí es donde deja de ser "dummy"
    st.subheader("Foco del Tutor")
    debilidad = st.text_input("¿En qué estás batallando? (Ej: Dosis, Diagnóstico)", "General")
    
    nivel = st.select_slider("Dificultad del caso", options=["Interno", "Residente", "Especialista"])

if st.button("🚀 Generar Caso Clínico"):
    with st.spinner("Leyendo GPC y creando caso..."):
        # Leer el contenido del archivo .md seleccionado
        with open(seleccion, "r", encoding="utf-8") as f:
            contenido_md = f.read()
        
        # Prompt de ingeniería para que la IA no "alucine"
        prompt_maestro = f"""
        Actúa como un sinodal del ENARM experto. 
        Utiliza este resumen de GPC como única fuente de verdad: {contenido_md}
        
        INSTRUCCIONES:
        1. Genera un caso clínico seriado (Cuadro clínico -> Diagnóstico -> Tratamiento).
        2. El usuario dice que su debilidad es: {debilidad}. Enfócate un 50% en eso.
        3. Dificultad nivel: {nivel}.
        4. Si la GPC no tiene un dato necesario, usa tu conocimiento médico general pero avísale al usuario que no viene en la guía.
        5. Al final, da la respuesta correcta con la justificación basada en la GPC.
        """
        
        response = model.generate_content(prompt_maestro)
        st.markdown("---")
        st.markdown(response.text)

# --- MEMORIA DE ERRORES (Básico) ---
if st.checkbox("Registrar que fallé este caso"):
    st.warning("Guardado en historial. La próxima vez te preguntaré más sobre este tema.")
    # Aquí podrías agregar lógica para guardar en un archivo .json luego