#!/bin/bash

# AWS Cost Management Project Environment Setup
# This script sets up the Python virtual environment and installs dependencies

echo "Setting up AWS Cost Management Project environment..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Verify installations
echo "Verifying installations..."
python -c "
import boto3
import botocore
import requests
import flask
import numpy
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
print('✅ All dependencies installed successfully!')
print('✅ Virtual environment is ready to use')
print('')
print('To activate the environment manually, run:')
print('source venv/bin/activate')
"

echo "Setup complete!"