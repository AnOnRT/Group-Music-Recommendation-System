import sklearn
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

def make_recommendations(my_pl, my_db,  top_n=3):
    """
    Generate song recommendations from my_db for each song in my_pl.

    Args:
    my_pl (DataFrame): DataFrame containing features of songs in the playlist.
    my_db (DataFrame): DataFrame containing features of songs in the database.
    top_n (int): Number of top recommendations to return for each song.

    Returns:
    dict: A dictionary where keys are song IDs from my_pl and values are lists of recommended song IDs from my_db.
    """

    common_features = list(set(my_pl.columns).intersection(set(my_db.columns)))
    if 'id' in common_features:
        common_features.remove('id')


    # Ensure both DataFrames contain only the common features
    my_pl_common = my_pl[common_features]
    my_db_common = my_db[common_features]

    print(my_db_common.shape)
    print(my_pl_common.shape)

    # Compute the cosine similarity matrix
    similarity_matrix = cosine_similarity(my_db_common, my_pl_common)

    # Convert to DataFrame for easier handling
    similarity_df = pd.DataFrame(similarity_matrix, index=my_db['id'], columns=my_pl['id'])


    recommendations = {}
    recs = []
    for song_id in my_pl['id']:
        top_indices = similarity_df[song_id].nlargest(top_n).index.tolist()
        recommendations[song_id] = top_indices
        recs += top_indices

    return recommendations, recs

# recommendations, rec_list = make_recommendations(my_pl, my_db, top_n=5)

# # Print recommendations for each song
# for song_id, recs in recommendations.items():
#     print(f"Recommendations for song ID {song_id}: {recs}")


# def create_feature_set(df, float_cols):
#     '''
#     Process spotify df to create a final set of features that will be used to generate recommendations
#     ---
#     Input: 
#     df (pandas dataframe): Spotify Dataframe
#     float_cols (list(str)): List of float columns that will be scaled
            
#     Output: 
#     final (pandas dataframe): Final set of features 
#     '''
    
#     # Tfidf genre lists
#     tfidf = TfidfVectorizer()
#     tfidf_matrix =  tfidf.fit_transform(df['genres_list'].apply(lambda x: " ".join(x)))
#     genre_df = pd.DataFrame(tfidf_matrix.toarray())
#     genre_df.columns = ['genre' + "_" + i for i in tfidf.get_feature_names_out()]
#     genre_df.drop(columns='genre_unknown', errors='ignore') # drop unknown genre
#     genre_df.reset_index(drop = True, inplace=True)
    
#     # Sentiment analysis
#     df = sentiment_analysis(df, "track_name")

#     # One-hot Encoding
#     subject_ohe = ohe_prep(df, 'subjectivity','subject') * 0.3
#     polar_ohe = ohe_prep(df, 'polarity','polar') * 0.5
#     key_ohe = ohe_prep(df, 'key','key') * 0.5
#     mode_ohe = ohe_prep(df, 'mode','mode') * 0.5

#     # Normalization
#     # Scale popularity columns
#     pop = df[["artist_pop","track_pop"]].reset_index(drop = True)
#     scaler = MinMaxScaler()
#     pop_scaled = pd.DataFrame(scaler.fit_transform(pop), columns = pop.columns) 

#     # Scale audio columns
#     floats = df[float_cols].reset_index(drop = True)
#     scaler = MinMaxScaler()
#     floats_scaled = pd.DataFrame(scaler.fit_transform(floats), columns = floats.columns)
    
#     # Scale 'time_signature'
#     ts = df[['time_signature']].reset_index(drop = True)
#     scaler = MinMaxScaler()
#     ts_scaled = pd.DataFrame(scaler.fit_transform(ts), columns = ts.columns)

#     # Concanenate all features
#     final = pd.concat([genre_df, floats_scaled, ts_scaled, pop_scaled, subject_ohe, polar_ohe, key_ohe, mode_ohe], axis = 1)
    
#     # Add song id
#     final['id']=df['id'].values
    
#     return final
