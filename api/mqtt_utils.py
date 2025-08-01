# api/mqtt_utils.py
import os
import json
import time
import uuid
import threading
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, List

# --- 从环境变量读取配置 ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_CLIENT_ID_BASE = os.getenv("MQTT_CLIENT_ID", f"dify_serverless_bridge_{uuid.uuid4().hex[:6]}")
MQTT_DATA_TOPIC = os.getenv("MQTT_DATA_TOPIC", "smarthome/data")
MQTT_CONTROL_TOPIC = os.getenv("MQTT_CONTROL_TOPIC", "smarthome/control")
MQTT_PUBLISH_QOS = int(os.getenv("MQTT_PUBLISH_QOS", 1))
MQTT_SUBSCRIBE_QOS = int(os.getenv("MQTT_SUBSCRIBE_QOS", 1))
LOG_FILE_PATH = os.getenv("DEVICE_LOG_FILE", "/tmp/device_data_log.jsonl") # 在Vercel中使用 /tmp 目录

# --- 确保日志文件和目录存在 ---
log_dir = os.path.dirname(LOG_FILE_PATH)
os.makedirs(log_dir, exist_ok=True)
if not os.path.exists(LOG_FILE_PATH):
    open(LOG_FILE_PATH, 'w').close()

# 用于在同步期间临时存储消息
_sync_messages = []
_sync_lock = threading.Lock()

def _on_message_sync(client, userdata, msg):
    """同步时专用的 on_message 回调函数"""
    global _sync_messages
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        device_id = data.get("device_id")

        if not device_id:
            print(f"[MQTT_SYNC] Ignoring message without device_id on topic {msg.topic}")
            return

        log_entry = {
            "timestamp_iso": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            "timestamp_epoch": time.time(),
            "topic": msg.topic,
            "qos": msg.qos,
            "device_id": device_id,
            "device_data": data
        }
        with _sync_lock:
            _sync_messages.append(log_entry)
        print(f"[MQTT_SYNC] Received data for device: {device_id}")

    except Exception as e:
        print(f"[MQTT_SYNC_ERROR] Failed to process message: {e}")

def _sync_data_from_mqtt(timeout: int = 2):
    """
    核心修复函数：连接到MQTT，短暂监听并同步数据到日志文件。
    """
    global _sync_messages
    _sync_messages = [] # 清空上次的临时消息

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{MQTT_CLIENT_ID_BASE}_sync_{uuid.uuid4().hex[:4]}")
    client.on_message = _on_message_sync

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[MQTT_SYNC] Connected. Subscribing to {MQTT_DATA_TOPIC}...")
            client.subscribe(MQTT_DATA_TOPIC, qos=MQTT_SUBSCRIBE_QOS)
        else:
            print(f"[MQTT_SYNC_ERROR] Connection failed with code: {reason_code}")

    client.on_connect = on_connect

    try:
        print(f"[MQTT_SYNC] Starting data sync from {MQTT_BROKER} for {timeout} seconds...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(timeout) # 等待接收消息
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"[MQTT_SYNC] Sync finished. Received {len(_sync_messages)} messages.")

    # 将同步到的消息写入日志文件
    if _sync_messages:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            for entry in _sync_messages:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[MQTT_SYNC] Appended {len(_sync_messages)} messages to log file: {LOG_FILE_PATH}")


def publish_command(device_id: str, action: str, value: Any):
    """连接，发布命令，然后断开。 (此函数保持不变)"""
    payload = {
        "command_id": f"cmd_{device_id.replace('_','')}_{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:3]}",
        "action": action,
        "value": value,
        "timestamp": int(time.time())
    }
    topic = f"{MQTT_CONTROL_TOPIC}/{device_id}"
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{MQTT_CLIENT_ID_BASE}_pub_{uuid.uuid4().hex[:4]}")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        result, mid = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=MQTT_PUBLISH_QOS)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise Exception(f"Failed to publish command. MQTT Error Code: {result}")
        print(f"[MQTT_PUB] Successfully published to {topic}: {payload}")
    finally:
        client.disconnect()


def get_latest_device_statuses(online_only: bool = False) -> List[Dict[str, Any]]:
    """从日志文件中读取每个设备的最新状态。"""
    _sync_data_from_mqtt() # *** 在读取前执行同步 ***

    latest_statuses: Dict[str, Dict[str, Any]] = {}
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    device_id = log_entry.get("device_id")
                    if device_id:
                        latest_statuses[device_id] = log_entry.get("device_data", {})
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []

    result_list = []
    for data in latest_statuses.values():
        is_online = data.get("status", {}).get("online", False)
        if online_only and not is_online:
            continue
        
        result_list.append({
            "device_id": data.get("device_id"),
            "device_description": data.get("device_description", "N/A"),
            "device_type": data.get("device_type"),
            "last_reported_time": data.get("timestamp", "N/A"),
            "status_summary": data.get("status", {}).get("text_data", "N/A")
        })
        
    return result_list

def get_device_status(device_id: str) -> Optional[Dict[str, Any]]:
    """从日志文件中查找特定设备的最新状态。"""
    _sync_data_from_mqtt() # *** 在读取前执行同步 ***

    latest_status: Optional[Dict[str, Any]] = None
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    if log_entry.get("device_id") == device_id:
                        latest_status = log_entry.get("device_data", {})
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return None
        
    return latest_status