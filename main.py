from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore, storage
import starlette.status as status
import local_constants
from google.cloud import storage
from datetime import datetime

#-------------------Barry Denby-------------------#
app = FastAPI()
firestore_db = firestore.Client()
firebase_request_adapter = requests.Request()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")
#-------------------Barry Denby-------------------#


def get_user_by_email(email):
    users_ref = firestore_db.collection('User')
    query = users_ref.where('email', '==', email).limit(1).get()
    for doc in query:
        return doc.to_dict()
    return None

def is_following(userx_username: str, current_user_email: str) -> bool:
    current_user_data = get_user_by_email(current_user_email)
    if current_user_data and 'following' in current_user_data:
        following_list = current_user_data['following']
        return userx_username in following_list
    return False

def fetch_filtered_tweets(current_user_email):
    all_tweets = firestore_db.collection('Tweet').order_by('date', direction=firestore.Query.DESCENDING).get()
    filtered_tweets = []
    for tweet in all_tweets:
        tweet_data = tweet.to_dict()
        tweet_user_username = tweet_data.get('username')
        if is_following(tweet_user_username, current_user_email) or tweet_user_username == get_user_by_email(current_user_email).get('username'):
            filtered_tweets.append({**tweet_data, 'tweet_id': tweet.id})
    return filtered_tweets

def get_image():
    storage_client = storage.Client()
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob("logo.png")
    blob.upload_from_filename("static/logo.png")
    blob.make_public()
    return blob

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    blob = get_image()
    id_token = request.cookies.get("token")
    user_info = validateFirebaseToken(id_token)
    if not user_info:
        return templates.TemplateResponse('main.html', {'request': request, 'user_token': None, 'db_check_1': False, 'db_check_2': False, 'logo_url': blob.public_url})
    db_check_1 = False
    db_check_2 = False
    user_data = get_user_by_email(user_info['email'])
    if user_data:
        db_check_1 = True
        db_check_2 = 'username' in user_data
    if not db_check_2:
        return templates.TemplateResponse('main.html', {'request': request, 'user_token': user_info, 'db_check_1': db_check_1, 'db_check_2': db_check_2, 'currUsername': None, 'logo_url': blob.public_url})

    timestamp = datetime.now()

    if not 'following' in user_data:
        user_data['following'] = ''
    if not 'followers' in user_data:
        user_data['followers'] = ''

    tweet_data_mixed = fetch_filtered_tweets(user_info['email'])
    tweet_data_mixed_max_10 = tweet_data_mixed[:20]

    return templates.TemplateResponse('main.html', {'request': request, 'user_token': user_info, 'db_check_1': db_check_1, 'db_check_2': db_check_2, 'user_data': user_data, 'currTimestamp': timestamp, 'user_data_following': user_data['following'], 'user_data_followers': user_data['followers'], 'tweet_data_mixed': tweet_data_mixed, 'logo_url': blob.public_url, 'tweet_data_mixed_max_10': tweet_data_mixed_max_10})

@app.get("/sign-up", response_class=HTMLResponse)
async def sign_up_get(request: Request):
    blob = get_image()
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')
    curr_usernames = []
    users_ref = firestore_db.collection('User')
    query_snapshot = users_ref.stream()
    for doc in query_snapshot:
        user_data = doc.to_dict()
        if 'username' in user_data:
            curr_usernames.append(user_data['username'])
    return templates.TemplateResponse('signup.html', {'request': request, 'user_token': user_token, 'logo_url': blob.public_url, 'currUsernames': curr_usernames})

@app.post("/sign-up", response_class=RedirectResponse)
async def sign_up_post(request: Request, username: str = Form(...), sex: str = Form(...), birthdate: str = Form(...)):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')
    user_data = get_user_by_email(user_token['email'])
    user_ref = firestore_db.collection('User').where('username', '==', username).get()
    if user_data:
        return RedirectResponse('/already-signed-up')
    else:
        if user_ref:
            return RedirectResponse('/username-taken')
        else:
            firestore_db.collection('User').add({'username': username, 'sex': sex, 'birthdate': birthdate, 'email': user_token['email']})
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

