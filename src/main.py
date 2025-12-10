# main.py
import os 
from .core import NewsAnalyzer
from .core.history import set_repository
from .utils.file import set_repository_for_file_utils
from .repository.pg_repo import PostgreSQLNewsRepository
from .repository.text_repo import TxtNewsRepository  # 可选：保留 txt 兼容

def main():
    try:
        db_url = os.environ["DATABASE_URL"]
        repo = PostgreSQLNewsRepository(db_url)

        # repo = TxtNewsRepository()  # 原始 .txt 实现（略）
        set_repository(repo)
        set_repository_for_file_utils(repo)
           
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\n参考项目文档进行正确配置")
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")
        raise

if __name__ == "__main__":
    main()