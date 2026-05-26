"""项目启动入口——直接 python run.py 启动服务。"""

import uvicorn
from app.config import config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info",
    )
