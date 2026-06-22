import os
import struct
import pyodbc
from tqdm import tqdm

# ==========================================
# KONFIGURASI DATABASE (Windows Authentication)
# ==========================================
DB_CONFIG = {
    'server': 'DESKTOP-57UNT30',
    'database': 'DragonNest_DNT',
    'driver': '{ODBC Driver 17 for SQL Server}'
}

DNT_FOLDER = r'D:\Server\Gameres\resource\ext'

def get_connection(use_master=False):
    """Mendapatkan koneksi menggunakan Windows Authentication."""
    target_db = 'master' if use_master else DB_CONFIG['database']
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={target_db};"
        "Trusted_Connection=yes;"        # Menggunakan Akun Windows
        "TrustServerCertificate=yes;"    # Mengabaikan verifikasi sertifikat SSL
    )
    return pyodbc.connect(conn_str, autocommit=use_master)

def ensure_database_exists():
    """Mengecek apakah database ada, jika tidak, maka dibuat menggunakan Windows Auth."""
    try:
        # Koneksi ke 'master' untuk mengecek/membuat database
        conn = get_connection(use_master=True)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{DB_CONFIG['database']}'")
        if not cursor.fetchone():
            print(f"Database '{DB_CONFIG['database']}' tidak ditemukan. Membuat database baru...")
            cursor.execute(f"CREATE DATABASE [{DB_CONFIG['database']}]")
            print("Database berhasil dibuat.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error saat mengecek/membuat database: {e}")
        print("Pastikan akun Windows Anda memiliki hak akses 'sysadmin' di SQL Server.")
        exit()

def setup_metadata_table(cursor):
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dnt_metadata')
        CREATE TABLE dnt_metadata (
            id INT IDENTITY(1,1) PRIMARY KEY,
            file_name NVARCHAR(255),
            table_name NVARCHAR(255),
            column_order INT,
            column_name NVARCHAR(255),
            column_type INT,
            version SMALLINT,
            reversion_len SMALLINT
        )
    """)

def parse_dnt(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    offset = 0
    version = struct.unpack_from('<h', data, offset)[0]; offset += 2
    reversion_len = struct.unpack_from('<h', data, offset)[0]; offset += 2
    fild_count = struct.unpack_from('<h', data, offset)[0]; offset += 2
    data_count = struct.unpack_from('<i', data, offset)[0]; offset += 4
    
    columns = []
    for _ in range(fild_count):
        name_len = struct.unpack_from('<h', data, offset)[0]; offset += 2
        name = data[offset:offset+name_len].decode('utf-8', errors='replace'); offset += name_len
        col_type = struct.unpack_from('<B', data, offset)[0]; offset += 1
        columns.append({'name': name, 'type': col_type})
        
    rows = []
    for _ in range(data_count):
        row_id = struct.unpack_from('<I', data, offset)[0]; offset += 4
        row = [row_id]
        for col in columns:
            if col['type'] == 0: val = struct.unpack_from('<B', data, offset)[0]; offset += 1
            elif col['type'] == 1:
                str_len = struct.unpack_from('<h', data, offset)[0]; offset += 2
                val = data[offset:offset+str_len].decode('utf-8', errors='replace') if str_len > 0 else ''
                offset += str_len
            elif col['type'] in [2, 3]: val = struct.unpack_from('<i', data, offset)[0]; offset += 4
            elif col['type'] in [4, 5]: val = struct.unpack_from('<f', data, offset)[0]; offset += 4
            else: val = None
            row.append(val)
        rows.append(tuple(row))
    return version, reversion_len, columns, rows

def get_sql_type(col_type):
    if col_type == 0: return 'TINYINT'
    if col_type == 1: return 'NVARCHAR(MAX)'
    if col_type == 2: return 'BIT'
    if col_type == 3: return 'INT'
    if col_type == 4: return 'NUMERIC(30, 10)'
    if col_type == 5: return 'FLOAT'
    return 'NVARCHAR(MAX)'

def process_file(conn, file_path):
    file_name = os.path.basename(file_path)
    table_name = file_name.replace('.dnt', '').replace('.', '_').replace('-', '_')
    cursor = conn.cursor()
    version, reversion_len, columns, rows = parse_dnt(file_path)
    
    cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE [{table_name}]")
    cols_def = ["[RowID] INT NOT NULL"]
    for col in columns:
        cols_def.append(f"[{col['name']}] {get_sql_type(col['type'])}")
    cursor.execute(f"CREATE TABLE [{table_name}] ({', '.join(cols_def)})")
    
    for idx, col in enumerate(columns):
        cursor.execute("INSERT INTO dnt_metadata (file_name, table_name, column_order, column_name, column_type, version, reversion_len) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                       (file_name, table_name, idx, col['name'], col['type'], version, reversion_len))
        
    if rows:
        col_names = ['[RowID]'] + [f"[{c['name']}]" for c in columns]
        insert_sql = f"INSERT INTO [{table_name}] ({','.join(col_names)}) VALUES ({','.join(['?'] * len(col_names))})"
        cursor.fast_executemany = True 
        cursor.executemany(insert_sql, rows)
    
    conn.commit()

def main():
    ensure_database_exists()
    print("Connecting to database...")
    conn = get_connection(use_master=False)
    setup_metadata_table(conn.cursor())
    
    dnt_files = [os.path.join(DNT_FOLDER, f) for f in os.listdir(DNT_FOLDER) if f.lower().endswith('.dnt')]
    if not dnt_files:
        print(f"Tidak ada file .dnt di {DNT_FOLDER}")
        return

    print(f"Memproses {len(dnt_files)} file...")
    for file_path in tqdm(dnt_files):
        try:
            process_file(conn, file_path)
        except Exception as e:
            print(f"\nError di {os.path.basename(file_path)}: {e}")
            conn.rollback()
            
    conn.close()
    print("Selesai.")

if __name__ == '__main__':
    main()