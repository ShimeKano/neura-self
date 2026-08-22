import os
import threading

import gradio as gr

from dashboard.app import app as flask_app

PORT = int(os.getenv("PORT", "7860"))


def run_flask():
    flask_app.run(
        host="0.0.0.0",
        port=7861,
        debug=False,
        use_reloader=False,
    )


# The existing Neura dashboard is Flask. Gradio provides the HF Spaces
# frontend/health endpoint while Flask serves the actual dashboard.
threading.Thread(target=run_flask, daemon=True).start()


def dashboard():
    return "NeuraSelf dashboard is running. Open /dashboard/ or use the embedded dashboard below."


with gr.Blocks(title="NeuraSelf") as demo:
    gr.Markdown("# NeuraSelf")
    gr.Markdown("The NeuraSelf Flask dashboard is running inside this Hugging Face Space.")
    gr.HTML('<iframe src="http://127.0.0.1:7861/" style="width:100%;height:800px;border:0;border-radius:12px;"></iframe>')

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=PORT,
        share=False,
    )
