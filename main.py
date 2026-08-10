import streamlit as st
import whisper
import librosa
import numpy as np
import subprocess
import os
import glob
import yt_dlp

st.set_page_config(page_title="App de Doblaje Party 🎙️", page_icon="🎬", layout="wide")

# Estilos CSS para el modo Teleprompter y las tarjetas
st.markdown("""
    <style>
    .teleprompter-box {
        background-color: #111827;
        border-left: 5px solid #3B82F6;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
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
st.write("Busca cualquier escena, guíate con la vista previa por frase y el teleprompter, graba tus voces y genera tu doblaje.")

def buscar_videos_yt(query, max_results=4):
    """Busca videos en YouTube y devuelve miniaturas, títulos y URLs"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
    }
    resultados = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    resultados.append({
                        'title': entry.get('title', 'Sin título'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'thumbnail': f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                    })
        except Exception as e:
            st.error(f"Error en la búsqueda: {e}")
    return resultados

def descargar_escena(url):
    """Descarga la escena e extrae el audio de referencia"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'format': 'worstvideo[ext=mp4]+bestaudio[ext=m4a]/worst[ext=mp4]/worst',
        'outtmpl': 'video_input.mp4',
        'overwrites': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    cmd_audio = "ffmpeg -y -i video_input.mp4 -vn -acodec pcm_s16le -ar 16000 audio_ref.wav"
    subprocess.run(cmd_audio, shell=True)

def recortar_fragmento_video(inicio, fin, output_path):
    """Recorta un fragmento específico de video usando FFmpeg"""
    duracion = fin - inicio
    cmd = f"ffmpeg -y -ss {inicio} -i video_input.mp4 -t {duracion} -c:v copy -c:a aac {output_path}"
    subprocess.run(cmd, shell=True)

def limpiar_archivos_temporales(limpiar_todo=False):
    """
    Elimina archivos de audio, fragmentos de video y cache.
    Si limpiar_todo=True, también borra el video de entrada original.
    """
    patrones = [
        "clip_preview_*.mp4",
        "user_toma_*.wav",
        "audio_ref.wav",
        "audio_temp.wav"
    ]
    if limpiar_todo:
        patrones.append("video_input.mp4")

    archivos_eliminados = 0
    for patron in patrones:
        archivos = glob.glob(patron)
        for archivo in archivos:
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

# --- PASO 1: BÚSQUEDA Y SELECCIÓN DE ESCENA ---
st.header("1. Busca y Selecciona tu Escena")
query = st.text_input("Escribe el nombre de la serie, anime o película que quieres doblar:")

if query:
    with st.spinner("Buscando las mejores escenas..."):
        resultados = buscar_videos_yt(query, max_results=4)
    
    if resultados:
        col1, col2, col3, col4 = st.columns(4)
        cols = [col1, col2, col3, col4]
        for idx, item in enumerate(resultados):
            with cols[idx]:
                st.image(item['thumbnail'], use_container_width=True)
                st.caption(f"**{item['title']}**")
                if st.button(f"🎬 Usar esta escena", key=f"btn_{idx}"):
                    st.session_state['selected_url'] = item['url']

if 'selected_url' in st.session_state:
    if st.button("📥 Descargar y preparar escena"):
        with st.spinner("Procesando audio y video..."):
            try:
                descargar_escena(st.session_state['selected_url'])
                st.session_state['archivos_listos'] = True
                st.success("¡Escena descargada y lista!")
            except Exception as e:
                st.error(f"Error al descargar la escena: {e}")

# --- PASO 2: EXTRAER DIÁLOGOS ---
if st.session_state.get('archivos_listos', False):
    st.divider()
    if st.button("🔍 Extraer Diálogos con IA"):
        with st.spinner("Whisper está escuchando y separando las frases..."):
            model = whisper.load_model("base")
            result = model.transcribe("audio_ref.wav")
            st.session_state['segments'] = result['segments']
            st.success("¡Diálogos listos!")

# --- PASO 3: ESTUDIO DE GRABACIÓN INTERACTIVO ---
if 'segments' in st.session_state:
    st.divider()
    st.header("2. Estudio de Grabación 🎬")
    st.write("Mira la escena completa a la izquierda o reproduce el clip específico de cada frase antes de grabar.")

    segments = st.session_state['segments']
    mapa_tomas = []

    col_video, col_estudio = st.columns([1, 1], gap="large")

    with col_video:
        st.subheader("📺 Escena Completa")
        if os.path.exists("video_input.mp4"):
            st.video("video_input.mp4")

    with col_estudio:
        st.subheader("🎙️ Teleprompter & Grabación")
        
        for idx, seg in enumerate(segments):
            st.markdown(f"""
                <div class="teleprompter-box">
                    <span class="time-badge">Frase {idx + 1} | Tiempo: {seg['start']:.1f}s - {seg['end']:.1f}s</span>
                    <p class="teleprompter-text">"{seg['text']}"</p>
                </div>
            """, unsafe_allow_html=True)
            
            clip_path = f"clip_preview_{idx}.mp4"
            if st.button(f"▶️ Ver fragmento de la frase {idx + 1}", key=f"prev_btn_{idx}"):
                with st.spinner("Generando vista previa..."):
                    recortar_fragmento_video(seg['start'], seg['end'], clip_path)
                
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

    # --- PASO 4: ENSAMBLADO FINAL Y LIMPIEZA ---
    st.header("3. Ensamblado Final")
    
    col_vol1, col_vol2 = st.columns(2)
    with col_vol1:
        vol_original = st.slider("🔊 Volumen del audio original:", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    with col_vol2:
        vol_usuario = st.slider("🎙️ Volumen de tus grabaciones:", min_value=0.5, max_value=3.0, value=1.5, step=0.1)

    col_gen, col_clean = st.columns([2, 1])
    
    with col_gen:
        btn_generar = st.button("🎬 Generar Video Final Doblado")
    with col_clean:
        if st.button("🧹 Limpiar memoria y archivos temporales"):
            eliminados = limpiar_archivos_temporales(limpiar_todo=True)
            st.toast(f"Se eliminaron {eliminados} archivos temporales.")

    if btn_generar and mapa_tomas:
        with st.spinner("FFmpeg está mezclando y ajustando los niveles de audio..."):
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
                st.subheader("🍿 ¡Resultado de tu Doblaje!")
                st.video("resultado.mp4")
                st.success("¡Tu doblaje ha sido completado con éxito!")
                
                archivos_borrados = limpiar_archivos_temporales(limpiar_todo=False)
                st.caption(f"🧹 *Memoria optimizada: Se borraron {archivos_borrados} archivos temporales de edición.*")
