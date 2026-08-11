import streamlit as st
import whisper
import numpy as np
import subprocess
import os
import glob
import json
import yt_dlp

st.set_page_config(page_title="App de Doblaje Party 🎙️", page_icon="🎬", layout="wide")

CACHE_FILE = "cache_sesion.json"

def guardar_cache_sesion(datos):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Error al guardar caché: {e}")

def cargar_cache_sesion():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

# Restauración de sesión
if 'restaurado' not in st.session_state:
    cache_previo = cargar_cache_sesion()
    if cache_previo:
        st.session_state['archivos_listos'] = cache_previo.get('archivos_listos', False)
        st.session_state['segments'] = cache_previo.get('segments', None)
        st.session_state['selected_url'] = cache_previo.get('selected_url', None)
    st.session_state['restaurado'] = True

if 'current_idx' not in st.session_state:
    st.session_state['current_idx'] = 0

# Estilos CSS
st.markdown("""
    <style>
    .subtitle-box {
        background-color: #0d1117;
        border: 2px solid #30363d;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    .subtitle-text {
        font-size: 26px;
        font-weight: bold;
        color: #58a6ff;
        margin: 0;
    }
    .time-info {
        font-size: 14px;
        color: #8b949e;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎙️ ¡Juego de Doblaje Party!")

def buscar_videos_yt(query, max_results=4):
    ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist', 'skip_download': True}
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
    opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'worstvideo[ext=mp4]+bestaudio[ext=m4a]/worst[ext=mp4]/worst',
        'outtmpl': 'video_input.mp4',
        'overwrites': True,
        'referer': 'https://www.tiktok.com/',
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    cmd_audio = "ffmpeg -y -i video_input.mp4 -vn -acodec pcm_s16le -ar 16000 audio_ref.wav"
    subprocess.run(cmd_audio, shell=True)

def recortar_fragmento_video(inicio, fin, output_path):
    duracion = fin - inicio
    cmd = f"ffmpeg -y -ss {inicio} -i video_input.mp4 -t {duracion} -c:v copy -c:a aac {output_path}"
    subprocess.run(cmd, shell=True)

def extraer_fragmento_audio_ref(inicio, fin, output_audio_path):
    duracion = fin - inicio
    cmd = f"ffmpeg -y -ss {inicio} -i audio_ref.wav -t {duracion} -acodec pcm_s16le {output_audio_path}"
    subprocess.run(cmd, shell=True)

def mostrar_grafico_ondas_nativo(audio_ref_path, audio_user_path=None, samples=300):
    """Genera una vista de ondas usando el gráfico nativo de Streamlit (sin dependencias de matplotlib)"""
    try:
        y_ref, _ = librosa.load(audio_ref_path, sr=8000)
        
        # Reducir resolución para renderizado rápido
        step_ref = max(1, len(y_ref) // samples)
        onda_ref = np.abs(y_ref[::step_ref][:samples])

        data_dict = {"Original (Azul)": onda_ref}

        if audio_user_path and os.path.exists(audio_user_path):
            y_user, _ = librosa.load(audio_user_path, sr=8000)
            step_user = max(1, len(y_user) // samples)
            onda_user = np.abs(y_user[::step_user][:samples])
            
            # Ajustar longitudes para que coincidan
            if len(onda_user) < len(onda_ref):
                onda_user = np.pad(onda_user, (0, len(onda_ref) - len(onda_user)))
            else:
                onda_user = onda_user[:len(onda_ref)]
                
            data_dict["Tu Grabación (Rojo)"] = onda_user

        st.line_chart(data_dict, height=180)
    except Exception as e:
        st.caption(f"No se pudo generar la vista previa de onda: {e}")

def evaluar_toma_divertida(audio_ref_path, audio_usuario_path):
    try:
        y_ref, sr_ref = librosa.load(audio_ref_path)
        y_user, sr_user = librosa.load(audio_usuario_path)
        dur_ref = librosa.get_duration(y=y_ref, sr=sr_ref)
        dur_user = librosa.get_duration(y=y_user, sr=sr_user)
        
        diferencia_tiempo = abs(dur_ref - dur_user)
        puntaje_tiempo = max(40, 100 - (diferencia_tiempo * 12))

        pitches_ref, _ = librosa.piptrack(y=y_ref, sr=sr_ref)
        pitches_user, _ = librosa.piptrack(y=y_user, sr=sr_user)
        p_ref = pitches_ref[pitches_ref > 0]
        p_user = pitches_user[pitches_user > 0]
        
        if len(p_ref) > 0 and len(p_user) > 0:
            dif_pitch = abs(np.median(p_ref) - np.median(p_user)) / np.median(p_ref)
            puntaje_pitch = max(50, 100 - (dif_pitch * 40))
        else:
            puntaje_pitch = 80.0

        score = round(min(100, max(50, (puntaje_tiempo * 0.5) + (puntaje_pitch * 0.5) + 15)), 1)

        if score >= 80:
            st.balloons()
            return score, "⭐⭐⭐⭐⭐", "🏆 ¡NIVEL ACTOR DE HOLLYWOOD!", "¡Excelente sincronización y energía!"
        elif score >= 65:
            return score, "⭐⭐⭐⭐", "🎙️ ¡MODO FANDUB ACTIVADO!", "Suenas increíble, listo para la mezcla final."
        elif score >= 50:
            return score, "⭐⭐⭐", "🎬 ¡BUENA TOMA!", "Cumple muy bien para el montaje de la escena."
        else:
            return score, "⭐⭐", "🤪 ¡VOZ DIVERTIDA!", "Buen intento, le pusiste ganas."
    except Exception:
        return 85.0, "⭐⭐⭐⭐", "👍 ¡GRABACIÓN COMPLETADA!", "Toma guardada para el montaje."

def limpiar_archivos_temporales(limpiar_todo=False):
    patrones = ["clip_preview_*.mp4", "user_toma_*.wav", "audio_ref_seg_*.wav", "audio_ref.wav"]
    if limpiar_todo:
        patrones.extend(["video_input.mp4", "resultado.mp4"])
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)

    archivos_eliminados = 0
    for patron in patrones:
        for archivo in glob.glob(patron):
            try:
                os.remove(archivo)
                archivos_eliminados += 1
            except Exception:
                pass
    return archivos_eliminados

# --- PASO 1: SELECCIÓN DE ESCENA ---
st.header("1. Carga tu Escena")

metodo_origen = st.radio(
    "Selecciona origen de la escena:",
    ("Subir archivo MP4 local 📁", "Pegar enlace directo (TikTok / YouTube) 🔗", "Buscador integrado 🔍"),
    horizontal=True
)

if metodo_origen == "Subir archivo MP4 local 📁":
    uploaded_file = st.file_uploader("Subir MP4:", type=["mp4"])
    if uploaded_file is not None:
        with open("video_input.mp4", "wb") as f:
            f.write(uploaded_file.read())
        subprocess.run("ffmpeg -y -i video_input.mp4 -vn -acodec pcm_s16le -ar 16000 audio_ref.wav", shell=True)
        st.session_state['archivos_listos'] = True
        guardar_cache_sesion({"archivos_listos": True})
        st.success("¡Video cargado con éxito!")

elif metodo_origen == "Pegar enlace directo (TikTok / YouTube) 🔗":
    url_directa = st.text_input("Pega el enlace de TikTok o YouTube:")
    if url_directa and st.button("Descargar"):
        with st.spinner("Descargando..."):
            descargar_escena(url_directa)
            st.session_state['archivos_listos'] = True
            guardar_cache_sesion({"archivos_listos": True, "selected_url": url_directa})
            st.success("¡Escena lista!")

elif metodo_origen == "Buscador integrado 🔍":
    query = st.text_input("Buscar video:")
    if query:
        resultados = buscar_videos_yt(query)
        cols = st.columns(len(resultados))
        for idx, item in enumerate(resultados):
            with cols[idx]:
                st.image(item['thumbnail'], use_container_width=True)
                st.caption(item['title'])
                if st.button("Usar", key=f"btn_{idx}"):
                    descargar_escena(item['url'])
                    st.session_state['archivos_listos'] = True
                    guardar_cache_sesion({"archivos_listos": True, "selected_url": item['url']})
                    st.success("¡Escena descargada!")

# --- PASO 2: EXTRAER DIÁLOGOS ---
if st.session_state.get('archivos_listos', False) or os.path.exists("video_input.mp4"):
    if 'segments' not in st.session_state or st.session_state['segments'] is None:
        if st.button("🔍 Extraer Diálogos con IA (Whisper)"):
            with st.spinner("Procesando diálogos..."):
                model = whisper.load_model("base")
                result = model.transcribe("audio_ref.wav")
                st.session_state['segments'] = result['segments']
                guardar_cache_sesion({
                    "archivos_listos": True,
                    "segments": result['segments']
                })
                st.rerun()

# --- PASO 3: ESTUDIO DE DOBLAJE PASO A PASO ---
if st.session_state.get('segments'):
    st.divider()
    segments = st.session_state['segments']
    total_frases = len(segments)
    curr_idx = st.session_state['current_idx']
    seg_actual = segments[curr_idx]

    c_prev, c_info, c_next = st.columns([1, 3, 1])
    with c_prev:
        if st.button("⬅️ Frase Anterior") and curr_idx > 0:
            st.session_state['current_idx'] -= 1
            st.rerun()
    with c_info:
        st.markdown(f"<h3 style='text-align: center;'>Frase {curr_idx + 1} de {total_frases}</h3>", unsafe_allow_html=True)
    with c_next:
        if st.button("Siguiente Frase ➡️") and curr_idx < total_frases - 1:
            st.session_state['current_idx'] += 1
            st.rerun()

    clip_path = f"clip_preview_{curr_idx}.mp4"
    audio_ref_seg_path = f"audio_ref_seg_{curr_idx}.wav"
    
    if not os.path.exists(clip_path):
        recortar_fragmento_video(seg_actual['start'], seg_actual['end'], clip_path)
    if not os.path.exists(audio_ref_seg_path):
        extraer_fragmento_audio_ref(seg_actual['start'], seg_actual['end'], audio_ref_seg_path)

    col_v1, col_v2, col_v3 = st.columns([1, 2, 1])
    with col_v2:
        st.video(clip_path)
        
        st.markdown(f"""
            <div class="subtitle-box">
                <p class="subtitle-text">"{seg_actual['text']}"</p>
                <span class="time-info">Tiempo: {seg_actual['start']:.1f}s - {seg_actual['end']:.1f}s</span>
            </div>
        """, unsafe_allow_html=True)

        toma_user_path = f"user_toma_{curr_idx}.wav"
        
        # Muestra la gráfica de ondas nativa
        mostrar_grafico_ondas_nativo(audio_ref_seg_path, toma_user_path if os.path.exists(toma_user_path) else None)
        st.caption("📈 Comparativa de ondas de audio (Original vs Tu Grabación)")

        audio_data = st.audio_input(f"Grabar frase {curr_idx + 1}", key=f"rec_single_{curr_idx}")
        if audio_data:
            with open(toma_user_path, "wb") as f:
                f.write(audio_data.read())
            score, estrellas, titulo, mensaje = evaluar_toma_divertida(audio_ref_seg_path, toma_user_path)
            st.markdown(f"**Puntuación:** {estrellas} `{score}%` — {mensaje}")
            st.rerun()

    # --- PASO 4: ENSAMBLADO FINAL ---
    st.divider()
    st.header("3. Ensamblado Final")
    
    col_vol1, col_vol2 = st.columns(2)
    with col_vol1:
        vol_original = st.slider("🔊 Volumen del audio original:", 0.0, 1.0, 0.2, 0.05)
    with col_vol2:
        vol_usuario = st.slider("🎙️ Volumen de tus grabaciones:", 0.5, 3.0, 1.5, 0.1)

    c_gen, c_clean = st.columns([2, 1])
    with c_gen:
        if st.button("🎬 Generar Video Final Doblado", type="primary"):
            mapa_tomas = []
            for i, seg in enumerate(segments):
                path_toma = f"user_toma_{i}.wav"
                if os.path.exists(path_toma):
                    mapa_tomas.append((path_toma, seg['start']))

            if not mapa_tomas:
                st.warning("No has grabado ninguna frase aún.")
            else:
                with st.spinner("Ensamblando doblaje final..."):
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
                        st.subheader("🍿 ¡Resultado Final!")
                        st.video("resultado.mp4")

    with c_clean:
        if st.button("🔄 Nueva Escena / Reiniciar"):
            limpiar_archivos_temporales(limpiar_todo=True)
            st.session_state.clear()
            st.rerun()
