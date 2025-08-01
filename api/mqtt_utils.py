# api/mqtt_utils.py
import os
import json
import time
import uuid
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, List

# --- 从环境变量读取配置 ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_CLIENT_ID_BASE = os.getenv("MQTT_CLIENT_ID", f"dify_serverless_bridge_{uuid.uuid4().hex[:6]}")
MQTT_DATA_TOPIC = os.getenv("MQTT_DATA_TOPIC", "smarthome/data")
MQTT_CONTROL_TOPIC = os.getenv("MQTT_CONTROL_TOPIC", "smarthome/control")
MQTT_PUBLISH_QOS = int(os.getenv("MQTT_PUBLISH_QOS", 1))
LOG_FILE_PATH = os.getenv("DEVICE_LOG_FILE", "/tmp/device_data_log.jsonl") # 在Vercel中使用 /tmp 目录

# 确保日志文件所在的目录存在
log_dir = os.path.dirname(LOG_FILE_PATH)
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)
if not os.path.exists(LOG_FILE_PATH):
    # 创建一个空的日志文件，以防第一次读取时失败
    with open(LOG_FILE_PATH, 'w') as f:
        pass


def publish_command(device_id: str, action: str, value: Any):
    """连接，发布命令，然后断开。"""
    payload = {
        "command_id": f"cmd_{device_id.replace('_','')}_{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:3]}",
        "action": action,
        "value": value,
        "timestamp": int(time.time())
    }
    topic = f"{MQTT_CONTROL_TOPIC}/{device_id}"
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{MQTT_CLIENT_ID_BASE}_{uuid.uuid4().hex[:4]}")
    
    try:
        print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT} to publish command...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        result, mid = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=MQTT_PUBLISH_QOS)
        
        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Successfully published to {topic}: {payload}")
        else:
            raise Exception(f"Failed to publish command. MQTT Error Code: {result}")
            
        # 等待消息发出
        time.sleep(0.5)

    finally:
        client.loop_stop()
        client.disconnect()
        print("[MQTT] Disconnected after publishing.")


def get_latest_device_statuses(online_only: bool = False) -> List[Dict[str, Any]]:
    """从日志文件中读取每个设备的最新状态。"""
    latest_statuses: Dict[str, Dict[str, Any]] = {}
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    device_id = log_entry.get("device_id")
                    if device_id:
                        # 只保留最新的记录
                        latest_statuses[device_id] = log_entry.get("device_data", {})
                except json.JSONDecodeError:
                    print(f"[LOG_READER] Skipping corrupted line: {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"[LOG_READER] Log file not found at {LOG_FILE_PATH}. Returning empty list.")
        return []

    # 筛选并格式化输出
    result_list = []
    for device_id, data in latest_statuses.items():
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