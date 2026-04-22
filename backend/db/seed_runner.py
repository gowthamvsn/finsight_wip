"""
Seed runner for FinSight database.
Pre-hashes passwords with bcrypt (pgcrypto not available on Azure PostgreSQL).
"""
import bcrypt
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

DB_URL = "postgresql://menouser:WEHealth123@wehealthdb.postgres.database.azure.com:5432/wealth_manage"

def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def run():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("Hashing passwords for 50 customers...")
    customer_passwords = {f"CUS-{i:04d}": hash_pw(f"Cust@{i:04d}") for i in range(1, 51)}
    print("Passwords hashed.")

    # ── CUSTOMERS ────────────────────────────────────────────────────────────
    print("Inserting customers...")
    customers = [
        ('CUS-0001','Arjun','Mehta','arjun.meh@gmail.com','moderate','premium','2019-03-14','2025-04-19 08:30:00+00','US',True,'2019-03-14 10:00:00+00'),
        ('CUS-0002','Sofia','Reyes','sofia.rey@outlook.com','aggressive','standard','2021-07-02','2025-04-18 14:22:00+00','UK',True,'2021-07-02 09:00:00+00'),
        ('CUS-0003','James','Okafor','james.oka@corp.com','conservative','premium','2017-11-28','2025-04-17 19:05:00+00','CA',True,'2017-11-28 08:00:00+00'),
        ('CUS-0004','Emily','Walsh','emily.wal@yahoo.com','moderate','standard','2020-05-10','2025-04-19 07:15:00+00','AU',True,'2020-05-10 11:00:00+00'),
        ('CUS-0005','Ravi','Patel','ravi.pate@icloud.com','aggressive','elite','2018-09-22','2025-04-19 06:44:00+00','IN',True,'2018-09-22 07:30:00+00'),
        ('CUS-0006','Mei','Zhang','mei.zhan@gmail.com','conservative','standard','2022-01-15','2025-04-16 12:00:00+00','SG',True,'2022-01-15 10:00:00+00'),
        ('CUS-0007','Carlos','Gomez','carlos.gom@outlook.com','moderate','premium','2020-11-03','2025-04-18 09:30:00+00','AE',True,'2020-11-03 09:00:00+00'),
        ('CUS-0008','Amara','Diallo','amara.dia@corp.com','aggressive','standard','2023-03-20','2025-04-17 16:45:00+00','DE',True,'2023-03-20 08:00:00+00'),
        ('CUS-0009','Liam','Turner','liam.turn@yahoo.com','conservative','elite','2016-08-11','2025-04-19 10:00:00+00','FR',True,'2016-08-11 07:00:00+00'),
        ('CUS-0010','Fatima','Hassan','fatima.has@icloud.com','moderate','standard','2021-12-05','2025-04-18 11:30:00+00','NL',True,'2021-12-05 09:30:00+00'),
        ('CUS-0011','Noah','Brown','noah.brow@gmail.com','aggressive','premium','2020-04-17','2025-04-15 08:00:00+00','US',True,'2020-04-17 10:00:00+00'),
        ('CUS-0012','Yuki','Tanaka','yuki.tana@outlook.com','conservative','standard','2019-07-30','2025-04-14 14:00:00+00','UK',True,'2019-07-30 09:00:00+00'),
        ('CUS-0013','Andre','Dubois','andre.dub@corp.com','moderate','elite','2018-02-14','2025-04-19 09:15:00+00','CA',True,'2018-02-14 08:00:00+00'),
        ('CUS-0014','Priya','Sharma','priya.sha@yahoo.com','aggressive','standard','2022-08-09','2025-04-18 17:00:00+00','AU',True,'2022-08-09 10:00:00+00'),
        ('CUS-0015','Ethan','Clark','ethan.cla@icloud.com','conservative','premium','2017-05-25','2025-04-17 20:30:00+00','IN',True,'2017-05-25 07:00:00+00'),
        ('CUS-0016','Layla','Al-Amin','layla.al@gmail.com','moderate','standard','2021-03-08','2025-04-16 13:00:00+00','SG',True,'2021-03-08 09:00:00+00'),
        ('CUS-0017','Omar','Nasser','omar.nass@outlook.com','aggressive','elite','2019-10-14','2025-04-19 07:45:00+00','AE',True,'2019-10-14 08:00:00+00'),
        ('CUS-0018','Chloe','Martin','chloe.mar@corp.com','conservative','standard','2023-01-22','2025-04-18 10:15:00+00','DE',True,'2023-01-22 10:00:00+00'),
        ('CUS-0019','Diego','Torres','diego.tor@yahoo.com','moderate','premium','2020-09-01','2025-04-17 15:00:00+00','FR',True,'2020-09-01 09:30:00+00'),
        ('CUS-0020','Aisha','Rahman','aisha.rah@icloud.com','aggressive','standard','2022-04-18','2025-04-19 08:00:00+00','NL',True,'2022-04-18 08:00:00+00'),
        ('CUS-0021','Lucas','Silva','lucas.sil@gmail.com','conservative','elite','2018-06-30','2025-04-18 09:00:00+00','US',True,'2018-06-30 07:30:00+00'),
        ('CUS-0022','Hana','Kimura','hana.kimu@outlook.com','moderate','standard','2021-11-11','2025-04-17 11:00:00+00','UK',True,'2021-11-11 10:00:00+00'),
        ('CUS-0023','Felix','Weber','felix.web@corp.com','aggressive','premium','2020-02-28','2025-04-16 16:00:00+00','CA',True,'2020-02-28 09:00:00+00'),
        ('CUS-0024','Nina','Petrov','nina.petr@yahoo.com','conservative','standard','2019-04-05','2025-04-15 14:30:00+00','AU',True,'2019-04-05 08:00:00+00'),
        ('CUS-0025','Sam','Jones','sam.jone@icloud.com','moderate','elite','2017-12-19','2025-04-19 10:30:00+00','IN',True,'2017-12-19 07:00:00+00'),
        ('CUS-0026','Zara','Khan','zara.khan@gmail.com','aggressive','standard','2022-07-07','2025-04-18 08:15:00+00','SG',True,'2022-07-07 09:30:00+00'),
        ('CUS-0027','Ben','Cohen','ben.cohe@outlook.com','conservative','premium','2020-03-15','2025-04-17 13:45:00+00','AE',True,'2020-03-15 10:00:00+00'),
        ('CUS-0028','Nora','Ivanova','nora.ivan@corp.com','moderate','standard','2021-09-23','2025-04-16 10:00:00+00','DE',True,'2021-09-23 09:00:00+00'),
        ('CUS-0029','Ivan','Novak','ivan.nova@yahoo.com','aggressive','elite','2018-01-07','2025-04-19 07:30:00+00','FR',True,'2018-01-07 08:00:00+00'),
        ('CUS-0030','Sara','Ali','sara.ali@icloud.com','conservative','standard','2023-05-14','2025-04-18 12:00:00+00','NL',True,'2023-05-14 10:00:00+00'),
        ('CUS-0031','Jack','Moore','jack.moor@gmail.com','moderate','premium','2019-08-26','2025-04-17 09:00:00+00','US',True,'2019-08-26 09:00:00+00'),
        ('CUS-0032','Mia','Flores','mia.flor@outlook.com','aggressive','standard','2021-06-13','2025-04-16 11:30:00+00','UK',True,'2021-06-13 10:00:00+00'),
        ('CUS-0033','Raj','Gupta','raj.gupt@corp.com','conservative','elite','2017-03-21','2025-04-19 08:45:00+00','CA',True,'2017-03-21 07:30:00+00'),
        ('CUS-0034','Leila','Mansour','leila.man@yahoo.com','moderate','standard','2022-10-04','2025-04-18 15:30:00+00','AU',True,'2022-10-04 09:00:00+00'),
        ('CUS-0035','Tom','Hill','tom.hill@icloud.com','aggressive','premium','2020-07-19','2025-04-17 18:00:00+00','IN',True,'2020-07-19 08:30:00+00'),
        ('CUS-0036','Yara','Sahin','yara.sahi@gmail.com','conservative','standard','2021-02-28','2025-04-16 09:30:00+00','SG',True,'2021-02-28 10:00:00+00'),
        ('CUS-0037','Ali','Hussein','ali.huss@outlook.com','moderate','elite','2019-05-17','2025-04-19 09:30:00+00','AE',True,'2019-05-17 09:00:00+00'),
        ('CUS-0038','Ines','Carvalho','ines.carv@corp.com','aggressive','standard','2023-02-09','2025-04-18 13:00:00+00','DE',True,'2023-02-09 08:00:00+00'),
        ('CUS-0039','Leo','Grant','leo.gran@yahoo.com','conservative','premium','2018-11-30','2025-04-17 10:15:00+00','FR',True,'2018-11-30 07:00:00+00'),
        ('CUS-0040','Maya','Singh','maya.sing@icloud.com','moderate','standard','2021-08-16','2025-04-16 14:30:00+00','NL',True,'2021-08-16 09:30:00+00'),
        ('CUS-0041','Max','Muller','max.mull@gmail.com','aggressive','elite','2020-01-25','2025-04-19 08:00:00+00','US',True,'2020-01-25 10:00:00+00'),
        ('CUS-0042','Rosa','Santos','rosa.sant@outlook.com','conservative','standard','2019-06-08','2025-04-18 07:45:00+00','UK',True,'2019-06-08 09:00:00+00'),
        ('CUS-0043','Kim','Park','kim.park@corp.com','moderate','premium','2022-03-27','2025-04-17 12:30:00+00','CA',True,'2022-03-27 08:30:00+00'),
        ('CUS-0044','Dan','Evans','dan.evan@yahoo.com','aggressive','standard','2020-10-12','2025-04-16 16:45:00+00','AU',True,'2020-10-12 09:00:00+00'),
        ('CUS-0045','Ava','Chen','ava.chen@icloud.com','conservative','elite','2017-07-04','2025-04-19 10:00:00+00','IN',True,'2017-07-04 07:30:00+00'),
        ('CUS-0046','Chen','Wu','chen.wu@gmail.com','moderate','standard','2021-04-20','2025-04-18 09:45:00+00','SG',True,'2021-04-20 10:00:00+00'),
        ('CUS-0047','Tara','Nair','tara.nair@outlook.com','aggressive','premium','2020-08-31','2025-04-17 14:00:00+00','AE',True,'2020-08-31 09:00:00+00'),
        ('CUS-0048','Erik','Larsson','erik.lars@corp.com','conservative','standard','2019-01-15','2025-04-16 10:30:00+00','DE',True,'2019-01-15 08:00:00+00'),
        ('CUS-0049','Lena','Bauer','lena.baue@yahoo.com','moderate','elite','2022-06-02','2025-04-19 09:00:00+00','FR',True,'2022-06-02 09:30:00+00'),
        ('CUS-0050','Jay','Das','jay.das@icloud.com','aggressive','standard','2021-10-28','2025-04-18 16:00:00+00','NL',True,'2021-10-28 10:00:00+00'),
    ]
    for c in customers:
        cid = c[0]
        pw_hash = customer_passwords[cid]
        cur.execute("""
            INSERT INTO customers
                (customer_id, first_name, last_name, email, password_hash,
                 risk_profile, advisor_tier, joined_date, last_login, country, is_active, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (c[0], c[1], c[2], c[3], pw_hash,
              c[4], c[5], c[6], c[7], c[8], c[9], c[10]))
    conn.commit()
    print(f"  Inserted/verified {len(customers)} customers.")

    # ── PORTFOLIO HOLDINGS ────────────────────────────────────────────────────
    print("Inserting portfolio holdings...")
    cur.execute(open("D:/Wealth_Management/finsight/backend/db/seed_holdings.sql").read())
    conn.commit()
    print("  Holdings done.")

    # ── TRANSACTIONS ──────────────────────────────────────────────────────────
    print("Inserting transactions...")
    cur.execute(open("D:/Wealth_Management/finsight/backend/db/seed_txn.sql").read())
    conn.commit()
    print("  Transactions done.")

    # ── LOANS ─────────────────────────────────────────────────────────────────
    print("Inserting loans...")
    cur.execute(open("D:/Wealth_Management/finsight/backend/db/seed_loans.sql").read())
    conn.commit()
    print("  Loans done.")

    # ── ALERTS ────────────────────────────────────────────────────────────────
    print("Inserting alerts...")
    cur.execute(open("D:/Wealth_Management/finsight/backend/db/seed_alerts.sql").read())
    conn.commit()
    print("  Alerts done.")

    # ── REPORTS ───────────────────────────────────────────────────────────────
    print("Inserting reports...")
    cur.execute(open("D:/Wealth_Management/finsight/backend/db/seed_reports.sql").read())
    conn.commit()
    print("  Reports done.")

    # ── customer_summary: trigger by touching portfolio_holdings ──────────────
    print("Refreshing customer_summary via trigger...")
    cur.execute("""
        UPDATE portfolio_holdings
        SET last_updated = NOW()
        WHERE asset_type != 'cash'
    """)
    conn.commit()
    print("  customer_summary refreshed.")

    cur.close()
    conn.close()
    print("\nAll seed data inserted successfully!")

if __name__ == "__main__":
    run()
