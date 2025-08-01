# Dify-Serverless-MQTT-Bridge：智能家居智能体桥接器 (Vercel 云函数版)

这是一个将 `Dify-Flask-MQTT-Bridge` 重构为在 Vercel 上运行的无服务器 (Serverless) 版本的项目。它实现了与原项目完全兼容的 API，但无需自行管理和维护服务器。

## 核心优势

* **零服务器运维**: 无需购买或配置服务器，Vercel 会自动处理所有基础设施。
* **按需付费**: 只在 API被调用时产生计算费用，没有请求时成本几乎为零。
* **自动扩缩容**: 面对高并发请求，Vercel 会自动扩展函数实例来应对。
* **一键部署**: 通过连接 GitHub 仓库，可以实现 Git Push 自动部署更新。

## Vercel 一键部署指南

### 第1步：准备工作

1.  **一个 GitHub 账号**
2.  **一个 Vercel 账号** (可以使用 GitHub 账号免费注册)
3.  **一个 EMQX MQTT Broker** (可以直接使用公共的 `broker.emqx.io` 进行测试)

### 第2步：Fork 并克隆代码仓库

1.  访问此项目的主页，点击右上角的 **"Fork"** 按钮，将项目复制到你自己的 GitHub 账号下。
2.  将你 Fork 后的仓库克隆到本地。

### 第3步：在 Vercel 上创建新项目

1.  登录 Vercel，进入你的 Dashboard。
2.  点击 **"Add New..."** -> **"Project"**。
3.  在 **"Import Git Repository"** 区域，选择你刚刚 Fork 的项目，点击 **"Import"**。
4.  Vercel 会自动识别这是一个 Python 项目，并使用 `vercel.json` 进行配置。

### 第4步：配置环境变量

在项目导入页面，展开 **"Environment Variables"** 部分。这里是配置服务所有参数的地方，其作用等同于原项目中的 `.env` 文件。

请添加以下变量 (根据你的需求修改值):

| 变量名                   | 示例值                          | 描述                                                              |
| ------------------------ | ------------------------------- | ----------------------------------------------------------------- |
| `MQTT_BROKER`            | `broker.emqx.io`                | 你的 MQTT Broker 地址。                                             |
| `MQTT_PORT`              | `1883`                          | MQTT Broker 端口。                                                  |
| `MQTT_CLIENT_ID`         | `dify_serverless_agent_prod`    | MQTT 客户端 ID，建议设置一个固定的 ID。                             |
| `MQTT_DATA_TOPIC`        | `smarthome/data`                | 设备上报数据的话题。                                              |
| `MQTT_CONTROL_TOPIC`     | `smarthome/control`             | 设备控制命令的话题前缀。                                          |
| `MQTT_WAIT_TIMEOUT`      | `3`                             | 发送控制命令后，等待设备响应的秒数。**建议设为2-4秒**。           |
| `DEVICE_LOG_FILE`        | `/tmp/device_data_log.jsonl`    | **(保持默认值)** 日志文件在 Vercel 临时文件系统中的路径。         |
| `API_PREFIX`             | `/api`                          | **(保持默认值)** API 的路由前缀。                                   |


### 第5步：部署

点击 **"Deploy"** 按钮。Vercel 会开始构建和部署你的应用。等待几分钟，部署完成后，Vercel 会提供一个类似 `my-project-name.vercel.app` 的公共 URL。

### 第6步：配置 Dify 工具

1.  在本地，打开 `openapi.yaml` 文件。
2.  找到 `servers` 部分，将其中的 `url` 修改为你从 Vercel获得的**部署 URL**，并确保结尾是 `/api`。
    ```yaml
    servers:
      - url: [https://your-deployment-name.vercel.app/api](https://your-deployment-name.vercel.app/api)
    ```
3.  登录 Dify，进入你的智能体应用，在“工具”设置中，添加一个 OpenAPI 工具。
4.  将修改后的 `openapi.yaml` 文件内容**完整粘贴**到 Dify 的 OpenAPI 配置框中。
5.  导入并启用工具。

现在，你的 Dify 智能体就可以通过 Vercel 云函数与你的物联网设备进行交互了！