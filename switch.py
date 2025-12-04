import json

import consul
import argparse
import os
import sys
import yaml
import re
from typing import Dict, List, Optional, Tuple

# --- 确定脚本目录 ---
# 无论脚本从哪里运行，它都会基于自身所在的目录来查找相对路径的配置。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 配置区 ---
# 配置文件和环境变量文件所在的本地根目录 (相对于脚本自身的位置)
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "templates")
VARIABLE_DIR = os.path.join(SCRIPT_DIR, "variable")
# 用户配置目录 (用于备用查找)
USER_CONFIG_ROOT = os.path.expanduser("~/.config/consul")
USER_TEMPLATE_DIR = os.path.join(USER_CONFIG_ROOT, "templates")
USER_VARIABLE_DIR = os.path.join(USER_CONFIG_ROOT, "variable")

CONSUL_HOST = "127.0.0.1"
CONSUL_PORT = 8500
CONSUL_TOKEN: Optional[str] = None


# --- 辅助函数 ---

def find_file_in_paths(filenames: List[str], paths: List[str]) -> Optional[str]:
    """
    在给定的路径列表中查找文件，找到第一个就返回其完整路径。
    """
    for filename in filenames:
        for path in paths:
            full_path = os.path.join(path, filename)

            if os.path.exists(full_path):
                return full_path
    return None


def load_env_variables(env_name: str) -> Dict[str, str]:
    """
    加载指定环境名对应的 .env 文件。
    查找顺序：1. 脚本所在的 templates/ 目录 2. ~/.templates/consul/
    """
    env_files = [
        f"{env_name}.yml",
        f"{env_name}.yaml",
    ]
    env_vars = {}
    env_search_paths = [
        VARIABLE_DIR,
        USER_VARIABLE_DIR
    ]


    env_path = find_file_in_paths(env_files, env_search_paths)

    if not env_path:
        print(f"错误: 未找到变量文件 {';'.join(env_files)}。已在以下目录查找:", file=sys.stderr)
        for env_file in env_files:
            for path in env_search_paths:
                print(f" - {os.path.join(path, env_file)}", file=sys.stderr)
        sys.exit(1)

    print(f"-> 正在加载变量: {env_path}")

    with open(env_path, 'r') as f:
        var_files = yaml.safe_load(f)
        for key in var_files:
            env_vars[key.strip()] = json.dumps(var_files[key])
    return env_vars



def find_config_files() -> Tuple[List[str], str]:
    print('TEMPLATE_DIR',TEMPLATE_DIR)
    """
    递归查找配置文件。
    查找优先级：1. SCRIPT_CONFIG_DIR (如果存在)
    2. USER_CONFIG_DIR (如果 SCRIPT 不存在)

    返回: (配置文件绝对路径列表, 实际找到配置文件的根目录)
    """
    config_files = []
    active_root = ""

    # 1. 严格检查脚本所在位置的 templates 文件夹是否存在
    if os.path.isdir(TEMPLATE_DIR):
        active_root = TEMPLATE_DIR
        print(f"-> 发现脚本配置目录: {TEMPLATE_DIR}")

    # 2. 如果脚本配置目录不存在，则检查用户配置目录
    elif os.path.isdir(USER_TEMPLATE_DIR):
        active_root = USER_TEMPLATE_DIR
        print(f"-> 脚本配置目录不存在，使用用户配置目录: {USER_TEMPLATE_DIR}")

    else:
        # 两个目录都不存在
        return [], ""

        # 在确定的根目录 active_root 中递归查找 .yml 文件
    for dirpath, _, filenames in os.walk(active_root):
        for filename in filenames:
            if filename.endswith(('.yml', '.yaml')):
                config_files.append(os.path.join(dirpath, filename))

    return config_files, active_root


# --- 核心替换和上传逻辑 (process_and_upload) ---

def process_and_upload(config_files: List[str], config_root: str, env_vars: Dict[str, str], env_name: str):
    """
    处理配置文件，替换占位符，并将内容上传到 Consul。
    """
    try:
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT, token=CONSUL_TOKEN)
    except Exception as e:
        print(f"错误: 初始化 Consul 客户端失败: {e}", file=sys.stderr)
        sys.exit(1)

    processed_count = 0

    for file_path in config_files:
        # 1. 确定 Consul Key
        # 使用 CONFIG_ROOT 来计算相对路径，确保 Consul Key 的一致性
        relative_path = os.path.relpath(file_path, config_root)
        consul_key = os.path.splitext(relative_path)[0].replace(os.sep, '/')
        # full_consul_key = f"{env_name}/{consul_key}"
        full_consul_key = f"{consul_key}"

        print(f"\n--- 处理文件: {file_path} -> {full_consul_key} ---")

        # 2. 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
            continue

        # 3. 核心替换逻辑
        modified_content = content

        # 遍历所有环境变量，进行精确替换
        for key, value in env_vars.items():
            # 1. 无引号替换：port: ${DB_PORT}
            modified_content = modified_content.replace(f'${{{key}}}', value)

            # 2. 双引号替换：host: "${DB_HOST}"
            # modified_content = modified_content.replace(f'"${{{key}}}"', f'"{value}"')

            # 3. 单引号替换：username: '${DB_USER}'
            # modified_content = modified_content.replace(f"'${{{key}}}'", f"'{value}'")

        # 4. 检查未替换的占位符 (防止变量缺失)
        unreplaced = re.findall(r'\$\{([A-Z0-9_]+)\}', modified_content)
        if unreplaced:
            print(f"警告: 文件中存在未替换的变量: {', '.join(set(unreplaced))}", file=sys.stderr)

        # 5. 上传到 Consul
        try:
            yaml.safe_load(modified_content)
            print('full_consul_key:',full_consul_key)
            if c.kv.put(full_consul_key, modified_content.encode('utf-8')):
                print(f"✅ 成功上传到 Consul Key: {full_consul_key}")
                processed_count += 1
            else:
                print(f"❌ 上传到 Consul Key: {full_consul_key} 失败 (API 返回 False)。", file=sys.stderr)

        except yaml.YAMLError as e:
            print(f"❌ 警告: 替换后 YAML 格式错误，跳过上传。{e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ 上传到 Consul 失败: {e}", file=sys.stderr)

    print(f"\n--- 处理完成。共处理 {len(config_files)} 个文件，成功上传 {processed_count} 个。---")


def main():
    parser = argparse.ArgumentParser(
        description="本地配置文件动态替换并上传至 Consul 工具。"
    )
    parser.add_argument(
        "-env",
        type=str,
        required=False,
        help="指定环境名称 (例如: 'develop')。脚本将加载环境变量文件。"
    )

    args = parser.parse_args()
    args.env = args.env if args.env else 'local'

    # 1. 查找配置文件 (严格优先级查找)
    config_files, active_config_root = find_config_files()

    if not config_files:
        print("错误: 未在脚本目录下的 templates/ 目录或 ~/.templates/consul/templates/ 目录中找到任何 .yml 或 .yaml 文件。",
              file=sys.stderr)
        sys.exit(1)

    print(f"已找到 {len(config_files)} 个配置文件，使用根目录: {active_config_root}")

    # 2. 加载环境变量 (支持多路径查找)
    env_vars = load_env_variables(args.env)

    # 3. 处理并上传
    process_and_upload(config_files, active_config_root, env_vars, args.env)


if __name__ == "__main__":
    # 确保依赖已安装
    try:
        import yaml, consul
    except ImportError:
        print("错误: 缺少必要的库 (PyYAML 或 py-consul)。请运行 'pip install py-consul PyYAML'。", file=sys.stderr)
        sys.exit(1)

    main()