@app.post("/post-tweet", response_class=RedirectResponse)
async def post_tweet(request: Request, tweet: str = Form(None), username: str = Form(...), email: str = Form(...), date: datetime = Form(...), image: UploadFile = File(None)):
    if tweet is None:
        tweet = ""
    type = False
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        raise HTTPException(status_code=401, detail="Authentication failed")

    user_data = get_user_by_email(user_token['email'])
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD HH:MM:SS")
    blob_url = "NONE"
    if image and image.filename:
        storage_client = storage.Client()
        bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
        blob = bucket.blob(f"{image.filename}")
        blob.upload_from_file(image.file)
        blob.make_public()
        blob_url = blob.public_url
        type = True
    tweet_data = {'tweet': tweet, 'name': username, 'username': username, 'email': email, 'date': date, 'blob_url': blob_url, 'type': type}
    firestore_db.collection('Tweet').add(tweet_data)
    user_ref = firestore_db.collection('User').where('username', '==', username).get()
    if user_ref:
        user_doc = user_ref[0]
        if 'Tweet' in user_doc.to_dict():
            current_tweets = user_doc.to_dict()['Tweet']
            current_tweets.append(tweet)
            firestore_db.collection('User').document(user_doc.id).update({'Tweet': current_tweets})
        else:
            firestore_db.collection('User').document(user_doc.id).update({'Tweet': [tweet]})
    else:
        raise HTTPException(status_code=404, detail="User not found")

    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, search: str = Form(...)):
    blob = get_image()
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')

    users_ref = firestore_db.collection('User')
    query_snapshot = users_ref.stream()
    filtered_users = [doc.to_dict() for doc in query_snapshot if doc.to_dict().get('username', '').lower().startswith(search.lower())]

    tweets_ref = firestore_db.collection('Tweet')
    query_snapshot = tweets_ref.stream()
    filtered_tweets = [doc.to_dict() for doc in query_snapshot if doc.to_dict().get('tweet', '').lower().startswith(search.lower())]

    user_data = get_user_by_email(user_token['email'])
    if not 'following' in user_data:
        user_data['following'] = ''
    if not 'followers' in user_data:
        user_data['followers'] = ''

    if not filtered_users:
        filtered_users = None
    if not filtered_tweets:
        filtered_tweets = None
    return templates.TemplateResponse('search.html', {'request': request, 'user_token': user_token, 'filtered_users': filtered_users, 'filtered_tweets': filtered_tweets, 'logo_url': blob.public_url, 'user_data': user_data, 'user_data_following': user_data['following'], 'user_data_followers': user_data['followers']})

@app.get("/users/{user_name}", response_class=HTMLResponse)
async def user(request: Request, user_name: str):
    blob = get_image()
    x = False
    tweet_data_single = None
    tweet_data_single_max_10 = None
    timestamp = datetime.now()
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')
    user_data_1 = get_user_by_email(user_token['email'])
    if not user_data_1:
        return RedirectResponse('/')
    user_ref = firestore_db.collection('User').where('username', '==', user_name).get()
    if user_ref:
        user_doc = user_ref[0]
        user_data = user_doc.to_dict()
        if 'following' in user_data_1:
            if user_data['username'] in user_data_1['following']:
                x = True
            else:
                x = False
        tweet_query = firestore_db.collection('Tweet').where('username', '==', user_name).order_by('date', direction=firestore.Query.DESCENDING).limit(10).get()
        if x or user_data['username'] == user_data_1['username']:
            tweet_data_single = [{**tweet.to_dict(), 'tweet_id': tweet.id} for tweet in tweet_query]
            tweet_data_single_max_10 = tweet_data_single[:10]
        return templates.TemplateResponse('user.html', {'request': request, 'user_token': user_token, 'user_data': user_data, 'user_data_1': user_data_1, 'x': x, 'tweet_data_single': tweet_data_single, 'currTimestamp': timestamp, 'logo_url': blob.public_url, 'tweet_data_single_max_10': tweet_data_single_max_10})
    return RedirectResponse('/user-not-found')

@app.get("/edit-tweet/{tweet_id}", response_class=HTMLResponse)
async def edit_tweet(request: Request, tweet_id: str):
    blob = get_image()
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')
    user_data = get_user_by_email(user_token['email'])
    if not 'following' in user_data:
        user_data['following'] = ''
    if not 'followers' in user_data:
        user_data['followers'] = ''

    tweet_ref = firestore_db.collection('Tweet').document(tweet_id)
    tweet_data = tweet_ref.get()
    if not tweet_data.exists:
        raise HTTPException(status_code=404, detail="Tweet not found")
    
    tweet_dict = tweet_data.to_dict()
    tweet_dict['tweet_id'] = tweet_id

    if tweet_dict['email'] != user_token['email']:
        raise HTTPException(status_code=403, detail="You are not authorized to edit this tweet")
    
    return templates.TemplateResponse('edit.html', {
        'request': request,
        'tweet_data': tweet_dict,
        'user_token': user_token,
        'logo_url': blob.public_url,
        'user_data': user_data,
        'user_data_following': user_data['following'],
        'user_data_followers': user_data['followers']
    })

