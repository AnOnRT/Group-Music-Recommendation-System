from flask import Flask, copy_current_request_context, jsonify, render_template, request, redirect, session, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
from flask_socketio import emit
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

import random
from string import ascii_letters, ascii_lowercase, ascii_uppercase


from SongRecommender.featurizer import *
from SongRecommender.song_recommendations import *

from datetime import datetime, timedelta

import os

script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'db', 'chat.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)



app.config["SECRET_KEY"] = "hermes"
socketio = SocketIO(app)

client_id = "***"
client_secret = "***"


number_of_final_songs = 3
number_of_1st_round_songs = 5
first_round_duration = 300 #Seconds
second_round_duration = 300 #Seconds
votes_count_1st_round = 55 ##55
votes_count_2nd_round = 33 ##33


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    messages = db.relationship('Message', backref='user', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

room_songs = db.Table('room_songs',
    db.Column('room_id', db.Integer, db.ForeignKey('room.id'), primary_key=True),
    db.Column('song_id', db.Integer, db.ForeignKey('song.id'), primary_key=True)
)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    max_members = db.Column(db.Integer, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.relationship('Message', backref='room', lazy=True)
    songs = db.relationship('Song', secondary=room_songs, lazy='subquery', backref=db.backref('rooms', lazy=True))
    group_full_message_sent = db.Column(db.Boolean, default=False)
    pinned_message = db.Column(db.String(1000))
    timer_start = db.Column(db.DateTime, nullable=True)
    timer_start2 = db.Column(db.DateTime, nullable=True)
    # recommendations_generated_at = db.Column(db.DateTime, nullable=True)


class Membership(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), primary_key=True)
    joined_message_sent = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    spotify_id = db.Column(db.String(200), nullable=False, unique=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    # Store Spotify song IDs as strings without a foreign key constraint
    spotify_song_id = db.Column(db.String(200), nullable=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    song_id = db.Column(db.String(200), nullable=False)  # Spotify song ID
    vote_value = db.Column(db.Integer, nullable=False)
    round_number = db.Column(db.Integer, default = 1)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)


    

@app.route("/", methods=["GET", "POST"])
def start():
    # Check if the user is logged in
    if 'user_id' not in session:
        # User is not logged in, redirect to login page
        return redirect(url_for('login'))
    else:
        # User is logged in, render the home page
        return redirect(url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login(code=None):
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email, username=username).first()
        if user and user.check_password(password):
            # User login logic here, like storing user ID in session
            session['user_id'] = user.id
            code = request.args.get('code', None)
            if(code):
                return redirect(url_for("rate_songs", code=code))
            return redirect(url_for('home'))
        else:
            return 'Invalid email or password.'
        
    code = request.args.get('code', None)
    return render_template('login.html', code=code)


@app.route('/signup', methods=['GET', 'POST'])
def signup(code=None):
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user:
            return 'Email already registered.'

        user = User.query.filter_by(username=username).first()
        if user:
            return 'Username already taken.'
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        code = request.args.get('code', None)
        return redirect(url_for('login', code = code))

    code = request.args.get('code', None)
    return render_template('signup.html', code=code)


def generate_unique_code(length):
    while True:
        code = "".join(random.choices(ascii_uppercase, k=length))
        existing_room = Room.query.filter_by(code=code).first()
        if existing_room is None:
            return code

def add_song_if_not_exists(name, spotify_id):
    existing_song = Song.query.filter_by(spotify_id=spotify_id).first()
    if not existing_song:
        new_song = Song(name=name, spotify_id=spotify_id)
        db.session.add(new_song)
        db.session.commit()
        return new_song
    return existing_song

def assign_songs_to_room(room, song_ids):
    set_song_ids = set(song_ids)
    for song_id in set_song_ids:
        song = Song.query.get(song_id)
        if song:
            room.songs.append(song)
    db.session.commit()

@app.route('/home', methods=["POST", "GET"])
def home():
    # session.clear()
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))
    
    if request.method == "POST":
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
        max_members = request.form.get("max_members", type=int)
        
        if join and not code:
            return "Please enter a room code."

        if create != False:
            if max_members == None:
                return "Please enter a maximum number of members."
            

            room_code = generate_unique_code(6)
            new_room = Room(code=room_code, max_members=max_members+1, admin_id=session['user_id'])
            db.session.add(new_room)
            db.session.commit()

            new_membership = Membership(user_id=user_id, room_id=new_room.id)
            db.session.add(new_membership)
            db.session.commit()

            song_ids = []  # Replace with actual logic to select song IDs
            song_wizard = SongWizard(client_id, client_secret)
            songs_to_rate = song_wizard.get_random_song_from_each_playlist()

            for song_info in songs_to_rate:  # Assume get_songs() fetches song data
                song = add_song_if_not_exists(song_info['name'], song_info['spotify_id'])
                song_ids.append(song.id)
            assign_songs_to_room(new_room, song_ids)

            session["room_code"] = room_code

            return redirect(url_for("rate_songs", code=room_code))
        
        if join != False and code:
            room = Room.query.filter_by(code=code).first()
            if room is None:
                return "Room does not exist."
            
            member_count = Membership.query.filter_by(room_id=room.id).count()
            existing_membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
            if not existing_membership:
                if member_count >= room.max_members:
                    return "The room is full"
                
                # session["room_code"] = code
                return redirect(url_for("rate_songs", code=code))
            else:
                session["room_code"] = code
                # return redirect(url_for("rate_songs", code=code))
                return redirect(url_for("room", code=code))
        
    # Query the memberships for the current user
    memberships = Membership.query.filter_by(user_id=user_id).all()

    # Get the rooms for each membership
    groups = []
    for membership in memberships:
        room = Room.query.get(membership.room_id)
        if room:
            groups.append({'code': room.code, 'id': room.id})

    return render_template("home.html", user=user, groups=groups)

