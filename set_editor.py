import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

def open_editor(app, edit=False):
    editor = tk.Toplevel(app.root)
    editor.title("Editor")

    tk.Label(editor, text=f"Skupina: {app.selected_group}").pack(pady=5)

    name_frame = tk.Frame(editor)
    name_frame.pack(pady=5)

    tk.Label(name_frame, text="Název setu:").pack(side=tk.LEFT, padx=5)
    name_entry = tk.Entry(name_frame)
    name_entry.pack(side=tk.LEFT, padx=5)
    name_entry.focus_set()

    listbox = tk.Listbox(editor, width=40)
    listbox.pack()

    entry_frame = tk.Frame(editor)
    entry_frame.pack(pady=5)

    front_entry = tk.Entry(entry_frame)
    front_entry.pack(side=tk.LEFT, padx=5)

    tk.Label(entry_frame, text="→").pack(side=tk.LEFT, padx=5)

    back_entry = tk.Entry(entry_frame)
    back_entry.pack(side=tk.LEFT, padx=5)

    cards = []
    
    app.cursor.execute("SELECT path FROM sets WHERE id = ?", (app.editing_set_id,))
    db_path = app.cursor.fetchone()[0]

    conn_set = sqlite3.connect(db_path)
    cursor_set = conn_set.cursor()

    if edit:
        # Načtení správné databázové cesty setu
        app.cursor.execute("SELECT name, path FROM sets WHERE id = ?", (app.editing_set_id,))
        name, db_path = app.cursor.fetchone()
        
        name_entry.insert(0, name)  # Předvyplnění názvu setu

        # Připojení k databázi setu
        conn_set = sqlite3.connect(db_path)
        cursor_set = conn_set.cursor()

        # Načtení kartiček ze správné databáze
        cursor_set.execute("SELECT front, back FROM cards")
        cards = cursor_set.fetchall()
        conn_set.close()  # Zavření připojení po načtení kartiček

        # Naplnění listboxu kartičkami
        for card in cards:
            listbox.insert(tk.END, f"{card[0]} → {card[1]}")

    def add_card(cards, listbox, front_entry, back_entry, event=None):
        front = front_entry.get()
        back = back_entry.get()
        if not front or not back:
            return
        cards.append((front, back))
        listbox.insert(tk.END, f"{front} → {back}")
        front_entry.delete(0, tk.END)
        back_entry.delete(0, tk.END)
        front_entry.focus_set()

    def edit_card(event):
        index = listbox.curselection()
        if not index:
            return
        idx = index[0]
        front, back = cards[idx]

        edit_win = tk.Toplevel(editor)
        edit_win.title("Upravit kartičku")

        entry_f = tk.Entry(edit_win, width=30)
        entry_f.insert(0, front)
        entry_f.pack(pady=5)

        entry_b = tk.Entry(edit_win, width=30)
        entry_b.insert(0, back)
        entry_b.pack(pady=5)

        def save():
            cards[idx] = (entry_f.get().strip(), entry_b.get().strip())
            listbox.delete(idx)
            listbox.insert(idx, f"{cards[idx][0]} → {cards[idx][1]}")
            edit_win.destroy()

        def delete():
            del cards[idx]
            listbox.delete(idx)
            edit_win.destroy()

        tk.Button(edit_win, text="Uložit", command=save).pack(side=tk.LEFT, padx=5, pady=10)
        tk.Button(edit_win, text="Odstranit", command=delete).pack(side=tk.LEFT, padx=5, pady=10)
        tk.Button(edit_win, text="Zpět", command=edit_win.destroy).pack(side=tk.LEFT, padx=5, pady=10)

    def save_set():
        name = name_entry.get()
        if not name:
            return

        # 🔹 Znovu se připojíme ke správné databázi setu
        app.cursor.execute("SELECT path FROM sets WHERE id = ?", (app.editing_set_id,))
        db_path = app.cursor.fetchone()[0]  # ✅ Použití správně `db_path`

        conn_set = sqlite3.connect(db_path)  # ✅ Nové připojení ke správné databázi
        cursor_set = conn_set.cursor()

        for front, back in cards:
            cursor_set.execute("SELECT id FROM cards WHERE front = ? AND back = ?", (front, back))
            result = cursor_set.fetchone()
            card_id = result[0] if result else None  

            if card_id:
                cursor_set.execute("UPDATE cards SET front = ?, back = ? WHERE id = ?", (front, back, card_id))
            else:
                cursor_set.execute("INSERT INTO cards (front, back, status) VALUES (?, ?, 0)", (front, back))
                conn_set.commit()  # ✅ Uložíme změny před tím, než hledáme `card_id`
                card_id = cursor_set.lastrowid
            
            print(f"✅ Nová kartička přidána s ID = {card_id}, text = '{front}'")
            print(f"🔍 Generuji obrázek: text = '{front}', hledám odpovídající card_id v databázi...")
            print(f"🔍 Generuji obrázek: text = '{back}', hledám odpovídající card_id v databázi...")
            app.generate_image(front, app.selected_group, name, card_id, db_path, "front")
            app.generate_image(back, app.selected_group, name, card_id, db_path, "back")

        conn_set.commit()
        conn_set.close()  # ✅ Zavřeme připojení až po uložení všech změn
        editor.destroy()
        app.build_ui()

    add_button = tk.Button(editor, text="Přidat kartičku", command=lambda: add_card(cards, listbox, front_entry, back_entry))
    add_button.pack(pady=5)

    save_button = tk.Button(editor, text="Uložit set", command=save_set)
    save_button.pack(pady=5)

    front_entry.bind('<Return>', lambda event: add_card(cards, listbox, front_entry, back_entry, event))
    back_entry.bind('<Return>', lambda event: add_card(cards, listbox, front_entry, back_entry, event))
    listbox.bind('<Double-Button-1>', lambda event: edit_card(cards))

    editor.columnconfigure(1, weight=1)