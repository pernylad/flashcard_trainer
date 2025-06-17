import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import random
import json
import sqlite3

__all__ = ["start_learning"]

def assign_random_order(app, db_path):
    conn_set = sqlite3.connect(db_path)  
    cursor_set = conn_set.cursor()

    cursor_set.execute("SELECT id, index_id FROM cards")
    original_order = cursor_set.fetchall()
    print(f"🔍 Původní pořadí: {original_order}")

    # Generujeme náhodné pořadí
    card_ids = [row[0] for row in original_order]
    random_order = list(range(len(card_ids)))
    random.shuffle(random_order)

    # Uložíme nové pořadí do databáze
    for i, card_id in enumerate(card_ids):
        cursor_set.execute("UPDATE cards SET index_id = ? WHERE id = ?", (random_order[i], card_id))

    conn_set.commit()

    cursor_set.execute("SELECT id, index_id FROM cards")
    updated_order = cursor_set.fetchall()
    print(f"✅ Aktualizované pořadí: {updated_order}")  # 🛠 **OVĚŘENÍ**

    conn_set.close()

def start_learning(app):
    if hasattr(app, "learning_window") and app.learning_window.winfo_exists():
        app.learning_window.lift()  # Přesuneme existující okno do popředí
        return

    sel = app.set_listbox.curselection()
    if not sel:
        messagebox.showerror("Chyba", "Nebyl vybrán žádný set.")
        return

    set_id, set_name = app.sets[sel[0]]

    app.cursor.execute("SELECT group_name, path FROM sets WHERE id = ?", (set_id,))
    result = app.cursor.fetchone()

    print(f"🔍 Debug: Výsledek SQL dotazu = {result}")  # 🛠 Výpis výsledku SQL dotazu

    if result is None or len(result) < 2:
        messagebox.showerror("Chyba", "Databáze nevrátila správné hodnoty! Zkontrolujte, zda `path` existuje.")
        return

    group_name, db_path = result  # ✅ Získáme hodnoty správně jako jednotlivé proměnné

    # 🛠 Ověříme, zda `db_path` je skutečně řetězec
    print(f"🧐 Typ `db_path`: {type(db_path)}")  
    if not isinstance(db_path, str):
        messagebox.showerror("Chyba", "`db_path` není správný typ! Očekáván str, ale dostali jsme {type(db_path)}.")
        return

    print(f"✅ Načteno správně: group_name = {group_name}, db_path = {db_path}")  # 🛠 Výpis načtených hodnot

    # ✅ Před použitím zajistíme, že `db_path` skutečně existuje
    if 'db_path' not in locals():
        messagebox.showerror("Chyba", "`db_path` nebylo správně inicializováno.")
        return

    conn_set = sqlite3.connect(db_path)  # ✅ Používáme správně inicializovanou hodnotu
    cursor_set = conn_set.cursor()
    
    if result is None or len(result) < 2:
        messagebox.showerror("Chyba", "Databáze nevrátila správné hodnoty! Zkontrolujte, zda `path` existuje.")
        return

    group_name, db_path = result  # ✅ Rozbalíme hodnoty správně

    print(f"🔍 Debug: group_name = {group_name}, db_path = {db_path}")  # 🛠 Výpis načtených hodnot

    if not db_path:
        messagebox.showerror("Chyba", "Cesta k databázi nebyla nalezena!")
        return

    app.group_name = group_name  
    app.set_name = set_name

    shuffle = messagebox.askyesno("Náhodné pořadí", "Chcete zamíchat kartičky?")
    app.learning_shuffle = shuffle  

    if app.learning_shuffle:
        assign_random_order(app, db_path)

    conn_set = sqlite3.connect(db_path)
    cursor_set = conn_set.cursor()

    # 🔹 Načtení kartiček v zamíchaném pořadí podle `index_id`
    cursor_set.execute("SELECT id, front, back, status FROM cards ORDER BY index_id")
    app.cards = cursor_set.fetchall()

    print(f"🧐 Načtené kartičky pro GUI: {app.cards}")  # 🛠 Výpis, zda se načítají správně

    conn_set.close()  # ✅ Zavřeme připojení po načtení dat

    if not app.cards:
        messagebox.showwarning("Prázdný set", "Tento set neobsahuje žádné kartičky.")
        return
    
    app.known_ids = []
    app.unknown_ids = []

    # ✅ Vytvoříme **okno pro učení**
    learning_window = tk.Toplevel(app.root)
    learning_window.title(f"Procházení setu {set_name}")
    
    app.learning_window = learning_window  # Uchováme referenci pro další akce

    app.index = 0
    card_id, front, back, status = app.cards[app.index]  # ✅ Použijeme správné pořadí!
    app.learn_ui()

    def update_progress():
        total = len(app.cards)
        known = len(app.known_ids)
        unknown = len(app.unknown_ids)
        seen = known + unknown
        remaining = total - seen
        progress_var.set(seen / total * 100 if total else 0)
        label_known.config(text=f"{known}", fg="green")
        label_unknown.config(text=f"{unknown}", fg="red")
        label_remaining.config(text=f"{remaining}", fg="black")

    def flip():
        app.show_front = not app.show_front
        show_card()

    def rate(app, correct):
        card_id, _, _, _ = app.cards[app.index]

        # 🔹 Získání cesty k databázi setu
        app.cursor.execute("SELECT path FROM sets WHERE id = ?", (app.selected_set_id,))
        db_path = app.cursor.fetchone()[0]

        conn_set = sqlite3.connect(db_path)
        cursor_set = conn_set.cursor()

        # 🔹 Aktualizace `status` podle odpovědi
        new_status = 1 if correct else -1
        cursor_set.execute("UPDATE cards SET status = ? WHERE id = ?", (new_status, card_id))

        conn_set.commit()
        conn_set.close()  # ✅ Zavřeme připojení po aktualizaci

        # Přidání kartičky do odpovídajícího seznamu
        if correct:
            app.known_ids.append(card_id)
        else:
            app.unknown_ids.append(card_id)

        next_card()

    def next_card():
        app.index += 1
        if app.index >= len(app.cards):
            tk.messagebox.showinfo("Hotovo", "Prošli jste všechny kartičky.")
            save_results_dialog(app)
        else:
            app.show_front = True
            card_id, front, back, status = app.cards[app.index]  # ✅ Použijeme zamíchané pořadí!

            print(f"🔍 Přechod na další kartičku: ID={card_id}, front={front}, index={app.index}")  # 🛠 Diagnostika

            show_card()  # ✅ Zajistíme, že GUI vykresluje správně vybrané data
            update_progress()

    def show_card():
        if app.index >= len(app.cards):
            return
        card = app.cards[app.index]  # Kartička podle aktuálního indexu
        print(f"🧐 Zobrazená kartička: {card}")  # Výpis na konzoli pro kontrolu

        card_id, front, back, _ = card
        text = front if app.show_front else back
        side = "front" if app.show_front else "back"
        
        img_path = os.path.join("data", group_name, set_name, f"{card_id}_{side}.bmp")
        if os.path.exists(img_path):
            img = Image.open(img_path)
            img_tk = ImageTk.PhotoImage(img)
            image_label.config(image=img_tk, text='')
            image_label.image = img_tk
        else:
            image_label.config(image='', text=text, font=("Arial", 24), wraplength=600)

    def save_results():
        for card_id in app.known_ids:
            app.cursor.execute("UPDATE cards SET status = 2 WHERE id = ?", (card_id,))
        for card_id in app.unknown_ids:
            app.cursor.execute("UPDATE cards SET status = 1 WHERE id = ?", (card_id,))
        app.conn.commit()
        app.build_ui()

    def discard_results(app):
        # 🔹 Získání cesty k databázi setu
        app.cursor.execute("SELECT path FROM sets WHERE id = ?", (app.selected_set_id,))
        db_path = app.cursor.fetchone()[0]

        conn_set = sqlite3.connect(db_path)
        cursor_set = conn_set.cursor()

        # 🔹 Resetování `index_id` pro nové náhodné pořadí
        cursor_set.execute("UPDATE cards SET index_id = 0")

        conn_set.commit()
        conn_set.close()  # ✅ Zavřeme připojení

        app.conn.commit()
        app.build_ui()

    def save_results_dialog(app):
        result = tk.messagebox.askyesnocancel("Uložit postup?", "Chcete uložit svůj pokrok?")
        if result is None:
            return
        if result:
            save_results(app)
        else:
            discard_results(app)

    def on_key(event):
        if event.keysym == "Down":
            flip()
        elif event.keysym == "Left":
            rate(False)
        elif event.keysym == "Right":
            rate(True)

    learning_window.bind("<Key>", on_key)

    image_label = tk.Label(learning_window)
    image_label.pack(pady=20)

    shuffle_var = tk.BooleanVar(value=app.learning_shuffle)
    shuffle_check = tk.Checkbutton(learning_window, text="Náhodné pořadí", variable=shuffle_var, command=lambda: setattr(app, 'learning_shuffle', shuffle_var.get()))
    shuffle_check.pack()

    progress_var = tk.DoubleVar()
    progress_bar = tk.ttk.Progressbar(learning_window, variable=progress_var, maximum=100)
    progress_bar.pack(fill="x", padx=20, pady=5)

    stats_frame = tk.Frame(learning_window)
    stats_frame.pack()
    label_unknown = tk.Label(stats_frame, text="0", fg="red", width=10)
    label_unknown.pack(side="left")
    label_remaining = tk.Label(stats_frame, text="0", fg="black", width=10)
    label_remaining.pack(side="left")
    label_known = tk.Label(stats_frame, text="0", fg="green", width=10)
    label_known.pack(side="left")

    buttons_frame = tk.Frame(learning_window)
    buttons_frame.pack(pady=10)
    btn_unknown = tk.Button(buttons_frame, bg="red", width=10, height=2, command=lambda: rate(app, False), text="Neumím")
    btn_unknown.pack(side="left", padx=10)
    btn_turn = tk.Button(buttons_frame, bg="white", width=10, height=2, command=flip, text="Otočit")
    btn_turn.pack(side="left", padx=10)
    btn_known = tk.Button(buttons_frame, bg="green", width=10, height=2, command=lambda: rate(app, True), text="Umím")
    btn_known.pack(side="left", padx=10)

    btn_cancel = tk.Button(learning_window, text="Zpět", command=lambda: save_results_dialog(app))
    btn_cancel.pack(pady=5)

    show_card()
    update_progress()
