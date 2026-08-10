import streamlit as st
import whisper
import librosa
import numpy as np
import subprocess
import os
import glob
import yt_dlp
import urllib.parse

st.set_page_config(page_title="App de Doblaje Party 🎙️", page_icon="🎬", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    .teleprompter-box {
        background-color: #111827;
        border-left: 5px solid #3B82F6;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .time-badge {
        font-size: 13px;
        color: #9CA3AF;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎙️ ¡Juego de Doblaje Party!")
st.write("Elige tu escena, lee tus líneas paso a paso y graba tu doblaje.")

def buscar_videos_tiktok(query, max_results=4):
    """Busca videos directamente en TikTok mediante yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.tiktok.com/',
    }
    resultados = []
    url_busqueda = f"https://www.tiktok.com/search?q={urllib.parse.quote(query)}"
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url_busqueda, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if len(resultados) >= max_results:
                        break
                    url_video = entry.get('url') or entry.get('webpage_url')
                    if url_video:
                        resultados.append({
                            'title': entry.get('title') or entry.get('description') or 'Video de TikTok',
                            'url': url_video,
                            'thumbnail': entry.get('thumbnail', ''),
                        })
        except Exception as e:
            st.error(f"Error al buscar en TikTok: {e}")
    return resultados

def cargar_y_preparar_escena(origen_tipo, recurso):
    """Descarga/guarda el video, obtiene el audio y analiza los diálogos"""
    with st.spinner("Descargando escena y preparando el estudio..."):
        try:
            if origen_tipo == "local":
                with open("video_input.mp4", "wb") as f:
                    f.write(recurso.read())
            elif origen_tipo == "url":
                opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'format': 'mp4/bestvideo+bestaudio/best',
                    'outtmpl': 'video_input.mp4',
                    'overwrites': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
            st.session_state['paso_actual'] = 0
            st.session_state['tomas_grabadas'] = {}
            st.rerun()
        except Exception as e:
            st.error(f"Error al procesar el video: {e}")

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
    ("Buscador / Enlace TikTok 🎵", "Subir archivo MP4 local 📁")
)

if metodo_origen == "Buscador / Enlace TikTok 🎵":
    col_search, col_url = st.columns([1, 1], gap="medium")
    
    with col_search:
        st.subheader("🔍 Buscador de TikTok")
        query = st.text_input("Escribe el tema o nombre del video:")
        if st.button("Buscar videos"):
            if query:
                with st.spinner("Buscando clips en TikTok..."):
                    st.session_state['resultados_tiktok'] = buscar_videos_tiktok(query, max_results=4)

    with col_url:
        st.subheader("🔗 Pegar Enlace Directo")
        url_directa = st.text_input("Pega el enlace completo de TikTok:")
        if st.button("Cargar desde enlace"):
            if url_directa:
                cargar_y_preparar_escena("url", url_directa)

    if 'resultados_tiktok' in st.session_state and st.session_state['resultados_tiktok']:
        st.markdown("### Resultados encontrados:")
        cols = st.columns(len(st.session_state['resultados_tiktok']))
        for idx, item in enumerate(st.session_state['resultados_tiktok']):
            with cols[idx]:
                if item['thumbnail']:
                    st.image(item['thumbnail'], use_container_width=True)
                st.caption(f"**{item['title'][:40]}...**")
                if st.button(f"Usar este video", key=f"btn_tk_{idx}"):
                    cargar_y_preparar_escena("url", item['url'])

elif metodo_origen == "Subir archivo MP4 local 📁":
    uploaded_file = st.file_uploader("Sube tu archivo de video:", type=["mp4"])
    if uploaded_file is not None:
        if st.button("Cargar escena"):
            cargar_y_preparar_escena("local", uploaded_file)

# --- ESTUDIO DE GRABACIÓN PASO A PASO (SIN SCROLL) ---
if st.session_state.get('escena_lista', False) and 'segments' in st.session_state:
    st.divider()
    st.header("2. Estudio de Grabación 🎬")

    segments = st.session_state['segments']
    total_pasos = len(segments)
    paso_actual = st.session_state.get('paso_actual', 0)

    if 'tomas_grabadas' not in st.session_state:
        st.session_state['tomas_grabadas'] = {}

    col_video, col_estudio = st.columns([1, 1], gap="large")

    with col_video:
        st.subheader("📺 Video Guía")
        if os.path.exists("video_input.mp4"):
            st.video("video_input.mp4")

    with col_estudio:
        seg = segments[paso_actual]
        
        st.subheader(f"🎙️ Frase {paso_actual + 1} de {total_pasos}")
        
        st.markdown(f"""
            <div class="teleprompter-box">
                <span class="time-badge">⏱️ Tiempo: {seg['start']:.1f}s - {seg['end']:.1f}s</span>
            </div>
        """, unsafe_allow_html=True)

        texto_editado = st.text_input(
            "Texto del diálogo (editable):",
            value=seg['text'].strip(),
            key=f"text_edit_{paso_actual}"
        )
        st.session_state['segments'][paso_actual]['text'] = texto_editado

        clip_path = f"clip_preview_{paso_actual}.mp4"
        if st.button(f"▶️ Escuchar fragmento original", key=f"prev_btn_{paso_actual}"):
            with st.spinner("Cargando fragmento..."):
                recortar_fragmento_video(seg['start'], seg['end'], clip_path)

        if os.path.exists(clip_path):
            st.video(clip_path)

        audio_data = st.audio_input(f"Grabar voz para la frase {paso_actual + 1}", key=f"rec_{paso_actual}")
        toma_path = f"user_toma_{paso_actual}.wav"
        
        if audio_data:
            with open(toma_path, "wb") as f:
                f.write(audio_data.read())
            score, estrellas, titulo, mensaje = evaluar_toma_divertida("audio_ref.wav", toma_path)
            st.markdown(f"**Puntuación:** {estrellas} `{score}%` — {mensaje}")
            st.session_state['tomas_grabadas'][paso_actual] = (toma_path, seg['start'])

        # Controles de navegación paso a paso
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        
        with col_prev:
            if paso_actual > 0:
                if st.button("⬅️ Anterior"):
                    st.session_state['paso_actual'] -= 1
                    st.rerun()

        with col_info:
            st.caption(f"Progreso: **{len(st.session_state['tomas_grabadas'])}/{total_pasos}** frases grabadas")

        with col_next:
            if paso_actual < total_pasos - 1:
                if st.button("Siguiente ➡️"):
                    st.session_state['paso_actual'] += 1
                    st.rerun()

    # --- MONTAJE FINAL ---
    st.divider()
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
            limpiar_archivos_temporales(limpiar_todo=True)
            for k in ['resultados_tiktok', 'escena_lista', 'segments', 'paso_actual', 'tomas_grabadas']:
                if k in st.session_state:
                    del st.session_state[k]
            st.toast("Estudio listo para una nueva escena.")
            st.rerun()

    mapa_tomas = list(st.session_state['tomas_grabadas'].values())

    if btn_generar:
        if not mapa_tomas:
            st.warning("Graba al menos una frase antes de mezclar.")
        else:
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
