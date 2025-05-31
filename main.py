import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import openai
import requests
import io
import os
from concurrent.futures import ThreadPoolExecutor
import json
import time

# Try to import Tavily, fallback if not available
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

st.set_page_config(page_title="📻 AI Tagalog Radio", page_icon="📻", layout="wide")

# Get environment variables or use Streamlit secrets
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or st.secrets.get("SPOTIPY_CLIENT_ID", "")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or st.secrets.get("SPOTIPY_CLIENT_SECRET", "")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI") or st.secrets.get("SPOTIPY_REDIRECT_URI", "https://airadio-wyfdkkcryaifuvaywzbqtz.streamlit.app/callback")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
TAVILY_API_KEY = "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"

if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, OPENAI_API_KEY]):
    st.error("Missing required environment variables. Please set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and OPENAI_API_KEY")
    st.stop()

openai.api_key = OPENAI_API_KEY

# Initialize Tavily client if available
tavily_client = None
if TAVILY_AVAILABLE:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    except:
        TAVILY_AVAILABLE = False

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
                import random
                # Return a random track from recommendations instead of always first
                return random.choice(recommendations['tracks'][:10])
        except:
            pass
        
        # Search specifically for OPM/Filipino music
        for term in opm_search_terms:
            try:
                # Search with Philippines market preference
                results = sp.search(q=term, type='track', limit=50, market='PH')
                if results['tracks']['items']:
                    import random
                    # Return random track from search results
                    return random.choice(results['tracks']['items'][:20])
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

def search_artist_info(artist_name):
    """Search for artist information and marketing content"""
    if TAVILY_AVAILABLE and tavily_client:
        try:
            query = f"{artist_name} Filipino OPM artist biography achievements recent news"
            search_results = tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=3
            )
            
            # Combine search results into marketing content
            marketing_info = ""
            if search_results and 'results' in search_results:
                for result in search_results['results'][:2]:  # Use top 2 results
                    marketing_info += f"{result.get('content', '')[:200]}... "
            
            return marketing_info.strip()
        except Exception as e:
            pass
    
    # Fallback artist info database for popular OPM artists
    artist_info_db = {
        "Ben&Ben": "Ben&Ben ay isa sa mga pinakasikat na indie folk band sa Pilipinas na kilala sa kanilang emosyonal na mga kanta at magagandang lyrics.",
        "Moira Dela Torre": "Si Moira Dela Torre ay isang award-winning Filipino singer-songwriter na kilala sa kanyang mataas na boses at heartfelt na mga ballade.",
        "December Avenue": "December Avenue ay isang Filipino rock band na naging viral sa social media dahil sa kanilang mga romantic at relatable na mga kanta.",
        "IV of Spades": "IV of Spades ay isang Filipino rock band na naging kilala sa kanilang retro-funk sound at catchy na mga hit songs.",
        "SB19": "SB19 ay ang unang Filipino boy group na naging international sensation at naging pride ng Pilipinas sa K-pop industry.",
        "BINI": "BINI ay isang rising Filipino girl group na naging viral sa TikTok at kilala sa kanilang energetic performances.",
        "Eraserheads": "Eraserheads ay ang 'Beatles ng Pilipinas' at isa sa mga pinakaimpluwensyal na banda sa OPM history.",
        "Rivermaya": "Rivermaya ay isa sa mga pioneering rock bands sa Pilipinas na may malaking contribution sa 90s OPM scene."
    }
    
    return artist_info_db.get(artist_name, f"Si {artist_name} ay isa sa mga talented na OPM artist na patuloy na nagbibigay ng magagandang kanta para sa mga Filipino music lovers!")

