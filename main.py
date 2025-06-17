import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import sqlite3
import shutil

DB_PATH = "data/index.db"
BASE_DIR = "data"
FONT_PATH = "arial.ttf"
IMG_SIZE = (400, 200)
FONT_SIZE = 24

class FlashcardApp:
    def __init__(self, root):
        os.makedirs(BASE_DIR, exist_ok=True)
        self.root = root
        self.root.title("Učení kartiček")
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.initialize_db()
        self.selected_group = None
        self.selected_set = None
        self.current_set = None
        self.cards = []
        self.index = 0
        self.show_front = True
        self.random_order = tk.BooleanVar()
        self.learning_shuffle = False  # Výchozí hodnota, může být změněna v UI
        self.selected_set = None

        self.build_ui()

    def initialize_db(self):
        # Hlavní databáze pro správu setů
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                path TEXT NOT NULL
            )
        """)
        self.conn.commit()

        self.cursor.execute("SELECT name FROM sets")  # 🛠 Dotaz na sety
        self.sets = [row[0] for row in self.cursor.fetchall()]

        self.cursor.execute("SELECT group_name FROM sets")  # 🛠 Dotaz na skupiny
        self.groups = [row[0] for row in self.cursor.fetchall()]

    def build_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.menu_frame = tk.Frame(self.root)
        self.menu_frame.pack(pady=10)

        tk.Label(self.menu_frame, text="Vyberte skupinu:").pack()
        self.group_var = tk.StringVar()
        self.group_combo = ttk.Combobox(self.menu_frame, textvariable=self.group_var)
        self.group_combo.pack()
        self.group_combo.bind("<<ComboboxSelected>>", self.load_sets)

        tk.Label(self.menu_frame, text="Sety:").pack()
        self.set_listbox = tk.Listbox(self.menu_frame, width=50)
        self.set_listbox.pack(pady=5)

        self.learn_button = tk.Button(self.menu_frame, text="Učit se", command=self.select_and_learn)
        self.learn_button.pack(pady=5)

        self.add_card_button = tk.Button(self.menu_frame, text="Přidat kartičky", command=self.create_or_select_group)
        self.add_card_button.pack(pady=5)

        self.edit_button = tk.Button(self.menu_frame, text="Upravit", command=self.edit_selected_set)
        self.edit_button.pack(pady=5)

        # tk.Button(self.menu_frame, text="Odstranit", command=lambda: self.open_delete_window(self)).pack(pady=5)

        self.load_groups()

    def load_groups(self):
        self.cursor.execute("SELECT DISTINCT group_name FROM sets")
        groups = [r[0] for r in self.cursor.fetchall()]
        self.group_combo['values'] = groups

    def load_sets(self, event=None):
        group = self.group_var.get()
        self.cursor.execute("SELECT id, name FROM sets WHERE group_name = ?", (group,))
        self.sets = self.cursor.fetchall()
        self.set_listbox.delete(0, tk.END)
        for _, name in self.sets:
            self.set_listbox.insert(tk.END, name)

    def select_and_learn(self):
        sel = self.set_listbox.curselection()
        if not sel:
            messagebox.showerror("Chyba", "Nebyl vybrán žádný set.")
            return

        self.selected_set_id, self.set_name = self.sets[sel[0]]
        
        # Načteme cestu k databázi setu z index.db
        self.cursor.execute("SELECT path FROM sets WHERE id = ?", (self.selected_set_id,))
        db_path = self.cursor.fetchone()[0]

        # Připojíme se k databázi tohoto setu
        conn_set = sqlite3.connect(db_path)
        cursor_set = conn_set.cursor()
        
        # Načteme kartičky podle index_id
        cursor_set.execute("SELECT front, back, status FROM cards ORDER BY index_id")
        self.cards = cursor_set.fetchall()
        conn_set.close()

        if not self.cards:
            messagebox.showwarning("Prázdný set", "Tento set neobsahuje žádné kartičky.")
            return

        self.index = 0
        self.learn_ui()

    def create_or_select_group(self):
        group = simpledialog.askstring("Nová skupina", "Zadejte název nové skupiny:")
        if not group:
            return
        set_name = simpledialog.askstring("Nový set", "Zadejte název setu:")
        if not set_name:
            return
        
        # Vytvoření adresáře pro set
        set_path = os.path.join(BASE_DIR, group, set_name)
        os.makedirs(set_path, exist_ok=True)

        # Vytvoření databáze pro set
        db_path = os.path.join(set_path, "data.db")
        conn_set = sqlite3.connect(db_path)
        cursor_set = conn_set.cursor()
        
        cursor_set.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                status INTEGER DEFAULT 0,
                index_id INTEGER DEFAULT 0
            )
        """)
        conn_set.commit()
        conn_set.close()

        # Zapsání nového setu do hlavní databáze
        self.cursor.execute("INSERT INTO sets (name, group_name, path) VALUES (?, ?, ?)", (set_name, group, db_path))
        self.conn.commit()

        print(f"✅ Vytvořen set: {set_name}, cesta: {db_path}")
        self.load_groups()

    def edit_selected_set(self):
        sel = self.set_listbox.curselection()
        if not sel:
            return
        set_id, set_name = self.sets[sel[0]]
        self.cursor.execute("SELECT group_name FROM sets WHERE id = ?", (set_id,))
        group_name = self.cursor.fetchone()[0]
        self.selected_group = group_name
        self.editing_set_id = set_id
        self.open_set_editor(edit=True)

    def generate_image(self, text, group, set_name, card_id, db_path, side):
        conn_set = sqlite3.connect(db_path)  # ✅ Připojení k databázi setu
        cursor_set = conn_set.cursor()

        img = Image.new("RGB", IMG_SIZE, color="white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (IMG_SIZE[0] - w) / 2
        y = (IMG_SIZE[1] - h) / 2
        draw.text((x, y), text, font=font, fill="black")

        cursor_set.execute("PRAGMA table_info(cards)")
        columns = cursor_set.fetchall()
        print(f"🧐 Debug: Struktura tabulky `cards` = {columns}")
        cursor_set.execute("SELECT * FROM cards")

        # 🛠 Získáme ID kartičky odpovídající `text`
        cursor_set.execute("SELECT id FROM cards WHERE TRIM(front) = TRIM(?) OR TRIM(back) = TRIM(?)", (text, text))
        result = cursor_set.fetchone()
        card_id = result[0] if result else None  # ✅ Správně získáme ID

        set_path = os.path.join(BASE_DIR, group, set_name)
        os.makedirs(set_path, exist_ok=True)

        print(f"🧐 Debug: Přidaná kartička ID = {card_id}, text = '{text}'")
        if card_id is not None:  # ✅ Zabráníme chybě, pokud ID neexistuje
            img_path = os.path.join(set_path, f"{card_id}_{side}.bmp")
            img.save(img_path)
        else:
            print(f"🚨 Chyba: `card_id` není definováno pro text '{text}'")  # 🔍 Debugging

        conn_set.close()  # ✅ Zavřeme připojení po dokončení práce

    def open_set_editor(self, edit=False):
        from set_editor import open_editor
        open_editor(self, edit)

    def learn_ui(self):
        from learn_mode import start_learning
        start_learning(app=self)

    """def open_delete_window(app, self):
        delete_window = tk.Toplevel(app.root)
        delete_window.title("Odstranit set/skupinu")

        tk.Label(delete_window, text="Vyberte, co chcete odstranit:").pack(pady=5)

        choice_var = tk.StringVar(value="set")
        tk.Radiobutton(delete_window, text="Set", variable=choice_var, value="set").pack(anchor="w")
        tk.Radiobutton(delete_window, text="Skupina", variable=choice_var, value="group").pack(anchor="w")

        tk.Button(delete_window, text="Potvrdit", command=lambda: show_selection_window(app, choice_var.get(), delete_window)).pack(pady=10)

def confirm_deletion(app, choice):
    if choice == "group":
        selected_group = getattr(app, "selected_group", None)
        selected_set = getattr(app, "selected_set", None)
        if not selected_group or not selected_set:
            messagebox.showerror("Chyba", "Nebyla vybrána žádná skupina.")
            return

        app.sets = ["Set1", "Set2", "Set3"]

        if app.sets:
            confirm = messagebox.askyesno("Potvrzení", f"Skupina obsahuje {len(app.sets)} setů. Opravdu chcete odstranit?")
            if not confirm:
                return

        app.cursor.execute("DELETE FROM sets WHERE group_name = ?", (selected_group,))    
        shutil.rmtree(f"data/{selected_group}")
        messagebox.showinfo("Hotovo", f"Skupina {selected_group} byla odstraněna.")

    elif choice == "set":
        selected_set = getattr(app, "selected_set", None)
        selected_group = getattr(app, "selected_group", None)
        
        app.cursor.execute("DELETE FROM sets WHERE name = ?", (selected_set,))
        shutil.rmtree(f"data/{selected_group}/{selected_set}")
        messagebox.showinfo("Hotovo", f"Set {selected_set} byl odstraněn.")   

    app.load_data() 

def show_selection_window(app, choice, window):
        window.destroy()  # ✅ Zavřeme předchozí okno

        selection_window = tk.Toplevel(app.root)
        selection_window.title("Vyberte položku k odstranění")

        listbox = tk.Listbox(selection_window)
        listbox.pack(pady=5)

        items = app.groups if choice == "group" else app.sets
        
        # 🛠 Ověříme, zda `app.groups` a `app.sets` obsahují data
        print(f"🔍 Debug: Načtené položky k výběru = {items}")
        
        if not items:
            messagebox.showerror("Chyba", "Žádné položky k výběru!")
            selection_window.destroy()
            return

        for item in items:
            listbox.insert(tk.END, item)

        listbox.bind("<<ListboxSelect>>", lambda event: set_selection(app, choice, listbox))

        tk.Button(selection_window, text="Odstranit", command=lambda: confirm_deletion(app, choice)).pack(pady=10)

def set_selection(app, choice, listbox):
    selection_index = listbox.curselection()
        
    if not selection_index:  # ✅ Kontrola, zda uživatel něco vybral
        return  # 🔹 Pokud ne, jednoduše nic neděláme

    selection = listbox.get(selection_index)  # ✅ Načtení vybrané položky

    if choice == "group":
        app.selected_group = selection  # ✅ Uchováme vybranou skupinu
    else:
        app.selected_set = selection  # ✅ Uchováme vybraný set

    print(f"🧐 Uloženo: {choice} = {selection}")  # 🔍 Diagnostika pro kontrolu
    print(f"🧐 Debug: Vybraná skupina = {app.selected_group}")"""

if __name__ == "__main__":
    root = tk.Tk()
    app = FlashcardApp(root)
    root.mainloop()