@app.route("/rate_songs/<code>")
def rate_songs(code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))
    
    room = Room.query.filter_by(code=code).first()
    if not room:
        return redirect(url_for('home'))
    
    
    member_count = Membership.query.filter_by(room_id=room.id).count()
    existing_membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not existing_membership:
        if member_count >= room.max_members:
            return "The room is full"
    
    
    songs = room.songs
    existing_ratings = Rating.query.filter_by(user_id=user_id, room_id=room.id).all()
    if existing_ratings or user_id == room.admin_id:
        session["room_code"] = code
        # User has already rated songs for this room, redirect to chat
        return redirect(url_for('room', code=code))  # Replace 'chat' with your chat route

    return render_template("rate_songs.html", songs=songs, code=code)

@app.route("/submit_ratings/<code>", methods=["POST"])
def submit_ratings(code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))
    
    room = Room.query.filter_by(code=code).first()
    if not room:
        return redirect(url_for('home'))
    
    existing_ratings = Rating.query.filter_by(user_id=user_id, room_id=room.id).all()
    if existing_ratings or user_id == room.admin_id:
        session["room_code"] = code
        # User has already rated songs for this room, redirect to chat
        return redirect(url_for('room', code=code))  # Replace 'chat' with your chat route
    

    member_count = Membership.query.filter_by(room_id=room.id).count()
    existing_membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not existing_membership:
        if member_count >= room.max_members:
            return "The room is full"
        
        new_membership = Membership(user_id=user_id, room_id=room.id)
        db.session.add(new_membership)
        db.session.commit()
        
        session["room_code"] = code
    

    for song in room.songs:
        rating_value = request.form.get(song.spotify_id)
        if rating_value:
            rating = Rating(
                value=int(rating_value),
                user_id=user_id,
                song_id=song.id,
                room_id=room.id
            )
            db.session.add(rating)
        # #print(song.name, str(rating_value))
        db.session.commit()
        # return redirect(url_for('home'))  # Redirect to chat after submitting ratings

    # Redirect to the chat room after storing ratings
    return redirect(url_for('room', code=code))

