# This file sets up the venv and installs dependencies from dependencies.txt.
# Note this sh file will be run by Cygwin, not Linux bash/zsh.

# Create the venv if needed.
if [ -d "OwlcatPortraitToolVenv" ]; then
    echo "Virtual environment already exists. Activating it."
    source OwlcatPortraitToolVenv/Scripts/activate
else
    python -m venv OwlcatPortraitToolVenv
    source OwlcatPortraitToolVenv/Scripts/activate
fi

# Always install dependencies so updates to dependencies.txt are applied.
python -m pip install -r dependencies.txt
echo "Virtual environment ready and dependencies installed."
return 0 2>/dev/null || exit 0