@app.post("/post-edit-tweet", response_class=RedirectResponse)
async def post_edit_tweet(request: Request, tweet: str = Form(None), tweet_id: str = Form(...), image: UploadFile = File(None), delete_image: bool = Form(False)):
    
    if tweet is None:
        tweet = ""
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        raise HTTPException(status_code=401, detail="Authentication failed")

    tweet_ref = firestore_db.collection('Tweet').document(tweet_id)
    tweet_data = tweet_ref.get()
    if not tweet_data.exists:
        raise HTTPException(status_code=404, detail="Tweet not found")

    tweet_dict = tweet_data.to_dict()
    if tweet_dict['email'] != user_token['email']:
        raise HTTPException(status_code=403, detail="You are not authorized to edit this tweet")

    blob_url = tweet_dict.get('blob_url', 'NONE')
    if delete_image and blob_url != 'NONE':
        storage_client = storage.Client()
        bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
        blob_name = blob_url.split('/')[-1]
        blob_name = blob_name.split('?')[0]
        blob = bucket.blob(blob_name)
        try:
            blob.delete()
            blob_url = 'NONE'
        except Exception as e:
            print(f"Failed to delete blob: {e}")
    else:
        if image and image.filename:
            storage_client = storage.Client()
            bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
            blob = bucket.blob(f"{image.filename}")
            blob.upload_from_file(image.file)
            blob.make_public()
            blob_url = blob.public_url

    updated_data = {'tweet': tweet, 'blob_url': blob_url}
    tweet_ref.update(updated_data)

    return RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)


@app.post("/delete-tweet", response_class=RedirectResponse)
async def delete_tweet(request: Request, tweet_id: str = Form(...)):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')
    tweet_ref = firestore_db.collection('Tweet').document(tweet_id)
    tweet_data = tweet_ref.get().to_dict()
    if tweet_data:
        if tweet_data['email'] == user_token['email']:
            tweet_ref.delete()
        else:
            raise HTTPException(status_code=403, detail="You are not authorized to delete this tweet")
    else:
        raise HTTPException(status_code=404, detail="Tweet not found")
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

@app.post("/follow", response_class=RedirectResponse)
async def follow(request: Request, follower: str = Form(...), followee: str = Form(...)):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')

    follower_ref = firestore_db.collection('User').where('username', '==', follower).get()
    followee_ref = firestore_db.collection('User').where('username', '==', followee).get()

    if follower_ref and followee_ref:
        follower_doc = follower_ref[0]
        followee_doc = followee_ref[0]

        follower_data = follower_doc.to_dict()
        if 'following' in follower_data:
            current_following = follower_data['following']
            if followee not in current_following:
                current_following.append(followee)
        else:
            current_following = [followee]
        firestore_db.collection('User').document(follower_doc.id).update({'following': current_following})

        followee_data = followee_doc.to_dict()
        if 'followers' in followee_data:
            current_followers = followee_data['followers']
            if follower not in current_followers:
                current_followers.append(follower)
        else:
            current_followers = [follower]
        firestore_db.collection('User').document(followee_doc.id).update({'followers': current_followers})
    else:
        return RedirectResponse('/user-not-found')

    return RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)

@app.post("/unfollow", response_class=RedirectResponse)
async def unfollow(request: Request, follower: str = Form(...), followee: str = Form(...)):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        return RedirectResponse('/')

    follower_ref = firestore_db.collection('User').where('username', '==', follower).get()
    followee_ref = firestore_db.collection('User').where('username', '==', followee).get()

    if follower_ref and followee_ref:
        follower_doc = follower_ref[0]
        followee_doc = followee_ref[0]

        follower_data = follower_doc.to_dict()
        if 'following' in follower_data:
            current_following = follower_data['following']
            if followee in current_following:
                current_following.remove(followee)
        else:
            current_following = []
        firestore_db.collection('User').document(follower_doc.id).update({'following': current_following})

        followee_data = followee_doc.to_dict()
        if 'followers' in followee_data:
            current_followers = followee_data['followers']
            if follower in current_followers:
                current_followers.remove(follower)
        else:
            current_followers = []
        firestore_db.collection('User').document(followee_doc.id).update({'followers': current_followers})
    else:
        return RedirectResponse('/user-not-found')

    return RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)

#-------------------Barry Denby - Functions-------------------#
def validateFirebaseToken(id_token):
    if not id_token:
        return None
    user_token = None
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
    except ValueError as err:
        print(str(err))
    return user_token
#-------------------Barry Denby - Functions-------------------#