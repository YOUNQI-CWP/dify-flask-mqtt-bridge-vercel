# api/index.py
import os
import json
import time
import uuid
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from redis import Redis
import paho.mqtt.client as mqtt

# --- 初始化 ---
load_dotenv()
app = Flask(__name__)

# --- 配置 ---
API_PREFIX = os.getenv("API_PREFIX", "/api")
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_CONTROL_TOPIC = os.getenv("MQTT_CONTROL_TOPIC", "smarthome/control")
MQTT_PUBLISH_QOS = int(os.getenv("MQTT_PUBLISH_QOS", 1))
MQTT_WAIT_TIMEOUT = int(os.getenv("MQTT_WAIT_TIMEOUT", 3)) # 等待命令响应的时间
REDIS_URL = os.getenv("KV_URL")
REDIS_DEVICE_HASH_KEY = "devices"

# --- 连接 Redis ---
try:
    if not REDIS_URL:
        raise ValueError("KV_URL is not set. Please set up Vercel KV.")
    redis_client = Redis.from_url(REDIS_URL)
    print("[API] Connected to Redis.")
except Exception as e:
    redis_client = None
    print(f"[API_ERROR] Failed to connect to Redis: {e}")

# --- API 路由实现 ---

@app.route(f"{API_PREFIX}/devices", methods=['GET'])
def list_online_devices():
    if not redis_client:
        return jsonify({"error": "Database connection failed."}), 503

    try:
        all_devices_raw = redis_client.hgetall(REDIS_DEVICE_HASH_KEY)
        online_devices = []
        for raw_data in all_devices_raw.values():
            data = json.loads(raw_data)
            if data.get("status", {}).get("online") is True:
                online_devices.append({
                    "device_id": data.get("device_id"),
                    "device_description": data.get("device_description", "N/A"),
                    "device_type": data.get("device_type"),
                    "last_reported_time": data.get("timestamp", "N/A"),
                    "status_summary": data.get("status", {}).get("text_data", "N/A")
                })
        return jsonify(online_devices), 200
    except Exception as e:
        return jsonify({"error": "Failed to retrieve device list.", "details": str(e)}), 500

@app.route(f"{API_PREFIX}/devices/<string:device_id>/status", methods=['GET'])
def get_device_status(device_id: str):
    if not redis_client:
        return jsonify({"error": "Database connection failed."}), 503

    try:
        raw_status = redis_client.hget(REDIS_DEVICE_HASH_KEY, device_id)
        if raw_status:
            return jsonify(json.loads(raw_status)), 200
        else:
            return jsonify({"error": f"Device '{device_id}' not found."}), 404
    except Exception as e:
        return jsonify({"error": "Failed to retrieve device status.", "details": str(e)}), 500

@app.route(f"{API_PREFIX}/devices/<string:device_id>/command", methods=['POST'])
def control_device(device_id: str):
    if not redis_client:
        return jsonify({"error": "Database connection failed."}), 503

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    action = data.get("action")
    value = data.get("value")

    if not action:
        return jsonify({"error": "Missing 'action' in request body"}), 400

    try:
        # 发布 MQTT 命令
        payload = {
            "command_id": f"cmd_{uuid.uuid4().hex[:8]}", "action": action, "value": value, "timestamp": int(time.time())
        }
        topic = f"{MQTT_CONTROL_TOPIC}/{device_id}"
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"api_pub_client_{uuid.uuid4().hex[:4]}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(topic, json.dumps(payload), qos=MQTT_PUBLISH_QOS)
        client.disconnect()
        print(f"[API] Published command '{action}' to '{topic}'.")

        # 等待一小段时间，让设备有时间响应并被Cron Job同步
        time.sleep(MQTT_WAIT_TIMEOUT)

        # 从 Redis 中获取最新的状态作为响应
        raw_status = redis_client.hget(REDIS_DEVICE_HASH_KEY, device_id)
        if raw_status:
            new_status = json.loads(raw_status)
            return jsonify(new_status), 200
        else:
            return jsonify({
                "error": f"Command sent, but no status update received from device '{device_id}' within the timeout period."
            }), 408

    except Exception as e:
        return jsonify({"error": "An internal error occurred.", "details": str(e)}), 500