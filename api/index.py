# api/index.py
import os
import time
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# 导入为无服务器环境重构的 MQTT 工具函数
from . import mqtt_utils

# 加载环境变量 (在Vercel环境中，变量在项目设置中配置)
load_dotenv()

# 初始化 Flask 应用
app = Flask(__name__)

# 从环境变量读取配置
API_PREFIX = os.getenv("API_PREFIX", "/api")
MQTT_WAIT_TIMEOUT = int(os.getenv("MQTT_WAIT_TIMEOUT", 5))

# --- API 路由实现 ---

@app.route(f"{API_PREFIX}/devices", methods=['GET'])
def list_online_devices():
    """列出所有在线设备"""
    try:
        online_devices = mqtt_utils.get_latest_device_statuses(online_only=True)
        return jsonify(online_devices), 200
    except Exception as e:
        print(f"[ERROR] list_online_devices: {e}")
        return jsonify({"error": "Failed to retrieve device list.", "details": str(e)}), 500

@app.route(f"{API_PREFIX}/devices/<string:device_id>/status", methods=['GET'])
def get_device_status(device_id: str):
    """获取指定设备的最新状态"""
    try:
        status = mqtt_utils.get_device_status(device_id)
        if status:
            return jsonify(status), 200
        else:
            return jsonify({"error": f"Device '{device_id}' not found."}), 404
    except Exception as e:
        print(f"[ERROR] get_device_status for {device_id}: {e}")
        return jsonify({"error": "Failed to retrieve device status.", "details": str(e)}), 500

@app.route(f"{API_PREFIX}/devices/<string:device_id>/command", methods=['POST'])
def control_device(device_id: str):
    """向指定设备发送控制命令"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    action = data.get("action")
    value = data.get("value")

    if not action:
        return jsonify({"error": "Missing 'action' in request body"}), 400

    print(f"[API] Received command '{action}' for {device_id} with value: {value}")

    try:
        # 发布命令
        mqtt_utils.publish_command(device_id, action, value)

        # 等待设备响应并更新日志
        time.sleep(MQTT_WAIT_TIMEOUT) # 简单延时等待设备上报

        # 从日志中获取最新的状态作为响应
        new_status = mqtt_utils.get_device_status(device_id)

        if new_status:
            # 检查是否有命令执行失败的ACK
            if 'command_ack' in new_status and new_status['command_ack'].get('success') is False:
                 print(f"[API] Command resulted in a failure ACK for {device_id}.")
                 return jsonify(new_status), 400 # 如果设备明确返回失败，则返回400错误

            print(f"[API] Command successful. Returning updated status for {device_id}.")
            return jsonify(new_status), 200
        else:
             return jsonify({
                "error": f"Command sent, but no status update found for device '{device_id}' after {MQTT_WAIT_TIMEOUT} seconds. The device might be offline or did not respond."
            }), 408

    except Exception as e:
        print(f"[ERROR] control_device for {device_id}: {e}")
        return jsonify({"error": "An internal error occurred while controlling the device.", "details": str(e)}), 500

# Vercel 会将所有请求重定向到这个 'app' 对象
# 本地测试时，可以取消以下代码的注释来运行一个本地开发服务器
# if __name__ == '__main__':
#     app.run(debug=True, port=8080)