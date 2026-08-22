import os

# Hugging Face Spaces provides the public HTTP port through PORT.
PORT = int(os.getenv("PORT", "7860"))

from dashboard.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
