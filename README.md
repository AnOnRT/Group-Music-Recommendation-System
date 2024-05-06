# Installation Manual

1. Prerequisites
    * Python 3.8 or newer
    * pip for installing Python packages
    * A Spotify Developer account for API access Setup

2. Clone the Repository
    * Clone the project repository from GitHub using
        * `git clone [Your Repository URL]`
        * `cd [Your Project Directory]`

3. Install Dependencies
    * Install the necessary Python packages using pip
        * `pip install -r requirements.txt`

4. Configure Spotify API Keys
    * Obtain your Spotify Client ID and Client Secret from the Spotify Developer Dashboard.
    * Open `main_withDBandSR.py` file in the project directory and assign your Spotify credentials:
        * `client_id='your_client_id_here'`
        * `client_secret='your_client_secret_here'`

5. Launch the Application
    * As the server is implemented with local SQLite3 database and not a production WSGI server, you can only run it as development server.
    * Type `python main_withDBandSR.py` in terminal to run the server/program.
    * Your application will be accessible at `http://localhost:8000`.


# User's Guide

1. Overview
    * This system allows users to participate in group music recommendation sessions. Users can join existing rooms or create new ones to share music preferences and receive Spotify track recommendations.
    When the user enters the webpage there appears “Log-in” or “Sign up” window. After user signs up or logs into the system, 
    the user will see an option create a group or join to group.

    * Here the important part is that there are two types of users: “participants” and “group administrator”. 
    The participant is someone, who is going to use the system and participate in the user study. 
    The "administrator" corresponds to the person that creates the user study, gets the link/code and distributes it to other users/participants. 
    Each will be able to create group with specified count of group members (so becoming what we call an administrator). 

    * When the group is created, the administrator will get a unique group link/code to distribute among other users who want to join to that recommendation group. 
    When the group will be created the system will retrieve 20 songs from Spotify API and assign to the group, which should be rated by the participants when they use the join link/code.
    After other members search the unique link or join with the code, they will get that songs to rate and be redirected to the room window, where are the small chat window, info about group members. 
    When all the group members will join the room after rating the songs(when the group is full), on the chat-box they will be notified that the room recommendations are being generated based on their songs.
    The initial group recommendations will be shown in the `Initial group recommendations` section, and next to each song there will be a small rating box.

    * After the appearance of the recommendations in the `Initial group recommendations` section, so called the countdown for the 1st round voting will be started and new `Fist round voting` will be created underneath the `Initial group recommendations` section. 
    The countdown state is shown by the timer which appears underneath the `Fist round voting` section.
    A special automated generated message from the Admin will notify the users about the following staff:
        1. The start of countdown of the 1st round.
        2. What should the users do during the 1st round voting.
    The users will have M(by default 55) votes to distribute among the `Initial group recommendations` and they should discuss their opinions about recommendations in the chat and vote individually. 
    When the countdown ends in the `Fist round voting` the submit button will be activated and the users will be able to submit their votes.

    * After all the users will submit their votes for the 1st round, the users will be notified by the automatically generated message from the Admin that the countdown for the 2nd round of voting will be started and new `Group Recommendations After 1st Round of Voting` and `Second round voting` sectiona will be created above the `Initial group recommendations` section. 
    In the `Group Recommendations After 1st Round of Voting` section the system will show the top 5 highly voted songs (that were in `Initial group recommendations` section) and next to each song there will be a small rating box.
    The countdown state is shown by the timer which appears underneath the `Second round voting` section.
    A special automated generated message from the Admin will notify the users about the following staff:
        1. The start of countdown of the 2nd round.
        2. What should the users do during the 2nd round voting.
    The users will have K(by default 30) votes to distribute among the `Group Recommendations After 1st Round of Voting` and they should discuss their opinions about recommendations in the chat and vote individually.
    When the countdown ends in the `Second round voting` the submit button will be activated and the users will be able to submit their votes.

    * Finally after all the users will submit their vote for the `Second round voting` the system will take the top 3 most voted songs and show them in the newly created `Final Recommendations` section above the `Group Recommendations After 1st Round of Voting` section. The users will be notified by the automatically generated message from the Admin that the final recommendations for the group are ready and shown.


# Developer Documentation

1. Compilation
    * The project is written in Python, utilizing Flask for the web framework and Socket.IO for real-time communication.
    * Machine Learning library “scikit-learn” is used for building the recommendation model. Spotify API is integrated retrieving real-time music data. 
    * User authentication using Flask-Login.
    * SQLite database is used to store user profiles, group information, and music data. 
    * HTML, CSS, and JavaScript for creating a user-friendly web interface. 
    * Compilation is not required for Python scripts. Run the application using the Flask command as mentioned in the installation manual.

2. Implementation Details
    * Languages/Frameworks
        * Python, Flask, JavaScript, HTML/CSS.
    * Recommendation Generation
        * Recommended to firstly check the `https://github.com/AnOnRT/Music-Recommendation-System-for-Group`.
        * The system randomly retrieves 20 songs from the top 30 playlists of different genres from Spotify.
        * Then accepts the ratings of that songs from the users. It creates a feature matrix from top 10 highly rated songs ~ 2900 features for each song (check `https://github.com/AnOnRT/Music-Recommendation-System-for-Group`).
        * Then it uses already existing matrix (songs' features ~34000 songs and ~ 2900 features) and newly created matrix from user rated songs and computes similarity matrix. Using it it gives back recommendations from its knowledge, which corresponds to the users ratings.
        * For more detailed explaination, please check `https://github.com/AnOnRT/Music-Recommendation-System-for-Group`.
    * Real-Time Chat
        * Implemented using Flask-SocketIO, allowing users to discuss and decide on the recommended tracks in real-time.  
    * Utilization of the environmental variables, inside the `main_withDBandSR.py`.
        * Change `client_id = "***"` with your own Spotify API client id.
        * Change `client_secret = "***"` with your own Spotify API client secret.
        * The number of the final songs after final voting, meaning number of final songs `number_of_final_songs = 3`.
        * The number of the songs after 1st round of voting `number_of_1st_round_songs = 5`.
        * The countdown duration for the 1st round of voting `first_round_duration = 300 #Seconds`
        * The countdown duration for the 1st round of voting `second_round_duration = 300 #Seconds`
        * The number of votes to use for the songs from the initial group recommendations `votes_count_1st_round = 55 ##55`
        * The number of votes to use for the songs from the group recommendations after 1st round of voting `recommendationsvotes_count_2nd_round = 33 ##33`
    * Database
        * The server uses `./db/chat.db` SQLite database to store all the information. 

3. Non-Trivial Data Structures
    * User and Room Management
        * Utilizes SQLAlchemy models to manage users, rooms, and song ratings, storing data in a SQLite database for simplicity.
    * The reocmmendation generation 
        * Please check `https://github.com/AnOnRT/Music-Recommendation-System-for-Group`.