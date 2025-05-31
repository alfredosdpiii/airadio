import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import openai
import requests
import io
import os
from concurrent.futures import ThreadPoolExecutor
import json

st.set_page_config(page_title="📻 AI Tagalog Radio", page_icon="📻", layout="wide")

# Get environment variables or use Streamlit secrets
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or st.secrets.get("SPOTIPY_CLIENT_ID", "")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or st.secrets.get("SPOTIPY_CLIENT_SECRET", "")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI") or st.secrets.get("SPOTIPY_REDIRECT_URI", "https://airadio.streamlit.app")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, OPENAI_API_KEY]):
    st.error("Missing required environment variables. Please set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and OPENAI_API_KEY")
    st.stop()

openai.api_key = OPENAI_API_KEY

def infer_mood(features):
    valence = features['valence']
    energy = features['energy']
    danceability = features['danceability']
    
    if valence > 0.7 and energy > 0.7:
        return "masaya at energetic"
    elif valence > 0.6 and danceability > 0.7:
        return "nakakasayaw"
    elif valence < 0.3:
        return "malungkot"
    elif energy < 0.3:
        return "relaxing"
    else:
        return "chill"

def generate_dj_script(track_name, artist_name, mood):
    prompt = f"""
    Ikaw ay isang radio DJ na masigla at kalmado. 
    Track: {track_name} – {artist_name}
    Mood: {mood}
    
    Gumawa ng 1-2 pangungusap pambati sa Tagalog na mag-market din ng kanta. 
    Maging engaging at huwag masyadong mahaba.
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Kamusta mga ka-tropa! Narito si DJ AI at papakinggan natin ang {track_name} ni {artist_name}!"

def generate_tts(text):
    try:
        response = openai.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text
        )
        return response.content
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def generate_album_art(mood, track_name):
    prompt = f"{mood} abstract album art for {track_name}, vibrant Filipino-inspired colors, modern design"
    try:
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        img_url = response.data[0].url
        img_response = requests.get(img_url)
        return img_response.content
    except Exception as e:
        st.error(f"Image generation error: {e}")
        return None

def main():
    st.title("📻 AI Tagalog Radio")
    st.markdown("*Ang pinakamasayang radio station na may AI DJ!*")
    
    # Initialize session state
    if 'spotify_token' not in st.session_state:
        st.session_state.spotify_token = None
    
    # Spotify Authentication
    scope = "user-read-playback-state user-library-modify"
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=scope
    )
    
    # Check for auth code in URL
    auth_url = sp_oauth.get_authorize_url()
    
    if st.session_state.spotify_token is None:
        st.markdown("### 🎵 Connect to Spotify")
        st.markdown(f"[Click here to authorize Spotify access]({auth_url})")
        
        auth_code = st.text_input("Paste the authorization code from the URL after clicking above:")
        if auth_code:
            try:
                token_info = sp_oauth.get_access_token(auth_code)
                st.session_state.spotify_token = token_info['access_token']
                st.success("Spotify connected!")
                st.rerun()
            except Exception as e:
                st.error(f"Authentication error: {e}")
    else:
        # Main app interface
        sp = spotipy.Spotify(auth=st.session_state.spotify_token)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🎧 Current Track")
            
            # Option to manually enter track ID for testing
            manual_track = st.text_input("Or enter Spotify Track ID manually:", 
                                       placeholder="e.g., 4iV5W9uYEdYUVa79Axb7Rh")
            
            track_id = None
            track = None
            
            if manual_track:
                track_id = manual_track
            else:
                # Try to get current playing track
                try:
                    current = sp.current_playback()
                    if current and current['item']:
                        track = current['item']
                        track_id = track['id']
                    else:
                        st.info("No track currently playing. Please start playing a song on Spotify or enter a track ID manually.")
                except Exception as e:
                    st.error(f"Error getting current track: {e}")
            
            if track_id:
                if not track:
                    try:
                        track = sp.track(track_id)
                    except Exception as e:
                        st.error(f"Error getting track details: {e}")
                        return
                
                # Display track info
                st.markdown(f"**{track['name']}** by **{track['artists'][0]['name']}**")
                
                # Spotify embed
                embed_html = f"""
                <iframe src="https://open.spotify.com/embed/track/{track_id}" 
                        width="100%" height="152" frameborder="0" 
                        allowtransparency="true" allow="encrypted-media">
                </iframe>
                """
                st.components.v1.html(embed_html, height=152)
                
                # Generate AI content
                if st.button("🎙️ Generate DJ Intro"):
                    with st.spinner("AI DJ is preparing your intro..."):
                        try:
                            # Get audio features
                            features = sp.audio_features(track_id)[0]
                            mood = infer_mood(features)
                            
                            # Generate DJ script
                            dj_script = generate_dj_script(track['name'], track['artists'][0]['name'], mood)
                            
                            # Generate TTS
                            tts_audio = generate_tts(dj_script)
                            
                            # Generate album art
                            album_art = generate_album_art(mood, track['name'])
                            
                            # Display results
                            st.markdown("### 🎨 AI Generated Content")
                            
                            if album_art:
                                st.image(album_art, caption="AI Generated Album Art", width=300)
                            
                            st.markdown("### 🎙️ DJ Script")
                            st.write(dj_script)
                            
                            if tts_audio:
                                st.markdown("### 🔊 DJ Voice")
                                st.audio(tts_audio, format="audio/mp3")
                            
                            st.markdown(f"**Detected Mood:** {mood}")
                            
                        except Exception as e:
                            st.error(f"Error generating content: {e}")
        
        with col2:
            st.markdown("### 💚 Quick Actions")
            
            if track_id and st.button("💚 Save Track"):
                try:
                    sp.current_user_saved_tracks_add([track_id])
                    st.success("Track saved to your library!")
                except Exception as e:
                    st.error(f"Error saving track: {e}")
            
            if track_id:
                share_url = f"https://open.spotify.com/track/{track_id}"
                st.markdown(f"### 🔗 Share")
                st.code(share_url)

if __name__ == "__main__":
    main()
