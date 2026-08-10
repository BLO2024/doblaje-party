import streamlit as st
import whisper
import librosa
import numpy as np
import subprocess
import os
import glob
import yt_dlp
import urllib.parse
import urllib.request
import json

st.set_page_config(page_title="App de Doblaje Party 🎙️", page_icon="🎬", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    .teleprompter-box {
        background-color: #111827;
        border-left: 5px solid #3B82F6;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .teleprompter-text {
        font-size: 22px;
        font-weight: bold;
        color: #F3F4F6;
        margin: 0;
    }
    .time-badge {
        font-size: 12px;
        color: #9CA3AF;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎙️ ¡Juego de Doblaje Party!")
st.write("Elige tu escena, edita los diálogos si es necesario, lee tus líneas y graba tu doblaje.")

def buscar_videos_generales(query, max_results=4):
    """Busca videos web usando Google Search mediante yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    resultados = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"gvsearch{max_results}:{query}", download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    resultados.append({
                        'title': entry.get('title', 'Sin título'),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'thumbnail': entry.get('thumbnail', ''),
                    })
        except Exception as e:
            st.error(f"Error en la búsqueda: {e}")
    return resultados

def buscar_referencia_google(frase_original):
    """Busca sugerencias usando el motor de autocompletado de DuckDuckGo / Google sin librerías externas"""
    try:
        query = urllib.parse.quote(frase_original)
        url = f"https://duckduckgo.com/ac/?q={query}&type=list"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if len(data) > 1 and len(data[1]) > 0:
                sugerencias = ", ".join(data[1][:3])
                return f"Sugerencias de búsqueda encontradas: {sugerencias}"
    except Exception:
        pass
    return "No se encontraron coincidencias automáticas. Puedes ajustar la frase manualmente arriba."

def cargar_y_preparar_escena(origen_tipo, recurso):
    """Descarga/guarda el video, obtiene el audio y realiza la detección de diálogos automáticamente"""
    with st.spinner("Preparando la escena y configurando el estudio..."):
        try:
            if origen_tipo == "local":
                with open("video_input.mp4", "wb") as f:
                    f.write(recurso.read())
            elif origen_tipo == "url":
                opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'format': 'worstvideo[ext=mp4]+bestaudio[ext=m4a]/worst[ext=mp4]/worst',
                    'outtmpl': 'video_input.mp4',
                    'overwrites': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'referer': 'https://www.tiktok.com/',
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([recurso])

            cmd_audio = "ffmpeg -y -i video_input.mp4 -vn -acodec pcm_s16le -ar 16000 audio_ref.wav"
            subprocess.run(cmd_audio, shell=True)

            model = whisper.load_model("base")
            result = model.transcribe("audio_ref.wav")
            
            st.session_state['segments'] = result['segments']
            st.session_state['escena_lista'] = True
        except Exception as e:
            st.error(f"Error al preparar la escena: {e}")

def recortar_fragmento_video(inicio, fin, output_path):
    duracion = fin - inicio
    cmd = f"ffmpeg -y -ss {inicio} -i video_input.mp4 -t {duracion} -c:v copy -c:a aac {output_path}"
    subprocess.run(cmd, shell=True)

def limpiar_archivos_temporales(limpiar_todo=False):
    patrones = ["clip_preview_*.mp4", "user_toma_*.wav", "audio_ref.wav", "audio_temp.wav"]
    if limpiar_todo:
        patrones.append("video_input.mp4")
    archivos_eliminados = 0
    for patron in patrones:
        for archivo in glob.glob(patron):
            try:
                os.remove(archivo)
                archivos_eliminados += 1
            except Exception:
                pass
    return archivos_eliminados

def evaluar_toma_divertida(audio_ref_path, audio_usuario_path):
    try:
        y_ref, sr_ref = librosa.load(audio_ref_path)
        y_user, sr_user = librosa.load(audio_usuario_path)
        dur_ref = librosa.get_duration(y=y_ref, sr=sr_ref)
        dur_user = librosa.get_duration(y=y_user, sr=sr_user)
        diferencia_tiempo = abs(dur_ref - dur_user)
        puntaje_tiempo = max(0, 100 - (diferencia_tiempo * 25))
        pitches_ref, _ = librosa.piptrack(y=y_ref, sr=sr_ref)
        pitches_user, _ = librosa.piptrack(y=y_user, sr=sr_user)
        p_ref = pitches_ref[pitches_ref > 0]
        p_user = pitches_user[pitches_user > 0]
        if len(p_ref) > 0 and len(p_user) > 0:
            dif_pitch = abs(np.median(p_ref) - np.median(p_user)) / np.median(p_ref)
            puntaje_pitch = max(0, 100 - (dif_pitch * 80))
        else:
            puntaje_pitch = 65.0
        score = round(min(100, max(0, (puntaje_tiempo * 0.5) + (puntaje_pitch * 0.5))), 1)
        if score >= 85:
            st.balloons()
            return score, "⭐⭐⭐⭐⭐", "🏆 ¡NIVEL ACTOR DE HOLLYWOOD!", "Le quitaste el trabajo al actor original."
        elif score >= 70:
            return score, "⭐⭐⭐⭐", "🎙️ ¡MODO FANDUB ACTIVADO!", "Suenas listo para subir tu reel."
        elif score >= 50:
            return score, "⭐⭐⭐", "🎬 ¡DOBLAJE DE BAJO PRESUPUESTO!", "Le pusiste ganas, que es lo que importa."
        elif score >= 30:
            return score, "⭐⭐", "🤪 ¡VOZ DE PERSONAJE RARO!", "Parece que estabas doblando un meme."
        else:
            return score, "⭐", "🐓 ¡EFECTO GALLO!", "Ni el micrófono entendió qué dijiste."
    except Exception:
        return 75.0, "⭐⭐⭐⭐", "👍 ¡BUENA TOMA!", "Grabación lista para el montaje final."

# --- SELECCIÓN DE ESCENA ---
st.header("1. Selecciona tu Escena")

metodo_origen = st.radio(
    "Opción de carga:",
    ("Subir archivo MP4 📁", "Enlace (TikTok / Web) 🔗", "Buscar en la Web 🔍")
)

if metodo_origen == "Subir archivo MP4 📁":
    uploaded_file = st.file_uploader("Sube tu archivo de video:", type=["mp4"])
    if uploaded_file is not None:
        if st.button("Cargar escena"):
            cargar_y_preparar_escena("local", uploaded_file)

elif metodo_origen == "Enlace (TikTok / Web) 🔗":
    url_directa = st.text_input("Pega el enlace de TikTok o de un sitio web:")
    if url_directa and st.button("Cargar escena"):
        cargar_y_preparar_escena("url", url_directa)

elif metodo_origen == "Buscar en la Web 🔍":
    query = st.text_input("Escribe el nombre de la escena o clip:")
    if query:
        with st.spinner("Buscando opciones..."):
            resultados = buscar_videos_generales(query, max_results=4)
        
        if resultados:
            cols = st.columns(len(resultados))
            for idx, item in enumerate(resultados):
                with cols[idx]:
                    if item['thumbnail']:
                        st.image(item['thumbnail'], use_container_width=True)
                    st.caption(f"**{item['title']}**")
                    if st.button(f"Usar esta escena", key=f"btn_{idx}"):
                        cargar_y_preparar_escena("url", item['url'])

# --- ESTUDIO DE GRABACIÓN & TELEPROMPTER EDITABLE ---
if st.session_state.get('escena_lista', False) and 'segments' in st.session_state:
    st.divider()
    st.header("2. Estudio de Grabación 🎬")

    segments = st.session_state['segments']
    mapa_tomas = []

    col_video, col_estudio = st.columns([1, 1], gap="large")

    with col_video:
        st.subheader("📺 Escena")
        if os.path.exists("video_input.mp4"):
            st.video("video_input.mp4")

    with col_estudio:
        st.subheader("🎙️ Teleprompter & Edición de Diálogos")
        
        for idx, seg in enumerate(segments):
            st.markdown(f"""
                <div class="teleprompter-box">
                    <span class="time-badge">Frase {idx + 1} | Tiempo: {seg['start']:.1f}s - {seg['end']:.1f}s</span>
                </div>
            """, unsafe_allow_html=True)
            
            texto_editado = st.text_input(
                f"Texto de la Frase {idx + 1}:",
                value=seg['text'].strip(),
                key=f"text_edit_{idx}"
            )
            st.session_state['segments'][idx]['text'] = texto_editado

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                clip_path = f"clip_preview_{idx}.mp4"
                if st.button(f"▶️ Ver fragmento {idx + 1}", key=f"prev_btn_{idx}"):
                    with st.spinner("Cargando fragmento..."):
                        recortar_fragmento_video(seg['start'], seg['end'], clip_path)
            
            with col_btn2:
                if st.button(f"🔍 Buscar referencias web", key=f"goog_btn_{idx}"):
                    with st.spinner("Buscando sugerencias..."):
                        info_ref = buscar_referencia_google(texto_editado)
                        st.info(info_ref)

            if os.path.exists(clip_path):
                st.caption(f"🎬 Fragmento ({seg['start']:.1f}s - {seg['end']:.1f}s):")
                st.video(clip_path)

            audio_data = st.audio_input(f"Grabar frase {idx + 1}", key=f"rec_{idx}")
            toma_path = f"user_toma_{idx}.wav"
            
            if audio_data:
                with open(toma_path, "wb") as f:
                    f.write(audio_data.read())
                score, estrellas, titulo, mensaje = evaluar_toma_divertida("audio_ref.wav", toma_path)
                st.markdown(f"**Puntuación:** {estrellas} `{score}%` — {mensaje}")
                mapa_tomas.append((toma_path, seg['start']))
            
            st.divider()

    # --- MONTAJE FINAL ---
    st.header("3. Resultado Final")
    
    col_vol1, col_vol2 = st.columns(2)
    with col_vol1:
        vol_original = st.slider("🔊 Volumen fondo original:", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    with col_vol2:
        vol_usuario = st.slider("🎙️ Volumen voz grabada:", min_value=0.5, max_value=3.0, value=1.5, step=0.1)

    col_gen, col_clean = st.columns([2, 1])
    
    with col_gen:
        btn_generar = st.button("🎬 Mezclar y Generar Video")
    with col_clean:
        if st.button("🧹 Reiniciar estudio"):
            eliminados = limpiar_archivos_temporales(limpiar_todo=True)
            st.toast("Estudio listo para una nueva escena.")

    if btn_generar and mapa_tomas:
        with st.spinner("Mezclando pistas de audio..."):
            inputs = ["-i video_input.mp4"]
            filter_complex = f"[0:a]volume={vol_original}[a_orig];"
            mix_labels = "[a_orig]"
            
            for i, (path, inicio) in enumerate(mapa_tomas):
                inputs.append(f"-i {path}")
                ms_delay = int(inicio * 1000)
                idx_input = i + 1
                filter_complex += f"[{idx_input}:a]volume={vol_usuario},adelay={ms_delay}|{ms_delay}[a{idx_input}];"
                mix_labels += f"[a{idx_input}]"
            
            total_entradas = len(mapa_tomas) + 1
            filter_complex += f"{mix_labels}amix=inputs={total_entradas}:duration=first[aout]"
            
            cmd = f"ffmpeg -y {' '.join(inputs)} -filter_complex \"{filter_complex}\" -map 0:v -map \"[aout]\" -c:v copy -c:a aac resultado.mp4"
            subprocess.run(cmd, shell=True)
            
            if os.path.exists("resultado.mp4"):
                st.subheader("🍿 ¡Tu Doblaje!")
                st.video("resultado.mp4")
                st.success("¡Video generado correctamente!")
                
                limpiar_archivos_temporales(limpiar_todo=False)
