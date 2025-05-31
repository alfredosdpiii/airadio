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
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI") or st.secrets.get("SPOTIPY_REDIRECT_URI", "https://airadio-wyfdkkcryaifuvaywzbqtz.streamlit.app/callback")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, OPENAI_API_KEY]):
    st.error("Missing required environment variables. Please set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and OPENAI_API_KEY")
    st.stop()

openai.api_key = OPENAI_API_KEY

def generate_dj_script():
    """Generate a DJ script that includes mood, genre, and song selection criteria"""
    prompt = """
    Ikaw ay isang radio DJ na masigla sa isang Tagalog radio station. 
    
    Gumawa ng:
    1. Magandang DJ intro/patter sa Tagalog (2-3 sentences)
    2. Describe kung anong mood/genre ng kanta na gusto mo i-play (e.g., "masayang pop song", "romantic ballad", "energetic dance track")
    3. Include marketing hype about the upcoming song
    
    Format your response as:
    INTRO: [your tagalog DJ intro]
    MOOD: [mood/genre you want to play] 
    HYPE: [marketing line about the song]
    
    Be engaging, fun, and authentically Filipino!
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return """INTRO: Kamusta mga ka-tropa! Narito si DJ AI para sa inyong paboritong kanta!
MOOD: masayang pop song
HYPE: Pakinggan natin ang bagong hit na siguradong magpapasaya sa inyong araw!"""

def extract_mood_from_script(script):
    """Extract mood/genre from DJ script to use for Spotify search"""
    try:
        lines = script.split('\n')
        mood_line = [line for line in lines if line.startswith('MOOD:')]
        if mood_line:
            mood = mood_line[0].replace('MOOD:', '').strip()
            return mood
        return "happy upbeat song"
    except:
        return "happy upbeat song"

def search_spotify_by_mood(sp, mood_description):
    """Search Spotify for OPM songs based on mood description"""
    try:
        # Map mood to search terms and audio features for OPM
        mood_lower = mood_description.lower()
        
        # OPM-specific search terms based on mood
        opm_search_terms = []
        target_features = {}
        
        if any(word in mood_lower for word in ['masaya', 'happy', 'energetic']):
            opm_search_terms = ['OPM happy', 'Filipino pop upbeat', 'Pinoy rock energetic']
            target_features = {'valence': 0.8, 'energy': 0.7}
        elif any(word in mood_lower for word in ['romantic', 'love', 'ballad', 'hugot']):
            opm_search_terms = ['OPM love songs', 'Filipino ballad', 'Pinoy romantic', 'hugot songs']
            target_features = {'valence': 0.6, 'energy': 0.4}
        elif any(word in mood_lower for word in ['dance', 'sayaw', 'party', 'disco']):
            opm_search_terms = ['OPM dance', 'Filipino party songs', 'Pinoy disco']
            target_features = {'danceability': 0.8, 'energy': 0.8}
        elif any(word in mood_lower for word in ['sad', 'malungkot', 'emo']):
            opm_search_terms = ['OPM sad', 'Filipino emotional', 'Pinoy emo']
            target_features = {'valence': 0.3, 'energy': 0.4}
        elif any(word in mood_lower for word in ['rock', 'metal', 'alternative']):
            opm_search_terms = ['OPM rock', 'Filipino rock', 'Pinoy alternative', 'Pinoy metal']
            target_features = {'energy': 0.8, 'loudness': -5}
        else:
            opm_search_terms = ['OPM hits', 'Filipino pop', 'Pinoy classics']
            target_features = {'valence': 0.6, 'energy': 0.6}
        
        # Try recommendations with Philippines OPM genre first
        try:
            recommendations = sp.recommendations(
                seed_genres=['philippines-opm'],
                limit=20,
                market='PH',
                **{f'target_{k}': v for k, v in target_features.items()}
            )
            if recommendations['tracks']:
                return recommendations['tracks'][0]
        except:
            pass
        
        # Search specifically for OPM/Filipino music
        for term in opm_search_terms:
            try:
                # Search with Philippines market preference
                results = sp.search(q=term, type='track', limit=50, market='PH')
                if results['tracks']['items']:
                    return results['tracks']['items'][0]
            except:
                continue
        
        # Additional OPM artist search
        famous_opm_artists = [
            'Ben&Ben', 'Moira Dela Torre', 'December Avenue', 'The Juans',
            'IV of Spades', 'Unique Salonga', 'SB19', 'BINI', 'Parokya ni Edgar',
            'Rivermaya', 'Eraserheads', 'Bamboo', 'Sponge Cola', 'Silent Sanctuary',
            'Kamikazee', 'Callalily', 'Moonstar88', 'Itchyworms', 'Orange and Lemons'
        ]
        
        for artist in famous_opm_artists[:5]:  # Try first 5 artists
            try:
                results = sp.search(q=f'artist:{artist}', type='track', limit=20, market='PH')
                if results['tracks']['items']:
                    return results['tracks']['items'][0]
            except:
                continue
        
        # Final fallback - general OPM search
        try:
            results = sp.search(q='OPM Filipino music', type='track', limit=20, market='PH')
            if results['tracks']['items']:
                return results['tracks']['items'][0]
        except:
            pass
            
        return None
        
    except Exception as e:
        st.error(f"Spotify search error: {e}")
        return None

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
    
    # Check for auth code in URL parameters
    query_params = st.query_params
    auth_code = query_params.get("code")
    
    if st.session_state.spotify_token is None:
        if auth_code:
            # Handle the callback automatically
            try:
                token_info = sp_oauth.get_access_token(auth_code)
                st.session_state.spotify_token = token_info['access_token']
                # Clear the URL parameters after successful auth
                st.query_params.clear()
                st.success("Spotify connected!")
                st.rerun()
            except Exception as e:
                st.error(f"Authentication error: {e}")
        else:
            # Show authorization link
            auth_url = sp_oauth.get_authorize_url()
            st.markdown("### 🎵 Connect to Spotify")
            st.markdown(f"[Click here to authorize Spotify access]({auth_url})")
    else:
        # Main app interface
        sp = spotipy.Spotify(auth=st.session_state.spotify_token)
        
        st.markdown("### 🎙️ AI Radio Station")
        st.markdown("*The AI DJ will generate a script, select a perfect song, and create the full radio experience!*")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Big button to start the AI radio experience
            if st.button("🎵 Start AI Radio Show", type="primary", use_container_width=True):
                with st.spinner("🤖 AI DJ is preparing the show..."):
                    try:
                        # Step 1: Generate DJ script
                        st.markdown("**Step 1:** Generating DJ script...")
                        dj_script = generate_dj_script()
                        
                        # Step 2: Extract mood and select song
                        st.markdown("**Step 2:** Selecting perfect song based on DJ's mood...")
                        mood = extract_mood_from_script(dj_script)
                        selected_track = search_spotify_by_mood(sp, mood)
                        
                        if not selected_track:
                            st.error("Could not find a suitable track. Please try again.")
                            return
                        
                        # Step 3: Generate TTS for the script
                        st.markdown("**Step 3:** Converting DJ script to voice...")
                        
                        # Parse the script components
                        script_lines = dj_script.split('\n')
                        intro_line = [line for line in script_lines if line.startswith('INTRO:')]
                        hype_line = [line for line in script_lines if line.startswith('HYPE:')]
                        
                        intro_text = intro_line[0].replace('INTRO:', '').strip() if intro_line else "Kamusta mga ka-tropa!"
                        hype_text = hype_line[0].replace('HYPE:', '').strip() if hype_line else "Pakinggan natin ang magandang kantang ito!"
                        
                        # Create full script with song info
                        full_script = f"{intro_text} {hype_text} Narito ang {selected_track['name']} ni {selected_track['artists'][0]['name']}!"
                        
                        tts_audio = generate_tts(full_script)
                        
                        # Step 4: Generate album art
                        st.markdown("**Step 4:** Creating mood-based album art...")
                        album_art = generate_album_art(mood, selected_track['name'])
                        
                        # Display the complete radio show
                        st.markdown("---")
                        st.markdown("## 📻 Your AI Radio Show")
                        
                        # Show album art
                        if album_art:
                            st.image(album_art, caption="AI Generated Album Art", width=400)
                        
                        # Show DJ script
                        st.markdown("### 🎙️ DJ Script")
                        st.info(f"**Mood:** {mood}")
                        st.write(dj_script)
                        
                        # Play DJ voice
                        if tts_audio:
                            st.markdown("### 🔊 DJ Voice")
                            st.audio(tts_audio, format="audio/mp3")
                        
                        # Show selected track
                        st.markdown("### 🎵 Selected Track")
                        st.markdown(f"**{selected_track['name']}** by **{selected_track['artists'][0]['name']}**")
                        
                        # Spotify embed
                        embed_html = f"""
                        <iframe src="https://open.spotify.com/embed/track/{selected_track['id']}" 
                                width="100%" height="152" frameborder="0" 
                                allowtransparency="true" allow="encrypted-media">
                        </iframe>
                        """
                        st.components.v1.html(embed_html, height=152)
                        
                        # Store track ID for actions
                        st.session_state.current_track_id = selected_track['id']
                        
                    except Exception as e:
                        st.error(f"Error generating radio show: {e}")
        
        with col2:
            st.markdown("### 💚 Quick Actions")
            
            if hasattr(st.session_state, 'current_track_id') and st.session_state.current_track_id:
                track_id = st.session_state.current_track_id
                
                if st.button("💚 Save Track"):
                    try:
                        sp.current_user_saved_tracks_add([track_id])
                        st.success("Track saved to your library!")
                    except Exception as e:
                        st.error(f"Error saving track: {e}")
                
                share_url = f"https://open.spotify.com/track/{track_id}"
                st.markdown("### 🔗 Share")
                st.code(share_url)
                
                if st.button("🔄 Generate New Show"):
                    st.rerun()

if __name__ == "__main__":
    main()
