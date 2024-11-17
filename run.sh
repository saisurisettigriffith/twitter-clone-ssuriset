#!/bin/bash

# This script sets the Google Cloud credentials and starts the FastAPI application using Uvicorn with reloading

# Set the path to your Google Cloud service account key file
export GOOGLE_APPLICATION_CREDENTIALS="ssuriset-twitter-clone-961e2fdf5a9a.json"

# Start the FastAPI application with Uvicorn in reload mode
uvicorn main:app --reload

# End of script