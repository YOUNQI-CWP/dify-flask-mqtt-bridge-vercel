# Dify-Serverless-MQTT-Bridge：智能家居智能体桥接器 (Vercel 云函数版)

这是一个将 `Dify-Flask-MQTT-Bridge` 重构为在 Vercel 上运行的无服务器 (Serverless) 版本的项目。**采用 Vercel KV (Redis) 和 Vercel Cron Jobs 实现，彻底解决了在无服务器环境中的状态持久化和数据同步问题，是稳定可靠的生产级方案。**

## 核心架构

* **Vercel KV (Redis) 数据库**: 作为设备状态的持久化存储中心。
* **Vercel Cron Job (定时任务)**: 每分钟自动运行一个后台函数。
* **同步函数 (`/api/crons/sync_mqtt`)**: 由 Cron Job 触发，负责连接 MQTT Broker，监听设备消息，并将最新的状态实时写入 Vercel KV。
* **API 函数 (`/api/index.py`)**: 面向 Dify 的公开接口，直接从 Vercel KV 读取数据，实现快速响应。

## Vercel 一键部署指南

### 第1步：准备工作
1.  **一个 GitHub 账号**
2.  **一个 Vercel 账号** (可使用 GitHub 免费注册)

### 第2步：Fork 并部署项目
1.  访问此项目主页，点击 **"Fork"** 按钮，将项目复制到你自己的 GitHub 账号下。
2.  登录 Vercel，进入 Dashboard，点击 **"Add New..."** -> **"Project"**。
3.  选择你刚刚 Fork 的 Git 仓库并导入。

### 第3步：连接 Vercel KV 数据库
1.  在 Vercel 项目设置页面，切换到 **"Storage"** 标签页。
2.  找到 **KV (Serverless Redis)**，点击 **"Connect Store"**。
3.  选择一个区域，然后点击 **"Create and Connect"**。
4.  Vercel 会自动创建一个 Redis 数据库，并将其连接到你的项目，同时会自动在环境变量中注入 `KV_URL` 等连接凭证。**这是最关键的一步。**

### 第4步：配置环境变量
回到项目的 **"Settings"** -> **"Environment Variables"** 页面。Vercel KV 的变量应该已经存在了。你还需要添加以下 MQTT 相关的变量：

| 变量名 | 示例值 | 描述 |
| --- | --- | --- |
| `MQTT_BROKER` | `broker.emqx.io` | 你的 MQTT Broker 地址。 |
| `MQTT_PORT` | `1883` | MQTT Broker 端口。 |
| `MQTT_DATA_TOPIC` | `smarthome/data`| 设备上报数据的话题。 |
| `MQTT_CONTROL_TOPIC`|`smarthome/control`| 设备控制命令话题前缀。|
| `MQTT_WAIT_TIMEOUT` | `3` | 发送控制命令后等待设备响应的秒数。 |

### 第5步：触发部署
完成以上配置后，回到项目的 **"Deployments"** 页面，找到最新的部署条目，点击右侧的 "..." 菜单，选择 **"Redeploy"** 来应用所有新的配置。

部署完成后，Cron Job 将在后台自动开始运行，每分钟同步一次数据到你的 Vercel KV 数据库中。

### 第6步：配置 Dify 工具
1.  在本地，打开 `openapi.yaml` 文件。
2.  将 `servers.url` 修改为你的 Vercel **部署 URL** (例如: `https://your-project.vercel.app/api`)。
3.  将修改后的 `openapi.yaml` 完整内容粘贴到 Dify 的 OpenAPI 工具配置中。

现在，你的 Dify 智能体就可以通过这个稳定、可靠的无服务器架构与你的物联网设备进行交互了！