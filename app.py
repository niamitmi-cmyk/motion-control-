from flask import Flask, request, jsonify, send_from_directory
import os
import time
import jwt
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ================== KLING API KEYS ==================
ACCESS_KEY = "AJJDmFrmAYA49Fk9a9ggtapBGEK9MAm3"
SECRET_KEY = "RGRpRJLpL8QFtKnDQ9CM9N8ATCeJFDNF"
BASE_URL = "https://api-singapore.klingai.com"
# ===================================================

def generate_jwt():
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": ACCESS_KEY,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256", headers=headers)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/generate', methods=['POST'])
def generate():
    if 'image' not in request.files or 'video' not in request.files:
        return jsonify({"error": "Image and Video both required"}), 400

    image_file = request.files['image']
    video_file = request.files['video']
    prompt = request.form.get('prompt', '')
    orientation = request.form.get('orientation', 'image')
    mode = request.form.get('mode', 'pro')
    model_name = request.form.get('model_name', 'kling-v2-6')

    image_filename = secure_filename(image_file.filename)
    video_filename = secure_filename(video_file.filename)

    image_file.save(os.path.join(UPLOAD_FOLDER, image_filename))
    video_file.save(os.path.join(UPLOAD_FOLDER, video_filename))

    base = request.host_url.rstrip('/')
    image_url = f"{base}/uploads/{image_filename}"
    video_url = f"{base}/uploads/{video_filename}"

    token = generate_jwt()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "model_name": model_name,
        "image_url": image_url,
        "video_url": video_url,
        "prompt": prompt,
        "keep_original_sound": "yes",
        "character_orientation": orientation,
        "mode": mode
    }

    try:
        resp = requests.post(f"{BASE_URL}/v1/videos/motion-control", json=payload, headers=headers, timeout=30)
        data = resp.json()

        if data.get("code") != 0:
            return jsonify({"error": "Kling API Error"}), 500

        task_id = data["data"]["task_id"]

        for _ in range(60):
            time.sleep(5)
            status_resp = requests.get(f"{BASE_URL}/v1/videos/motion-control/{task_id}", 
                                     headers={"Authorization": f"Bearer {token}"})
            status_data = status_resp.json()

            if status_data.get("code") == 0:
                if status_data["data"].get("task_status") == "succeed":
                    video_url = status_data["data"]["task_result"]["videos"][0]["url"]
                    return jsonify({"success": True, "video_url": video_url})
                elif status_data["data"].get("task_status") == "failed":
                    return jsonify({"error": "Generation failed"}), 500
        return jsonify({"error": "Timeout"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
