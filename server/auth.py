import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.oauth2 import id_token
from google.auth.transport import requests
import server.constants as constants

import hashlib
import datetime

# returns the MD5 hash of the user's email.
# used for the ID of the responses doc
def email_hash(email):
    return hashlib.md5(email.encode()).hexdigest()

# checks if the current user exists in DB and has the correct userId
def is_authenticated(userEmail : str, userId : str, collection_ref : firestore.firestore.CollectionReference):
    # typically triggered if there are no cookies
    if userEmail is None or userId is None:
        return False
    userDoc = collection_ref.document(userEmail).get()
    if userDoc is None or not userDoc.exists:
        return False
    userDict = userDoc.to_dict() 
    
    # this case would happen if we put people into the database through something other than the website
    # e.g. if they signed up at a freshmen fair or something
    if "id" not in userDict:
        return False
    # avoid double authentication. Check if this is the same user
    elif userDict["id"] == userId:
        return True
    else:
        # they're trying to fuck with us somehow
        raise Exception("Email and stored ID do not match")

# see if we can authenticate user account with google backend
# if yes, return tuple (userEmail, userId)
def authenticate_google_signin(token : str):
    # this is a google library for verifying stuff
    idinfo = id_token.verify_oauth2_token(token, requests.Request(), constants.get_google_client_id())
    userId = idinfo["sub"]
    userEmail = idinfo["email"]
    hd = idinfo["hd"]
    if hd is None or hd not in ["college.harvard.edu"]:
        raise Exception("Not a @college.harvard.edu email!")
    return (userEmail, userId)

# gets a user by their email and corresponding ID
# if user does not exist, create in DB and return new doc ref
# assumes email and id already authenticated with google backend
# throws exceptions if email or ID is None, or if they do not match
def create_respondent(userEmail : str, userId : str, db : firestore.firestore.Client) -> firestore.firestore.DocumentSnapshot:
    emails_ref = db.collection("emails")
    responses_ref = db.collection("responses")
    user_response_ref = responses_ref.document(email_hash(userEmail))
    user_response_doc = user_response_ref.get()
    if userEmail is None:
        raise Exception("User email not defined")
    if userId is None:
        raise Exception("User ID not defined")
    # user already exists
    if is_authenticated(userEmail, userId, emails_ref):
        if not user_response_doc.exists:
            # only create responses doc if it doesn't already exist
            responses_ref.document(email_hash(userEmail)).set({
            u"demographics" : {}
        })
        return emails_ref.document(userEmail).get()
    # user doesn't exist, have to create everything
    else: 
        user_email_ref = emails_ref.document(userEmail)
        user_email_doc = user_email_ref.get()
        if user_email_doc.exists:
            user_email_ref.update({
                u"id" : userId,
            })
        else:
            user_email_ref.set({
                u"id" : userId, 
                u"has_demographics" : False,
                u"monthly_responses" : {},
                u"total_responses" : 0, 
                u"date_created" : datetime.datetime.now()
            })
        if not user_response_doc.exists:
            responses_ref.document(email_hash(userEmail)).set({
            u"demographics" : {}
        })

        return emails_ref.document(userEmail).get()

def get_emails_dict(userEmail : str, db : firestore.firestore.Client):
    emails_ref = db.collection("emails")
    return emails_ref.document(userEmail).get().to_dict()

def get_responses_dict(userEmail : str, db : firestore.firestore.Client):
    responses_ref = db.collection("responses")
    return responses_ref.document(email_hash(userEmail)).get().to_dict()

def init_survey_firebase():
    # we're on the server, use the project ID
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': "hodp-surveys",
        }, name = "surveys")
    # locally testing, we have some credential file
    else:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'survey_creds.json'
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId' : "hodp-surveys"
        }, name = "surveys")

def init_website_firebase():
    # we're on the server, use the project ID
    if os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/'):
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': "hodp-website",
        }, name = "website")
    # locally testing, we have some credential file
    else:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'website_creds.json'
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId' : "hodp-website"
        }, name = "website")

def get_survey_firestore_client():
    app = firebase_admin.get_app("surveys")
    return firestore.client(app)

def get_website_firestore_client():
    app = firebase_admin.get_app("website")
    return firestore.client(app)