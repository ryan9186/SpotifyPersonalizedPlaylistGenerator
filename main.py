import requests
import urllib.parse
from datetime import datetime
from flask import Flask, redirect, request, jsonify, session

# Initialize the Flask app
app = Flask(__name__)
app.secret_key = load_.dotenv()

CLIENT_ID = '' 
CLIENT_SECRET = ''
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

def token_validity():
    if 'access_token' not in session:
        return redirect('/login'), False
  
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh_token'), False
    
    return None, True

@app.route('/')
def index():
    return "Welcome to my Spotify app. Click to have a custom playlist made. <a href='/login'>Login with Spotify</a>"

@app.route('/login')
def login():
    scope = 'user-read-private user-read-email user-library-read user-top-read playlist-modify-public'
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    if 'code' in request.args:
        req_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        response = requests.post(TOKEN_URL, data=req_body)
        token_info = response.json()
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']
        return redirect('/create-playlist')

@app.route('/top-artists-tracks')
def get_top_artists_tracks():
    redirect_response, valid = token_validity()
    if not valid:
        return redirect_response
  
    headers = {'Authorization': f"Bearer {session['access_token']}"}

    top_artists = requests.get(API_BASE_URL + 'me/top/artists', headers=headers, params={'time_range': 'medium_term', 'limit': 10})
    if top_artists.status_code != 200:
        return jsonify({'error': 'Failed to fetch top artists'}), top_artists.status_code
    top_artists = top_artists.json()
    
    top_tracks = []
    popularity_threshold = 75
    for artist in top_artists['items']:
        artist_id = artist['id']
        tracks_response = requests.get(API_BASE_URL + f'artists/{artist_id}/top-tracks', headers=headers, params={'country': 'US'})
        tracks = tracks_response.json().get('tracks', [])
        popular_tracks = [track['uri'] for track in tracks if track['popularity'] > popularity_threshold]
        top_tracks.extend(popular_tracks)
    return top_tracks

@app.route('/create-playlist')
def create_personalized_playlist():
    redirect_response, valid = token_validity()
    if not valid:
        return redirect_response
    
    headers = {'Authorization': f"Bearer {session['access_token']}"}

    top_track_uris = get_top_artists_tracks()
    user_info = requests.get(API_BASE_URL + 'me', headers=headers)
    user_id = user_info.json()['id']
    playlist_data = {
        'name': 'Your Personalized Playlist',
        'description': 'Playlist created based on your top artists',
        'public': True
    }
    create_playlist_response = requests.post(API_BASE_URL + f'users/{user_id}/playlists', headers=headers, json=playlist_data)
    playlist_id = create_playlist_response.json()['id']

    add_tracks_data = {'uris': top_track_uris}
    add_tracks_response = requests.post(API_BASE_URL + f'playlists/{playlist_id}/tracks', headers=headers, json=add_tracks_data)
    if add_tracks_response.status_code not in [200, 201]:
        return jsonify({'error': 'Failed to add tracks to playlist'}), add_tracks_response.status_code
    requests.post(API_BASE_URL + f'playlists/{playlist_id}/tracks', headers=headers, json=add_tracks_data)

    return jsonify({'message': 'Playlist Created Successfully', 'playlist_id': playlist_id})
  
@app.route('/refresh_token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect('/login')

    req_body = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token'],
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=req_body)
    new_token_info = response.json()
    session['access_token'] = new_token_info['access_token']
    session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
