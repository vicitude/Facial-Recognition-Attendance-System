"""Connect to MySQL and list actual tables."""
import os
os.chdir(r"d:\yol\yolov8_facenet")

# Add user site-packages to path (where pymysql was installed)
import sys
user_site = r"C:\Users\will vicissitude\AppData\Roaming\Python\Python312\site-packages"
if os.path.isdir(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Mock heavy modules
import types
for n in ['torch', 'torch.nn', 'torchvision', 'matplotlib', 'matplotlib.pyplot',
          'facenet', 'facenet.facenet']:
    sys.modules[n] = types.ModuleType(n)

import pymysql

# Read INI
import configparser
parser = configparser.ConfigParser()
parser.read(r"d:\yol\yolov8_facenet\attendance_config.ini", encoding="utf-8")

host = parser.get("database", "host")
port = parser.getint("database", "port")
user = parser.get("database", "user")
password = parser.get("database", "password")
database = parser.get("database", "database")

out = []
out.append(f"Connecting to MySQL {host}:{port} as {user}")
out.append(f"Target database: {database}")
out.append("")

try:
    conn = pymysql.connect(host=host, port=port, user=user,
                           password=password, database=database,
                           charset="utf8mb4")
    with conn.cursor() as cur:
        # List all tables
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        out.append(f"=== Tables in `{database}` ===")
        if not tables:
            out.append("(none)")
        for (t,) in tables:
            out.append(f"  - {t}")

        out.append("")
        out.append("=== Row counts ===")
        for (t,) in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                cnt = cur.fetchone()[0]
                out.append(f"  - {t}: {cnt} rows")
            except Exception as e:
                out.append(f"  - {t}: ERR {e}")

        # Check if CheckRecord is mapped to 'checkrecord' or 'check_records'
        out.append("")
        out.append("=== Expected peewee auto table names ===")
        out.append("  - Admin -> 'admin'")
        out.append("  - Schedule -> 'schedule'")
        out.append("  - Employee -> 'employee'")
        out.append("  - CheckRecord -> 'checkrecord'")
    conn.close()
except Exception as e:
    out.append(f"ERR: {e}")

# Write to file
with open(r"d:\yol\yolov8_facenet\db_inspect.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

# Also print
for line in out:
    print(line)
