def create_admin():
    conn = get_db()
    c = conn.cursor()

    try:
        c.execute('''
            INSERT INTO users (name, email, mobile, admin pin, role, signature, accepted_terms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("Admin", "dl.1415.info@schools.sa.edu.au", "0400000000", "admin123", "admin", "Admin", 1))

        conn.commit()
        print("Admin created!")
    except:
        print("Admin already exists")

    conn.close()