@app.route('/room/<code>')
def room(code):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    room = Room.query.filter_by(code=code).first()
    
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))

    if not room:
        # Room not found, redirect to home or appropriate page
        return redirect(url_for('home'))

    # Check if user is a member of the room
    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not membership:
        # User is not a member of the room, handle accordingly
        return "Access Denied", 403
    
    # Fetch past messages
    past_messages = Message.query.filter_by(room_id=room.id).all()

    # Retrieve room members
    memberships = Membership.query.filter_by(room_id=room.id).all()
    members = [User.query.get(membership.user_id) for membership in memberships]

    # Retrieve songs and user's ratings
    songs = room.songs
    # user_ratings = Rating.query.filter_by(user_id=user_id, room_id=room.id).all()
    ratings_dict = {}

    if user_id != room.admin_id:
        user_ratings = Rating.query.filter_by(user_id=user_id, room_id=room.id).all()
        ratings_dict = {rating.song_id: rating.value for rating in user_ratings}        
    
    #Newly added
    
    top_songs_after_1st_round = []
    final_songs = []
    if all_members_have_voted(room.id):
        top_songs_after_1st_round = get_top_songs(room.id)
        if all_members_have_voted(room.id, round_number = 2):
            final_songs = get_top_songs(room.id, round_number = 2)


    remaining_time = None
    recs_details = Recommendation.query.filter_by(room_id=room.id).all()

    remaining_time2 = None
    top_songs_2 = []


    if recs_details:
        spotify_song_ids = [rec.spotify_song_id for rec in recs_details]
        voting_duration = timedelta(seconds=first_round_duration)
        time_passed = datetime.utcnow() - room.timer_start

        if time_passed < voting_duration:
            remaining_time = (voting_duration - time_passed).total_seconds()
            
        if remaining_time == None:
            remaining_time = -1
        
        
        #check if all voted for the 2nd round
        if all_members_have_voted(room.id, round_number = 1):
            print("all_members_have_voted")
            top_songs_2 = get_top_songs(room.id, round_number = 2)
            voting_duration = timedelta(seconds=second_round_duration)
            time_passed = datetime.utcnow() - room.timer_start2

            if time_passed < voting_duration:
                remaining_time2 = (voting_duration - time_passed).total_seconds()                

            if remaining_time2 == None:
                remaining_time2 = -1
        


        voted_1st_round = user_voted_1st_round(room.id, user_id)
        voted_2nd_round = user_voted_2nd_round(room.id, user_id)
        

        return render_template('room.html', room=room, user=user, past_messages=past_messages, members=members, songs=songs, ratings=ratings_dict, rec_song_ids = spotify_song_ids, remaining_time=remaining_time, top_songs_after_1st_round=top_songs_after_1st_round, top_songs_2=top_songs_2, remaining_time2=remaining_time2, voted_1st_round = voted_1st_round, voted_2nd_round = voted_2nd_round, final_songs = final_songs, votes_count_1st_round = votes_count_1st_round, votes_count_2nd_round = votes_count_2nd_round)
    else:
        return render_template('room.html', room=room, user=user, past_messages=past_messages, members=members, songs=songs, ratings=ratings_dict, rec_song_ids = [], remaining_time = 0, top_songs_after_1st_round=top_songs_after_1st_round, top_songs_2=top_songs_2, remaining_time2=0, voted_1st_round = False, voted_2nd_round = False, final_songs = [], votes_count_1st_round = votes_count_1st_round, votes_count_2nd_round = votes_count_2nd_round)


def generate_recommendations(room_id, song_ratings, top_k=10):
    # Calculate the average rating for each song
    song_averages = {spotify_id: sum(ratings) / len(ratings) for spotify_id, ratings in song_ratings.items() if ratings}
    
    # Sort songs by their average ratings in descending order and select top-k
    sorted_songs = sorted(song_averages.items(), key=lambda x: x[1], reverse=True)[:top_k]
    selected_songs = [spotify_id for spotify_id, _ in sorted_songs]
    
    # Initialize the SongWizard to get recommendations
    song_wizard = SongWizard(client_id, client_secret)
    recommendations = song_wizard.get_recommendations(selected_songs, 1)

    try:
        if(len(Recommendation.query.filter_by(room_id=room_id).all()) == 0):
            for song in recommendations:
                new_recommendation = Recommendation(room_id=room_id, spotify_song_id=song['spotify_id'])
                db.session.add(new_recommendation)
            db.session.commit()
        
    except Exception as e:
        db.session.rollback()

    db.session.commit()
    
    # Return the list of recommendations (or the IDs or any identifier)
    return recommendations

