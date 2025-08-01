# api/crons/sync_mqtt.py
import os
import json
import time
import uuid
import paho.mqtt.client as mqtt
from flask import Flask, jsonify
from dotenv import load_dotenv
from redis import Redis

# --- 初始化 ---
load_dotenv()
app = Flask(__name__)

# --- 配置 ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_DATA_TOPIC = os.getenv("MQTT_DATA_TOPIC", "smarthome/data")
MQTT_SUBSCRIBE_QOS = int(os.getenv("MQTT_SUBSCRIBE_QOS", 1))
REDIS_URL = os.getenv("KV_URL") # Vercel KV 会自动注入这个环境变量
REDIS_DEVICE_HASH_KEY = "devices"
CRON_LISTEN_DURATION = 55 # 监听55秒，确保在1分钟的定时周期内完成

# --- 连接 Redis ---
try:
    if not REDIS_URL:
        raise ValueError("KV_URL is not set. Please set up Vercel KV.")
    redis_client = Redis.from_url(REDIS_URL)
    print("[CRON_SYNC] Connected to Redis.")
except Exception as e:
    redis_client = None
    print(f"[CRON_SYNC_ERROR] Failed to connect to Redis: {e}")

def on_message(client, userdata, msg):
    """收到消息后的回调，直接写入 Redis"""
    if not redis_client:
        print("[CRON_SYNC_ERROR] Redis client not available, skipping message.")
        return
        
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        device_id = data.get("device_id")

        if not device_id:
            return

        # 将完整的设备数据（JSON字符串）存入 Redis Hash
        redis_client.hset(REDIS_DEVICE_HASH_KEY, device_id, payload_str)
        print(f"[CRON_SYNC] Updated device '{device_id}' in Redis.")

    except Exception as e:
        print(f"[CRON_SYNC_ERROR] Failed to process and save message: {e}")

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[CRON_SYNC] MQTT Connected. Subscribing to '{MQTT_DATA_TOPIC}'...")
        client.subscribe(MQTT_DATA_TOPIC, qos=MQTT_SUBSCRIBE_QOS)
    else:
        print(f"[CRON_SYNC_ERROR] MQTT Connection failed with code: {reason_code}")

@app.route('/api/crons/sync_mqtt', methods=['GET'])
def handler():
    """Vercel Cron Job 调用的处理函数"""
    if not redis_client:
        return "Redis connection failed. Aborting sync.", 500

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"cron_sync_client_{uuid.uuid4().hex[:8]}"
    )
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print("[CRON_SYNC] Starting MQTT listener...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        # 持续监听一段时间以接收数据
        time.sleep(CRON_LISTEN_DURATION)
    except Exception as e:
        print(f"[CRON_SYNC_ERROR] An error occurred during MQTT sync: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[CRON_SYNC] MQTT listener stopped.")

    return "MQTT sync cycle completed.", 200