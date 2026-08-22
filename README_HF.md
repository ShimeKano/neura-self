# NeuraSelf on Hugging Face Spaces

This branch adds a Docker-based Hugging Face Space runtime for the NeuraSelf web dashboard.

## Space configuration

Create a **Docker Space** and point it at this repository/branch.

The container listens on `0.0.0.0:$PORT` and defaults to Hugging Face's standard `7860` port.

The dashboard is started by `hf_app.py` instead of the interactive `neura.py` launcher.

## Important

Hugging Face Spaces storage should not be treated as permanent application storage. Keep secrets such as dashboard credentials and account tokens in Space Secrets rather than committing them to Git.

The original dependency file contains desktop/Termux-oriented packages. `requirements-huggingface.txt` replaces GUI/audio-oriented dependencies and uses `opencv-python-headless` so the Space can build without a desktop environment.