def generate_recommendations2(room_id, song_ratings):
    # Your algorithm to generate recommendations
    def calculate_overall_average(song_ratings):
        total_sum = 0
        total_count = 0
        for ratings in song_ratings.values():
            total_sum += sum(ratings)
            total_count += len(ratings)
        return total_sum / total_count if total_count else 0
    
    def filter_songs_based_on_ratings(song_ratings, relative_threshold=0.10):
        overall_average = calculate_overall_average(song_ratings)
        threshold = overall_average * (1 + relative_threshold)
        
        selected_songs = []
        for spotify_id, ratings in song_ratings.items():
            average_rating = sum(ratings) / len(ratings) if ratings else 0
            if average_rating >= threshold:
                selected_songs.append(spotify_id)
        return selected_songs
    
    selected_songs = filter_songs_based_on_ratings(song_ratings)
    song_wizard = SongWizard(client_id, client_secret)
    recommendations = song_wizard.get_recommendations(selected_songs, 3)

    
    # Save recommendations to the database
    for song in recommendations:
        new_recommendation = Recommendation(room_id=room_id, spotify_song_id=song['spotify_id'])
        db.session.add(new_recommendation)
    db.session.commit()
    
    # Return the list of recommendations (or the IDs or any identifier)
    return recommendations


@socketio.on('join')
def on_join(data):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    room_code = data['room']
    room = Room.query.filter_by(code=room_code).first()
    if not room:
        return  redirect(url_for('home'))

    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))

    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not membership:
        # User is not a member of the room, handle accordingly
        return "Access Denied", 403
    
    join_room(room_code)
    
    #update members
    memberships = Membership.query.filter_by(room_id=room.id).all()
    members = [{'username': User.query.get(membership.user_id).username, 'id': membership.user_id, 'isAdmin': membership.user_id == room.admin_id} for membership in memberships]
    socketio.emit('update_members', {'members': members}, room=room_code)
    ######

    # Check if the room is full
    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if membership and not membership.joined_message_sent: #room.admin_id == user_id
        
        join_message = f"Joined the group."
        if room.admin_id == user_id:
            join_message = f"""Welcome to the group, when the group will be full, you will be 
                            able to see the recommendations link above in the highlighted 
                            section."""
            join_message = f"""Welcome to the group, when the group will be full the initial recommendations will appear under the 
                             "Initial Group Recommendations:" section.\n
                              Whenever the initial recommendations will be ready, you will be given {first_round_duration} seconds of time
                              to discuss and vote for the songs. 
                              You can see the timer underneath the 'Initial Group Recommendations:' section. \n
                              Whenever the timer goes off, you will be able to submit your votes for the songs.\n
                              After all the members have submitted their votes, you will be able to see the collobarative recommendations
                              and will get the upcoming instructions in the chat.
                              """
            socketio.emit('receive_message', {'msg': f'{user.username} (admin) : {join_message}', 'admin': True}, room=room_code)
            room.pinned_message = """Waiting for the group to be full."""
            db.session.commit()
            socketio.emit('update_pinned_message', {'msg': room.pinned_message}, room=room_code)
        else:
            socketio.emit('receive_message', {'msg': f'{user.username} : {join_message}'}, room=room_code)
        
        membership.joined_message_sent = True
        db.session.commit()
        new_message = Message(content=join_message, user_id=user.id, room_id=room.id)
        db.session.add(new_message)
        db.session.commit()
    
 

    member_count = Membership.query.filter_by(room_id=room.id).count()
    if member_count >= room.max_members:  
        # Room is full - send a message to the room from the admin
        # admin_message = "The group is now full. Let's get started!"
        admin = User.query.get(room.admin_id)
        if admin and not room.group_full_message_sent:
            #Notify that group is full, to wait for the recommendations
            # admin_message = f"The group is now full. Please wait for the recommendations link to appear above, under the group name."
            admin_message = f"""The group is now full. Please wait for the recommendations to appear under the 
                             "Initial Group Recommendations:" section.\n
                              Whenever the initial recommendations will be ready, you will be given {first_round_duration} seconds of time
                              to have discussion with the other group members and distribute your votes for the songs. 
                              You can see the timer underneath the 'Initial Group Recommendations:' section. \n
                              Whenever the timer goes off, you will be able to submit your votes for the songs.
                              After all the members have submitted their votes, you will be able to see the collobarative recommendations.
                              """
            new_message = Message(content=admin_message, user_id=admin.id, room_id=room.id)
            db.session.add(new_message)
            db.session.commit()
            socketio.emit('receive_message', {'msg': f'{admin.username} (admin) : {admin_message}', 'admin':True}, room=room_code)
            room.group_full_message_sent = True
            db.session.commit()
            socketio.emit('update_pinned_message', {'msg': """Generating the recommendations, please wait"""}, room=room_code)
            room.pinned_message = """Generating the recommendations, please wait"""
            db.session.commit()
            

        check_recommendations = Recommendation.query.filter_by(room_id=room.id).all()

        if admin and len(check_recommendations) == 0:
            songs = room.songs

            # Retrieve all ratings for each song associated with the room
            song_ratings = {}
            for song in songs:
                ratings = Rating.query.filter_by(song_id=song.id, room_id=room.id).all()
                if ratings:
                    # Use Spotify ID as the key
                    song_ratings[song.spotify_id] = [rating.value for rating in ratings]

            
            print("Steem1")
            if(len(Recommendation.query.filter_by(room_id=room.id).all()) == 0):
                print("Steem2")
                recommendations = generate_recommendations(room.id, song_ratings)
            

            admin_message = f"""The countdown for the 1st round of voting has started. You can see the timer underneath the 'Initial Group Recommendations:' section.
                                Take your time to discuss the recommended songs. Whenever the timer goes off, you will be able to submit your votes for the songs.
                                """

           

            room.pinned_message = admin_message
            db.session.commit()
            
            recs_details = Recommendation.query.filter_by(room_id=room.id).all()
            spotify_song_ids = [rec.spotify_song_id for rec in recs_details]
            
            remaining_time = first_round_duration

            socketio.emit('show_recommendations', {'spotify_song_ids': spotify_song_ids, 'remaining_time':remaining_time}, room=room_code)

            room.timer_start = datetime.utcnow()
            db.session.commit()



    if room.pinned_message:
        socketio.emit('receive_message', {'msg': room.pinned_message, 'pinned': True}, room=room_code)
    # Additional logic for when a user joins a room
        
