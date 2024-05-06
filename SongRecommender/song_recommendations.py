import pandas as pd
from tqdm import tqdm
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import random
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

from SongRecommender.featurizer import create_feature_set



class SongWizard:
    _default_top_playlist_ids = ["37i9dQZF1DXcBWIGoYBM5M", "37i9dQZEVXbMDoHDwVN2tF", "37i9dQZF1DX0XUsuxWHRQd",
                            "37i9dQZF1DX10zKzsJ2jva", "37i9dQZF1DWXRqgorJj26U", "37i9dQZF1DWY7IeIP1cdjF",
                            "37i9dQZF1DX4o1oenSJRJd", "37i9dQZF1DWWMOmoXKqHTD", "37i9dQZF1DX4UtSsGT1Sbe", 
                            "37i9dQZF1DX76Wlfdnj7AP", "37i9dQZF1DX4WYpdgoIcn6", "37i9dQZF1DX186v583rmzp", 
                            "37i9dQZF1DXbTxeAdrVG2l", "37i9dQZF1DX08mhnhv6g9b", "37i9dQZF1DX3rxVfibe1L0",
                            "37i9dQZF1DX1lVhptIYRda", "37i9dQZF1DXdSjVZQzv2tl", "37i9dQZF1DX4sWSpwq3LiO",
                            "0vvXsWCC9xrXsKd4FyS8kM", "37i9dQZF1DXdxcBWuJkbcy", "37i9dQZF1DX6aTaZa0K6VA",
                            "37i9dQZF1DWY4xHQp97fN6", "37i9dQZF1DX4SBhb3fqCJd", "37i9dQZF1DXdPec7aLTmlC",
                            "37i9dQZF1DX1rVvRgjX59F", "37i9dQZF1DXcF6B6QPhFDv", "37i9dQZF1DXbrUpGvoi3TS",
                            "37i9dQZF1DWWGFQLoP9qlv", "1nRNXjzFAF5uKK1586mfSZ", "00qcmuVkchZsWn3Sp4pFTJ"]
    
    _default_complete_feature_set_path = "SongRecommender/complete_feature_final.csv"

    def __init__(self, client_id, client_secret, _default_top_playlist_ids=None, _default_complete_feature_set_path=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.sp = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)

        self._default_top_playlist_ids = _default_top_playlist_ids or self._default_top_playlist_ids
        self._default_complete_feature_set_path = _default_complete_feature_set_path or self._default_complete_feature_set_path

        self.complete_feature_set = pd.read_csv(self._default_complete_feature_set_path)
        self.songs_to_rate = None


    def replace_spaces_in_genres(self, genres_list):
        return [genre.replace(" ", "_") for genre in genres_list]
    
    def get_random_song_from_each_playlist(self):
        selected_tracks = []
        featureLIST = []
        for playlist_id in self._default_top_playlist_ids:
            results = self.sp.playlist_tracks(playlist_id)
            tracks = results['items']
            
            while results['next']:
                results = self.sp.next(results)
                tracks.extend(results['items'])
            
            if tracks:
                chosen_track = random.choice(tracks)
                if chosen_track['track']:
                    track_name = chosen_track['track']['name']
                    track_uri = chosen_track['track']['id']
                    
                    selected_tracks.append({'name': track_name, 'spotify_id': track_uri})
        self.songs_to_rate = selected_tracks
        return selected_tracks
    
    def get_recommendations(self, songs_to_rate, top_n):
        
        songs_to_rate_features = []
        if songs_to_rate == []:
            my_db = pd.read_csv(self._default_complete_feature_set_path)
            random_ids = my_db['id'].sample(n=20, random_state=42).tolist()
            recs_details = []
            for spotify_id in set(random_ids):  # Using a set to avoid duplicate IDs
                recs_details.append({'name': self.sp.track(spotify_id)['name'], 'spotify_id': spotify_id})
            return recs_details


        for song in songs_to_rate:
            track_uri = song
            audio_features = self.sp.audio_features(track_uri)[0]
            # features = sp.audio_features(track_uri)[0]

            # Fetch track details
            track_details = self.sp.track(track_uri)
            artist_id = track_details["artists"][0]["id"]
            track_name = track_details["name"]
            track_pop = track_details["popularity"]

            # Fetch artist details
            artist_details = self.sp.artist(artist_id)
            artist_name = artist_details["name"]
            artist_pop = artist_details["popularity"]
            artist_genres = artist_details["genres"]

            # Compile the desired information
            track_info = {
                "artist_name": artist_name,
                "id": track_uri,
                "track_name": track_name,
                "artist_pop": artist_pop,
                "genres": artist_genres,
                "track_pop": track_pop,
                "danceability": audio_features["danceability"],
                "energy": audio_features["energy"],
                "key": audio_features["key"],
                "loudness": audio_features["loudness"],
                "mode": audio_features["mode"],
                "speechiness": audio_features["speechiness"],
                "acousticness": audio_features["acousticness"],
                "instrumentalness": audio_features["instrumentalness"],
                "liveness": audio_features["liveness"],
                "valence": audio_features["valence"],
                "tempo": audio_features["tempo"],
                "time_signature": audio_features["time_signature"],
                "genres_list": artist_genres
            }
            songs_to_rate_features.append(track_info)
            

        songs_to_rate_featuresDF = pd.DataFrame(songs_to_rate_features)
        songs_to_rate_featuresDF['genres_list'] = songs_to_rate_featuresDF['genres_list'].apply(self.replace_spaces_in_genres)
        float_cols = songs_to_rate_featuresDF.dtypes[songs_to_rate_featuresDF.dtypes == 'float64'].index.values
        
        my_pl = create_feature_set(songs_to_rate_featuresDF, float_cols=float_cols)

        my_db = pd.read_csv(self._default_complete_feature_set_path)

        common_features = list(set(my_pl.columns).intersection(set(my_db.columns)))
        if 'id' in common_features:
            common_features.remove('id')


        # Ensure both DataFrames contain only the common features
        my_pl_common = my_pl[common_features]
        my_db_common = my_db[common_features]

        # print(my_db_common.shape)
        # print(my_pl_common.shape)

        # Compute the cosine similarity matrix
        similarity_matrix = cosine_similarity(my_db_common, my_pl_common)

        # Convert to DataFrame for easier handling
        similarity_df = pd.DataFrame(similarity_matrix, index=my_db['id'], columns=my_pl['id'])


        # recommendations = {}
        recs = []
        for song_id in my_pl['id']:
            top_indices = similarity_df[song_id].nlargest(top_n).index.tolist()
            # recommendations[song_id] = top_indices
            recs += top_indices
        
        recs_details = []
        for spotify_id in set(recs):  # Using a set to avoid duplicate IDs
            recs_details.append({'name': self.sp.track(spotify_id)['name'], 'spotify_id': spotify_id})

        return recs_details #recommendations, 




# client_id = "d2ade2cffe624536bc3b49ab57135a94"
# client_secret = "1625fc9e86a648939c6620d78f9b7e0b"

# sw = SongWizard(client_id, client_secret)
# songs_to_rate = sw.get_random_song_from_each_playlist()
# recommendations, recommendations_inFormat = sw.get_recommendations(songs_to_rate, 2)

# for i in recommendations_inFormat:
#     print(i['name'], i['spotify_id'])


# exit()
