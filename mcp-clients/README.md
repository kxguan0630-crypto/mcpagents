MCP服务搭建
１. 创建虚拟环境
python3.11 -m venv weiyunmcpenv

２. 激活虚拟环境
source weiyunmcpenv/bin/activate

３.安装必要的库
pip3 install httpx openai python-dotenv PyJWT quart mcp quart-cors tenacity pydantic requests redis

4.设置环境变量
　本地开发环境　export MCP_ENV=development
　测试环境　export MCP_ENV=staging
生产环境　export MCP_ENV=production

5.git部署项目
mcpserver
git clone ssh:git@nj.gitlab.ui.delant.net.cn"">//git@nj.gitlab.ui.delant.net.cn:6000/weiyun/weiyun-mcp-servers.git
切换到feature/R633

mcpclient
git clone ssh:git@nj.gitlab.ui.delant.net.cn"">//git@nj.gitlab.ui.delant.net.cn:6000/weiyun/weiyun-mcp-clients.git
切换到feature/R633 启动client
python3.11 chatapi_case_mcp_client.py –port 分配的端口号