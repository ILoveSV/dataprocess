# File Name: database.py
# Project Name: dataprocess
# Description: SQLite数据库初始化和表结构定义
import sqlite3
import logging
from pathlib import Path
import yaml
import os

logger = logging.getLogger('data_process')

def load_config():
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config


class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_path=None):
        """
        初始化数据库管理器
        Args:
            db_path (str): 数据库文件路径，如果为None则使用配置文件中的路径或默认路径
        """
        # 加载配置文件
        config = load_config()
        if db_path is not None:
            # 优先使用传入的路径
            self.db_path = Path(db_path)
        elif config and "database_path" in config:
            # 使用配置文件中的路径
            self.db_path = Path(config["database_path"])
        else:
            # 使用默认路径：项目根目录下的data文件夹
            project_root = Path(__file__).resolve().parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            self.db_path = data_dir / "lab_data.db"
            
            # 记录警告
            logger.warning("未在配置文件中找到database_path，使用默认路径")
        
        # 确保数据库文件目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection = None
        self.cursor = None
        
        logger.info(f"数据库文件路径: {self.db_path}")

    def connect(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()
            self.cursor.execute("PRAGMA journal_mode=WAL")  # 写前日志模式，提高并发性能
            self.cursor.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和数据安全
            self.cursor.execute("PRAGMA cache_size=-64000")  # 设置缓存大小
            self.cursor.execute("PRAGMA temp_store=MEMORY")  # 临时表存储在内存中
            return True
        except sqlite3.Error as e:
            logger.error(f"连接数据库失败: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()

    def initialize_database(self):
        if not self.connect():
            return False
        try:
            self._create_experiments_table()
            self._create_tdms_files_table()
            self._create_time_domain_table()
            self._create_frequency_domain_table()
            self._create_incremental_frequency_table()
            self._create_indexes()
            self.connection.commit()
            logger.info("数据库初始化完成，所有表结构已创建")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            self.connection.rollback()
            return False
        finally:
            self.disconnect()

    def _create_experiments_table(self):
        """创建实验组表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_name TEXT NOT NULL,
            folder_path TEXT NOT NULL,
            description TEXT,
            created_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.cursor.execute(create_table_sql)

    def _create_tdms_files_table(self):
        """创建TDMS文件表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tdms_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            start_timestamp TEXT NOT NULL,
            file_size INTEGER,
            channel_count INTEGER DEFAULT 16,
            data_points INTEGER DEFAULT 30000,
            sampling_rate REAL DEFAULT 500000,
            file_path TEXT,
            created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
        )
        """
        self.cursor.execute(create_table_sql)

    def _create_time_domain_table(self):
        """创建时域数据表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS time_domain_data (
            data_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            time_index INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            channel1 REAL, channel2 REAL, channel3 REAL, channel4 REAL,
            channel5 REAL, channel6 REAL, channel7 REAL, channel8 REAL,
            channel9 REAL, channel10 REAL, channel11 REAL, channel12 REAL,
            channel13 REAL, channel14 REAL, channel15 REAL, channel16 REAL,
            FOREIGN KEY (file_id) REFERENCES tdms_files(file_id)
        )
        """
        self.cursor.execute(create_table_sql)

    def _create_frequency_domain_table(self):
        """创建频域数据表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS frequency_domain_data (
            freq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            frequency REAL NOT NULL,
            amplitude1 REAL, phase1 REAL,
            amplitude2 REAL, phase2 REAL,
            amplitude3 REAL, phase3 REAL,
            amplitude4 REAL, phase4 REAL,
            amplitude5 REAL, phase5 REAL,
            amplitude6 REAL, phase6 REAL,
            amplitude7 REAL, phase7 REAL,
            amplitude8 REAL, phase8 REAL,
            amplitude9 REAL, phase9 REAL,
            amplitude10 REAL, phase10 REAL,
            amplitude11 REAL, phase11 REAL,
            amplitude12 REAL, phase12 REAL,
            amplitude13 REAL, phase13 REAL,
            amplitude14 REAL, phase14 REAL,
            amplitude15 REAL, phase15 REAL,
            amplitude16 REAL, phase16 REAL,
            FOREIGN KEY (file_id) REFERENCES tdms_files(file_id)
        )
        """
        self.cursor.execute(create_table_sql)

    def _create_incremental_frequency_table(self):
        """创建增量合并频域数据表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS incremental_frequency_data (
            inc_freq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            incremental_step INTEGER NOT NULL,
            files_merged_count INTEGER NOT NULL,
            frequency REAL NOT NULL,
            amplitude1 REAL, phase1 REAL,
            amplitude2 REAL, phase2 REAL,
            amplitude3 REAL, phase3 REAL,
            amplitude4 REAL, phase4 REAL,
            amplitude5 REAL, phase5 REAL,
            amplitude6 REAL, phase6 REAL,
            amplitude7 REAL, phase7 REAL,
            amplitude8 REAL, phase8 REAL,
            amplitude9 REAL, phase9 REAL,
            amplitude10 REAL, phase10 REAL,
            amplitude11 REAL, phase11 REAL,
            amplitude12 REAL, phase12 REAL,
            amplitude13 REAL, phase13 REAL,
            amplitude14 REAL, phase14 REAL,
            amplitude15 REAL, phase15 REAL,
            amplitude16 REAL, phase16 REAL,
            created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
        )
        """
        self.cursor.execute(create_table_sql)

    def _create_indexes(self):
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_time_domain_file_time ON time_domain_data(file_id, time_index)",
            "CREATE INDEX IF NOT EXISTS idx_time_domain_timestamp ON time_domain_data(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_freq_domain_file_freq ON frequency_domain_data(file_id, frequency)",
            "CREATE INDEX IF NOT EXISTS idx_freq_domain_frequency ON frequency_domain_data(frequency)",
            "CREATE INDEX IF NOT EXISTS idx_inc_freq_experiment_step ON incremental_frequency_data(experiment_id, incremental_step)",
            "CREATE INDEX IF NOT EXISTS idx_inc_freq_frequency ON incremental_frequency_data(frequency)",
            "CREATE INDEX IF NOT EXISTS idx_tdms_files_experiment ON tdms_files(experiment_id)",
            "CREATE INDEX IF NOT EXISTS idx_tdms_files_filename ON tdms_files(filename)",
            "CREATE INDEX IF NOT EXISTS idx_tdms_files_timestamp ON tdms_files(start_timestamp)"
        ]
        
        for index_sql in indexes:
            self.cursor.execute(index_sql)

    def check_tables_exist(self):

        if not self.connect():
            logger.error("无法连接数据库，检查表状态失败")
            return {}
        try:
            tables = [
            'experiments', 'tdms_files', 'time_domain_data',
            'frequency_domain_data', 'incremental_frequency_data'
            ]
            status = {}
            for table in tables:
                self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                exists = self.cursor.fetchone() is not None
                status[table] = exists
                status_text = "✓ 存在" if exists else "✗ 不存在"
                logger.info(f"  表 {table}: {status_text}")
            existing_tables = sum(status.values())
            total_tables = len(tables)
            logger.info(f"表状态检查完成: {existing_tables}/{total_tables} 个表存在")
            return status
        except sqlite3.Error as e:
            logger.error(f"检查表状态失败: {e}")
            return {}
        finally:
            self.disconnect()

    def get_database_info(self):

        if not self.connect():
           logger.error("无法连接数据库，获取数据库信息失败")
           return {}
        try:
          info = {
               'database_path': str(self.db_path),
              'database_size': self.db_path.stat().st_size if self.db_path.exists() else 0
          }
          tables = ['experiments', 'tdms_files', 'time_domain_data', 
                'frequency_domain_data', 'incremental_frequency_data']
          total_records = 0
          for table in tables:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                info[f'{table}_count'] = count
                total_records += count
                logger.info(f"  表 {table}: {count} 条记录")
          logger.info(f"数据库路径: {info['database_path']}")
          logger.info(f"数据库大小: {self._format_file_size(info['database_size'])}")
          logger.info(f"总记录数: {total_records} 条")
          return info
        except sqlite3.Error as e:
            logger.error(f"获取数据库信息失败: {e}")
            return {}
        finally:
            self.disconnect()

    def _format_file_size(self, size_bytes):

        if size_bytes == 0:
           return "0 B"
    
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
         size_bytes /= 1024.0
         i += 1
    
        return f"{size_bytes:.2f} {size_names[i]}"
    
def main():
    db_manager = DatabaseManager()
    db_manager.initialize_database()
    db_manager.check_tables_exist()
    db_manager.get_database_info()

if __name__ == "__main__":
    main()