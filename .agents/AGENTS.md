# Project Rules for AI Workspace

## Environment Specification
- 本项目指定的 Conda 环境名称为 `ai` (`conda activate ai`)。
- 在运行 Python 脚本、安装依赖或进行代码验证时，请统一使用 `ai` 环境：
  - Conda 环境激活命令：`conda activate ai`
  - Python 可执行文件路径：`C:\Users\10302\miniconda3\envs\ai\python.exe`
  - uv 包管理器路径：`C:\Users\10302\miniconda3\envs\ai\Scripts\uv.exe`

## GPU Memory & Process Management
- 在进行 GPU / 向量模型测试或脚本运行后，必须主动检查并确保 GPU 显存与后台进程已被及时清理和释放。
- 测试或临时脚本完成后，若产生残留的 Python 进程或高显存占用，必须主动终止僵尸进程或释放缓存，切勿等显存溢出或爆满。

## Delete Operation Safety & Confirmation (删除操作确认规则)
- 在执行任何文件、目录、代码或数据记录的**删除操作**（包括但不限于命令行删除 `Remove-Item` / `rm` / `git rm`、代码删除文件、删除数据库记录等）前，必须向用户清晰列出拟删除的目标列表，并主动询问以获得用户的明确许可。
- 严禁私自或未经确认隐式执行任何删除指令；在未收到用户确认回复前，切勿继续执行删除动作。
## Git Commit Specification (Git 提交规范)
- 在执行 Git 提交（git commit）时，提交描述信息（commit message）必须统一使用中文描述。

## Git Security & Repository Specification (Git 安全与版本控制规范)
- 允许提交 `.env` 环境变量文件到 Git 仓库（用于云端备份与防丢失，请注意保持仓库安全与私密性）。
- `.agents` 目录及项目规则配置（如 `AGENTS.md`）属于通用仓库规范，必须正常提交并上传至 Git 远程仓库，以防配置丢失并保障协同协同一致。

