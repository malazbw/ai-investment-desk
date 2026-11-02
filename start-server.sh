#!/bin/bash
# Start the FastAPI server with proper libpq PATH

export PATH=/opt/homebrew/opt/libpq/bin:$PATH
export LDFLAGS=-L/opt/homebrew/opt/libpq/lib
export CPPFLAGS=-I/opt/homebrew/opt/libpq/include

cd /Users/hala.al.kuwatly/ai-investment-desk
source venv/bin/activate
python run.py
