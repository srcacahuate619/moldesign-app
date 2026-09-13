import sqlite3

def main():
    conn = sqlite3.connect(r'd:\moldesign-build\backend\moldesign.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='targets';")
    row = cursor.fetchone()
    if row:
        print(row[0])
    else:
        print("Table 'targets' not found.")

if __name__ == '__main__':
    main()