@socketio.on('show_recommendations')
def handle_show_recommendations(data):
    if 'user_id' not in session:
            return redirect(url_for('login'))
    
    room_code = data['room']
    room = Room.query.filter_by(code=room_code).first()
    if not room:
        return  redirect(url_for('home'))

    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))

    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not membership:
        # User is not a member of the room, handle accordingly
        return "Access Denied", 403
    recs_details = Recommendation.query.filter_by(room_id=room.id).all()
    spotify_song_ids = [rec.spotify_song_id for rec in recs_details]
    socketio.emit('display_recommendations', {'recommendations': spotify_song_ids}, room=room_code)


def user_voted_1st_round(room_id, user_id):
    votes = Vote.query.filter_by(room_id=room_id, user_id=user_id, round_number = 1).all()
    return len(votes) > 0

def user_voted_2nd_round(room_id, user_id):
    votes = Vote.query.filter_by(room_id=room_id, user_id=user_id, round_number = 2).all()
    return len(votes) > 0


def all_members_have_voted(room_id, round_number = 1):
    room = Room.query.get(room_id)
    if not room:
        return False

    member_count = Membership.query.filter_by(room_id=room.id).count()
    if(round_number == 1):
        votes_count = Vote.query.filter_by(room_id=room.id, round_number = round_number).count()

        count = Recommendation.query.filter_by(room_id=room_id).count()


        if(count == 0):
            return False
        votes_count /= count
        # Assuming each member votes exactly once, check if the votes count match the member count
        return votes_count == member_count - 1
    else:
        votes_count = Vote.query.filter_by(room_id=room.id, round_number = round_number).count()
        if(votes_count == 0):
            return False
        votes_count /= number_of_1st_round_songs

        return votes_count == member_count - 1


