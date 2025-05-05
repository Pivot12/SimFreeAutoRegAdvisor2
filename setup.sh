#!/bin/bash

mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"your-email@example.com\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
enableCORS = false\n\
port = $PORT\n\
[theme]\n\
primaryColor = \"#3498db\"\n\
backgroundColor = \"#f5f7fa\"\n\
secondaryBackgroundColor = \"#e6eaf0\"\n\
textColor = \"#2c3e50\"\n\
font = \"sans serif\"\n\
" > ~/.streamlit/config.toml
