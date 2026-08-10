import streamlit as st
import whisper
import librosa
import numpy as np
import subprocess
import os
import yt_dlp
import urllib.parse

st.set_page_config(page_title="App de Doblaje Fiesta 🎙️", page_icon="🎬", layout="centered")
st.title("🎙️ ¡Juego de Doblaje Party!")
st.write("Conviértete en actor de voz: busca una escena, graba frase por frase y descubre tu talento.")

# Opciones optimizadas para bajar audio/video desde URL
YTDLP_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': 'video_input.mp4',
    'overwrites': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios']
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'
    }
}

def descargar_desde_youtube(url_youtube):
    with yt_dlp.YoutubeDL(YTDLP_OPTS) as ydl:
        ydl.download([url_youtube])
    
    cmd_audio = "ffmpeg -y -i video_input.mp4 -vn -acodec pcm_s16le -ar 16000 audio_ref.wav"
    subprocess.run(cmd_audio, shell=True)

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

st.header("1. Elige tu Escena")
opcion_origen = st.radio("¿De dónde obtenemos la escena?", ("YouTube (Enlace / Búsqueda) 📹", "Subir archivo MP4 local 📁"))

if opcion_origen == "YouTube (Enlace / Búsqueda) 📹":
    query = st.text_input("Escribe el nombre de la escena o pega la URL directamente:")
    
    if query:
        if "youtube.com" in query or "youtu.be" in query:
            url_final = query
        else:
            url_busqueda = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            st.markdown(f"👉 [Haz clic aquí para abrir los resultados en YouTube]({url_busqueda}) y copia el enlace del video que te guste.")
            url_final = st.text_input("Pega aquí el enlace copiado:")

        if url_final:
            st.write("**Vista previa del video:**")
            st.video(url_final)
            
            if st.button("Cargar esta escena"):
                with st.spinner("Descargando video y procesando audio..."):
                    try:
                        descargar_desde_youtube(url_final)
                        st.session_state['archivos_listos'] = True
                        st.success("¡Escena lista para doblar!")
                    except Exception as e:
                        st.error(f"Error al descargar: {e}")
else:
    video_file = st.file_uploader("Sube tu archivo de video (MP4)", type=["mp4"])
    audio_ref = st.file_uploader("Sube el audio de referencia (WAV/MP3)", type=["wav", "mp3"])
    if video_file:
        st.video(video_file)
    if video_file and audio_ref:
        with open("video_input.mp4", "wb") as f:
            f.write(video_file.getbuffer())
        with open("audio_ref.wav", "wb") as f:
            f.write(audio_ref.getbuffer())
        st.session_state['archivos_listos'] = True

if st.session_state.get('archivos_listos', False):
    st.divider()
    if st.button("🔍 Extraer Diálogos con IA"):
        with st.spinner("Whisper está escuchando y cortando las frases..."):
            model = whisper.load_model("base")
            result = model.transcribe("audio_ref.wav")
            st.session_state['segments'] = result['segments']
            st.success("¡Listas las frases para grabar!")

if 'segments' in st.session_state:
    st.header("2. Grabación y Calificación Cómica")
    segments = st.session_state['segments']
    mapa_tomas = []
    for idx, seg in enumerate(segments):
        st.subheader(f"Frase {idx + 1} ({seg['start']:.1f}s - {seg['end']:.1f}s)")
        st.info(f"👉 **\"{seg['text']}\"**")
        audio_data = st.audio_input(f"Grabar frase {idx + 1}", key=f"rec_{idx}")
        toma_path = f"user_toma_{idx}.wav"
        if audio_data:
            with open(toma_path, "wb") as f:
                f.write(audio_data.read())
            score, estrellas, titulo, mensaje = evaluar_toma_divertida("audio_ref.wav", toma_path)
            st.markdown(f"### {estrellas} {titulo}")
            st.caption(f"**Puntuación: {score}%** — {mensaje}")
            mapa_tomas.append((toma_path, seg['start']))

    st.divider()
    st.header("3. Ensamblado y Resultado")
    if st.button("🎬 Generar Video Final Doblado") and mapa_tomas:
        with st.spinner("FFmpeg está mezclando tu interpretación con la escena..."):
            inputs = ["-i video_input.mp4"]
            filter_complex = ""
            mix_labels = ""
            for i, (path, inicio) in enumerate(mapa_tomas):
                inputs.append(f"-i {path}")
                ms_delay = int(inicio * 1000)
                idx_input = i + 1
                filter_complex += f"[{idx_input}:a]adelay={ms_delay}|{ms_delay}[a{idx_input}];"
                mix_labels += f"[a{idx_input}]"
            count_inputs = len(mapa_tomas)
            filter_complex += f"{mix_labels}amix=inputs={count_inputs}:duration=first[aout]"
            cmd = f"ffmpeg -y {' '.join(inputs)} -filter_complex \"{filter_complex}\" -map 0:v -map \"[aout]\" -c:v copy -c:a aac resultado.mp4"
            subprocess.run(cmd, shell=True)
            if os.path.exists("resultado.mp4"):
                st.video("resultado.mp4")
                st.success("¡Tu doblaje quedó listo!")