def get_top_songs(room_id, round_number = 1):
    # Fetch all votes for this room
    votes = Vote.query.filter_by(room_id=room_id, round_number = round_number).all()

    # Aggregate votes by song
    vote_aggregate = {}
    for vote in votes:
        if vote.song_id in vote_aggregate:
            vote_aggregate[vote.song_id] += vote.vote_value
        else:
            vote_aggregate[vote.song_id] = vote.vote_value

    # Sort songs by total vote values
    sorted_songs = sorted(vote_aggregate.items(), key=lambda item: item[1], reverse=True)

    # Get the top six songs or less if there aren't enough songs
    top_songs_after_1st_round = [song_id for song_id, _ in sorted_songs[:number_of_1st_round_songs]] if round_number == 1 else [song_id for song_id, _ in sorted_songs[:number_of_final_songs]]

    return top_songs_after_1st_round

@app.route('/submit_votes/<string:room_id>', methods=['POST'])
def submit_votes(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    print("SteemSubmitVotes")
    user_id = session['user_id']

            
    # Check if have already voted
    existing_votes = Vote.query.filter_by(user_id=user_id, room_id=room_id).all()
    if existing_votes:
        return jsonify({'message': 'You have already voted for the 1st round!'})
    

    for spotify_song_id, vote_value in request.form.items():
        # Save the vote value for the song
        # Assuming you have a Vote model to save the votes
        new_vote = Vote(user_id=user_id, song_id=spotify_song_id, vote_value=vote_value, room_id=room_id)
        db.session.add(new_vote)
        db.session.commit()

    db.session.commit()
    
    if all_members_have_voted(room_id):
        top_songs_after_1st_round = get_top_songs(room_id)
        # Emit the top six songs to the room
        room = Room.query.get(room_id)

        remaining_time = second_round_duration
        socketio.emit('top_songs_after_1st_round', {'top_songs_after_1st_round': top_songs_after_1st_round, 'remaining_time_2':remaining_time}, room=room.code)
        pinned_message = f"""The countdown for the 2nd round of voting has started. Take your time to discuss the recommended songs. You can see the timer underneath the 'Group Recommendations After 1st Round of Voting:' section."""
        socketio.emit('update_pinned_message', {'msg': pinned_message}, room=room.code)
        room.pinned_message = pinned_message
        db.session.commit()
        room.timer_start2 = datetime.utcnow()
        db.session.commit()

        admin_message = f"""The group successfully passed the 1st round of voting. 
                            You can see the filtered recommendations under the 'Group Recommendations After 1st Round of Voting:' section.\n
                            The countdown of the 2nd round of voting has started. You can see the timer underneath the 'Group Recommendations After 1st Round of Voting:' section. \n
                            Take your time to discuss the recommendations. Whenever the timer goes off, you will be able to submit your votes for the songs.
                            After all the members would have submitted their votes, you will be able to see the Final Recommendations.
                            """
        admin = User.query.get(room.admin_id)
        new_message = Message(content=admin_message, user_id=admin.id, room_id=room.id)
        db.session.add(new_message)
        db.session.commit()
        socketio.emit('receive_message', {'msg': f'{admin.username} (admin) : {admin_message}', 'admin': True, 'pinned':False}, room=room.code)

    # socketio.emit('disable_voting', room=room.code)
    return jsonify({'message': 'Votes for the 1st round submitted successfully!'})



@app.route('/submit_votes_2nd/<string:room_id>', methods=['POST'])
def submit_votes_2nd(room_id):
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401


    user_id = session['user_id']
    
    # Check if have already voted
    existing_votes = Vote.query.filter_by(user_id=user_id, room_id=room_id, round_number = 2).all()
    if existing_votes:
        return jsonify({'message': 'You have already voted for the 2nd round!'})
    

    for spotify_song_id, vote_value in request.form.items():
        # Save the vote value for the song
        # Assuming you have a Vote model to save the votes
        new_vote = Vote(user_id=user_id, song_id=spotify_song_id, vote_value=vote_value, room_id=room_id, round_number = 2)
        db.session.add(new_vote)
        db.session.commit()

    db.session.commit()

    if all_members_have_voted(room_id, round_number = 2):
        final_songs = get_top_songs(room_id, round_number = 2)
        # Emit the top six songs to the room
        print("Emiting 2nd round")
        room = Room.query.get(room_id)
        socketio.emit('final_songs', {'final_songs': final_songs}, room=room.code)

        pinned_message = f"""The final recommendations are ready. You can see the final recommendations under the 'Final Recommendations:' section."""
        socketio.emit('update_pinned_message', {'msg': pinned_message}, room=room.code)
        room.pinned_message = pinned_message
        db.session.commit()

        admin_message = f"""The final recommendations are ready. You can see the final recommendations under the 'Final Recommendations:' section."""
        admin = User.query.get(room.admin_id)
        new_message = Message(content=admin_message, user_id=admin.id, room_id=room.id)
        db.session.add(new_message)
        db.session.commit()
        socketio.emit('receive_message', {'msg': f'{admin.username} (admin) : {admin_message}', 'admin': True, 'pinned':False}, room=room.code)

    # jsonify({'message': 'Votes for the 2nd round submitted successfully!'})
    return jsonify({'message': 'Votes for the 2nd round submitted successfully!'})



@socketio.on('send_message')
def handle_send_message_event(data):
    room_code = data['room']
    message_content = data['data']
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))

    room = Room.query.filter_by(code=room_code).first()
    if not room or not user_id:
        return redirect(url_for('home'))

    if len(message_content) == 0:
        return
    new_message = Message(content=message_content, user_id=user_id, room_id=room.id)
    db.session.add(new_message)
    db.session.commit()

    is_admin = room.admin_id == user_id

    if is_admin:
        socketio.emit('receive_message', {'msg': f'{new_message.user.username} (admin) : {message_content}'}, room=room_code)
    else:
        socketio.emit('receive_message', {'msg': f'{new_message.user.username} : {message_content}'}, room=room_code)


