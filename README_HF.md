# NeuraSelf on Hugging Face Spaces

This branch runs the existing Flask dashboard through a **Gradio Space**, so it does not require a Docker Space.

## Space configuration

Create a new Hugging Face Space with:

- **SDK:** Gradio
- **Hardware:** CPU Basic / Free

The Space starts `app.py`. Gradio listens on Hugging Face's `$PORT` (normally `7860`) and the existing Flask dashboard runs internally on port `7861`.

## Important

Hugging Face Space storage should not be treated as permanent application storage. Keep secrets such as dashboard credentials and account tokens out of Git. Use Space Secrets/environment variables where the application supports them.

The original dependency file contains desktop/Termux-oriented packages. `requirements-huggingface.txt` uses `opencv-python-headless` and omits desktop audio dependencies so the Space can run without a GUI.