def generate_artist_marketing_script(artist_name, track_name, artist_info):
    """Generate marketing script about the artist using web search results"""
    prompt = f"""
    Ikaw ay isang radio DJ na nag-market ng OPM artists. 
    
    Artist: {artist_name}
    Song: {track_name}
    Artist Info: {artist_info}
    
    Gumawa ng 2-3 pangungusap na marketing script sa Tagalog about the artist.
    Include interesting facts, recent achievements, or why listeners should follow them.
    Be enthusiastic and promotional!
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Si {artist_name} ay isa sa mga pinakasikat na OPM artist ngayon! Suportahan natin ang kanilang bagong kanta {track_name}!"

def create_custom_playlist(sp, playlist_name="AI Radio Playlist"):
    """Create a custom playlist for the radio station"""
    try:
        user_id = sp.current_user()['id']
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            description="AI-generated OPM playlist from AI Tagalog Radio"
        )
        return playlist['id']
    except Exception as e:
        st.error(f"Error creating playlist: {e}")
        return None

def add_track_to_playlist(sp, playlist_id, track_id):
    """Add a track to the custom playlist"""
    try:
        sp.playlist_add_items(playlist_id, [track_id])
        return True
    except Exception as e:
        st.error(f"Error adding track to playlist: {e}")
        return False

def upload_playlist_cover_image(sp, playlist_id, image_bytes):
    """Upload AI-generated image as playlist cover"""
    try:
        import base64
        from PIL import Image
        import io
        
        # Convert image bytes to PIL Image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Ensure it's JPEG and square format
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize to optimal square dimensions (640x640)
        img = img.resize((640, 640), Image.Resampling.LANCZOS)
        
        # Convert back to bytes with optimal compression
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
        
        # Check size limit (256 KB)
        if img_byte_arr.tell() > 256000:
            # Try with lower quality if too large
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=70, optimize=True)
        
        if img_byte_arr.tell() > 256000:
            st.warning("Generated image too large for playlist cover (>256KB)")
            return False
        
        # Encode to base64
        img_byte_arr.seek(0)
        image_64_encode = base64.b64encode(img_byte_arr.getvalue())
        
        # Upload to Spotify
        sp.playlist_upload_cover_image(playlist_id, image_64_encode)
        return True
        
    except Exception as e:
        st.error(f"Error uploading playlist cover: {e}")
        return False

def generate_playlist_cover_art(mood, playlist_name):
    """Generate cover art specifically for the playlist"""
    prompt = f"""
    Create a vibrant playlist cover for "{playlist_name}". 
    Style: {mood}, Filipino-inspired, modern design, music themed.
    Include musical elements like notes, instruments, or sound waves.
    Colors: Bright and appealing, suitable for a music playlist cover.
    Format: Square album cover style, professional quality.
    """
    
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
        st.error(f"Playlist cover generation error: {e}")
        return None

def get_multiple_omp_tracks(sp, mood_description, count=5):
    """Get multiple diverse OPM tracks for continuous radio play"""
    tracks = []
    track_ids_seen = set()  # Track IDs to avoid duplicates
    
    # Diverse search strategies for variety including indie/small artist discovery
    search_strategies = [
        # Strategy 1: Use original mood
        lambda: search_spotify_by_mood(sp, mood_description),
        
        # Strategy 2: Search by popular OPM artists
        lambda: search_by_random_opm_artist(sp),
        
        # Strategy 3: Discover indie/underground artists (30% chance)
        lambda: discover_indie_opm_artists(sp),
        lambda: discover_emerging_opm_artists(sp),
        lambda: search_by_independent_labels(sp),
        lambda: search_regional_opm_scenes(sp),
        
        # Strategy 4: Search different moods
        lambda: search_spotify_by_mood(sp, "masayang pop song"),
        lambda: search_spotify_by_mood(sp, "romantic ballad"),
        lambda: search_spotify_by_mood(sp, "energetic rock"),
        lambda: search_spotify_by_mood(sp, "chill acoustic"),
        lambda: search_spotify_by_mood(sp, "dance party song"),
        
        # Strategy 5: Search by genre
        lambda: search_opm_by_genre(sp, "OPM rock"),
        lambda: search_opm_by_genre(sp, "Filipino pop"),
        lambda: search_opm_by_genre(sp, "Pinoy alternative"),
    ]
    
    # Try each strategy until we get enough unique tracks
    for strategy in search_strategies:
        if len(tracks) >= count:
            break
            
        try:
            track = strategy()
            if track and track['id'] not in track_ids_seen:
                tracks.append(track)
                track_ids_seen.add(track['id'])
        except:
            continue
    
    return tracks

def search_by_random_opm_artist(sp):
    """Search for tracks by randomly selecting from popular OPM artists"""
    import random
    
    opm_artists = [
        'Ben&Ben', 'Moira Dela Torre', 'December Avenue', 'The Juans',
        'IV of Spades', 'Unique Salonga', 'SB19', 'BINI', 'Parokya ni Edgar',
        'Rivermaya', 'Eraserheads', 'Bamboo', 'Sponge Cola', 'Silent Sanctuary',
        'Kamikazee', 'Callalily', 'Moonstar88', 'Itchyworms', 'Orange and Lemons',
        'Hale', 'Urbandub', 'Typecast', 'Chicosci', 'Sandwich', 'Teeth',
        'Yeng Constantino', 'Sarah Geronimo', 'Regine Velasquez', 'Gary Valenciano'
    ]
    
    artist = random.choice(opm_artists)
    try:
        results = sp.search(q=f'artist:"{artist}"', type='track', limit=20, market='PH')
        if results['tracks']['items']:
            return random.choice(results['tracks']['items'])
    except:
        pass
    return None

def search_opm_by_genre(sp, genre_query):
    """Search OPM by specific genre"""
    try:
        results = sp.search(q=genre_query, type='track', limit=50, market='PH')
        if results['tracks']['items']:
            import random
            return random.choice(results['tracks']['items'])
    except:
        pass
    return None

def discover_indie_opm_artists(sp):
    """Discover small/indie OPM artists with low visibility"""
    try:
        import random
        
        # Search strategies for indie/underground OPM
        indie_search_terms = [
            '"filipino indie" market:PH',
            '"pinoy underground" market:PH', 
            '"manila music scene" market:PH',
            '"quezon city bands" market:PH',
            '"OPM indie" market:PH',
            '"pinoy DIY" market:PH',
            '"filipino alternative" market:PH',
            '"independent filipino" market:PH'
        ]
        
        indie_tracks = []
        
        for search_term in indie_search_terms:
            try:
                results = sp.search(q=search_term, type='track', limit=50, market='PH')
                if results['tracks']['items']:
                    # Filter for low-popularity tracks (under 30 popularity score)
                    low_popularity_tracks = [
                        track for track in results['tracks']['items']
                        if track['popularity'] < 30
                    ]
                    indie_tracks.extend(low_popularity_tracks)
            except:
                continue
        
        # Remove duplicates and return random track
        if indie_tracks:
            unique_tracks = {track['id']: track for track in indie_tracks}
            return random.choice(list(unique_tracks.values()))
            
        return None
        
    except Exception as e:
        return None

def search_by_independent_labels(sp):
    """Search for artists from independent Filipino labels"""
    try:
        import random
        
        # Key independent Filipino labels
        indie_labels = [
            'O/C Records',
            'PolyEast Records', 
            'Music Colony Records',
            'Downtown Q',
            'LIAB Studios',
            'Tarsier Records',
            'Offshore Music',
            'Careless Music Manila'
        ]
        
        for label in indie_labels:
            try:
                # Search for tracks associated with these labels
                results = sp.search(q=f'label:"{label}" market:PH', type='track', limit=20, market='PH')
                if not results['tracks']['items']:
                    # Try alternative search if label search doesn't work
                    results = sp.search(q=f'"{label}" filipino music', type='track', limit=20, market='PH')
                
                if results['tracks']['items']:
                    # Prefer tracks with lower popularity
                    tracks = sorted(results['tracks']['items'], key=lambda x: x['popularity'])
                    return tracks[0] if tracks else None
                    
            except:
                continue
                
        return None
        
    except Exception as e:
        return None

def discover_emerging_opm_artists(sp):
    """Find emerging OPM artists with recent releases and low popularity"""
    try:
        import random
        from datetime import datetime, timedelta
        
        # Search for recent releases in Philippines
        current_year = datetime.now().year
        last_year = current_year - 1
        
        emerging_search_terms = [
            f'"OPM" year:{current_year} market:PH',
            f'"filipino music" year:{current_year} market:PH',
            f'"pinoy artist" year:{last_year}-{current_year} market:PH',
            f'genre:"philippines-opm" year:{last_year}-{current_year}'
        ]
        
        emerging_tracks = []
        
        for search_term in emerging_search_terms:
            try:
                results = sp.search(q=search_term, type='track', limit=50, market='PH')
                if results['tracks']['items']:
                    # Filter for very low popularity (emerging artists)
                    very_new_tracks = [
                        track for track in results['tracks']['items']
                        if track['popularity'] < 25  # Very low popularity threshold
                    ]
                    emerging_tracks.extend(very_new_tracks)
            except:
                continue
        
        if emerging_tracks:
            # Remove duplicates and prioritize newest releases
            unique_tracks = {track['id']: track for track in emerging_tracks}
            tracks_list = list(unique_tracks.values())
            
            # Sort by release date (newest first) and popularity (lowest first)
            sorted_tracks = sorted(tracks_list, 
                                 key=lambda x: (x['album']['release_date'], x['popularity']), 
                                 reverse=True)
            
            return random.choice(sorted_tracks[:10])  # Pick from top 10 newest/lowest popularity
            
        return None
        
    except Exception as e:
        return None

def search_regional_opm_scenes(sp):
    """Discover artists from specific Filipino regional music scenes"""
    try:
        import random
        
        # Regional music scenes and venues
        regional_terms = [
            '"route 196" manila',  # Famous indie venue
            '"mows bar" quezon city',
            '"saguijo" makati',
            '"b-side" the collective',
            '"cebu music scene"',
            '"davao indie"',
            '"baguio musicians"',
            '"iloilo bands"',
            '"bacolod music"'
        ]
        
        for term in regional_terms:
            try:
                results = sp.search(q=f'{term} filipino', type='track', limit=30, market='PH')
                if results['tracks']['items']:
                    # Filter for lower popularity regional artists
                    regional_tracks = [
                        track for track in results['tracks']['items']
                        if track['popularity'] < 35
                    ]
                    if regional_tracks:
                        return random.choice(regional_tracks)
            except:
                continue
                
        return None
        
    except Exception as e:
        return None

def main():
    st.title("📻 AI Tagalog Radio")
    st.markdown("*Ang pinakamasayang radio station na may AI DJ!*")
    
    # Initialize session state
    if 'spotify_token' not in st.session_state:
        st.session_state.spotify_token = None
    
    # Spotify Authentication  
    scope = "user-read-playback-state user-library-modify playlist-modify-public playlist-modify-private ugc-image-upload"
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
        st.markdown("*The AI DJ will create a custom playlist, generate scripts, and play continuous OPM radio!*")
        
        # Initialize session state for radio
        if 'radio_active' not in st.session_state:
            st.session_state.radio_active = False
        if 'playlist_id' not in st.session_state:
            st.session_state.playlist_id = None
        if 'current_track_index' not in st.session_state:
            st.session_state.current_track_index = 0
        if 'radio_tracks' not in st.session_state:
            st.session_state.radio_tracks = []
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Start/Stop Radio Controls
            radio_col1, radio_col2 = st.columns(2)
            
            with radio_col1:
                if not st.session_state.radio_active:
                    if st.button("🎵 Start AI Radio Station", type="primary", use_container_width=True):
                        with st.spinner("🤖 Starting AI Radio Station..."):
                            try:
                                # Step 1: Create custom playlist
                                st.markdown("**Step 1:** Creating your custom playlist...")
                                playlist_name = f"AI Radio - {time.strftime('%Y-%m-%d %H:%M')}"
                                playlist_id = create_custom_playlist(sp, playlist_name)
                                st.session_state.playlist_id = playlist_id
                                
                                # Step 2: Generate initial DJ script to determine mood
                                st.markdown("**Step 2:** DJ is preparing the show...")
                                dj_script = generate_dj_script()
                                mood = extract_mood_from_script(dj_script)
                                
                                # Step 3: Generate playlist cover art
                                st.markdown("**Step 3:** Creating custom playlist cover art...")
                                playlist_cover = generate_playlist_cover_art(mood, playlist_name)
                                
                                # Step 4: Get multiple tracks for continuous play
                                st.markdown("**Step 4:** Selecting OPM tracks for the show...")
                                tracks = get_multiple_omp_tracks(sp, mood, count=5)
                                
                                if not tracks:
                                    st.error("Could not find suitable tracks. Please try again.")
                                    return
                                
                                # Step 5: Add tracks to playlist
                                st.markdown("**Step 5:** Building your playlist...")
                                for track in tracks:
                                    if playlist_id:
                                        add_track_to_playlist(sp, playlist_id, track['id'])
                                
                                # Step 6: Upload custom cover art
                                if playlist_cover and playlist_id:
                                    st.markdown("**Step 6:** Setting custom playlist cover...")
                                    cover_uploaded = upload_playlist_cover_image(sp, playlist_id, playlist_cover)
                                    if cover_uploaded:
                                        st.success("✅ Custom playlist cover uploaded!")
                                    else:
                                        st.warning("⚠️ Playlist created but cover upload failed")
                                
                                st.session_state.radio_tracks = tracks
                                st.session_state.radio_active = True
                                st.session_state.current_track_index = 0
                                st.session_state.playlist_cover = playlist_cover  # Store for display
                                
                                st.success("🎉 AI Radio Station is now live!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Error starting radio: {e}")
            
            with radio_col2:
                if st.session_state.radio_active:
                    if st.button("⏹️ Stop Radio", type="secondary", use_container_width=True):
                        st.session_state.radio_active = False
                        st.session_state.current_track_index = 0
                        st.success("Radio stopped!")
                        st.rerun()
            
            # Radio Player Interface
            if st.session_state.radio_active and st.session_state.radio_tracks:
                current_track = st.session_state.radio_tracks[st.session_state.current_track_index]
                
                st.markdown("---")
                st.markdown("## 📻 Now Playing - AI Radio")
                
                # Generate content for current track
                with st.spinner("🎙️ AI DJ is introducing the next song..."):
                    try:
                        # Generate DJ script for this specific track
                        artist_name = current_track['artists'][0]['name']
                        track_name = current_track['name']
                        
                        # Search for artist info using Tavily
                        artist_info = search_artist_info(artist_name)
                        
                        # Generate artist marketing script
                        marketing_script = generate_artist_marketing_script(artist_name, track_name, artist_info)
                        
                        # Check if this is a small/indie artist (low popularity)
                        is_indie_artist = current_track['popularity'] < 30
                        indie_promo = ""
                        if is_indie_artist:
                            indie_promo = "Ito ay isang hidden gem mula sa isang talented indie artist na deserve ng mas maraming suporta! "
                        
                        # Generate TTS for marketing + intro
                        full_intro = f"""Kamusta mga ka-tropa! Narito ang susunod nating kanta. 
                        {indie_promo}{marketing_script} 
                        Pakinggan natin ang {track_name} ni {artist_name}!"""
                        
                        tts_audio = generate_tts(full_intro)
                        
                        # Generate album art
                        album_art = generate_album_art("vibrant OPM", track_name)
                        
                        # Display content
                        track_col1, track_col2 = st.columns([1, 1])
                        
                        with track_col1:
                            if album_art:
                                st.image(album_art, caption="AI Generated Album Art", width=300)
                        
                        with track_col2:
                            st.markdown(f"### 🎵 {track_name}")
                            st.markdown(f"**Artist:** {artist_name}")
                            
                            # Show indie artist badge
                            if is_indie_artist:
                                st.markdown("🌟 **Indie/Emerging Artist** - *Support small OPM artists!*")
                                st.markdown(f"**Popularity Score:** {current_track['popularity']}/100")
                            
                            st.markdown(f"**Track {st.session_state.current_track_index + 1}** of {len(st.session_state.radio_tracks)}")
                            
                            # DJ Voice
                            if tts_audio:
                                st.markdown("### 🎙️ DJ Introduction")
                                st.audio(tts_audio, format="audio/mp3")
                        
                        # Marketing info
                        st.markdown("### 📰 Artist Spotlight")
                        st.info(marketing_script)
                        
                        # Spotify embed
                        st.markdown("### 🎧 Now Playing")
                        embed_html = f"""
                        <iframe src="https://open.spotify.com/embed/track/{current_track['id']}" 
                                width="100%" height="152" frameborder="0" 
                                allowtransparency="true" allow="encrypted-media">
                        </iframe>
                        """
                        st.components.v1.html(embed_html, height=152)
                        
                        # Navigation controls
                        nav_col1, nav_col2, nav_col3 = st.columns(3)
                        
                        with nav_col1:
                            if st.button("⏮️ Previous Track") and st.session_state.current_track_index > 0:
                                st.session_state.current_track_index -= 1
                                st.rerun()
                        
                        with nav_col2:
                            if st.button("🔄 Refresh Show"):
                                st.rerun()
                        
                        with nav_col3:
                            if st.button("⏭️ Next Track") and st.session_state.current_track_index < len(st.session_state.radio_tracks) - 1:
                                st.session_state.current_track_index += 1
                                st.rerun()
                        
                        # Store current track for sidebar actions
                        st.session_state.current_track_id = current_track['id']
                        
                    except Exception as e:
                        st.error(f"Error playing track: {e}")
        
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
            
            # Show playlist info
            if st.session_state.radio_active and st.session_state.playlist_id:
                st.markdown("### 📝 Your Playlist")
                
                # Show playlist cover if available
                if hasattr(st.session_state, 'playlist_cover') and st.session_state.playlist_cover:
                    st.image(st.session_state.playlist_cover, caption="Custom Playlist Cover", width=200)
                
                playlist_url = f"https://open.spotify.com/playlist/{st.session_state.playlist_id}"
                st.markdown(f"[View AI Radio Playlist on Spotify]({playlist_url})")
                
                if st.button("📋 Copy Playlist Link"):
                    st.code(playlist_url)
            
            # Radio stats
            if st.session_state.radio_active and st.session_state.radio_tracks:
                st.markdown("### 📊 Radio Stats")
                st.metric("Total Tracks", len(st.session_state.radio_tracks))
                st.metric("Current Track", f"{st.session_state.current_track_index + 1}")
                
                progress = (st.session_state.current_track_index + 1) / len(st.session_state.radio_tracks)
                st.progress(progress)
            
            # Reset radio
            if st.session_state.radio_active:
                if st.button("🔄 Reset Radio Station"):
                    st.session_state.radio_active = False
                    st.session_state.radio_tracks = []
                    st.session_state.current_track_index = 0
                    st.session_state.playlist_id = None
                    st.success("Radio reset! Start a new station.")
                    st.rerun()

if __name__ == "__main__":
    main()