@app.route('/recommendations/<code>')
def view_recommendations(code):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    room = Room.query.filter_by(code=code).first()
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))
    if not room:
        # Room not found, redirect to home or appropriate page
        return redirect(url_for('home'))

    # Check if user is a member of the room
    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not membership:
        # User is not a member of the room, handle accordingly
        return "Access Denied", 403
    
    # Query recommendations from the database
    recommendations = Recommendation.query.filter_by(room_id=room.id).all()
    if not recommendations:
        return 'Recommendations are not available yet.'
    return render_template('recommendations.html', recommendations=recommendations)

@app.route('/yoursongsandratings/<code>')
def view_SongsAndRatings(code):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    room = Room.query.filter_by(code=code).first()
    if user is None:
        # User not found, possibly log out and redirect to login page
        session.clear()
        return redirect(url_for('login'))
    if not room:
        # Room not found, redirect to home or appropriate page
        return redirect(url_for('home'))

    # Check if user is a member of the room
    membership = Membership.query.filter_by(user_id=user_id, room_id=room.id).first()
    if not membership:
        # User is not a member of the room, handle accordingly
        return "Access Denied", 403
    
    # Query recommendations from the database
    user_ratings = Rating.query.filter_by(user_id=user_id, room_id=room.id).all()
    ratings_dict = {rating.song_id: rating.value for rating in user_ratings}
    songs = room.songs

    return render_template('yourratingsandsongs.html', room=room, user=user, ratings=ratings_dict, songs=songs)
    

@socketio.on('leave')
def on_leave(data):
    room_code = data['room']
    leave_room(room_code)


@app.route('/logout')
def logout():
# Clear the user's session
    session.clear()
    # Redirect to the login page or another appropriate page
    return redirect(url_for('login'))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    # db.create_all()
    socketio.run(app, debug=True, port=8000)